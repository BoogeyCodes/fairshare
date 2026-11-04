"""Pydantic request/response models for the JSON API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from fairshare.models import SplitType


class RegisterIn(BaseModel):
    email: str
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    display_name: str


class GroupCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    created_by: int


class MemberIn(BaseModel):
    email: str


class ExpenseCreateIn(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    amount_cents: int = Field(gt=0)
    paid_by: int
    split_type: SplitType = SplitType.equal
    # For an equal split: the participants (omit to split across everyone in the group).
    participants: list[int] | None = None
    # For exact/percent/shares: per-user value (cents, percent, or integer weight).
    splits: dict[int, float] | None = None


class ExpenseShareOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    share_cents: int


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    description: str
    amount_cents: int
    paid_by: int
    split_type: str
    created_at: datetime
    shares: list[ExpenseShareOut]


class SettlementIn(BaseModel):
    from_user: int
    to_user: int
    amount_cents: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=200)


class SettlementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    from_user: int
    to_user: int
    amount_cents: int
    note: str | None
    created_at: datetime


class BalanceOut(BaseModel):
    user_id: int
    net_cents: int


class TransferOut(BaseModel):
    from_user: int
    to_user: int
    amount_cents: int
