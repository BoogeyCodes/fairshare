"""SQLAlchemy ORM models for users, groups, expenses, splits and settlements."""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fairshare.db import Base


def utcnow() -> datetime:
    """Naive UTC timestamp (SQLite stores naive datetimes)."""
    return datetime.now(UTC).replace(tzinfo=None)


class SplitType(enum.StrEnum):
    equal = "equal"
    exact = "exact"
    percent = "percent"
    shares = "shares"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    memberships: Mapped[list[Membership]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(1000), default=None)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    members: Mapped[list[Membership]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    expenses: Mapped[list[Expense]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    settlements: Mapped[list[Settlement]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_group_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    group: Mapped[Group] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    description: Mapped[str] = mapped_column(String(200))
    amount_cents: Mapped[int] = mapped_column(Integer)
    paid_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    split_type: Mapped[str] = mapped_column(String(10))  # a SplitType value
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    group: Mapped[Group] = relationship(back_populates="expenses")
    shares: Mapped[list[ExpenseShare]] = relationship(
        back_populates="expense", cascade="all, delete-orphan"
    )


class ExpenseShare(Base):
    __tablename__ = "expense_shares"
    __table_args__ = (UniqueConstraint("expense_id", "user_id", name="uq_expense_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    share_cents: Mapped[int] = mapped_column(Integer)

    expense: Mapped[Expense] = relationship(back_populates="shares")


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    from_user: Mapped[int] = mapped_column(ForeignKey("users.id"))
    to_user: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount_cents: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    group: Mapped[Group] = relationship(back_populates="settlements")
