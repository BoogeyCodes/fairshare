"""FastAPI dependencies: a request-scoped DB session and the current user."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from fairshare.db import Database
from fairshare.models import User


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_session(request: Request) -> Iterator[Session]:
    db = get_db(request)
    session = db.session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def optional_user(request: Request, session: Session = Depends(get_session)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return session.get(User, user_id)


def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
    return user
