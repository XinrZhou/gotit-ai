export type PlanItem = {
  id: string;
  title: string;
  source: string;
  status: string;
  claim_id: string | null;
  sort_order: number;
  due_at: string | null;
  due_time: string | null;
  project_id: string | null;
  topic: string | null;
};

export type DayNote = {
  id: string;
  title: string | null;
  body: string;
  excerpt: string;
  tags: string[];
  claim_ids: string[];
  created_at: string;
  day: string | null;
};

export type DayCloseSummary = {
  passed_count: number;
  still_owed_count: number;
  note: string;
  closed_at: string | null;
};

/** First-pass empty-library guide from `/v1/today`. */
export type BootcampView = {
  status: "none" | "in_progress" | "done" | "skipped";
  show: boolean;
  step: "ingest" | "verify" | "celebrate" | null;
  claim_count: number;
  note_count: number;
  claim_id: string | null;
  claim_text: string | null;
  gate_verdict: MasteryVerdict | null;
};

/** Quiet / featured drill hint from `/v1/today` when interview ramp is on. */
export type InterviewFocusHint = {
  interview_id: string;
  company: string;
  role_title: string;
  hours_until: number;
  ramp_tier: "urgent" | "warm" | "light";
  prompt: string;
  prominence: "quiet" | "featured";
  project_name: string | null;
  project_id: string | null;
  round: string | null;
  open_drill: OpenDrillPayload;
};

export type DayPlan = {
  date: string;
  user_id: string;
  items: PlanItem[];
};

export type Project = {
  id: string;
  user_id: string;
  name: string;
  role: string | null;
  goal: string | null;
  tech_stack: string[];
  status: string;
  created_at: string;
};

export type ProjectProgress = {
  claims_total: number;
  mastered: number;
  in_progress: number;
  not_yet: number;
};

export type MasteryVerdict = "passed" | "almost" | "owe_next";

/** Preferred verify form (VISION P3). null/omit → probe. */
export type CheckMode = "probe" | "drill" | "teach_back";

export type Claim = {
  id: string;
  text: string;
  status: string;
  topic: string | null;
  source_note_id: string | null;
  next_review_at: string | null;
  project_id?: string | null;
  preferred_check_mode?: CheckMode | null;
  /** Present on `/v1/today` due list — why this claim is owed today. */
  due_reason_code?: string | null;
  due_reason_text?: string | null;
  /** Quiet prior-miss tip on today/due views. */
  failure_hint?: string | null;
};

/** `POST /v1/notes/{id}/ingest` body. */
export type NoteIngestResponse = {
  note_id: string;
  claims: Claim[];
  plan_items: PlanItem[];
};

/** In-modal note→claim progress (compose / view note). */
export type IngestUi =
  | { phase: "generating"; noteId: string | null; surface: "compose" | "view" }
  | { phase: "ready"; noteId: string; claims: Claim[]; surface: "compose" | "view" };

export type VerifyPath = {
  examine_verdict: MasteryVerdict;
  recheck_verdict: MasteryVerdict;
  gate_verdict: MasteryVerdict;
  gate?: { reason?: string; verdict?: MasteryVerdict };
};

export type ChatMsg = {
  role: "examiner" | "user";
  text: string;
  /** Present when this examiner turn closed a claim. */
  verdict?: MasteryVerdict | null;
  session_done?: boolean;
  /** Critic → gate path when this turn closed a claim. */
  verify?: VerifyPath | null;
  /** Quiet “你曾在这栽过” when re-examining / re-teaching. */
  failure_hint?: string | null;
  /** Soft failure bubble (e.g. LLM/gateway down). */
  error?: boolean;
};

export type TopicExamineVerdict = {
  current_claim_id?: string | null;
  done: boolean;
  verdict: MasteryVerdict | null;
  follow_up: string;
  session_done?: boolean;
};

/** Writeback slice from apply_examine_verdict (already on the wire). */
export type VerifyWriteback = {
  claim?: {
    id?: string;
    text?: string;
    status?: string;
    next_review_at?: string | null;
  } | null;
  plan_items?: unknown[];
  verdict?: MasteryVerdict | string;
  schedule_reason?: string | null;
  interval_days?: number | null;
  failure_digest_id?: string | null;
};

/** Session-done summary for Verify Done bar — no new domain state. */
export type VerifyOutcome = {
  gate_verdict: MasteryVerdict;
  gate_reason?: string | null;
  writeback: VerifyWriteback | null;
  claim_id?: string | null;
  claim_label?: string | null;
};

export type TopicExamineResponse = {
  verdict: TopicExamineVerdict;
  writeback: VerifyWriteback | null;
  verify?: VerifyPath | null;
  /** Learner-facing prior-miss tip when re-examining. */
  failure_hint?: string | null;
};

export type TeachVerdict = {
  done: boolean;
  you_taught_well: boolean | null;
  gaps: string[];
  next_question: string | null;
};

export type TeachResponse = {
  verdict: TeachVerdict;
  writeback?: VerifyWriteback | null;
  verify?: VerifyPath | null;
  failure_hint?: string | null;
};

export type SageVerdict = {
  done: boolean;
  depth_reached: number;
  gaps: string[];
  follow_up: string | null;
  round: string | null;
};

export type DrillResponse = {
  verdict: SageVerdict;
};

export type ResumeBasics = {
  name: string | null;
  target_role: string | null;
};

export type ResumeProject = {
  name: string;
  role: string | null;
  goal: string | null;
  tech_stack: string[];
  description: string;
};

export type ResumeDocument = {
  basics: ResumeBasics;
  projects: ResumeProject[];
};

export type ResumeRecord = {
  id: string;
  user_id: string;
  upload_id: string;
  file_path: string;
  document: ResumeDocument;
  created_at: string;
};

export type ResumeUploadResponse = {
  upload_id: string;
  file_path: string;
  document: ResumeDocument;
};

export type ResumeApplyResponse = {
  projects: Project[];
  notes: DayNote[];
  claims: unknown[];
};

export type DrillMaterial = {
  id: string;
  user_id: string;
  title: string;
  body: string;
  created_at: string;
  updated_at: string;
};

export type DrillRound = "tech_1" | "tech_2" | "tech_3" | "tech_4" | "hr";

export type DrillSession = {
  id: string;
  user_id: string;
  resume_id: string;
  round: DrillRound;
  direction: string | null;
  project_id: string | null;
  status: string;
  started_at: string;
  ended_at: string | null;
  messages: ChatMsg[];
};

export type DrillSessionStartResponse = {
  session: DrillSession;
  verdict: SageVerdict;
};

export type DrillSessionContinueResponse = {
  verdict: SageVerdict;
};

export type Mode = "chat" | "examine" | "teach" | "drill";

export type CalibrationOutcome = "correct" | "incorrect";

export type CalibrationItem = {
  claim_id: string;
  text: string;
  topic: string | null;
  difficulty: number;
  discrimination: number;
  knowledge_key: string;
  n: number;
  max_items: number;
};

export type CalibrationSummary = {
  passed_count: number;
  failed_count: number;
  confused_edges_seeded: number;
  due_count: number;
  stop_reason: string | null;
  theta: number | null;
  se: number | null;
  item_count: number;
};

export type CalibrationSession = {
  id: string;
  user_id: string;
  status: "active" | "completed" | "cancelled";
  theta: number;
  se: number;
  item_count: number;
  stop_reason: string | null;
  scope: Record<string, unknown>;
  trace: Record<string, unknown>[];
  summary: CalibrationSummary | null;
  current_item: CalibrationItem | null;
  done: boolean;
  created_at: string | null;
  completed_at: string | null;
};

export type ImportTab = "write" | "link" | "zip";

// --- companion-arch: chat surface ---

export type Thread = {
  id: string;
  user_id: string;
  title: string;
  kind: "chat" | "verify";
  status: string;
  created_at: string;
  updated_at: string;
};

/** Companion whitelist tool trail on agent message metadata. */
export type CompanionToolCall = {
  name: string;
  args_digest: string;
  ok: boolean;
  summary: string;
  open_examine?: OpenExaminePayload | null;
  open_teach?: OpenTeachPayload | null;
  open_drill?: OpenDrillPayload | null;
};

/** Tappable card on agent message ``metadata.action_blocks``. */
export type ActionBlockAction = {
  id: string;
  label: string;
};

export type OwedClaimActionBlock = {
  type: "owed_claim";
  claim_id: string;
  title: string;
  due_reason_text?: string | null;
  preferred_check_mode?: CheckMode | null;
  project_id?: string | null;
  actions: ActionBlockAction[];
};

export type VerdictActionBlock = {
  type: "verdict";
  gate_verdict: MasteryVerdict;
  claim_id?: string;
  actions: ActionBlockAction[];
};

export type ActionBlock = OwedClaimActionBlock | VerdictActionBlock;

/** Payload from `start_examine` for one-tap follow into /v1/examine. */
export type OpenExaminePayload = {
  action?: string;
  claim_id?: string;
  claim_text?: string;
  topic?: string | null;
  note_id?: string;
  note_title?: string | null;
  claim_ids?: string[];
  plan_item_id?: string;
  plan_changed?: boolean;
  thread_id?: string | null;
};

/** Payload from `start_verify` → teach for one-tap follow into /v1/teach. */
export type OpenTeachPayload = {
  action?: string;
  claim_id?: string;
  claim_text?: string;
  topic?: string | null;
  plan_item_id?: string;
  plan_changed?: boolean;
  thread_id?: string | null;
};

/** Payload from `start_drill` / upcoming interview for one-tap drill. */
export type OpenDrillPayload = {
  action?: string;
  round?: DrillRound | string;
  direction?: string | null;
  project_id?: string | null;
  project_name?: string | null;
  interview_id?: string | null;
  company?: string | null;
  thread_id?: string | null;
  has_resume?: boolean;
};

export type ChatMessage = {
  id: string;
  thread_id: string;
  agent_name: string | null;
  role: "user" | "agent" | "system";
  text: string;
  mentions: string[];
  metadata: Record<string, unknown>;
  created_at: string;
};

export type AgentReply = {
  user_message: ChatMessage;
  agent_messages: ChatMessage[];
  thread?: Thread | null;
};

export type AgentIdentity = {
  id: string;
  agent_name: string;
  display_name: string;
  personality: string;
  role: string;
  llm_config: Record<string, unknown>;
  memory_scope: Record<string, unknown>;
  prompt_version_id: string | null;
  created_at: string;
  updated_at: string;
};

export type SkillInfo = {
  name: string;
  notes: string | null;
  enabled: boolean;
  source: "builtin" | "user";
};

export type SkillDetail = SkillInfo & {
  markdown: string;
  editable: boolean;
};

export type McpConnector = {
  id: string;
  user_id: string;
  name: string;
  transport: "stdio" | "http" | "sse";
  config: Record<string, unknown>;
  enabled: boolean;
  last_status: "unknown" | "ok" | "error";
  last_error: string | null;
  created_at: string;
  updated_at: string;
};

export type MemoryEntry = {
  id: string;
  user_id: string;
  layer: string;
  kind: string;
  topic: string | null;
  content: Record<string, unknown>;
  source: Record<string, unknown>;
  created_at: string;
  expires_at: string | null;
};

export type InterestPromoteResult = {
  ok: boolean;
  interest_id: string;
  already_promoted: boolean;
  reason: string | null;
  rewrite_suggestion: string | null;
  note_id: string | null;
  claims: Claim[];
  plan_item_ids: string[];
};

export type ProfileTopicStat = {
  topic: string;
  trajectory_failures: number;
  trajectory_passes: number;
  interest_count: number;
};

export type ProfileView = {
  topics: ProfileTopicStat[];
  weak_topics: string[];
  interest_total: number;
  shell_event_total: number;
  trajectory_total: number;
};

export type GraphNode = {
  id: string;
  type: "claim" | "topic" | "project" | "interest";
  label: string;
  meta: Record<string, unknown>;
};

export type GraphEdge = {
  source: string;
  target: string;
  rel:
    | "has_topic"
    | "in_project"
    | "interest_topic"
    | "confused_with"
    | "depends_on";
  weight?: number;
  meta?: Record<string, unknown>;
};

export type GraphView = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type InterviewStatus = "scheduled" | "done" | "cancelled";

export type InterviewEvent = {
  id: string;
  user_id: string;
  company: string;
  role_title: string;
  scheduled_at: string;
  round: string | null;
  status: InterviewStatus;
  notes: string | null;
  remind_offsets_hours: number[];
  last_reminded_at: string | null;
  last_ramp_nudge_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type InterviewRampPrefs = {
  enabled: boolean;
  max_nudges_per_week: number;
};

export type InterviewUpcoming = {
  interview_id: string;
  company: string;
  role_title: string;
  scheduled_at: string;
  round: string | null;
  hours_until: number;
  ramp_tier: "past" | "urgent" | "warm" | "light" | "silent";
  tier_hint: string;
  suggest_action: string;
  project_name: string | null;
  project_id?: string | null;
};
