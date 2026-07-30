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

export type Claim = {
  id: string;
  text: string;
  status: string;
  topic: string | null;
  source_note_id: string | null;
  next_review_at: string | null;
  /** Present on `/v1/today` due list — why this claim is owed today. */
  due_reason_code?: string | null;
  due_reason_text?: string | null;
};

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

export type TopicExamineResponse = {
  verdict: TopicExamineVerdict;
  writeback: { claim: { status: string }; plan_items: unknown[] } | null;
  verify?: VerifyPath | null;
};

export type TeachVerdict = {
  done: boolean;
  you_taught_well: boolean | null;
  gaps: string[];
  next_question: string | null;
};

export type TeachResponse = {
  verdict: TeachVerdict;
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
  rel: "has_topic" | "in_project" | "interest_topic" | "confused_with";
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
  created_at: string;
  updated_at: string;
};
