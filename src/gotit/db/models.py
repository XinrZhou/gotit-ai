"""SQLAlchemy ORM models for learning days, plans, notes, and claims."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, TypeDecorator, Uuid


class JSONB(TypeDecorator[Any]):
    """跨库 JSONB：Postgres 下用原生 JSONB，其它方言回退到 JSON。"""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB

            return dialect.type_descriptor(PG_JSONB())
        return dialect.type_descriptor(JSON())


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


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str | None] = mapped_column(String(200), nullable=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech_stack: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


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
    due_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    project_id: Mapped[Any | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True
    )

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
    project_id: Mapped[Any | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True
    )

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
    topic: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    tags: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    project_id: Mapped[Any | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True
    )


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


# --- Agent rewrite: memory, prompts, harness ---


class MemoryEntryRow(Base):
    __tablename__ = "memory_entries"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    layer: Mapped[str] = mapped_column(String(16), index=True)  # long | working | session
    kind: Mapped[str] = mapped_column(String(64))
    topic: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    source: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PromptVersionRow(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("agent_name", "version_label", name="uq_prompt_agent_version"),
    )

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    agent_name: Mapped[str] = mapped_column(String(32), index=True)
    version_label: Mapped[str] = mapped_column(String(64))
    content_hash: Mapped[str] = mapped_column(String(64))
    system_prompt: Mapped[str] = mapped_column(Text)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)


class HarnessRunRow(Base):
    __tablename__ = "harness_runs"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    git_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    prompt_versions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    label: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    case_set: Mapped[str] = mapped_column(String(64))
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    case_results: Mapped[list[HarnessCaseResultRow]] = relationship(back_populates="run")


class HarnessCaseResultRow(Base):
    __tablename__ = "harness_case_results"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[Any] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("harness_runs.id"), index=True
    )
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    case_type: Mapped[str] = mapped_column(String(32))
    layer: Mapped[str] = mapped_column(String(32))  # prompt | agent | loop | system
    passed: Mapped[bool] = mapped_column(Boolean)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    trace: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    run: Mapped[HarnessRunRow] = relationship(back_populates="case_results")


# --- Resume-driven drill ---


class ResumeRow(Base):
    """全局一份简历（user_id 唯一，再上传覆盖）。"""

    __tablename__ = "resumes"
    __table_args__ = (UniqueConstraint("user_id", name="uq_resumes_user"),)

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    upload_id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DrillMaterialRow(Base):
    """用户导入的深挖资料（全局多份）。"""

    __tablename__ = "drill_materials"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    title: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class InterviewEventRow(Base):
    """Scheduled real-world interview (companion-os P3d)."""

    __tablename__ = "interview_events"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    company: Mapped[str] = mapped_column(String(200))
    role_title: Mapped[str] = mapped_column(String(200))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    round: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="scheduled", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    remind_offsets_hours: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    last_reminded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DrillSessionRow(Base):
    """模拟面试 session（简历级，可选聚焦项目，分轮次/方向）。"""

    __tablename__ = "drill_sessions"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    resume_id: Mapped[Any] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("resumes.id"), nullable=False
    )
    round: Mapped[str] = mapped_column(String(16), nullable=False)
    direction: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_id: Mapped[Any | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="active")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    messages: Mapped[list[Any]] = mapped_column(JSONB, default=list)


# --- Companion-arch: identity / messaging ---


class AgentIdentityRow(Base):
    __tablename__ = "agent_identities"
    __table_args__ = (
        UniqueConstraint("agent_name", name="uq_agent_identities_name"),
    )

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    agent_name: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(64))
    personality: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(32))
    model_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    memory_scope: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    prompt_version_id: Mapped[Any | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("prompt_versions.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ThreadRow(Base):
    __tablename__ = "threads"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    title: Mapped[str] = mapped_column(String(500))
    kind: Mapped[str] = mapped_column(String(16), default="chat", index=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MessageRow(Base):
    __tablename__ = "messages"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    thread_id: Mapped[Any] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("threads.id"), index=True
    )
    agent_name: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | agent | system
    text: Mapped[str] = mapped_column(Text)
    mentions: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BallCustodyRow(Base):
    __tablename__ = "ball_custody"
    __table_args__ = (
        UniqueConstraint("thread_id", name="uq_ball_custody_thread"),
    )

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    thread_id: Mapped[Any] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("threads.id"), unique=True, index=True
    )
    holder: Mapped[str] = mapped_column(String(32))
    stage: Mapped[str] = mapped_column(String(32))  # examine | recheck | gate
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# --- Profile center: user skills / MCP connectors ---


class UserSkillRow(Base):
    """User-installed skill body and/or enabled override for a builtin skill."""

    __tablename__ = "user_skills"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_skills_user_name"),
    )

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(16), default="user")  # builtin | user
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class McpConnectorRow(Base):
    __tablename__ = "mcp_connectors"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_mcp_connectors_user_name"),
    )

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    transport: Mapped[str] = mapped_column(String(16))  # stdio | http | sse
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_status: Mapped[str] = mapped_column(String(16), default="unknown")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# --- Mastery graph: fail events + confused_with edges ---


class FailEventRow(Base):
    __tablename__ = "fail_events"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    claim_id: Mapped[Any] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("claims.id"), index=True
    )
    topic: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    gate_verdict: Mapped[str] = mapped_column(String(32))
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class GraphEdgeRow(Base):
    """Undirected mastery edges; endpoints stored in canonical UUID order."""

    __tablename__ = "graph_edges"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_claim_id",
            "target_claim_id",
            "rel",
            name="uq_graph_edges_user_pair_rel",
        ),
    )

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    source_claim_id: Mapped[Any] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("claims.id"), index=True
    )
    target_claim_id: Mapped[Any] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("claims.id"), index=True
    )
    rel: Mapped[str] = mapped_column(String(32), default="confused_with")
    weight: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
