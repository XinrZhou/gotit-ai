import type {
  DayNote,
  DayPlan,
  DrillMaterial,
  DrillRound,
  DrillSession,
  Mode,
  Project,
  ProjectProgress,
  ResumeDocument,
  ResumeRecord,
  ResumeUploadResponse,
} from "../types";

export type ChatTurn = { role: "examiner" | "user"; text: string };

export type Run = (
  action: () => Promise<unknown>,
  okMessage?: string,
) => Promise<void>;

export type Store = {
  day: string;
  setDay: (d: string) => void;
  plan: DayPlan | null;
  notes: DayNote[];
  noteScope: "today" | "all";
  setNoteScope: (s: "today" | "all") => void;
  projects: Project[];
  items: { id: string; title: string; topic: string | null; status: string }[];
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
  userProfile: { name: string; avatar: string };
  setUserProfile: (p: { name: string; avatar: string }) => void;
  viewNote: DayNote | null;
  setViewNote: (n: DayNote | null) => void;
  onOpenNote: (id: string) => void;
  onDeleteNote: (id: string) => void;
  onDeleteNotes: (ids: string[]) => void;
  onIngestNote: (id: string) => void;
  onIngestAll: () => void;
  showCompose: boolean;
  setShowCompose: (b: boolean) => void;
  showProjectModal: boolean;
  setShowProjectModal: (b: boolean) => void;
  editingProject: Project | null;
  onOpenEditProject: (p: Project) => void;
  saveProject: (
    editing: Project | null,
    fields: { name: string; role: string; goal: string; tech_stack: string[] },
  ) => void;
  examineNote: DayNote | null;
  examineChat: ChatTurn[];
  examineAnswer: string;
  setExamineAnswer: (s: string) => void;
  examineSessionDone: boolean;
  onExamineStart: (note: DayNote) => void;
  onExamineAnswer: () => void;
  teachTopic: string;
  setTeachTopic: (s: string) => void;
  teachChat: ChatTurn[];
  teachAnswer: string;
  setTeachAnswer: (s: string) => void;
  teachDone: boolean;
  onTeachStart: () => void;
  onTeachAnswer: () => void;
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
  onDrillAnswer: () => void;
  onSelectDrillSession: (s: DrillSession) => void;
  onBackToDrillStart: () => void;
};
