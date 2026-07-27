"""SQLAlchemy ORM models for learning days, plans, notes, and claims."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid


class Base(DeclarativeBase):
    pass


class LearningDayRow(Base):
    __tablename__ = "learning_days"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_learning_days_user_day"),)

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")

    plan_items: Mapped[list[PlanItemRow]] = relationship(back_populates="learning_day")
    notes: Mapped[list[DayNoteRow]] = relationship(back_populates="learning_day")


class PlanItemRow(Base):
    __tablename__ = "plan_items"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    day_id: Mapped[Any] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("learning_days.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(32), default="manual")
    status: Mapped[str] = mapped_column(String(32), default="planned")
    claim_id: Mapped[Any | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("claims.id"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    learning_day: Mapped[LearningDayRow] = relationship(back_populates="plan_items")


class DayNoteRow(Base):
    __tablename__ = "day_notes"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    day_id: Mapped[Any] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("learning_days.id"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    tags: Mapped[list[Any]] = mapped_column(JSON, default=list)
    claim_ids: Mapped[list[Any]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    learning_day: Mapped[LearningDayRow] = relationship(back_populates="notes")


class ClaimRow(Base):
    __tablename__ = "claims"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    text: Mapped[str] = mapped_column(Text)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="not_yet")
    source_note_id: Mapped[Any | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    next_review_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class ChatMessageRow(Base):
    __tablename__ = "chat_messages"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    plan_item_id: Mapped[Any] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("plan_items.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # examiner | user
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
