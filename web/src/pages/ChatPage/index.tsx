import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "../../api";
import {
  KarenAvatar,
  PatrickAvatar,
  SandyAvatar,
  SpongeBobAvatar,
  SquidwardAvatar,
} from "../../components/Avatars";
import { ModeHeader } from "./ModeHeader";
import { useStore } from "../../store";
import { fmtDate } from "../../lib/format";
import type { AgentIdentity, AgentReply, ChatMessage, Mode, Thread } from "../../types";
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

function fmtTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ChatPage() {
  const {
    mode,
    setMode,
    notes,
    day,
    setDay,
    busy: storeBusy,
    libraryOpen,
    setLibraryOpen,
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
  const streamRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMention(MODE_AGENT[mode]);
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
        const sk = await api<string[]>("/v1/skills");
        setSkills(sk);
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
  }, [messages]);

  const createThread = useCallback(
    async (presetTitle?: string) => {
      const title =
        presetTitle?.trim() ||
        window.prompt("新对话标题", "新的学习对话")?.trim();
      if (!title) return;
      try {
        const t = await api<Thread>("/v1/threads", {
          method: "POST",
          body: JSON.stringify({ title, kind: "chat" }),
        });
        setThreads((prev) => [t, ...prev]);
        setMode("chat");
        setActiveId(t.id);
      } catch (e) {
        setErr(String(e));
      }
    },
    [setMode],
  );

  const send = useCallback(async () => {
    if (!activeId || !draft.trim() || busy) return;
    const text = draft.trim();
    const reqSkills = activeSkill ? [activeSkill] : [];
    setDraft("");
    setBusy(true);
    try {
      const res = await api<AgentReply>(`/v1/threads/${activeId}/messages`, {
        method: "POST",
        body: JSON.stringify({ text, mentions: [mention], skills: reqSkills }),
      });
      setMessages((prev) => [...prev, res.user_message, ...res.agent_messages]);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }, [activeId, draft, busy, mention, activeSkill]);

  return (
    <div className={styles.chatPage}>
      <aside className={styles.navRail}>
        <div className={styles.navBrand}>
          <div className={styles.brandRow}>
            <div className={styles.brand}>
              <svg className={styles.brandIcon} viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="9.25" stroke="currentColor" strokeWidth="1.5" />
                <path
                  d="M7.5 12.3l3 3 6-6.6"
                  stroke="currentColor"
                  strokeWidth="1.9"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <span>gotit</span>
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
              {libraryOpen ? "资料库" : "资料库"}
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

        <div className={styles.workflowRow}>
          {WORKFLOWS.map((w) => (
            <button
              key={w.mode}
              type="button"
              className={`${styles.workflowTab} ${mode === w.mode ? styles.workflowTabActive : ""}`}
              onClick={() => startWorkflow(w.mode)}
              title={w.hint}
            >
              {w.label}
              {w.mode === "examine" && examineCount > 0 ? (
                <span className={styles.workflowTabCount}>{examineCount}</span>
              ) : null}
            </button>
          ))}
        </div>

        <div className={styles.threadHead}>
          <span className={styles.threadHeadTitle}>对话</span>
          <button type="button" className={styles.newThreadBtn} onClick={() => void createThread()}>
            + 新对话
          </button>
        </div>

        <div className={styles.threadItems}>
          {threads.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`${styles.threadItem} ${!inWorkflow && activeId === t.id ? styles.threadItemActive : ""}`}
              onClick={() => openThread(t.id)}
            >
              <span className={styles.threadItemTitle}>{t.title}</span>
              <span className={styles.threadItemSub}>{fmtTime(t.updated_at)}</span>
            </button>
          ))}
          {threads.length === 0 ? (
            <span className={styles.threadItemSub}>还没有对话</span>
          ) : null}
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
              onClick={() => void createThread("新的学习对话")}
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
            <div className={styles.stream} ref={streamRef}>
              {messages.map((m) => {
                const isUser = m.role === "user";
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
              {messages.length === 0 ? (
                <span className={styles.threadItemSub}>说点什么开始吧。</span>
              ) : null}
            </div>

            <div className={styles.composer}>
              <div className={styles.mentionRow}>
                <span className={styles.mentionLabel}>@搭子：</span>
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
                  <span className={styles.mentionLabel}>技能：</span>
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
              <div className={styles.composerRow}>
                <textarea
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
                  rows={1}
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
              {err ? <span className={styles.threadItemSub}>{err}</span> : null}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
