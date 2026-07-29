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
import { ModeHeader } from "./ModeHeader";
import { useResizableWidth } from "../../hooks/useResizableWidth";
import { useStore } from "../../store";
import { fmtDate } from "../../lib/format";
import { profileInitials, profileTint } from "../../lib/userProfile";
import type { AgentIdentity, AgentReply, ChatMessage, Mode, SkillInfo, Thread } from "../../types";
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
    hint: "考官 · 追问验证，判过了 / 还差点 / 欠着下次",
    avatar: () => <SquidwardAvatar />,
  },
  compass: {
    label: "海绵宝宝",
    hint: "管家 · 从资料里抽考点、排复习、推今日该练什么",
    avatar: () => <SpongeBobAvatar />,
  },
  echo: {
    label: "派大星",
    hint: "回讲官 · 扮不懂的学生听你讲，追问为什么",
    avatar: () => <PatrickAvatar />,
  },
  sage: {
    label: "桑迪",
    hint: "面试官 · 按轮次深挖简历项目，指出讲不清的缝隙",
    avatar: () => <SandyAvatar />,
  },
  critic: {
    label: "凯伦",
    hint: "复核官 · 冷静重审判定，专挑边界情况和反例",
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
  { mode: "examine", label: "考我", hint: "章鱼哥追问验证" },
  { mode: "teach", label: "回讲", hint: "派大星听你讲" },
  { mode: "drill", label: "项目深挖", hint: "桑迪模拟面试" },
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
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function messageThinking(m: ChatMessage): string | null {
  const raw = m.metadata?.thinking;
  return typeof raw === "string" && raw.trim() ? raw : null;
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
        {open ? "收起思考" : "深度思考"}
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
    setSettingsOpen,
    userProfile,
  } = useStore();
  const examineCount = notes.filter((n) => n.claim_ids.length > 0).length;
  const inWorkflow = mode !== "chat";

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
  const streamRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
    (next: Exclude<Mode, "chat">) => {
      setMode(next);
    },
    [setMode],
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
    if (!activeId || !draft.trim() || busy) return;
    const text = draft.trim();
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
      setMessages((prev) => prev.filter((m) => m.id !== localId));
      setDraft(text);
      setErr(String(e));
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
            title={libraryOpen ? "收起资料库" : "打开资料库（项目与今日资料）"}
          >
            <span className={styles.libraryBtnLabel}>
              资料库
              {notes.length > 0 ? ` · ${notes.length}` : ""}
            </span>
            <span className={styles.libraryBtnHint}>
              {libraryOpen ? "收起" : "打开"}
              <span className={styles.libraryBtnChevron} aria-hidden>
                {libraryOpen ? "‹" : "›"}
              </span>
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
          {threads.length === 0 ? (
            <span className={styles.threadItemSub}>还没有对话</span>
          ) : null}
        </div>

        <div className={styles.navFooter}>
          <button
            type="button"
            className={styles.profileBtn}
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
          </button>
          <button
            type="button"
            className={styles.settingsBtn}
            onClick={() => setSettingsOpen(true)}
            title="设置"
            aria-label="打开设置"
          >
            <svg className={styles.settingsIcon} viewBox="0 0 24 24" fill="none" aria-hidden>
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
      </aside>

      <section className={styles.conversation}>
        {inWorkflow ? (
          <div className={styles.workflowPane}>
            <div className={styles.workflowPaneHead}>
              <ModeHeader
                mode={mode}
                onBack={() => setMode("chat")}
                examineCount={examineCount}
              />
            </div>
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
            <div className={styles.emptyCrew} aria-hidden>
              {AGENTS.map((a) => (
                <span key={a} className={styles.emptyCrewAvatar} title={AGENT_UI[a].label}>
                  {AGENT_UI[a].avatar()}
                </span>
              ))}
            </div>
            <p className={styles.emptyLead}>和搭子聊起来</p>
            <p className={styles.emptyHint}>记弱项、排复习，或随时开一场验证</p>
            <button
              type="button"
              className={styles.emptyPrimary}
              onClick={() => void createThread()}
            >
              开新对话
            </button>
            <div className={styles.emptyWorkflows}>
              <span className={styles.emptyWorkflowsLabel}>或直接</span>
              {WORKFLOWS.map((w) => (
                <button
                  key={w.mode}
                  type="button"
                  className={styles.emptyWorkflowLink}
                  onClick={() => startWorkflow(w.mode)}
                  title={w.hint}
                >
                  {w.label}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            <div className={styles.chatBar}>
              {WORKFLOWS.map((w) => (
                <button
                  key={w.mode}
                  type="button"
                  className={styles.chatBarTab}
                  onClick={() => startWorkflow(w.mode)}
                  title={w.hint}
                >
                  {w.label}
                  {w.mode === "examine" && examineCount > 0 ? (
                    <span className={styles.chatBarCount}>{examineCount}</span>
                  ) : null}
                </button>
              ))}
            </div>

            <div className={styles.stream} ref={streamRef}>
              {messages.map((m) => {
                const isUser = m.role === "user";
                const thinking = !isUser ? messageThinking(m) : null;
                return (
                  <div
                    key={m.id}
                    className={`${styles.bubbleRow} ${isUser ? styles.bubbleRowUser : ""}`}
                  >
                    <div className={`${styles.avatar} ${isUser ? styles.avatarUser : ""}`}>
                      {isUser ? "你" : agentAvatar(m.agent_name)}
                    </div>
                    <div className={styles.bubbleCol}>
                      {!isUser ? (
                        <div className={styles.bubbleName}>{agentLabel(m.agent_name)}</div>
                      ) : null}
                      {thinking ? <ThinkingBlock text={thinking} /> : null}
                      <div className={`${styles.bubble} ${isUser ? styles.bubbleUser : ""}`}>
                        {m.text}
                      </div>
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
                      思考中…
                    </div>
                  </div>
                </div>
              ) : null}
              {!busy && messages.length === 0 ? (
                <span className={styles.threadItemSub}>说点什么开始吧。</span>
              ) : null}
            </div>

            <div className={styles.composer}>
              {toolsOpen ? (
                <div className={styles.toolsTray}>
                  <div className={styles.mentionRow}>
                    <span className={styles.mentionLabel}>搭子</span>
                    {AGENTS.map((a) => (
                      <button
                        key={a}
                        type="button"
                        className={`${styles.mentionChip} ${mention === a ? styles.mentionChipActive : ""}`}
                        onClick={() => setMention(a)}
                        data-tip={AGENT_UI[a].hint}
                      >
                        <span className={styles.mentionChipAvatar}>{AGENT_UI[a].avatar()}</span>
                        {AGENT_UI[a].label}
                      </button>
                    ))}
                  </div>
                  {skills.length > 0 ? (
                    <div className={styles.mentionRow}>
                      <span className={styles.mentionLabel}>技能</span>
                      <button
                        type="button"
                        className={`${styles.mentionChip} ${activeSkill === null ? styles.mentionChipActive : ""}`}
                        onClick={() => setActiveSkill(null)}
                      >
                        无
                      </button>
                      {skills.map((s) => (
                        <button
                          key={s}
                          type="button"
                          className={`${styles.mentionChip} ${activeSkill === s ? styles.mentionChipActive : ""}`}
                          onClick={() => setActiveSkill(s)}
                        >
                          {s}
                        </button>
                      ))}
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
                  <span className={styles.composerAgentAvatar}>{AGENT_UI[mention].avatar()}</span>
                  <span className={styles.composerAgentName}>
                    {AGENT_UI[mention].label}
                    {activeSkill ? ` · ${activeSkill}` : ""}
                  </span>
                </button>
              </div>
              <div className={styles.composerField}>
                <textarea
                  ref={textareaRef}
                  className={styles.textarea}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder={`和${AGENT_UI[mention].label}聊点什么…`}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
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
          </>
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
    </div>
  );
}
