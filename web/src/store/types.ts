import type {
  BootcampView,
  Claim,
  DayCloseSummary,
  DayNote,
  DayPlan,
  DrillMaterial,
  DrillRound,
  DrillSession,
  IngestUi,
  InterviewFocusHint,
  MasteryVerdict,
  Mode,
  Project,
  ProjectProgress,
  ResumeDocument,
  ResumeRecord,
  ResumeUploadResponse,
  VerifyPath,
} from "../types";

export type ChatTurn = {
  role: "examiner" | "user";
  text: string;
  verdict?: MasteryVerdict | null;
  session_done?: boolean;
  verify?: VerifyPath | null;
  error?: boolean;
};

export type Run = (
  action: () => Promise<unknown>,
  okMessage?: string,
) => Promise<void>;

export type Store = {
  day: string;
  setDay: (d: string) => void;
  plan: DayPlan | null;
  notes: DayNote[];
  dueClaims: Claim[];
  dayClosed: boolean;
  closeSuggested: boolean;
  closeSummary: DayCloseSummary | null;
  closeToday: (note?: string) => Promise<void>;
  interviewFocus: InterviewFocusHint | null;
  bootcamp: BootcampView | null;
  setBootcampStatus: (
    status: "in_progress" | "done" | "skipped",
  ) => Promise<void>;
  noteScope: "today" | "all";
  setNoteScope: (s: "today" | "all") => void;
  projects: Project[];
  items: {
    id: string;
    title: string;
    topic: string | null;
    status: string;
    claim_id: string | null;
    project_id?: string | null;
  }[];
  selectedProjectId: string | null;
  setSelectedProjectId: (id: string | null) => void;
  projectPicked: boolean;
  setProjectPicked: (v: boolean) => void;
  selectedProject: Project | null;
  mode: Mode;
  setMode: (m: Mode) => void;
  busy: boolean;
  setBusy: (b: boolean) => void;
  error: string;
  flash: string;
  setFlash: (s: string) => void;
  setError: (s: string) => void;
  refresh: () => Promise<void>;
  run: Run;
  openMenuId: string | null;
  setOpenMenuId: (id: string | null) => void;
  libraryOpen: boolean;
  setLibraryOpen: (open: boolean) => void;
  masteryGraphOpen: boolean;
  setMasteryGraphOpen: (open: boolean) => void;
  settingsOpen: boolean;
  setSettingsOpen: (open: boolean) => void;
  workflowThreadId: string | null;
  setWorkflowThreadId: (id: string | null) => void;
  userProfile: { name: string; avatar: string };
  setUserProfile: (p: { name: string; avatar: string }) => void;
  viewNote: DayNote | null;
  setViewNote: (n: DayNote | null) => void;
  onOpenNote: (id: string) => void;
  onDeleteNote: (id: string) => void;
  onDeleteNotes: (ids: string[]) => void;
  onIngestNote: (
    id: string,
    opts?: { surface?: "compose" | "view" | "silent" },
  ) => Promise<void>;
  onIngestAll: () => void;
  ingestUi: IngestUi | null;
  beginComposeIngest: () => void;
  clearIngestUi: () => void;
  dismissIngestReady: () => void;
  requestExamineFromIngest: () => void;
  pendingExamineClaim: Claim | null;
  clearPendingExamineClaim: () => void;
  showCompose: boolean;
  setShowCompose: (b: boolean) => void;
  showProjectModal: boolean;
  setShowProjectModal: (b: boolean) => void;
  editingProject: Project | null;
  onOpenEditProject: (p: Project) => void;
  onDeleteProject: (p: Project) => void;
  saveProject: (
    editing: Project | null,
    fields: { name: string; role: string; goal: string; tech_stack: string[] },
  ) => void;
  examineNote: DayNote | null;
  examineClaimId: string | null;
  examineLabel: string;
  examineChat: ChatTurn[];
  examineAnswer: string;
  setExamineAnswer: (s: string) => void;
  examineSessionDone: boolean;
  onExamineStart: (note: DayNote) => void;
  onExamineStartClaim: (claim: Claim) => void;
  onExamineAnswer: () => void;
  teachTopic: string;
  setTeachTopic: (s: string) => void;
  teachClaimId: string | null;
  setTeachClaimId: (id: string | null) => void;
  teachChat: ChatTurn[];
  teachAnswer: string;
  setTeachAnswer: (s: string) => void;
  teachDone: boolean;
  teachSttAvailable: boolean;
  teachTranscribing: boolean;
  onTeachStart: () => void;
  onTeachStartClaim: (claim: Claim) => void;
  onTeachAnswer: () => void;
  onTeachTranscribe: (file: File) => Promise<void>;
  resume: ResumeRecord | null;
  drillMaterials: DrillMaterial[];
  drillSessions: DrillSession[];
  activeDrillSession: DrillSession | null;
  drillRound: DrillRound;
  setDrillRound: (r: DrillRound) => void;
  drillDirection: string;
  setDrillDirection: (s: string) => void;
  drillFocusProjectId: string | null;
  setDrillFocusProjectId: (id: string | null) => void;
  drillChat: ChatTurn[];
  drillAnswer: string;
  setDrillAnswer: (s: string) => void;
  drillDone: boolean;
  progress: ProjectProgress | null;
  showResumeModal: boolean;
  setShowResumeModal: (b: boolean) => void;
  showMaterialModal: boolean;
  setShowMaterialModal: (b: boolean) => void;
  showResumeViewer: boolean;
  setShowResumeViewer: (b: boolean) => void;
  onUploadResume: (file: File) => Promise<ResumeUploadResponse>;
  onApplyResume: (
    uploadId: string,
    document: ResumeDocument,
    filePath: string,
  ) => Promise<void>;
  onUpsertMaterial: (id: string | null, title: string, body: string) => Promise<void>;
  onImportMaterialFile: (file: File) => Promise<{ title: string; body: string }>;
  onDeleteMaterial: (id: string) => Promise<void>;
  onDrillStartSession: () => void;
  onDrillStartWithPayload: (payload: {
    round?: string;
    direction?: string | null;
    project_id?: string | null;
    thread_id?: string | null;
  }) => void;
  onDrillAnswer: () => void;
  onSelectDrillSession: (s: DrillSession) => void;
  onBackToDrillStart: () => void;
};
