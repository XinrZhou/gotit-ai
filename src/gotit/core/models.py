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
    # Populated on today/due views (server-assembled; optional elsewhere).
    due_reason_code: str | None = None
    due_reason_text: str | None = None


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
    due_time: str | None = None  # HH:MM local wall clock for Reminders
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


class ShellDigestItem(BaseModel):
    """One RSS item inside a shell_event."""

    n: int
    title: str
    link: str | None = None
    feed_id: str | None = None
    label: str | None = None


class DigestFeed(BaseModel):
    """One configurable RSS / YouTube Atom source for digest news."""

    id: str
    label: str
    url: str
    enabled: bool = True


class DigestPrefs(BaseModel):
    """User prefs for OpenClaw plan/news digests (gotit is source of truth)."""

    timezone: str = "Asia/Shanghai"
    item_count: int = Field(default=3, ge=1, le=20)
    morning_cron: str = "0 8 * * *"
    evening_cron: str = "0 21 * * *"
    news_cron: str | None = "0 20 * * *"
    news_enabled: bool = True
    morning_include_news: bool = False
    evening_include_news: bool = False
    keywords: list[str] = Field(default_factory=list)
    feeds: list[DigestFeed] = Field(default_factory=list)
    # Public https URL of /open/notes bridge (WeChat only auto-links https).
    # Example: https://<tailscale-or-tunnel-host>/open/notes
    notes_open_url: str | None = None


class DigestCronSyncResult(BaseModel):
    """Result of running skills/digest/install-cron.sh from gotit API."""

    ok: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    detail: str | None = None


class DigestCronSuggestRequest(BaseModel):
    """Natural language → cron for digest prefs."""

    text: str = Field(min_length=1, max_length=200)
    target: Literal["morning", "evening", "news"] = "morning"


class DigestCronSuggestResult(BaseModel):
    cron: str
    explanation: str | None = None
    source: Literal["rule", "llm"] = "rule"


class ProfileTopicStat(BaseModel):
    """Per-topic aggregation for obs profile v0."""

    topic: str
    trajectory_failures: int = 0
    trajectory_passes: int = 0
    interest_count: int = 0


class ProfileView(BaseModel):
    """User profile v0 from trajectory + interest (+ shell volume)."""

    topics: list[ProfileTopicStat] = Field(default_factory=list)
    weak_topics: list[str] = Field(default_factory=list)
    interest_total: int = 0
    shell_event_total: int = 0
    trajectory_total: int = 0


class GraphNode(BaseModel):
    id: str
    type: Literal["claim", "topic", "project", "interest"]
    label: str
    meta: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    rel: Literal["has_topic", "in_project", "interest_topic", "confused_with"]
    weight: int = 1
    meta: dict[str, Any] = Field(default_factory=dict)


class GraphView(BaseModel):
    """Mastery / obs graph: claim–topic–project + confused_with (+ interest)."""

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class FailEventView(BaseModel):
    id: UUID
    claim_id: UUID
    topic: str | None = None
    gate_verdict: str
    score: float | None = None
    reason: str | None = None
    created_at: datetime


class BudgetSubgraphView(BaseModel):
    """P4 budget context for one claim under examination."""

    claim_id: UUID
    confused_claim_ids: list[UUID] = Field(default_factory=list)
    confused_labels: list[str] = Field(default_factory=list)
    fail_reasons: list[str] = Field(default_factory=list)
    prompt_block: str | None = None


# --- Cold-start calibration ---


class CalibrationMeta(BaseModel):
    """Per-claim item parameters for CAT selection."""

    difficulty: int = 3
    discrimination: float = 1.0
    knowledge_key: str = "_untagged"


class CalibrationItemView(BaseModel):
    """Current (or next) probe shown to the learner."""

    claim_id: UUID
    text: str
    topic: str | None = None
    difficulty: int = 3
    discrimination: float = 1.0
    knowledge_key: str = "_untagged"
    n: int = 1
    max_items: int = 10


class CalibrationSummary(BaseModel):
    passed_count: int = 0
    failed_count: int = 0
    confused_edges_seeded: int = 0
    due_count: int = 0
    stop_reason: str | None = None
    theta: float | None = None
    se: float | None = None
    item_count: int = 0


class CalibrationSessionView(BaseModel):
    id: UUID
    user_id: str
    status: Literal["active", "completed", "cancelled"] = "active"
    theta: float = 3.0
    se: float = 1.5
    item_count: int = 0
    stop_reason: str | None = None
    scope: dict[str, Any] = Field(default_factory=dict)
    trace: list[dict[str, Any]] = Field(default_factory=list)
    summary: CalibrationSummary | None = None
    current_item: CalibrationItemView | None = None
    done: bool = False
    created_at: datetime | None = None
    completed_at: datetime | None = None


class SyntheticCalibrationResult(BaseModel):
    true_theta: float
    theta_hat: float
    abs_error: float
    item_count: int
    stop_reason: str | None = None
    trace: list[dict[str, Any]] = Field(default_factory=list)


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


# --- Companion-os: scheduled real interviews ---


class InterviewStatus(StrEnum):
    SCHEDULED = "scheduled"
    DONE = "done"
    CANCELLED = "cancelled"


DEFAULT_REMIND_OFFSETS_HOURS: list[int] = [-24, -2]


class InterviewEvent(BaseModel):
    """Upsert input for a scheduled real-world interview."""

    id: UUID | None = None
    company: str = Field(min_length=1, max_length=200)
    role_title: str = Field(min_length=1, max_length=200)
    scheduled_at: datetime
    round: str | None = Field(default=None, max_length=32)
    status: InterviewStatus = InterviewStatus.SCHEDULED
    notes: str | None = None
    remind_offsets_hours: list[int] = Field(
        default_factory=lambda: list(DEFAULT_REMIND_OFFSETS_HOURS)
    )


class InterviewEventView(BaseModel):
    """Persisted interview event returned from REST/MCP."""

    id: UUID
    user_id: str
    company: str
    role_title: str
    scheduled_at: datetime
    round: str | None = None
    status: InterviewStatus
    notes: str | None = None
    remind_offsets_hours: list[int] = Field(
        default_factory=lambda: list(DEFAULT_REMIND_OFFSETS_HOURS)
    )
    last_reminded_at: datetime | None = None
    last_ramp_nudge_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DueInterviewReminder(BaseModel):
    """A due reminder for OpenClaw interview-remind skill."""

    interview_id: UUID
    company: str
    role_title: str
    scheduled_at: datetime
    round: str | None = None
    offset_hours: int
    fire_at: datetime


class InterviewRampPrefs(BaseModel):
    """Optional countdown-ramp nudges (P4). Offset reminders always stay on."""

    enabled: bool = True
    max_nudges_per_week: int = Field(default=2, ge=0, le=14)


class InterviewUpcoming(BaseModel):
    """Nearest / upcoming interviews with deterministic ramp tier."""

    interview_id: UUID
    company: str
    role_title: str
    scheduled_at: datetime
    round: str | None = None
    hours_until: float
    ramp_tier: Literal["past", "urgent", "warm", "light", "silent"]
    tier_hint: str = ""
    suggest_action: str = ""
    project_name: str | None = None


class InterviewRampNudge(BaseModel):
    """Deliverable ramp nudge for OpenClaw (light/warm only)."""

    interview_id: UUID
    company: str
    role_title: str
    scheduled_at: datetime
    round: str | None = None
    hours_until: float
    ramp_tier: Literal["light", "warm"]
    suggest_action: str
    project_name: str | None = None
    tier_hint: str = ""


# --- Companion-arch: identity / messaging / loop ---


class AgentIdentity(BaseModel):
    """持久人格 agent = personality + role + model config + memory scope + rubric pin."""

    id: UUID = Field(default_factory=uuid4)
    agent_name: str  # axiom | compass | echo | sage | critic
    display_name: str
    personality: str  # 人格 prompt 片段，注入 system prompt
    role: str  # examiner | curator | teachback | reviewer | critic
    llm_config: dict[str, Any] = Field(
        default_factory=dict
    )  # {model|model_name, base_url, api_key|api_key_env}
    memory_scope: dict[str, Any] = Field(default_factory=dict)  # {layers, topics}
    prompt_version_id: UUID | None = None  # 绑定的 rubric 版本
    created_at: datetime
    updated_at: datetime


class ThreadKind(StrEnum):
    CHAT = "chat"
    VERIFY = "verify"


class Thread(BaseModel):
    """一个学习对话 thread（隔离的上下文工作区）。"""

    id: UUID = Field(default_factory=uuid4)
    user_id: str
    title: str
    kind: ThreadKind = ThreadKind.CHAT
    status: str = "active"  # active | done
    created_at: datetime
    updated_at: datetime


class MessageRole(StrEnum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class Message(BaseModel):
    """thread 内一条消息（user / agent / system）。"""

    id: UUID = Field(default_factory=uuid4)
    thread_id: UUID
    agent_name: str | None = None  # 哪个 agent 发的；user/system 为 None
    role: MessageRole
    text: str
    mentions: list[str] = Field(default_factory=list)  # @mention 路由目标
    metadata: dict[str, Any] = Field(default_factory=dict)  # claim_id/verdict/gate_result/step
    created_at: datetime


class BallStage(StrEnum):
    CHAT = "chat"  # free-chat "current companion" custody (A2A handoff)
    EXAMINE = "examine"
    RECHECK = "recheck"
    GATE = "gate"


class BallCustody(BaseModel):
    """verify-loop 接力棒：谁持棒、在哪个阶段、交棒上下文包。"""

    id: UUID = Field(default_factory=uuid4)
    thread_id: UUID
    holder: str  # 当前持棒 agent_name
    stage: BallStage
    context: dict[str, Any] = Field(default_factory=dict)  # {claim_id, verdict, evidence, ...}
    acquired_at: datetime
    expires_at: datetime | None = None


class GateResult(BaseModel):
    """确定性 mastery gate 判定结果（不调 LLM）。"""

    passed: bool
    verdict: Literal["passed", "almost", "owe_next"]
    next_review_at: date | None = None
    reason: str


class RecheckVerdict(BaseModel):
    """Critic 对 Axiom 判定的独立复核结果。"""

    verdict: Literal["passed", "almost", "owe_next"]
    reason: str


class ChatTurn(BaseModel):
    """A conversational agent's structured reply: text + optional A2A handoff.

    `thinking` is optional chain-of-thought shown in a collapsed UI block.
    `handoff_to` lets an agent cede the floor to another agent in the same turn
    (true agent-to-agent接力). `reason` is injected into the next holder's
    context so it knows why it was handed the ball.
    """

    thinking: str | None = Field(
        default=None,
        description="Optional brief reasoning before the visible reply.",
    )
    text: str
    handoff_to: str | None = None
    reason: str | None = None


class AgentReply(BaseModel):
    """Result of one user message through the A2A 接力 chain."""

    user_message: Message
    agent_messages: list[Message] = Field(
        description="Agent replies produced this turn — may be more than one when "
        "agents hand off to each other (A2A 接力).",
    )
    thread: Thread | None = Field(
        default=None,
        description="Updated thread when title (or other fields) changed this turn.",
    )


# --- Profile center: skills / MCP connectors (for companion agents) ---


class SkillInfo(BaseModel):
    """Installed or builtin on-demand skill visible in Settings + chat tray."""

    name: str
    notes: str | None = None
    enabled: bool = True
    source: Literal["builtin", "user"] = "builtin"


class SkillDetail(SkillInfo):
    """Skill body for Settings view/edit."""

    markdown: str
    editable: bool = False


class McpConnector(BaseModel):
    """User-configured MCP server that companion agents may call as tools."""

    id: UUID = Field(default_factory=uuid4)
    user_id: str
    name: str
    transport: Literal["stdio", "http", "sse"]
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    last_status: Literal["unknown", "ok", "error"] = "unknown"
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
