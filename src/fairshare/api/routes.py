"""JSON API: authentication, groups, members, expenses, settlements and balances."""

from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from fairshare import services as svc
from fairshare.deps import current_user, get_session
from fairshare.models import SplitType, User
from fairshare.schemas import (
    BalanceOut,
    ExpenseCreateIn,
    ExpenseOut,
    GroupCreateIn,
    GroupOut,
    LoginIn,
    MemberIn,
    RegisterIn,
    SettlementIn,
    SettlementOut,
    TransferOut,
    UserOut,
)

router = APIRouter(prefix="/api")


@contextmanager
def _mapped_errors():
    try:
        yield
    except svc.NotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except svc.Forbidden as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except svc.Invalid as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# --- auth ------------------------------------------------------------------

@router.post("/auth/register", response_model=UserOut, status_code=201, tags=["auth"])
def register(body: RegisterIn, request: Request, session: Session = Depends(get_session)) -> User:
    with _mapped_errors():
        user = svc.register_user(
            session, email=body.email, display_name=body.display_name, password=body.password
        )
    request.session["user_id"] = user.id
    return user


@router.post("/auth/login", response_model=UserOut, tags=["auth"])
def login(body: LoginIn, request: Request, session: Session = Depends(get_session)) -> User:
    user = svc.authenticate(session, email=body.email, password=body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid email or password")
    request.session["user_id"] = user.id
    return user


@router.post("/auth/logout", status_code=204, tags=["auth"])
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=204)


@router.get("/auth/me", response_model=UserOut, tags=["auth"])
def me(user: User = Depends(current_user)) -> User:
    return user


# --- groups ----------------------------------------------------------------

@router.post("/groups", response_model=GroupOut, status_code=201, tags=["groups"])
def create_group(
    body: GroupCreateIn, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    with _mapped_errors():
        return svc.create_group(session, name=body.name, description=body.description, owner=user)


@router.get("/groups", response_model=list[GroupOut], tags=["groups"])
def list_groups(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return svc.list_groups_for(session, user.id)


@router.get("/groups/{group_id}", response_model=GroupOut, tags=["groups"])
def get_group(group_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
    with _mapped_errors():
        return svc.require_membership(session, group_id, user.id)


@router.get("/groups/{group_id}/members", response_model=list[UserOut], tags=["members"])
def list_members(group_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
    with _mapped_errors():
        svc.require_membership(session, group_id, user.id)
    return svc.members_of(session, group_id)


@router.post("/groups/{group_id}/members", response_model=UserOut, status_code=201, tags=["members"])
def add_member(
    group_id: int,
    body: MemberIn,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    with _mapped_errors():
        group = svc.require_membership(session, group_id, user.id)
        return svc.add_member(session, group=group, actor_id=user.id, email=body.email)


# --- expenses --------------------------------------------------------------

@router.get("/groups/{group_id}/expenses", response_model=list[ExpenseOut], tags=["expenses"])
def list_expenses(group_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
    with _mapped_errors():
        svc.require_membership(session, group_id, user.id)
    return svc.list_expenses(session, group_id)


@router.post("/groups/{group_id}/expenses", response_model=ExpenseOut, status_code=201, tags=["expenses"])
def create_expense(
    group_id: int,
    body: ExpenseCreateIn,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    with _mapped_errors():
        group = svc.require_membership(session, group_id, user.id)

        if body.split_type is SplitType.equal:
            participants: list[int] | dict[int, float] = body.participants or [
                u.id for u in svc.members_of(session, group_id)
            ]
        else:
            if not body.splits:
                raise HTTPException(400, f"'{body.split_type.value}' split needs a 'splits' map")
            participants = body.splits

        return svc.create_expense(
            session,
            group=group,
            created_by=user.id,
            description=body.description,
            amount_cents=body.amount_cents,
            paid_by=body.paid_by,
            split_type=body.split_type,
            participants=participants,
        )


# --- settlements & balances ------------------------------------------------

@router.get("/groups/{group_id}/balances", response_model=list[BalanceOut], tags=["balances"])
def balances(group_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
    with _mapped_errors():
        svc.require_membership(session, group_id, user.id)
    net = svc.group_balances(session, group_id)
    return [BalanceOut(user_id=uid, net_cents=amount) for uid, amount in sorted(net.items())]


@router.get("/groups/{group_id}/settle", response_model=list[TransferOut], tags=["balances"])
def settle_suggestions(
    group_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    with _mapped_errors():
        svc.require_membership(session, group_id, user.id)
    transfers = svc.settle_up(session, group_id)
    return [
        TransferOut(from_user=t.from_user, to_user=t.to_user, amount_cents=t.amount_cents)
        for t in transfers
    ]


@router.get("/groups/{group_id}/settlements", response_model=list[SettlementOut], tags=["balances"])
def list_settlements(
    group_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    from sqlalchemy import select

    from fairshare.models import Settlement

    with _mapped_errors():
        svc.require_membership(session, group_id, user.id)
    rows = session.scalars(
        select(Settlement).where(Settlement.group_id == group_id).order_by(Settlement.id.desc())
    )
    return list(rows)


@router.post("/groups/{group_id}/settlements", response_model=SettlementOut, status_code=201, tags=["balances"])
def create_settlement(
    group_id: int,
    body: SettlementIn,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    with _mapped_errors():
        group = svc.require_membership(session, group_id, user.id)
        return svc.record_settlement(
            session,
            group=group,
            from_user=body.from_user,
            to_user=body.to_user,
            amount_cents=body.amount_cents,
            note=body.note,
        )
