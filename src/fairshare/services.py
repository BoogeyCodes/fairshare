"""Application services: the operations the API and web UI both build on.

This is the only layer that touches both the ORM and the pure split/balance logic, so the
business rules (who may do what, how shares are computed) live in one place.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from fairshare import balances as bal
from fairshare.models import Expense, ExpenseShare, Group, Membership, Settlement, SplitType, User
from fairshare.security import hash_password, verify_password
from fairshare.splitting import SplitError, split_equal, split_exact, split_percent, split_shares


class ServiceError(Exception):
    """Base class for expected, user-facing service failures."""


class NotFound(ServiceError):
    pass


class Forbidden(ServiceError):
    pass


class Invalid(ServiceError):
    pass


# --- users -----------------------------------------------------------------

def register_user(session: Session, *, email: str, display_name: str, password: str) -> User:
    email = email.strip().lower()
    if not email or "@" not in email:
        raise Invalid("a valid email is required")
    if len(password) < 8:
        raise Invalid("password must be at least 8 characters")
    if not display_name.strip():
        raise Invalid("display name is required")
    if session.scalar(select(User).where(User.email == email)):
        raise Invalid("an account with that email already exists")

    user = User(email=email, display_name=display_name.strip(), password_hash=hash_password(password))
    session.add(user)
    session.flush()
    return user


def authenticate(session: Session, *, email: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.email == email.strip().lower()))
    if user and verify_password(password, user.password_hash):
        return user
    return None


def get_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise NotFound("user not found")
    return user


# --- groups & membership ---------------------------------------------------

def create_group(session: Session, *, name: str, description: str | None, owner: User) -> Group:
    if not name.strip():
        raise Invalid("group name is required")
    group = Group(name=name.strip(), description=(description or "").strip() or None, created_by=owner.id)
    group.members.append(Membership(user_id=owner.id))
    session.add(group)
    session.flush()
    return group


def require_membership(session: Session, group_id: int, user_id: int) -> Group:
    """Return the group only if ``user_id`` is a member; otherwise 404 (don't reveal it)."""
    group = session.get(Group, group_id)
    member = session.scalar(
        select(Membership).where(Membership.group_id == group_id, Membership.user_id == user_id)
    )
    if group is None or member is None:
        raise NotFound("group not found")
    return group


def list_groups_for(session: Session, user_id: int) -> list[Group]:
    rows = session.scalars(
        select(Group).join(Membership).where(Membership.user_id == user_id).order_by(Group.id.desc())
    )
    return list(rows)


def members_of(session: Session, group_id: int) -> list[User]:
    rows = session.scalars(
        select(User).join(Membership).where(Membership.group_id == group_id).order_by(Membership.id)
    )
    return list(rows)


def add_member(session: Session, *, group: Group, actor_id: int, email: str) -> User:
    if group.created_by != actor_id:
        raise Forbidden("only the group creator can add members")
    user = session.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        raise NotFound(f"no account with email '{email.strip().lower()}'")
    exists = session.scalar(
        select(Membership).where(Membership.group_id == group.id, Membership.user_id == user.id)
    )
    if exists:
        raise Invalid("that user is already a member")
    session.add(Membership(group_id=group.id, user_id=user.id))
    session.flush()
    return user


# --- expenses --------------------------------------------------------------

def _member_ids(session: Session, group_id: int) -> set[int]:
    return set(session.scalars(select(Membership.user_id).where(Membership.group_id == group_id)))


def create_expense(
    session: Session,
    *,
    group: Group,
    created_by: int,
    description: str,
    amount_cents: int,
    paid_by: int,
    split_type: SplitType,
    participants: Sequence[int] | Mapping[int, float],
) -> Expense:
    if not description.strip():
        raise Invalid("a description is required")

    member_ids = _member_ids(session, group.id)
    if paid_by not in member_ids:
        raise Invalid("the payer must be a member of the group")

    requested_ids = list(participants)
    if not requested_ids:
        raise Invalid("select at least one participant")
    unknown = set(requested_ids) - member_ids
    if unknown:
        raise Invalid("every participant must be a member of the group")

    try:
        shares = _compute_shares(amount_cents, split_type, participants)
    except SplitError as exc:
        raise Invalid(str(exc)) from exc

    expense = Expense(
        group_id=group.id,
        description=description.strip(),
        amount_cents=amount_cents,
        paid_by=paid_by,
        split_type=SplitType(split_type).value,
        created_by=created_by,
    )
    for uid, share in shares.items():
        expense.shares.append(ExpenseShare(user_id=uid, share_cents=share))
    session.add(expense)
    session.flush()
    return expense


def _compute_shares(
    amount_cents: int, split_type: SplitType, participants: Sequence[int] | Mapping[int, float]
) -> dict[int, int]:
    split_type = SplitType(split_type)
    if split_type is SplitType.equal:
        return split_equal(amount_cents, list(participants))
    if split_type is SplitType.exact:
        return split_exact(amount_cents, {int(k): int(v) for k, v in dict(participants).items()})
    if split_type is SplitType.percent:
        return split_percent(amount_cents, {int(k): float(v) for k, v in dict(participants).items()})
    if split_type is SplitType.shares:
        return split_shares(amount_cents, {int(k): int(v) for k, v in dict(participants).items()})
    raise Invalid(f"unknown split type '{split_type}'")  # pragma: no cover


def list_expenses(session: Session, group_id: int) -> list[Expense]:
    rows = session.scalars(
        select(Expense).where(Expense.group_id == group_id).order_by(Expense.id.desc())
    )
    return list(rows)


# --- settlements & balances ------------------------------------------------

def record_settlement(
    session: Session, *, group: Group, from_user: int, to_user: int, amount_cents: int, note: str | None
) -> Settlement:
    member_ids = _member_ids(session, group.id)
    if from_user not in member_ids or to_user not in member_ids:
        raise Invalid("both people must be members of the group")
    if from_user == to_user:
        raise Invalid("a settlement needs two different people")
    if amount_cents <= 0:
        raise Invalid("settlement amount must be positive")

    settlement = Settlement(
        group_id=group.id,
        from_user=from_user,
        to_user=to_user,
        amount_cents=amount_cents,
        note=(note or "").strip() or None,
    )
    session.add(settlement)
    session.flush()
    return settlement


def group_balances(session: Session, group_id: int) -> dict[int, int]:
    member_ids = list(_member_ids(session, group_id))
    expenses = list_expenses(session, group_id)
    entries = [
        bal.ExpenseEntry(paid_by=e.paid_by, shares={s.user_id: s.share_cents for s in e.shares})
        for e in expenses
    ]
    settlements = session.scalars(select(Settlement).where(Settlement.group_id == group_id))
    settle_entries = [
        bal.SettlementEntry(from_user=s.from_user, to_user=s.to_user, amount_cents=s.amount_cents)
        for s in settlements
    ]
    return bal.compute_balances(member_ids, entries, settle_entries)


def settle_up(session: Session, group_id: int) -> list[bal.Transfer]:
    return bal.simplify_debts(group_balances(session, group_id))
