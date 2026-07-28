import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, uploadFile } from "./api";
import type {
  DayNote,
  DayPlan,
  DrillMaterial,
  DrillRound,
  DrillSession,
  DrillSessionContinueResponse,
  DrillSessionStartResponse,
  Mode,
  Project,
  ProjectProgress,
  ResumeApplyResponse,
  ResumeDocument,
  ResumeRecord,
  ResumeUploadResponse,
  TeachResponse,
  TopicExamineResponse,
} from "./types";

type Store = {
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
  run: (action: () => Promise<unknown>, okMessage?: string) => Promise<void>;
  openMenuId: string | null;
  setOpenMenuId: (id: string | null) => void;
  viewNote: DayNote | null;
  setViewNote: (n: DayNote | null) => void;
  onOpenNote: (id: string) => void;
  onDeleteNote: (id: string) => void;
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
  // examine
  examineNote: DayNote | null;
  examineChat: { role: "examiner" | "user"; text: string }[];
  examineAnswer: string;
  setExamineAnswer: (s: string) => void;
  examineSessionDone: boolean;
  onExamineStart: (note: DayNote) => void;
  onExamineAnswer: () => void;
  // teach
  teachTopic: string;
  setTeachTopic: (s: string) => void;
  teachChat: { role: "examiner" | "user"; text: string }[];
  teachAnswer: string;
  setTeachAnswer: (s: string) => void;
  teachDone: boolean;
  onTeachStart: () => void;
  onTeachAnswer: () => void;
  // drill (resume-driven mock interview)
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
  drillChat: { role: "examiner" | "user"; text: string }[];
  drillAnswer: string;
  setDrillAnswer: (s: string) => void;
  drillDone: boolean;
  progress: ProjectProgress | null;
  showResumeModal: boolean;
  setShowResumeModal: (b: boolean) => void;
  showMaterialModal: boolean;
  setShowMaterialModal: (b: boolean) => void;
  onUploadResume: (file: File) => Promise<ResumeUploadResponse>;
  onApplyResume: (uploadId: string, document: ResumeDocument) => Promise<void>;
  onUpsertMaterial: (id: string | null, title: string, body: string) => Promise<void>;
  onDeleteMaterial: (id: string) => Promise<void>;
  onDrillStartSession: () => void;
  onDrillAnswer: () => void;
  onSelectDrillSession: (s: DrillSession) => void;
  onBackToDrillStart: () => void;
};

const Ctx = createContext<Store | null>(null);

export function useStore(): Store {
  const v = useContext(Ctx);
  if (!v) throw new Error("useStore must be inside StoreProvider");
  return v;
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [day, setDay] = useState(() => new Date().toISOString().slice(0, 10));
  const [plan, setPlan] = useState<DayPlan | null>(null);
  const [dayNotes, setDayNotes] = useState<DayNote[]>([]);
  const [allNotes, setAllNotes] = useState<DayNote[]>([]);
  const [noteScope, setNoteScope] = useState<"today" | "all">("today");
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("examine");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [viewNote, setViewNote] = useState<DayNote | null>(null);
  const [showCompose, setShowCompose] = useState(false);
  const [showProjectModal, setShowProjectModal] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);

  const [examineNote, setExamineNote] = useState<DayNote | null>(null);
  const [examineChat, setExamineChat] = useState<
    { role: "examiner" | "user"; text: string }[]
  >([]);
  const [examineAnswer, setExamineAnswer] = useState("");
  const [examineSessionDone, setExamineSessionDone] = useState(false);

  const [teachTopic, setTeachTopic] = useState("");
  const [teachAnswer, setTeachAnswer] = useState("");
  const [teachChat, setTeachChat] = useState<
    { role: "examiner" | "user"; text: string }[]
  >([]);
  const [teachDone, setTeachDone] = useState(false);

  // drill (resume-driven)
  const [resume, setResume] = useState<ResumeRecord | null>(null);
  const [drillMaterials, setDrillMaterials] = useState<DrillMaterial[]>([]);
  const [drillSessions, setDrillSessions] = useState<DrillSession[]>([]);
  const [activeDrillSession, setActiveDrillSession] = useState<DrillSession | null>(null);
  const [drillRound, setDrillRound] = useState<DrillRound>("tech_2");
  const [drillDirection, setDrillDirection] = useState("");
  const [drillFocusProjectId, setDrillFocusProjectId] = useState<string | null>(null);
  const [drillChat, setDrillChat] = useState<
    { role: "examiner" | "user"; text: string }[]
  >([]);
  const [drillAnswer, setDrillAnswer] = useState("");
  const [drillDone, setDrillDone] = useState(false);
  const [progress, setProgress] = useState<ProjectProgress | null>(null);
  const [showResumeModal, setShowResumeModal] = useState(false);
  const [showMaterialModal, setShowMaterialModal] = useState(false);

  const items = plan?.items ?? [];
  const selectedProject = useMemo(
    () => projects.find((p) => p.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );

  const refresh = useCallback(async () => {
    setError("");
    const fetches: Promise<unknown>[] = [
      api<DayPlan>(`/v1/days/${day}/plan`),
      api<DayNote[]>(`/v1/days/${day}/notes`),
      api<Project[]>(`/v1/projects`),
      api<ResumeRecord | null>(`/v1/resumes`),
      api<DrillMaterial[]>(`/v1/drill/materials`),
      api<DrillSession[]>(`/v1/drill/sessions`),
    ];
    if (noteScope === "all") {
      fetches.push(api<DayNote[]>(`/v1/notes`));
    }
    const results = await Promise.all(fetches);
    setPlan(results[0] as DayPlan);
    setDayNotes(results[1] as DayNote[]);
    setProjects(results[2] as Project[]);
    setResume(results[3] as ResumeRecord | null);
    setDrillMaterials(results[4] as DrillMaterial[]);
    setDrillSessions(results[5] as DrillSession[]);
    if (results[6]) setAllNotes(results[6] as DayNote[]);
  }, [day, noteScope]);

  const notes = useMemo(
    () => (noteScope === "all" ? allNotes : dayNotes),
    [noteScope, allNotes, dayNotes],
  );

  useEffect(() => {
    void refresh().catch((err: unknown) => setError(String(err)));
  }, [refresh]);

  const run = useCallback(
    async (action: () => Promise<unknown>, okMessage?: string) => {
      setBusy(true);
      setError("");
      try {
        await action();
        if (okMessage) setFlash(okMessage);
        await refresh();
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    },
    [refresh],
  );

  const onOpenNote = useCallback((id: string) => {
    void (async () => {
      setError("");
      try {
        const n = await api<DayNote>(`/v1/notes/${id}`);
        setViewNote(n);
      } catch (err) {
        setError(String(err));
      }
    })();
  }, []);

  const onDeleteNote = useCallback(
    (id: string) => {
      void run(
        async () => {
          await api<{ ok: boolean }>(`/v1/notes/${id}`, { method: "DELETE" });
          setViewNote(null);
        },
        "笔记已删除",
      );
    },
    [run],
  );

  const onIngestNote = useCallback(
    (id: string) => {
      void run(
        () =>
          api<unknown>(`/v1/notes/${id}/ingest`, {
            method: "POST",
            body: JSON.stringify({ add_plan_item: true }),
          }),
        "题出好了",
      );
    },
    [run],
  );

  const onIngestAll = useCallback(() => {
    const pending = notes.filter((n) => n.claim_ids.length === 0);
    if (pending.length === 0) return;
    void (async () => {
      setBusy(true);
      setError("");
      try {
        for (const n of pending) {
          await api<unknown>(`/v1/notes/${n.id}/ingest`, {
            method: "POST",
            body: JSON.stringify({ add_plan_item: true }),
          });
        }
        setFlash(`出好了，${pending.length} 条都变成题了`);
        await refresh();
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    })();
  }, [notes, refresh]);

  const onOpenEditProject = useCallback((p: Project) => {
    setEditingProject(p);
    setShowProjectModal(true);
  }, []);

  const saveProject = useCallback(
    (
      editing: Project | null,
      fields: { name: string; role: string; goal: string; tech_stack: string[] },
    ) => {
      if (!editing || !fields.name.trim()) return;
      void run(async () => {
        await api<Project>(`/v1/projects/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            name: fields.name.trim(),
            role: fields.role.trim() || null,
            goal: fields.goal.trim() || null,
            tech_stack: fields.tech_stack,
          }),
        });
        setShowProjectModal(false);
      }, "项目已更新");
    },
    [run],
  );

  // --- resume + materials ---

  const onUploadResume = useCallback((file: File) => {
    return uploadFile<ResumeUploadResponse>("/v1/resumes/upload", file);
  }, []);

  const onApplyResume = useCallback(
    async (uploadId: string, document: ResumeDocument) => {
      await run(async () => {
        await api<ResumeApplyResponse>("/v1/resumes/apply", {
          method: "POST",
          body: JSON.stringify({ upload_id: uploadId, document, ingest: false }),
        });
        setShowResumeModal(false);
      }, "简历已导入，项目库已重建");
    },
    [run],
  );

  const onUpsertMaterial = useCallback(
    async (id: string | null, title: string, body: string) => {
      if (!title.trim() || !body.trim()) return;
      await run(async () => {
        await api<DrillMaterial>("/v1/drill/materials", {
          method: "POST",
          body: JSON.stringify({ id, title: title.trim(), body: body.trim() }),
        });
      }, id ? "资料已更新" : "资料已添加");
    },
    [run],
  );

  const onDeleteMaterial = useCallback(
    async (id: string) => {
      await run(async () => {
        await api<{ status: string }>(`/v1/drill/materials/${id}`, { method: "DELETE" });
      }, "资料已删除");
    },
    [run],
  );

  const onExamineStart = useCallback((note: DayNote) => {
    setExamineNote(note);
    setExamineChat([]);
    setExamineAnswer("");
    setExamineSessionDone(false);
    void (async () => {
      setBusy(true);
      setError("");
      try {
        const res = await api<TopicExamineResponse>("/v1/examine", {
          method: "POST",
          body: JSON.stringify({ note_id: note.id }),
        });
        setExamineChat([{ role: "examiner", text: res.verdict.follow_up }]);
        if (res.verdict.session_done) setExamineSessionDone(true);
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    })();
  }, []);

  const onExamineAnswer = useCallback(() => {
    if (!examineNote || !examineAnswer.trim() || examineSessionDone) return;
    const userText = examineAnswer.trim();
    const history = examineChat.map((m) => ({ role: m.role, text: m.text }));
    setExamineChat((prev) => [...prev, { role: "user", text: userText }]);
    setExamineAnswer("");
    void (async () => {
      setBusy(true);
      try {
        const res = await api<TopicExamineResponse>("/v1/examine", {
          method: "POST",
          body: JSON.stringify({
            note_id: examineNote.id,
            answer: userText,
            history,
          }),
        });
        setExamineChat((prev) => [
          ...prev,
          { role: "examiner", text: res.verdict.follow_up },
        ]);
        if (res.verdict.session_done) setExamineSessionDone(true);
        await refresh();
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    })();
  }, [examineNote, examineAnswer, examineChat, examineSessionDone, refresh]);

  const onTeachStart = useCallback(() => {
    if (!teachTopic.trim()) return;
    void (async () => {
      setBusy(true);
      setError("");
      try {
        const res = await api<TeachResponse>("/v1/teach", {
          method: "POST",
          body: JSON.stringify({ topic: teachTopic.trim() }),
        });
        const v = res.verdict;
        if (v.done) {
          const label = v.you_taught_well ? "讲得清楚 ✓" : "还有缺口";
          const gaps = v.gaps.length ? `\n缺口：${v.gaps.join("；")}` : "";
          setTeachChat([{ role: "examiner", text: label + gaps }]);
          setTeachDone(true);
        } else {
          setTeachChat([{ role: "examiner", text: v.next_question ?? "继续讲讲？" }]);
        }
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    })();
  }, [teachTopic]);

  const onTeachAnswer = useCallback(() => {
    if (!teachAnswer.trim() || teachDone) return;
    const userText = teachAnswer.trim();
    const history = teachChat.map((m) => ({ role: m.role, text: m.text }));
    setTeachChat((prev) => [...prev, { role: "user", text: userText }]);
    setTeachAnswer("");
    void (async () => {
      setBusy(true);
      try {
        const res = await api<TeachResponse>("/v1/teach", {
          method: "POST",
          body: JSON.stringify({ topic: teachTopic.trim(), answer: userText, history }),
        });
        const v = res.verdict;
        if (v.done) {
          const label = v.you_taught_well ? "讲得清楚 ✓" : "还有缺口";
          const gaps = v.gaps.length ? `\n缺口：${v.gaps.join("；")}` : "";
          setTeachChat((prev) => [...prev, { role: "examiner", text: label + gaps }]);
          setTeachDone(true);
        } else {
          setTeachChat((prev) => [
            ...prev,
            { role: "examiner", text: v.next_question ?? "继续讲讲？" },
          ]);
        }
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    })();
  }, [teachTopic, teachAnswer, teachChat, teachDone]);

  // When entering drill mode with a selected project, prefill focus + fetch progress.
  useEffect(() => {
    if (mode !== "drill") return;
    if (selectedProject) {
      setDrillFocusProjectId(selectedProject.id);
      void (async () => {
        try {
          const prog = await api<ProjectProgress>(
            `/v1/projects/${selectedProject.id}/progress`,
          );
          setProgress(prog);
        } catch {
          setProgress(null);
        }
      })();
    } else {
      setDrillFocusProjectId(null);
      setProgress(null);
    }
  }, [mode, selectedProject]);

  const onDrillStartSession = useCallback(() => {
    void (async () => {
      setBusy(true);
      setError("");
      try {
        const res = await api<DrillSessionStartResponse>("/v1/drill/sessions", {
          method: "POST",
          body: JSON.stringify({
            round: drillRound,
            direction: drillDirection.trim() || null,
            project_id: drillFocusProjectId,
          }),
        });
        setActiveDrillSession(res.session);
        const v = res.verdict;
        if (v.done) {
          const gaps = v.gaps.length ? `\n缺口：${v.gaps.join("；")}` : "";
          setDrillChat([
            { role: "examiner", text: `深挖结束（深度 ${v.depth_reached}）${gaps}` },
          ]);
          setDrillDone(true);
        } else {
          setDrillChat([{ role: "examiner", text: v.follow_up ?? "说说你做了什么？" }]);
          setDrillDone(false);
        }
        await refresh();
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    })();
  }, [drillRound, drillDirection, drillFocusProjectId, refresh]);

  const onDrillAnswer = useCallback(() => {
    if (!activeDrillSession || !drillAnswer.trim() || drillDone) return;
    const userText = drillAnswer.trim();
    setDrillChat((prev) => [...prev, { role: "user", text: userText }]);
    setDrillAnswer("");
    void (async () => {
      setBusy(true);
      try {
        const res = await api<DrillSessionContinueResponse>(
          `/v1/drill/sessions/${activeDrillSession.id}`,
          { method: "POST", body: JSON.stringify({ answer: userText }) },
        );
        const v = res.verdict;
        if (v.done) {
          const gaps = v.gaps.length ? `\n缺口：${v.gaps.join("；")}` : "";
          setDrillChat((prev) => [
            ...prev,
            { role: "examiner", text: `深挖结束（深度 ${v.depth_reached}）${gaps}` },
          ]);
          setDrillDone(true);
        } else {
          setDrillChat((prev) => [
            ...prev,
            { role: "examiner", text: v.follow_up ?? "继续说？" },
          ]);
        }
        await refresh();
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    })();
  }, [activeDrillSession, drillAnswer, drillDone, refresh]);

  const onSelectDrillSession = useCallback((s: DrillSession) => {
    setActiveDrillSession(s);
    setDrillChat(s.messages.map((m) => ({ role: m.role, text: m.text })));
    setDrillDone(s.status === "done");
    setDrillRound(s.round);
    setDrillDirection(s.direction ?? "");
    setDrillFocusProjectId(s.project_id);
  }, []);

  const onBackToDrillStart = useCallback(() => {
    setActiveDrillSession(null);
    setDrillChat([]);
    setDrillAnswer("");
    setDrillDone(false);
  }, []);

  const value: Store = {
    day,
    setDay,
    plan,
    notes,
    noteScope,
    setNoteScope,
    projects,
    items: items as { id: string; title: string; topic: string | null; status: string }[],
    selectedProjectId,
    setSelectedProjectId,
    selectedProject,
    mode,
    setMode,
    busy,
    setBusy,
    error,
    flash,
    setFlash,
    setError,
    refresh,
    run,
    openMenuId,
    setOpenMenuId,
    viewNote,
    setViewNote,
    onOpenNote,
    onDeleteNote,
    onIngestNote,
    onIngestAll,
    showCompose,
    setShowCompose,
    showProjectModal,
    setShowProjectModal,
    editingProject,
    onOpenEditProject,
    saveProject,
    examineNote,
    examineChat,
    examineAnswer,
    setExamineAnswer,
    examineSessionDone,
    onExamineStart,
    onExamineAnswer,
    teachTopic,
    setTeachTopic,
    teachChat,
    teachAnswer,
    setTeachAnswer,
    teachDone,
    onTeachStart,
    onTeachAnswer,
    drillChat,
    drillAnswer,
    setDrillAnswer,
    drillDone,
    progress,
    resume,
    drillMaterials,
    drillSessions,
    activeDrillSession,
    drillRound,
    setDrillRound,
    drillDirection,
    setDrillDirection,
    drillFocusProjectId,
    setDrillFocusProjectId,
    showResumeModal,
    setShowResumeModal,
    showMaterialModal,
    setShowMaterialModal,
    onUploadResume,
    onApplyResume,
    onUpsertMaterial,
    onDeleteMaterial,
    onDrillStartSession,
    onDrillAnswer,
    onSelectDrillSession,
    onBackToDrillStart,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
