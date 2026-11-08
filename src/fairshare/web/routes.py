"""Server-rendered web UI (Jinja2 + a little HTMX)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from fairshare import services as svc
from fairshare.deps import current_user, get_session, optional_user
from fairshare.models import SplitType, User
from fairshare.money import MoneyError, format_cents, parse_amount

router = APIRouter(include_in_schema=False)

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
templates.env.filters["money"] = format_cents


def _redirect(url: str, error: str | None = None) -> RedirectResponse:
    if error:
        url = f"{url}?{urlencode({'error': error})}"
    return RedirectResponse(url, status_code=303)


@router.get("/", response_class=HTMLResponse)
def home(request: Request, user: User | None = Depends(optional_user)):
    if user is not None:
        return _redirect("/groups")
    return templates.TemplateResponse(request, "login.html", {"mode": "login"})


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"mode": "register"})


@router.post("/register")
def register_submit(
    request: Request,
    email: str = Form(...),
    display_name: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    try:
        user = svc.register_user(session, email=email, display_name=display_name, password=password)
    except svc.ServiceError as exc:
        return _redirect("/register", str(exc))
    request.session["user_id"] = user.id
    return _redirect("/groups")


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    user = svc.authenticate(session, email=email, password=password)
    if user is None:
        return _redirect("/", "invalid email or password")
    request.session["user_id"] = user.id
    return _redirect("/groups")


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return _redirect("/")


@router.get("/groups", response_class=HTMLResponse)
def groups_page(
    request: Request, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    groups = svc.list_groups_for(session, user.id)
    return templates.TemplateResponse(request, "groups.html", {"user": user, "groups": groups})


@router.post("/groups")
def create_group_submit(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    try:
        group = svc.create_group(session, name=name, description=description, owner=user)
    except svc.ServiceError as exc:
        return _redirect("/groups", str(exc))
    return _redirect(f"/groups/{group.id}")


@router.get("/groups/{group_id}", response_class=HTMLResponse)
def group_page(
    group_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    try:
        group = svc.require_membership(session, group_id, user.id)
    except svc.NotFound:
        return _redirect("/groups", "group not found")

    members = svc.members_of(session, group_id)
    names = {m.id: m.display_name for m in members}
    expenses = svc.list_expenses(session, group_id)
    net = svc.group_balances(session, group_id)
    balances = sorted(
        ({"user": names.get(uid, "?"), "net": amount} for uid, amount in net.items()),
        key=lambda b: b["net"],
    )
    return templates.TemplateResponse(
        request,
        "group.html",
        {
            "user": user,
            "group": group,
            "members": members,
            "names": names,
            "expenses": expenses,
            "balances": balances,
            "split_types": [s.value for s in SplitType],
        },
    )


@router.post("/groups/{group_id}/members")
def add_member_submit(
    group_id: int,
    email: str = Form(...),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    try:
        group = svc.require_membership(session, group_id, user.id)
        svc.add_member(session, group=group, actor_id=user.id, email=email)
    except svc.ServiceError as exc:
        return _redirect(f"/groups/{group_id}", str(exc))
    return _redirect(f"/groups/{group_id}")


@router.post("/groups/{group_id}/expenses")
async def add_expense_submit(
    group_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    form = await request.form()
    try:
        group = svc.require_membership(session, group_id, user.id)
        members = svc.members_of(session, group_id)
        amount_cents = parse_amount(str(form.get("amount", "")))
        split_type = SplitType(str(form.get("split_type", "equal")))
        participants = _parse_participants(form, members, split_type)
        svc.create_expense(
            session,
            group=group,
            created_by=user.id,
            description=str(form.get("description", "")),
            amount_cents=amount_cents,
            paid_by=int(str(form.get("paid_by"))),
            split_type=split_type,
            participants=participants,
        )
    except (svc.ServiceError, MoneyError, ValueError) as exc:
        return _redirect(f"/groups/{group_id}", str(exc))
    return _redirect(f"/groups/{group_id}")


def _parse_participants(form, members: list[User], split_type: SplitType):
    included = [m.id for m in members if form.get(f"include_{m.id}")]
    if split_type is SplitType.equal:
        return included
    result: dict[int, float] = {}
    for uid in included:
        raw = str(form.get(f"value_{uid}", "")).strip()
        if not raw:
            continue
        if split_type is SplitType.exact:
            result[uid] = parse_amount(raw)  # dollars -> cents
        elif split_type is SplitType.percent:
            result[uid] = float(raw)
        else:  # shares
            result[uid] = int(raw)
    return result


@router.post("/groups/{group_id}/settlements")
def record_settlement_submit(
    group_id: int,
    from_user: int = Form(...),
    to_user: int = Form(...),
    amount: str = Form(...),
    note: str = Form(""),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    try:
        group = svc.require_membership(session, group_id, user.id)
        amount_cents = parse_amount(amount)
        svc.record_settlement(
            session, group=group, from_user=from_user, to_user=to_user, amount_cents=amount_cents, note=note
        )
    except (svc.ServiceError, MoneyError) as exc:
        return _redirect(f"/groups/{group_id}", str(exc))
    return _redirect(f"/groups/{group_id}")


@router.get("/groups/{group_id}/settle", response_class=HTMLResponse)
def settle_fragment(
    group_id: int,
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    svc.require_membership(session, group_id, user.id)
    names = {m.id: m.display_name for m in svc.members_of(session, group_id)}
    transfers = svc.settle_up(session, group_id)
    return templates.TemplateResponse(
        request, "_settle.html", {"transfers": transfers, "names": names}
    )
