from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CheckMode(StrEnum):
    PROBE = "probe"
    DRILL = "drill"
    APPLY = "apply"
    TEACH_BACK = "teach_back"


class MasteryStatus(StrEnum):
    NOT_YET = "not_yet"
    IN_PROGRESS = "in_progress"
    MASTERED = "mastered"
    QUEUED = "queued"


class LoopState(StrEnum):
    INGEST = "ingest"
    CLAIM = "claim"
    EXAMINE = "examine"
    COACH = "coach"
    GATE = "gate"
    QUEUE = "queue"
    DONE = "done"


class PlanItemSource(StrEnum):
    MANUAL = "manual"
    QUEUE = "queue"


class PlanItemStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    VERIFIED = "verified"
    FAILED = "failed"
    DEFERRED = "deferred"


class Claim(BaseModel):
    """A testable assertion extracted from study material."""

    id: UUID = Field(default_factory=uuid4)
    text: str
    source_excerpt: str | None = None
    status: MasteryStatus = MasteryStatus.NOT_YET
    source_note_id: UUID | None = None
    next_review_at: date | None = None
    topic: str | None = None
    tags: list[str] = Field(default_factory=list)
    project_id: UUID | None = None


class CheckResult(BaseModel):
    claim_id: UUID
    mode: CheckMode
    passed: bool
    evidence: str
    score: float | None = None


class PlanItemView(BaseModel):
    id: UUID
    title: str
    source: PlanItemSource
    status: PlanItemStatus
    claim_id: UUID | None = None
    sort_order: int = 0
    due_at: date | None = None
    project_id: UUID | None = None
    topic: str | None = None


class DayNoteView(BaseModel):
    id: UUID
    title: str | None = None
    body: str
    excerpt: str
    tags: list[str] = Field(default_factory=list)
    claim_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime
    project_id: UUID | None = None
    day: date | None = None


class DayPlanView(BaseModel):
    date: date
    user_id: str
    items: list[PlanItemView] = Field(default_factory=list)


class ChatMessageView(BaseModel):
    id: UUID
    plan_item_id: UUID
    role: str
    text: str
    created_at: datetime


class TodayView(BaseModel):
    date: date
    plan: DayPlanView
    notes: list[DayNoteView] = Field(default_factory=list)
    due_claims: list[Claim] = Field(default_factory=list)


# --- Agent rewrite: verdicts, memory, prompts, harness ---


class ExamineVerdict(BaseModel):
    """Axiom 多轮端点统一返回；done 区分中间轮 / 最终轮。"""

    done: bool
    verdict: Literal["passed", "almost", "owe_next"] | None = None
    score: float | None = None
    evidence: str | None = None
    follow_up: str


class TopicExamineVerdict(BaseModel):
    """Axiom 主题 session 多轮返回：自主穿梭该主题的多个 claim。

    - done=false 时 current_claim_id 是正在追问的 claim，verdict=null
    - done=true 时 current_claim_id 是本轮判定的 claim，verdict 非空，后端回写
    - session_done=true 表示该主题所有 claim 都判完
    """

    current_claim_id: UUID | None = None
    done: bool
    verdict: Literal["passed", "almost", "owe_next"] | None = None
    follow_up: str
    session_done: bool = False


class ExtractedClaim(BaseModel):
    """Compass 抽出的单个 claim（带 topic/tags）。"""

    text: str
    topic: str | None = None
    tags: list[str] = Field(default_factory=list)
    source_excerpt: str | None = None


class Recommendation(BaseModel):
    """Compass 对今日该重点关注的 claim 的推荐。"""

    claim_text: str
    reason: str


class CompassOutput(BaseModel):
    """Compass 抽 claim + 推题的统一输出。"""

    claims: list[ExtractedClaim] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)


class TeachVerdict(BaseModel):
    """Echo 回讲（独立多轮模式）；done 区分中间轮 / 最终轮。"""

    done: bool
    you_taught_well: bool | None = None
    gaps: list[str] = Field(default_factory=list)
    next_question: str | None = None


class MemoryEntry(BaseModel):
    """分层记忆条目（long / working / session）。"""

    id: UUID = Field(default_factory=uuid4)
    user_id: str
    layer: str
    kind: str
    topic: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    source: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    expires_at: datetime | None = None


class PromptVersion(BaseModel):
    """提示词版本（agent_name + version_label + is_active）。"""

    id: UUID = Field(default_factory=uuid4)
    agent_name: str
    version_label: str
    content_hash: str
    system_prompt: str
    config: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    created_at: datetime
    is_active: bool = False


class HarnessRun(BaseModel):
    """一次 harness 运行（run 元信息 + summary）。"""

    id: UUID = Field(default_factory=uuid4)
    started_at: datetime
    git_sha: str | None = None
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    label: str | None = None
    case_set: str
    summary: dict[str, Any] = Field(default_factory=dict)
    verdict: str | None = None
    created_at: datetime


class HarnessCaseResult(BaseModel):
    """单个 case 在一次 run 下的结果（支持按 case 跨 run 聚合）。"""

    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    case_id: str
    case_type: str
    layer: str
    passed: bool
    score: float | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    trace: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


# --- Project drill ---


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class Project(BaseModel):
    """一个项目/主题（社招简历项目 / 工作主题通用）。"""

    id: UUID = Field(default_factory=uuid4)
    user_id: str
    name: str
    role: str | None = None
    goal: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    status: ProjectStatus = ProjectStatus.ACTIVE
    created_at: datetime


class ProjectProgress(BaseModel):
    """项目下 claims 的掌握度统计。"""

    claims_total: int = 0
    mastered: int = 0
    in_progress: int = 0
    not_yet: int = 0


class SageVerdict(BaseModel):
    """Sage 项目深挖多轮端点；done 区分中间轮 / 最终轮。"""

    done: bool
    depth_reached: int = 0
    gaps: list[str] = Field(default_factory=list)
    follow_up: str | None = None
    round: str | None = None  # DrillRound value, echoed for UI


# --- Resume-driven drill ---


class ResumeBasics(BaseModel):
    """简历基本信息（M0 仅 name / target_role）。"""

    name: str | None = None
    target_role: str | None = None


class ResumeProject(BaseModel):
    """从简历解析出的单个项目。"""

    name: str
    role: str | None = None
    goal: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    description: str  # 存进 note.body


class ResumeDocument(BaseModel):
    """一份简历的结构化解析结果。"""

    basics: ResumeBasics = Field(default_factory=ResumeBasics)
    projects: list[ResumeProject] = Field(default_factory=list)


class ResumeRecord(BaseModel):
    """落库的简历记录（全局一份，user_id 唯一）。"""

    id: UUID = Field(default_factory=uuid4)
    user_id: str
    upload_id: UUID
    file_path: str
    document: ResumeDocument
    created_at: datetime


class ResumeParseOutput(BaseModel):
    """解析端点输出：upload_id + document（前端预览编辑）。"""

    upload_id: UUID
    document: ResumeDocument


class DrillMaterial(BaseModel):
    """用户导入的深挖资料（全局多份，作为面试官消费上下文）。"""

    id: UUID = Field(default_factory=uuid4)
    user_id: str
    title: str
    body: str
    created_at: datetime
    updated_at: datetime


class DrillRound(StrEnum):
    """模拟面试轮次。"""

    TECH_1 = "tech_1"  # 技术一面：基础 + 项目梳理，偏广度
    TECH_2 = "tech_2"  # 技术二面：深度追问 + 系统设计
    TECH_3 = "tech_3"  # 技术三面：架构 / 跨项目
    TECH_4 = "tech_4"  # 技术四面：资深 / 终面技术
    HR = "hr"  # HR 面：行为面 / 职业规划


class DrillSession(BaseModel):
    """一次模拟面试 session（简历级，可选聚焦某项目，分轮次/方向）。"""

    id: UUID = Field(default_factory=uuid4)
    user_id: str
    resume_id: UUID
    round: DrillRound
    direction: str | None = None  # 自由文本，如「偏架构」
    project_id: UUID | None = None  # 可选聚焦某项目；None = 简历级
    status: str = "active"  # active | done
    started_at: datetime
    ended_at: datetime | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)  # [{role, text}]
