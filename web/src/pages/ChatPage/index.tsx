import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "../../api";
import {
  KarenAvatar,
  PatrickAvatar,
  SandyAvatar,
  SpongeBobAvatar,
  SquidwardAvatar,
} from "../../components/Avatars";
import { Modal } from "../../components/Modal";
import { isMasteryVerdict, VerifyVerdictChip } from "../../components/VerifyVerdict";
import {
  VerifyTrajectory,
  verifyPathFromMeta,
} from "../../components/VerifyTrajectory";
import { DailyBrief } from "../../components/DailyBrief";
import { CalibrationPanel } from "../../components/CalibrationPanel";
import { ModeHeader } from "./ModeHeader";
import { MessageBody } from "./MessageBody";
import {
  CompanionToolTrail,
  toolCallsFromMeta,
} from "./CompanionToolTrail";
import { ActionBlocks, actionBlocksFromMeta } from "./ActionBlocks";
import { BootcampPanel } from "./BootcampPanel";
import { InterviewFocusBrief } from "./InterviewFocusBrief";
import { useResizableWidth } from "../../hooks/useResizableWidth";
import { useStore } from "../../store";
import { fmtDate, parseApiDate } from "../../lib/format";
import { profileInitials, profileTint } from "../../lib/userProfile";
import type {
  AgentIdentity,
  AgentReply,
  ChatMessage,
  Claim,
  DayNote,
  Mode,
  OpenDrillPayload,
  OpenExaminePayload,
  SkillInfo,
  Thread,
} from "../../types";
import { ExaminePage } from "../ExaminePage";
import { TeachPage } from "../TeachPage";
import { DrillPage } from "../DrillPage";
import styles from "./index.module.scss";

const AGENTS = ["axiom", "compass", "echo", "sage", "critic"] as const;
type AgentName = (typeof AGENTS)[number];

/** UI 人格：与考我/回讲/深挖同一套角色，不依赖后端英文 display_name。 */
const AGENT_UI: Record<
  AgentName,
  { label: string; hint: string; avatar: () => ReactNode }
> = {
  axiom: {
    label: "章鱼哥",
    hint: "考官 · 追问，判过了 / 还差点 / 欠着下次",
    avatar: () => <SquidwardAvatar />,
  },
  compass: {
    label: "海绵宝宝",
    hint: "管家 · 从资料抽考点，提醒今天还欠什么",
    avatar: () => <SpongeBobAvatar />,
  },
  echo: {
    label: "派大星",
    hint: "回讲官 · 扮学生听你讲，讲不清就接着问",
    avatar: () => <PatrickAvatar />,
  },
  sage: {
    label: "桑迪",
    hint: "面试官 · 按简历往下挖，指出讲不清的地方",
    avatar: () => <SandyAvatar />,
  },
  critic: {
    label: "凯伦",
    hint: "复核官 · 冷静重看判定，专挑边界和反例",
    avatar: () => <KarenAvatar />,
  },
};

/** 工作流 / 自由聊 → 默认命中的搭子 */
const MODE_AGENT: Record<Mode, AgentName> = {
  chat: "axiom",
  examine: "axiom",
  teach: "echo",
  drill: "sage",
};

const WORKFLOWS: { mode: Exclude<Mode, "chat">; label: string; hint: string }[] = [
  { mode: "examine", label: "考我", hint: "过了 / 还差点 / 欠着" },
  { mode: "teach", label: "回讲", hint: "讲不清他会追问" },
  { mode: "drill", label: "项目深挖", hint: "按简历往下挖" },
];

function agentLabel(name: string | null | undefined) {
  if (!name) return "你";
  return AGENT_UI[name as AgentName]?.label ?? name;
}

function agentAvatar(name: string | null | undefined) {
  if (!name) return "你";
  const ui = AGENT_UI[name as AgentName];
  return ui ? ui.avatar() : name.slice(0, 1).toUpperCase();
}

function isAgentName(name: string | null | undefined): name is AgentName {
  return !!name && (AGENTS as readonly string[]).includes(name);
}

/** `@query` at caret — sticky mention accelerator, not message syntax. */
function mentionQueryAt(
  text: string,
  caret: number,
): { start: number; query: string } | null {
  const before = text.slice(0, caret);
  const m = before.match(/(?:^|[\s\n])@([^\s@]*)$/);
  if (!m) return null;
  const query = m[1] ?? "";
  const start = before.length - query.length - 1;
  return { start, query };
}

function filterAgentsByQuery(query: string): AgentName[] {
  const q = query.trim().toLowerCase();
  if (!q) return [...AGENTS];
  return AGENTS.filter((a) => {
    const label = AGENT_UI[a].label;
    return (
      a.toLowerCase().includes(q) ||
      label.toLowerCase().includes(q) ||
      label.includes(query.trim())
    );
  });
}

/** 当前对话里最后聊过的搭子：优先最后一条 agent 气泡，否则用户最后 @ 的。 */
function lastChatAgent(ms: ChatMessage[]): AgentName | null {
  for (let i = ms.length - 1; i >= 0; i -= 1) {
    const m = ms[i];
    if (m.role === "agent" && isAgentName(m.agent_name)) return m.agent_name;
  }
  for (let i = ms.length - 1; i >= 0; i -= 1) {
    const hit = ms[i].mentions?.find(isAgentName);
    if (hit) return hit;
  }
  return null;
}

function fmtTime(iso: string) {
  const d = parseApiDate(iso);
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Quiet message clock: today → HH:mm; else → MM-DD HH:mm (browser local tz). */
function fmtMsgTime(iso: string) {
  const d = parseApiDate(iso);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  if (sameDay) {
    return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
  }
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function messageThinking(m: ChatMessage): string | null {
  const raw = m.metadata?.thinking;
  if (typeof raw !== "string") return null;
  const text = raw.trim();
  if (!text) return null;
  // Stub / noise — don't surface a thinking chrome chip.
  if (text.startsWith("（桩）") || text.startsWith("(桩)")) return null;
  if (text.length < 12) return null;
  return text;
}

/** Drop consecutive identical agent bubbles (same speaker + text). */
function collapseDuplicateAgentReplies(ms: ChatMessage[]): ChatMessage[] {
  const out: ChatMessage[] = [];
  for (const m of ms) {
    const prev = out[out.length - 1];
    if (
      prev &&
      m.role === "agent" &&
      prev.role === "agent" &&
      m.agent_name === prev.agent_name &&
      m.text.trim() === prev.text.trim()
    ) {
      continue;
    }
    out.push(m);
  }
  return out;
}

function formatChatError(e: unknown): string {
  const raw = String(e).replace(/^Error:\s*/, "");
  const jsonMatch = raw.match(/\{[\s\S]*\}/);
  if (jsonMatch) {
    try {
      const parsed = JSON.parse(jsonMatch[0]) as { detail?: unknown };
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        return parsed.detail.trim();
      }
    } catch {
      /* keep raw */
    }
  }
  return raw.trim() || "发送失败，请再试一次。";
}

const WORKFLOW_BADGE: Record<string, string> = {
  examine: "考我",
  teach: "回讲",
  drill: "深挖",
};

function messageWorkflowBadge(m: ChatMessage): string | null {
  const raw = m.metadata?.workflow;
  if (typeof raw !== "string") return null;
  return WORKFLOW_BADGE[raw] ?? raw;
}

function messageExamineVerdict(m: ChatMessage): {
  verdict: "passed" | "almost" | "owe_next";
  sessionDone: boolean;
} | null {
  if (m.role !== "agent") return null;
  const wf = m.metadata?.workflow;
  if (wf !== "examine" && wf !== "teach") return null;
  if (m.metadata?.step === "answer") return null;
  if (!isMasteryVerdict(m.metadata?.verdict)) return null;
  return {
    verdict: m.metadata.verdict,
    sessionDone: Boolean(m.metadata?.session_done),
  };
}

function ThinkingBlock({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={styles.thinking}>
      <button
        type="button"
        className={styles.thinkingToggle}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className={styles.thinkingIcon} aria-hidden />
        {open ? "收起思考" : "思考过程"}
      </button>
      {open ? <div className={styles.thinkingBody}>{text}</div> : null}
    </div>
  );
}

export function ChatPage() {
  const {
    width: navWidth,
    dragging: navDragging,
    onResizePointerDown,
  } = useResizableWidth({
    storageKey: "gotit.navRailWidth",
    defaultWidth: 260,
    min: 200,
    max: 420,
  });

  const {
    mode,
    setMode,
    notes,
    day,
    setDay,
    busy: storeBusy,
    libraryOpen,
    setLibraryOpen,
    masteryGraphOpen,
    setMasteryGraphOpen,
    setSettingsOpen,
    userProfile,
    setWorkflowThreadId,
    onExamineStart,
    onExamineStartClaim,
    onDrillStartWithPayload,
    dueClaims,
    items,
    refresh,
    dayClosed,
    closeSuggested,
    closeSummary,
    closeToday,
    interviewFocus,
    bootcamp,
    setBootcampStatus,
    pendingExamineClaim,
    clearPendingExamineClaim,
  } = useStore();
  const examineCount = notes.filter((n) => n.claim_ids.length > 0).length;
  const showBootcamp = Boolean(bootcamp?.show);
  const hasDailyBrief =
    !dayClosed &&
    !showBootcamp &&
    (dueClaims.length > 0 ||
      items.some((i) => i.status !== "verified" && i.claim_id) ||
      notes.some((n) => n.claim_ids.length > 0));
  const showInterviewFocus = Boolean(interviewFocus) && !showBootcamp;
  const showFeaturedInterview =
    showInterviewFocus &&
    !dayClosed &&
    interviewFocus?.prominence === "featured";
  const showQuietInterview =
    showInterviewFocus &&
    !dayClosed &&
    interviewFocus?.prominence === "quiet";
  /** Cold-start CTA when nothing owed yet but claims exist to probe. */
  const showCalibrateCta =
    !dayClosed && !showBootcamp && dueClaims.length === 0 && examineCount > 0;
  /** Soft-hide close during first-pass bootcamp (design: Bootcamp 日不强调收工). */
  const showCloseCta = !dayClosed && !showBootcamp;
  const inWorkflow = mode !== "chat";

  const [calibrationOpen, setCalibrationOpen] = useState(false);
  const [closingDay, setClosingDay] = useState(false);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [threadsReady, setThreadsReady] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [mention, setMention] = useState<AgentName>(MODE_AGENT[mode]);
  const [skills, setSkills] = useState<string[]>([]);
  const [activeSkill, setActiveSkill] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [pendingDelete, setPendingDelete] = useState<Thread | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [compactNav, setCompactNav] = useState(false);
  const [showToTop, setShowToTop] = useState(false);
  const [atMenu, setAtMenu] = useState<{ start: number; query: string } | null>(
    null,
  );
  const [atHi, setAtHi] = useState(0);
  const streamRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const toolsRef = useRef<HTMLDivElement>(null);
  const atSuppressedRef = useRef(false);
  const atMatches = atMenu ? filterAgentsByQuery(atMenu.query) : [];

  useEffect(() => {
    if (!toolsOpen) return;
    const onPointer = (e: MouseEvent | PointerEvent) => {
      if (toolsRef.current?.contains(e.target as Node)) return;
      setToolsOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setToolsOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [toolsOpen]);

  const syncAtMenu = useCallback((text: string, caret: number) => {
    const hit = mentionQueryAt(text, caret);
    if (!hit) {
      atSuppressedRef.current = false;
      setAtMenu(null);
      return;
    }
    if (atSuppressedRef.current) {
      setAtMenu(null);
      return;
    }
    setAtMenu((prev) => {
      if (prev?.start === hit.start && prev?.query === hit.query) return prev;
      return hit;
    });
  }, []);

  useEffect(() => {
    setAtHi(0);
  }, [atMenu?.start, atMenu?.query]);

  useEffect(() => {
    if (atMatches.length > 0 && atHi >= atMatches.length) setAtHi(0);
  }, [atMatches.length, atHi]);

  const pickAtAgent = useCallback(
    (a: AgentName) => {
      if (!atMenu) return;
      const end = atMenu.start + 1 + atMenu.query.length;
      const before = draft.slice(0, atMenu.start);
      const after = draft.slice(end);
      const next = before + after;
      setDraft(next);
      setMention(a);
      setAtMenu(null);
      atSuppressedRef.current = false;
      setToolsOpen(false);
      requestAnimationFrame(() => {
        const el = textareaRef.current;
        if (!el) return;
        el.focus();
        const pos = before.length;
        el.setSelectionRange(pos, pos);
      });
    },
    [atMenu, draft],
  );

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 820px)");
    const apply = () => setCompactNav(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  useEffect(() => {
    // 工作流有固定默认搭子；回到 chat 时由 loadMessages 按历史恢复。
    if (mode !== "chat") setMention(MODE_AGENT[mode]);
  }, [mode]);

  const startWorkflow = useCallback(
    async (next: Exclude<Mode, "chat">) => {
      let tid = activeId;
      if (!tid) {
        try {
          const t = await api<Thread>("/v1/threads", {
            method: "POST",
            body: JSON.stringify({ title: "学习会话", kind: "chat" }),
          });
          setThreads((prev) => [t, ...prev]);
          setActiveId(t.id);
          tid = t.id;
        } catch (e) {
          setErr(String(e));
          return;
        }
      }
      setWorkflowThreadId(tid);
      setMode(next);
      return tid;
    },
    [activeId, setMode, setWorkflowThreadId],
  );

  const startExamineClaim = useCallback(
    async (claim: Claim) => {
      const tid = await startWorkflow("examine");
      if (!tid) return;
      onExamineStartClaim(claim);
    },
    [startWorkflow, onExamineStartClaim],
  );

  // Note ingest「去开考」handoff from compose / view-note modals.
  useEffect(() => {
    if (!pendingExamineClaim) return;
    const claim = pendingExamineClaim;
    clearPendingExamineClaim();
    setLibraryOpen(false);
    void startExamineClaim(claim);
  }, [
    pendingExamineClaim,
    clearPendingExamineClaim,
    setLibraryOpen,
    startExamineClaim,
  ]);

  const startExamineNote = useCallback(
    async (noteId: string, fallback?: Partial<DayNote>) => {
      const tid = await startWorkflow("examine");
      if (!tid) return;
      const found = notes.find((n) => n.id === noteId);
      const note: DayNote = found ?? {
        id: noteId,
        title: fallback?.title ?? null,
        body: fallback?.body ?? "",
        excerpt: fallback?.excerpt ?? "",
        tags: fallback?.tags ?? [],
        claim_ids: fallback?.claim_ids ?? [],
        created_at: fallback?.created_at ?? "",
        day: fallback?.day ?? null,
      };
      onExamineStart(note);
    },
    [startWorkflow, notes, onExamineStart],
  );

  const onCloseDay = useCallback(async () => {
    if (closingDay || dayClosed) return;
    setClosingDay(true);
    try {
      await closeToday();
    } catch (e) {
      setErr(String(e));
    } finally {
      setClosingDay(false);
    }
  }, [closingDay, dayClosed, closeToday]);

  const quietContinuePractice = useCallback(() => {
    void startWorkflow("examine");
  }, [startWorkflow]);

  const followOpenExamine = useCallback(
    (payload: OpenExaminePayload) => {
      if (payload.claim_id) {
        const found = dueClaims.find((c) => c.id === payload.claim_id);
        const claim: Claim = found ?? {
          id: payload.claim_id,
          text: (payload.claim_text || "开考").trim() || "开考",
          status: "in_progress",
          topic: payload.topic ?? null,
          source_note_id: null,
          next_review_at: null,
        };
        void startExamineClaim(claim);
        return;
      }
      if (payload.note_id) {
        void startExamineNote(payload.note_id, {
          title: payload.note_title ?? null,
          claim_ids: payload.claim_ids ?? [],
        });
      }
    },
    [dueClaims, startExamineClaim, startExamineNote],
  );

  const followOpenDrill = useCallback(
    (payload: OpenDrillPayload) => {
      void (async () => {
        const tid = await startWorkflow("drill");
        if (!tid) return;
        onDrillStartWithPayload({
          round: payload.round,
          direction: payload.direction,
          project_id: payload.project_id ?? null,
          thread_id: tid,
        });
      })();
    },
    [startWorkflow, onDrillStartWithPayload],
  );

  const openThread = useCallback(
    (id: string) => {
      setMode("chat");
      setActiveId(id);
    },
    [setMode],
  );

  const loadThreads = useCallback(async () => {
    try {
      const ts = await api<Thread[]>("/v1/threads");
      setThreads(ts);
      setActiveId((prev) => prev ?? ts[0]?.id ?? null);
    } catch (e) {
      setErr(String(e));
    } finally {
      setThreadsReady(true);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        await api<AgentIdentity[]>("/v1/identities/seed", { method: "POST" });
        const sk = await api<SkillInfo[]>("/v1/skills");
        setSkills(sk.filter((s) => s.enabled).map((s) => s.name));
      } catch (e) {
        setErr(String(e));
      }
      await loadThreads();
    })();
  }, [loadThreads]);

  const loadMessages = useCallback(async (id: string) => {
    try {
      const ms = await api<ChatMessage[]>(`/v1/threads/${id}/messages`);
      setMessages(ms);
      const last = lastChatAgent(ms);
      if (last) setMention(last);
      else setMention(MODE_AGENT.chat);
    } catch (e) {
      setErr(String(e));
    }
  }, []);

  useEffect(() => {
    if (activeId && mode === "chat") void loadMessages(activeId);
    if (!activeId) setMessages([]);
  }, [activeId, loadMessages, mode]);

  useEffect(() => {
    streamRef.current?.scrollTo({ top: streamRef.current.scrollHeight });
  }, [messages, busy]);

  useEffect(() => {
    const el = streamRef.current;
    if (!el) {
      setShowToTop(false);
      return;
    }
    const onScroll = () => {
      setShowToTop(el.scrollTop > 280);
    };
    onScroll();
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [activeId, messages.length]);

  const scrollStreamToTop = useCallback(() => {
    streamRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "0px";
    const next = Math.min(Math.max(el.scrollHeight, 68), 160);
    el.style.height = `${next}px`;
  }, [draft]);

  const createThread = useCallback(async () => {
    try {
      const t = await api<Thread>("/v1/threads", {
        method: "POST",
        body: JSON.stringify({ title: "新对话", kind: "chat" }),
      });
      setThreads((prev) => [t, ...prev]);
      setMode("chat");
      setActiveId(t.id);
      setMessages([]);
      setMention(MODE_AGENT.chat);
      setErr("");
    } catch (e) {
      setErr(String(e));
    }
  }, [setMode]);

  const confirmDeleteThread = useCallback(async () => {
    if (!pendingDelete || deleting) return;
    const id = pendingDelete.id;
    setDeleting(true);
    try {
      await api<{ ok: boolean }>(`/v1/threads/${id}`, { method: "DELETE" });
      setThreads((prev) => {
        const next = prev.filter((t) => t.id !== id);
        if (activeId === id) {
          setActiveId(next[0]?.id ?? null);
          setMessages([]);
        }
        return next;
      });
      setPendingDelete(null);
    } catch (e) {
      setErr(String(e));
    } finally {
      setDeleting(false);
    }
  }, [pendingDelete, deleting, activeId]);

  const send = useCallback(async () => {
    if (!activeId || busy) return;
    // 以 textarea 实值为准，避免 keydown 闭包拿到过期 draft
    const text = (textareaRef.current?.value ?? draft).trim();
    if (!text) return;
    const reqSkills = activeSkill ? [activeSkill] : [];
    const localId = `local-${Date.now()}`;
    const optimistic: ChatMessage = {
      id: localId,
      thread_id: activeId,
      agent_name: null,
      role: "user",
      text,
      mentions: [mention],
      metadata: {},
      created_at: new Date().toISOString(),
    };
    setDraft("");
    setAtMenu(null);
    atSuppressedRef.current = false;
    setErr("");
    setBusy(true);
    setMessages((prev) => [...prev, optimistic]);
    try {
      const res = await api<AgentReply>(`/v1/threads/${activeId}/messages`, {
        method: "POST",
        body: JSON.stringify({ text, mentions: [mention], skills: reqSkills }),
      });
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== localId),
        res.user_message,
        ...res.agent_messages,
      ]);
      if (res.thread) {
        const updated = res.thread;
        setThreads((prev) => {
          const rest = prev.filter((t) => t.id !== updated.id);
          return [updated, ...rest];
        });
      }
    } catch (e) {
      // Keep the optimistic user bubble; show failure as an agent reply (no draft restore).
      const errMsg: ChatMessage = {
        id: `local-err-${Date.now()}`,
        thread_id: activeId,
        agent_name: mention,
        role: "agent",
        text: formatChatError(e),
        mentions: [],
        metadata: { error: true },
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setBusy(false);
    }
  }, [activeId, draft, busy, mention, activeSkill]);

  return (
    <div className={styles.chatPage}>
      <aside
        className={`${styles.navRail} ${navDragging ? styles.navRailDragging : ""} ${compactNav ? styles.navRailCompact : ""}`}
        style={compactNav ? undefined : { width: navWidth }}
      >
        {!compactNav ? (
          <button
            type="button"
            className={styles.navResizeHandle}
            aria-label="拖拽调整侧边栏宽度"
            title="拖拽调整宽度"
            onPointerDown={onResizePointerDown}
          />
        ) : null}
        <div className={styles.navBrand}>
          <div className={styles.brandRow}>
            <div className={styles.brand}>
              <img className={styles.brandIcon} src="/icon.png" alt="" width={28} height={28} />
              <span className={styles.brandText}>GOTIT</span>
            </div>
            <label className={styles.dayPicker}>
              <input
                type="date"
                value={day}
                onChange={(e) => setDay(e.target.value)}
                disabled={storeBusy}
              />
              <span className={styles.dayLabel}>{fmtDate(day)}</span>
            </label>
          </div>
          <button
            type="button"
            className={`${styles.libraryBtn} ${libraryOpen ? styles.libraryBtnActive : ""}`}
            onClick={() => setLibraryOpen(!libraryOpen)}
            aria-expanded={libraryOpen}
            title={libraryOpen ? "收起资料库" : "打开资料库"}
          >
            <span className={styles.libraryBtnLabel}>资料库</span>
            {notes.length > 0 ? (
              <span className={styles.libraryBtnCount}>{notes.length}</span>
            ) : null}
            <span className={styles.libraryBtnChevron} aria-hidden>
              {libraryOpen ? "‹" : "›"}
            </span>
          </button>
        </div>

        <div className={styles.threadHead}>
          <span className={styles.threadHeadTitle}>对话</span>
          <button
            type="button"
            className={styles.newThreadBtn}
            onClick={() => void createThread()}
            title="新对话"
            aria-label="新对话"
          >
            <span className={styles.newThreadLabel}>+ 新对话</span>
            <span className={styles.newThreadIcon} aria-hidden>
              +
            </span>
          </button>
        </div>

        <div className={styles.threadItems}>
          {threads.map((t) => (
            <div
              key={t.id}
              className={`${styles.threadItemRow} ${!inWorkflow && activeId === t.id ? styles.threadItemActive : ""}`}
            >
              <button
                type="button"
                className={styles.threadItem}
                onClick={() => openThread(t.id)}
                title={t.title}
              >
                <span className={styles.threadItemTitle}>{t.title}</span>
                <span className={styles.threadItemSub}>{fmtTime(t.updated_at)}</span>
              </button>
              <button
                type="button"
                className={styles.threadDelete}
                title="删除对话"
                aria-label={`删除 ${t.title}`}
                onClick={(e) => {
                  e.stopPropagation();
                  setPendingDelete(t);
                }}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </aside>

      <section className={styles.conversation}>
        <header
          className={`${styles.conversationTop} ${
            inWorkflow ? "" : styles.conversationTopSparse
          }`}
        >
          {inWorkflow ? (
            <div className={styles.conversationTopLead}>
              <ModeHeader mode={mode} onBack={() => setMode("chat")} />
            </div>
          ) : null}
          <div className={styles.topActions}>
            <button
              type="button"
              className={`${styles.graphTopBtn} ${masteryGraphOpen ? styles.graphTopBtnActive : ""}`}
              onClick={() => {
                setLibraryOpen(false);
                setMasteryGraphOpen(true);
              }}
              aria-pressed={masteryGraphOpen}
              title="打开弱点图谱"
            >
              弱点图谱
            </button>
            <button
              type="button"
              className={styles.accountBtn}
              onClick={() => setSettingsOpen(true)}
              title="设置"
              aria-label={`打开设置 · ${userProfile.name}`}
            >
              <span
                className={styles.profileAvatar}
                style={
                  userProfile.avatar
                    ? undefined
                    : { background: profileTint(userProfile.name) }
                }
              >
                {userProfile.avatar ? (
                  <img src={userProfile.avatar} alt="" />
                ) : (
                  profileInitials(userProfile.name)
                )}
              </span>
              <span className={styles.profileName}>{userProfile.name}</span>
              <svg className={styles.accountGear} viewBox="0 0 24 24" fill="none" aria-hidden>
                <path
                  d="M12 8.75a3.25 3.25 0 1 1 0 6.5 3.25 3.25 0 0 1 0-6.5Z"
                  stroke="currentColor"
                  strokeWidth="1.5"
                />
                <path
                  d="M19.04 13.12a1.2 1.2 0 0 0 .24 1.32l.04.04a1.75 1.75 0 0 1-2.48 2.48l-.04-.04a1.2 1.2 0 0 0-1.32-.24 1.2 1.2 0 0 0-.72 1.1v.06a1.75 1.75 0 0 1-3.5 0v-.06a1.2 1.2 0 0 0-.78-1.1 1.2 1.2 0 0 0-1.32.24l-.04.04a1.75 1.75 0 1 1-2.48-2.48l.04-.04a1.2 1.2 0 0 0 .24-1.32 1.2 1.2 0 0 0-1.1-.72h-.06a1.75 1.75 0 0 1 0-3.5h.06a1.2 1.2 0 0 0 1.1-.78 1.2 1.2 0 0 0-.24-1.32l-.04-.04a1.75 1.75 0 1 1 2.48-2.48l.04.04a1.2 1.2 0 0 0 1.32.24h.06a1.2 1.2 0 0 0 .72-1.1v-.06a1.75 1.75 0 0 1 3.5 0v.06a1.2 1.2 0 0 0 .72 1.1 1.2 1.2 0 0 0 1.32-.24l.04-.04a1.75 1.75 0 1 1 2.48 2.48l-.04.04a1.2 1.2 0 0 0-.24 1.32v.06c.2.45.66.72 1.1.72h.06a1.75 1.75 0 0 1 0 3.5h-.06a1.2 1.2 0 0 0-1.1.72Z"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </div>
        </header>

        {inWorkflow ? (
          <div className={styles.workflowPane}>
            <div className={styles.workflowPaneBody}>
              {mode === "examine" ? <ExaminePage /> : null}
              {mode === "teach" ? <TeachPage /> : null}
              {mode === "drill" ? <DrillPage /> : null}
            </div>
          </div>
        ) : !threadsReady ? (
          <div className={styles.empty}>
            <p className={styles.emptyHint}>加载中…</p>
          </div>
        ) : !activeId ? (
          <div className={styles.empty}>
            <div className={styles.emptyStack}>
              <div className={styles.emptyCrew} aria-hidden>
                {AGENTS.map((a) => (
                  <span key={a} className={styles.emptyCrewAvatar} title={AGENT_UI[a].label}>
                    {AGENT_UI[a].avatar()}
                  </span>
                ))}
              </div>
              {showFeaturedInterview && interviewFocus ? (
                <InterviewFocusBrief
                  focus={interviewFocus}
                  busy={busy || storeBusy}
                  onOpenDrill={followOpenDrill}
                />
              ) : null}
              {showBootcamp && bootcamp ? (
                <BootcampPanel
                  bootcamp={bootcamp}
                  day={day}
                  busy={busy || storeBusy}
                  onStatus={setBootcampStatus}
                  onRefresh={refresh}
                  onOpenExamine={followOpenExamine}
                  onCalibrate={() => setCalibrationOpen(true)}
                />
              ) : hasDailyBrief ? (
                <div className={styles.briefStage}>
                  <DailyBrief
                    variant="home"
                    maxItems={4}
                    onExamineClaim={(c) => void startExamineClaim(c)}
                    onExamineNoteId={(id) => void startExamineNote(id)}
                    onViewAll={() => void startWorkflow("examine")}
                  />
                  <footer className={styles.briefFooter}>
                    {showCloseCta ? (
                      <button
                        type="button"
                        className={styles.briefClose}
                        disabled={closingDay || storeBusy}
                        onClick={() => void onCloseDay()}
                      >
                        今天收工
                      </button>
                    ) : null}
                    <nav className={styles.briefAltNav} aria-label="开练方式">
                      {WORKFLOWS.map((w) => (
                        <button
                          key={w.mode}
                          type="button"
                          className={styles.briefAltChip}
                          onClick={() => void startWorkflow(w.mode)}
                          title={w.hint}
                        >
                          {w.label}
                        </button>
                      ))}
                    </nav>
                  </footer>
                </div>
              ) : dayClosed ? (
                <div className={styles.emptyIntro}>
                  <p className={styles.emptyLead}>今天收工了</p>
                  <p className={styles.emptyHint}>
                    {closeSummary?.note?.trim() || "还想练随时可以继续"}
                  </p>
                  <button
                    type="button"
                    className={styles.emptyChatLink}
                    onClick={quietContinuePractice}
                  >
                    继续练
                  </button>
                  {interviewFocus ? (
                    <InterviewFocusBrief
                      focus={interviewFocus}
                      busy={busy || storeBusy}
                      quiet
                      onOpenDrill={followOpenDrill}
                    />
                  ) : null}
                </div>
              ) : showInterviewFocus ? null : (
                <div className={styles.emptyIntro}>
                  <p className={styles.emptyLead}>今天暂时没事</p>
                  <p className={styles.emptyHint}>
                    把笔记出成题，或先找搭子聊几句
                  </p>
                  <div className={styles.emptyWorkflows}>
                    {WORKFLOWS.map((w) => (
                      <button
                        key={w.mode}
                        type="button"
                        className={styles.emptyWorkflowChip}
                        onClick={() => void startWorkflow(w.mode)}
                        title={w.hint}
                      >
                        {w.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {showQuietInterview && interviewFocus ? (
                <InterviewFocusBrief
                  focus={interviewFocus}
                  busy={busy || storeBusy}
                  onOpenDrill={followOpenDrill}
                />
              ) : null}
              {showCalibrateCta ? (
                <button
                  type="button"
                  className={styles.emptyCalibrate}
                  onClick={() => setCalibrationOpen(true)}
                >
                  先摸底一下
                </button>
              ) : null}
              {!hasDailyBrief && showCloseCta ? (
                <button
                  type="button"
                  className={
                    closeSuggested ? styles.emptyCalibrate : styles.emptyChatLink
                  }
                  disabled={closingDay || storeBusy}
                  onClick={() => void onCloseDay()}
                >
                  今天收工
                </button>
              ) : null}
              <button
                type="button"
                className={styles.emptyChatLink}
                onClick={() => void createThread()}
              >
                开新对话
              </button>
            </div>
          </div>
        ) : (
          <div className={styles.chatMain}>
            <div className={styles.stream} ref={streamRef}>
              <div className={styles.streamInner}>
                {collapseDuplicateAgentReplies(messages).map((m) => {
                  const isUser = m.role === "user";
                  const thinking = !isUser ? messageThinking(m) : null;
                  const wfBadge = messageWorkflowBadge(m);
                  const examineVerdict = !isUser ? messageExamineVerdict(m) : null;
                  const toolCalls = !isUser ? toolCallsFromMeta(m.metadata) : null;
                  const actionBlocks = !isUser
                    ? actionBlocksFromMeta(m.metadata)
                    : null;
                  const hasVerdictBlock = Boolean(
                    actionBlocks?.some((b) => b.type === "verdict"),
                  );
                  const isError = Boolean(m.metadata?.error);
                  const timeLabel = fmtMsgTime(m.created_at);
                  return (
                    <div
                      key={m.id}
                      className={`${styles.bubbleRow} ${isUser ? styles.bubbleRowUser : ""}`}
                    >
                      {isUser ? (
                        <div
                          className={`${styles.avatar} ${styles.avatarUser}`}
                          style={
                            userProfile.avatar
                              ? undefined
                              : {
                                  background: profileTint(userProfile.name),
                                  color: "var(--ink)",
                                }
                          }
                          title={userProfile.name}
                        >
                          {userProfile.avatar ? (
                            <img src={userProfile.avatar} alt="" />
                          ) : (
                            profileInitials(userProfile.name)
                          )}
                        </div>
                      ) : (
                        <div className={styles.avatar}>{agentAvatar(m.agent_name)}</div>
                      )}
                      <div
                        className={`${styles.bubbleCol} ${isUser ? styles.bubbleColUser : ""}`}
                      >
                        <div
                          className={`${styles.bubbleMeta} ${isUser ? styles.bubbleMetaUser : ""}`}
                        >
                          <span className={styles.bubbleName}>
                            {isUser ? userProfile.name : agentLabel(m.agent_name)}
                          </span>
                          {wfBadge ? (
                            <span className={styles.workflowBadge}>{wfBadge}</span>
                          ) : null}
                          {timeLabel ? (
                            <span className={styles.bubbleTime}>{timeLabel}</span>
                          ) : null}
                        </div>
                        {thinking ? <ThinkingBlock text={thinking} /> : null}
                          <div
                            className={`${styles.bubble} ${isUser ? styles.bubbleUser : ""} ${isError ? styles.bubbleError : ""}`}
                          >
                            <MessageBody text={m.text} markdown={!isUser && !isError} />
                          </div>
                        {toolCalls ? (
                          <CompanionToolTrail
                            calls={toolCalls}
                            busy={busy || storeBusy}
                            onOpenExamine={followOpenExamine}
                            onOpenDrill={followOpenDrill}
                          />
                        ) : null}
                        {actionBlocks ? (
                          <ActionBlocks
                            blocks={actionBlocks}
                            busy={busy || storeBusy}
                            onOpenExamine={followOpenExamine}
                            onOpenDrill={followOpenDrill}
                          />
                        ) : null}
                        {examineVerdict && !hasVerdictBlock ? (
                          <VerifyVerdictChip
                            verdict={examineVerdict.verdict}
                            sessionDone={examineVerdict.sessionDone}
                          />
                        ) : null}
                        {!isUser && verifyPathFromMeta(m.metadata) ? (
                          <VerifyTrajectory path={verifyPathFromMeta(m.metadata)!} />
                        ) : null}
                        {!isUser && (m.metadata as { handoff_to?: string }).handoff_to ? (
                          <div className={styles.handoffBadge}>
                            → 转给 {agentLabel((m.metadata as { handoff_to?: string }).handoff_to)}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
                {busy ? (
                  <div className={styles.bubbleRow}>
                    <div className={styles.avatar}>{agentAvatar(mention)}</div>
                    <div className={styles.bubbleCol}>
                      <div className={styles.bubbleName}>{agentLabel(mention)}</div>
                      <div className={styles.thinkingPending} aria-live="polite">
                        <span className={styles.thinkingPulse} aria-hidden />
                        <span className={styles.thinkingLabel}>
                          思考中
                          <span className={styles.thinkingDots} aria-hidden>
                            <span>.</span>
                            <span>.</span>
                            <span>.</span>
                          </span>
                        </span>
                      </div>
                    </div>
                  </div>
                ) : null}
                {!busy && messages.length === 0 ? (
                  <div
                    className={`${styles.threadEmpty} ${hasDailyBrief || dayClosed || showInterviewFocus || showBootcamp ? styles.threadEmptyBrief : ""}`}
                  >
                    {showFeaturedInterview && interviewFocus ? (
                      <InterviewFocusBrief
                        focus={interviewFocus}
                        busy={busy || storeBusy}
                        onOpenDrill={followOpenDrill}
                      />
                    ) : null}
                    {showBootcamp && bootcamp ? (
                      <BootcampPanel
                        bootcamp={bootcamp}
                        day={day}
                        busy={busy || storeBusy}
                        onStatus={setBootcampStatus}
                        onRefresh={refresh}
                        onOpenExamine={followOpenExamine}
                        onCalibrate={() => setCalibrationOpen(true)}
                      />
                    ) : hasDailyBrief ? (
                      <div className={styles.briefStage}>
                        <DailyBrief
                          variant="thread"
                          maxItems={4}
                          onExamineClaim={(c) => void startExamineClaim(c)}
                          onExamineNoteId={(id) => void startExamineNote(id)}
                          onViewAll={() => void startWorkflow("examine")}
                        />
                        {showQuietInterview && interviewFocus ? (
                          <InterviewFocusBrief
                            focus={interviewFocus}
                            busy={busy || storeBusy}
                            onOpenDrill={followOpenDrill}
                          />
                        ) : null}
                        <footer className={styles.briefFooter}>
                          {showCloseCta ? (
                            <button
                              type="button"
                              className={styles.briefClose}
                              disabled={closingDay || storeBusy}
                              onClick={() => void onCloseDay()}
                            >
                              今天收工
                            </button>
                          ) : null}
                          <nav className={styles.briefAltNav} aria-label="开练方式">
                            {WORKFLOWS.map((w) => (
                              <button
                                key={w.mode}
                                type="button"
                                className={styles.briefAltChip}
                                onClick={() => void startWorkflow(w.mode)}
                                title={w.hint}
                              >
                                {w.label}
                              </button>
                            ))}
                          </nav>
                        </footer>
                      </div>
                    ) : dayClosed ? (
                      <>
                        <p className={styles.threadEmptyLead}>今天收工了</p>
                        <p className={styles.threadEmptyHint}>
                          {closeSummary?.note?.trim() || "还想练随时可以继续"}
                        </p>
                        <button
                          type="button"
                          className={styles.emptyChatLink}
                          onClick={quietContinuePractice}
                        >
                          继续练
                        </button>
                        {interviewFocus ? (
                          <InterviewFocusBrief
                            focus={interviewFocus}
                            busy={busy || storeBusy}
                            quiet
                            onOpenDrill={followOpenDrill}
                          />
                        ) : null}
                      </>
                    ) : showInterviewFocus ? null : (
                      <>
                        <p className={styles.threadEmptyLead}>想练就挑一种</p>
                        <p className={styles.threadEmptyHint}>也可以直接发消息</p>
                        {showCalibrateCta ? (
                          <button
                            type="button"
                            className={styles.emptyCalibrate}
                            onClick={() => setCalibrationOpen(true)}
                          >
                            先摸底一下
                          </button>
                        ) : null}
                      </>
                    )}
                    {!hasDailyBrief && showQuietInterview && interviewFocus ? (
                      <InterviewFocusBrief
                        focus={interviewFocus}
                        busy={busy || storeBusy}
                        onOpenDrill={followOpenDrill}
                      />
                    ) : null}
                    {!hasDailyBrief && showCloseCta ? (
                      <button
                        type="button"
                        className={
                          closeSuggested ? styles.emptyCalibrate : styles.emptyChatLink
                        }
                        disabled={closingDay || storeBusy}
                        onClick={() => void onCloseDay()}
                      >
                        今天收工
                      </button>
                    ) : null}
                    {!hasDailyBrief && !dayClosed && !showBootcamp ? (
                      <nav className={styles.workflowTabs} aria-label="开练方式">
                        {WORKFLOWS.map((w) => (
                          <button
                            key={w.mode}
                            type="button"
                            className={styles.chatBarTab}
                            onClick={() => void startWorkflow(w.mode)}
                            title={w.hint}
                          >
                            {w.label}
                            {w.mode === "examine" && examineCount > 0 ? (
                              <span className={styles.chatBarCount}>{examineCount}</span>
                            ) : null}
                          </button>
                        ))}
                      </nav>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>

            <div className={styles.composer}>
              <div className={styles.composerInner}>
                {messages.length > 0 ? (
                  <div className={styles.composerWorkflows} role="group" aria-label="开练方式">
                    {WORKFLOWS.map((w) => (
                      <button
                        key={w.mode}
                        type="button"
                        className={styles.composerWorkflowBtn}
                        onClick={() => void startWorkflow(w.mode)}
                        title={w.hint}
                      >
                        {w.label}
                      </button>
                    ))}
                  </div>
                ) : null}
                <div className={styles.composerTools} ref={toolsRef}>
                  {toolsOpen ? (
                    <div className={styles.toolsTray} role="dialog" aria-label="搭子与技能">
                      <div className={styles.mentionSection}>
                        <span className={styles.mentionLabel}>搭子</span>
                        <div className={styles.mentionChips}>
                          {AGENTS.map((a) => (
                            <button
                              key={a}
                              type="button"
                              className={`${styles.mentionChip} ${mention === a ? styles.mentionChipActive : ""}`}
                              onClick={() => setMention(a)}
                              title={AGENT_UI[a].hint}
                            >
                              <span className={styles.mentionChipAvatar}>
                                {AGENT_UI[a].avatar()}
                              </span>
                              <span className={styles.mentionChipName}>
                                {AGENT_UI[a].label}
                              </span>
                            </button>
                          ))}
                        </div>
                      </div>
                      {skills.length > 0 ? (
                        <div className={styles.mentionSection}>
                          <span className={styles.mentionLabel}>技能</span>
                          <div className={styles.mentionChips}>
                            <button
                              type="button"
                              className={`${styles.mentionChip} ${styles.mentionChipPlain} ${
                                activeSkill === null ? styles.mentionChipActive : ""
                              }`}
                              onClick={() => setActiveSkill(null)}
                            >
                              无
                            </button>
                            {skills.map((s) => (
                              <button
                                key={s}
                                type="button"
                                className={`${styles.mentionChip} ${styles.mentionChipPlain} ${
                                  activeSkill === s ? styles.mentionChipActive : ""
                                }`}
                                onClick={() => setActiveSkill(s)}
                              >
                                {s}
                              </button>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  <div className={styles.composerMeta}>
                    <button
                      type="button"
                      className={`${styles.toolsToggle} ${toolsOpen ? styles.toolsToggleOpen : ""}`}
                      aria-expanded={toolsOpen}
                      aria-label={toolsOpen ? "收起搭子与技能" : "选择搭子与技能"}
                      title={toolsOpen ? "收起" : "搭子与技能"}
                      onClick={() => setToolsOpen((v) => !v)}
                    >
                      {toolsOpen ? "−" : "+"}
                    </button>
                    <button
                      type="button"
                      className={styles.composerAgent}
                      onClick={() => setToolsOpen(true)}
                      title={AGENT_UI[mention].hint}
                    >
                      <span className={styles.composerAgentAvatar}>
                        {AGENT_UI[mention].avatar()}
                      </span>
                      <span className={styles.composerAgentName}>
                        {AGENT_UI[mention].label}
                      </span>
                    </button>
                    {activeSkill ? (
                      <button
                        type="button"
                        className={styles.skillChip}
                        onClick={() => setActiveSkill(null)}
                        title="本轮已选技能 · 点击清除"
                        aria-label={`清除技能 ${activeSkill}`}
                      >
                        <span>技能 · {activeSkill}</span>
                        <span className={styles.skillChipClear} aria-hidden>
                          ×
                        </span>
                      </button>
                    ) : null}
                  </div>
                </div>
                <div className={styles.composerField}>
                  {atMenu ? (
                    <div
                      className={styles.atMenu}
                      role="listbox"
                      aria-label="切换搭子"
                    >
                      {atMatches.length === 0 ? (
                        <div className={styles.atMenuEmpty}>没有匹配的搭子</div>
                      ) : (
                        atMatches.map((a, i) => (
                          <button
                            key={a}
                            type="button"
                            role="option"
                            aria-selected={i === atHi}
                            className={`${styles.atMenuItem} ${
                              i === atHi ? styles.atMenuItemActive : ""
                            } ${a === mention ? styles.atMenuItemCurrent : ""}`}
                            onMouseEnter={() => setAtHi(i)}
                            onMouseDown={(e) => {
                              e.preventDefault();
                              pickAtAgent(a);
                            }}
                          >
                            <span className={styles.atMenuAvatar}>
                              {AGENT_UI[a].avatar()}
                            </span>
                            <span className={styles.atMenuText}>
                              <span className={styles.atMenuName}>
                                {AGENT_UI[a].label}
                              </span>
                              <span className={styles.atMenuHint}>
                                {AGENT_UI[a].hint}
                              </span>
                            </span>
                          </button>
                        ))
                      )}
                    </div>
                  ) : null}
                  <textarea
                    ref={textareaRef}
                    className={styles.textarea}
                    value={draft}
                    onChange={(e) => {
                      const v = e.target.value;
                      setDraft(v);
                      syncAtMenu(v, e.target.selectionStart ?? v.length);
                    }}
                    onClick={(e) =>
                      syncAtMenu(draft, e.currentTarget.selectionStart ?? 0)
                    }
                    onKeyUp={(e) => {
                      if (
                        e.key === "ArrowLeft" ||
                        e.key === "ArrowRight" ||
                        e.key === "Home" ||
                        e.key === "End"
                      ) {
                        syncAtMenu(
                          draft,
                          e.currentTarget.selectionStart ?? 0,
                        );
                      }
                    }}
                    placeholder={`和${AGENT_UI[mention].label}聊点什么…（@切换）`}
                    onKeyDown={(e) => {
                      // IME 选词中的 Enter 不应触发发送 / 选人
                      if (e.nativeEvent.isComposing || e.keyCode === 229) {
                        return;
                      }
                      const isEnter =
                        (e.key === "Enter" || e.code === "NumpadEnter") &&
                        !e.shiftKey;
                      if (atMenu) {
                        if (atMatches.length > 0) {
                          if (e.key === "ArrowDown") {
                            e.preventDefault();
                            setAtHi((i) => (i + 1) % atMatches.length);
                            return;
                          }
                          if (e.key === "ArrowUp") {
                            e.preventDefault();
                            setAtHi(
                              (i) =>
                                (i - 1 + atMatches.length) % atMatches.length,
                            );
                            return;
                          }
                          if (e.key === "Enter" || e.key === "Tab") {
                            e.preventDefault();
                            pickAtAgent(atMatches[atHi] ?? atMatches[0]);
                            return;
                          }
                        }
                        if (e.key === "Escape") {
                          e.preventDefault();
                          atSuppressedRef.current = true;
                          setAtMenu(null);
                          return;
                        }
                        // 无匹配的 @query（如 @gmail）：勿吞掉 Enter，关掉菜单并发送
                        if (isEnter) {
                          e.preventDefault();
                          atSuppressedRef.current = true;
                          setAtMenu(null);
                          void send();
                          return;
                        }
                      }
                      if (isEnter) {
                        e.preventDefault();
                        void send();
                      }
                    }}
                    rows={2}
                  />
                  <button
                    type="button"
                    className={styles.sendBtn}
                    disabled={busy || !draft.trim()}
                    onClick={send}
                  >
                    发送
                  </button>
                </div>
                {err ? <span className={styles.sendError}>{err}</span> : null}
              </div>
            </div>

            {showToTop ? (
              <button
                type="button"
                className={styles.toTop}
                onClick={scrollStreamToTop}
                aria-label="回到顶部"
                title="回到顶部"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
                  <path
                    d="M8 12.5V3.5M8 3.5 4 7.5M8 3.5l4 4"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            ) : null}
          </div>
        )}
      </section>

      {pendingDelete ? (
        <Modal
          title="删除对话"
          onClose={() => {
            if (!deleting) setPendingDelete(null);
          }}
          actions={
            <>
              <button
                type="button"
                className="btn-ghost"
                disabled={deleting}
                onClick={() => setPendingDelete(null)}
              >
                取消
              </button>
              <button
                type="button"
                className="btn-ink"
                disabled={deleting}
                onClick={() => void confirmDeleteThread()}
              >
                {deleting ? "删除中…" : "删除"}
              </button>
            </>
          }
        >
          <p className={styles.deleteCopy}>
            确定删除「{pendingDelete.title}」？删除后无法恢复。
          </p>
        </Modal>
      ) : null}

      <CalibrationPanel
        open={calibrationOpen}
        onClose={() => setCalibrationOpen(false)}
        onFinished={() => void refresh()}
      />
    </div>
  );
}
