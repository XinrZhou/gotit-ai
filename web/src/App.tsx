import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from "react";
import {
  YuqueNoteEditor,
  type YuqueNoteEditorHandle,
} from "./components/YuqueNoteEditor";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const API_KEY = import.meta.env.VITE_GOTIT_API_KEY ?? "dev-change-me";

type PlanItem = {
  id: string;
  title: string;
  source: string;
  status: string;
  claim_id: string | null;
  sort_order: number;
  due_at: string | null;
};

type DayNote = {
  id: string;
  title: string | null;
  body: string;
  excerpt: string;
  tags: string[];
  claim_ids: string[];
  created_at: string;
};

type DayPlan = {
  date: string;
  user_id: string;
  items: PlanItem[];
};

type ImportTab = "write" | "link" | "zip" | "manual" | "review";

type ChatMsg = {
  role: "examiner" | "user";
  text: string;
};

type ChatMsgWithId = {
  id: string;
  role: string;
  text: string;
};

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function stripHtml(html: string): string {
  return html
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function fmtDate(iso: string): string {
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return iso;
  return `${parseInt(m[2], 10)} 月 ${parseInt(m[3], 10)} 日`;
}

function stubExaminerQuestion(title: string): string {
  return `我们来测这一条：「${title}」。你能用自己的话说说，它到底指什么？为什么是对的？`;
}

function stubExaminerPass(): string {
  return "答得清楚，这一条过了。";
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_KEY}`,
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export function App() {
  const [day, setDay] = useState(todayISO);
  const [plan, setPlan] = useState<DayPlan | null>(null);
  const [notes, setNotes] = useState<DayNote[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [chat, setChat] = useState<ChatMsg[]>([]);
  const [answer, setAnswer] = useState("");
  const [showCompose, setShowCompose] = useState(false);
  const [noteHtml, setNoteHtml] = useState("<p></p>");
  const [noteTitle, setNoteTitle] = useState("");
  const [importTab, setImportTab] = useState<ImportTab>("write");
  const [linkUrl, setLinkUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [viewNote, setViewNote] = useState<DayNote | null>(null);
  const [manualTitle, setManualTitle] = useState("");
  const editorRef = useRef<YuqueNoteEditorHandle>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  const items = plan?.items ?? [];
  const active = useMemo(() => {
    if (!items.length) return null;
    return items.find((i) => i.id === selectedId) ?? items[0];
  }, [items, selectedId]);

  const refresh = useCallback(async () => {
    setError("");
    const [planData, notesData] = await Promise.all([
      api<DayPlan>(`/v1/days/${day}/plan`),
      api<DayNote[]>(`/v1/days/${day}/notes`),
    ]);
    setPlan(planData);
    setNotes(notesData);
    setSelectedId((prev) => {
      if (prev && planData.items.some((i) => i.id === prev)) return prev;
      return planData.items[0]?.id ?? null;
    });
  }, [day]);

  useEffect(() => {
    void refresh().catch((err: unknown) => setError(String(err)));
  }, [refresh]);

  // 选中项变化时加载历史对话
  useEffect(() => {
    if (!active) {
      setChat([]);
      return;
    }
    setAnswer("");
    void (async () => {
      try {
        const msgs = await api<ChatMsg[]>(`/v1/plan/items/${active.id}/messages`);
        if (msgs.length > 0) {
          setChat(msgs.map((m) => ({ role: m.role, text: m.text })));
        } else {
          const q = stubExaminerQuestion(active.title);
          setChat([{ role: "examiner", text: q }]);
          void api(`/v1/plan/items/${active.id}/messages`, {
            method: "POST",
            body: JSON.stringify({ role: "examiner", text: q }),
          });
        }
      } catch (err) {
        setError(String(err));
      }
    })();
  }, [active?.id]);

  // 对话区自动滚到底
  useEffect(() => {
    const el = chatScrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [chat]);

  async function run(action: () => Promise<unknown>, okMessage?: string) {
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
  }

  const [flash, setFlash] = useState("");

  function readEditorBody(): string {
    const html = editorRef.current?.getHtml() ?? noteHtml;
    return stripHtml(html).length > 0 ? html : "";
  }

  function clearEditor() {
    setNoteHtml("<p></p>");
    setNoteTitle("");
    editorRef.current?.setHtml("<p></p>");
  }

  function onFillQueue() {
    void run(() =>
      api<DayPlan>(`/v1/days/${day}/plan/fill-queue`, {
        method: "POST",
        body: "{}",
      }),
    );
  }

  function onSubmitAnswer() {
    if (!active || !answer.trim()) return;
    const userText = answer.trim();
    setChat((prev) => [...prev, { role: "user", text: userText }]);
    setAnswer("");
    void (async () => {
      try {
        await api<ChatMsgWithId>(`/v1/plan/items/${active.id}/messages`, {
          method: "POST",
          body: JSON.stringify({ role: "user", text: userText }),
        });
        await api<PlanItem>(`/v1/plan/items/${active.id}`, {
          method: "PATCH",
          body: JSON.stringify({ status: "verified" }),
        });
        const passText = stubExaminerPass();
        await api<ChatMsgWithId>(`/v1/plan/items/${active.id}/messages`, {
          method: "POST",
          body: JSON.stringify({ role: "examiner", text: passText }),
        });
        setChat((prev) => [...prev, { role: "examiner", text: passText }]);
        await refresh();
      } catch (err) {
        setError(String(err));
      }
    })();
  }

  function onDeletePlanItem() {
    if (!active) return;
    const id = active.id;
    void run(async () => {
      await api<{ ok: boolean }>(`/v1/plan/items/${id}`, { method: "DELETE" });
      setSelectedId(null);
      setChat([]);
    }, "已删除");
  }

  function onSkip() {
    if (!active) return;
    const next = new Date(day);
    next.setDate(next.getDate() + 1);
    void run(() =>
      api<PlanItem>(`/v1/plan/items/${active.id}`, {
        method: "PATCH",
        body: JSON.stringify({ defer_to: next.toISOString().slice(0, 10) }),
      }),
    );
  }

  function onSaveNote() {
    const body = readEditorBody();
    if (!body) return;
    void run(async () => {
      await api<DayNote>(`/v1/days/${day}/notes`, {
        method: "POST",
        body: JSON.stringify({
          body,
          title: noteTitle.trim() || null,
          tags: ["yuque"],
        }),
      });
      clearEditor();
    }, "笔记已保存");
  }

  function onIngestNote(noteId: string) {
    void run(
      () =>
        api<unknown>(`/v1/notes/${noteId}/ingest`, {
          method: "POST",
          body: JSON.stringify({ add_plan_item: true }),
        }),
      "已整理成测验项",
    );
  }

  function onOpenNote(noteId: string) {
    void (async () => {
      setError("");
      try {
        const n = await api<DayNote>(`/v1/notes/${noteId}`);
        setViewNote(n);
      } catch (err) {
        setError(String(err));
      }
    })();
  }

  function onDeleteNote(noteId: string) {
    void run(
      async () => {
        await api<{ ok: boolean }>(`/v1/notes/${noteId}`, { method: "DELETE" });
        setViewNote(null);
      },
      "笔记已删除",
    );
  }

  function onManualAdd(e: FormEvent) {
    e.preventDefault();
    if (!manualTitle.trim()) return;
    void run(async () => {
      await api<PlanItem>(`/v1/days/${day}/plan/items`, {
        method: "POST",
        body: JSON.stringify({ title: manualTitle.trim() }),
      });
      setManualTitle("");
      setShowCompose(false);
    });
  }

  function onGotItMaterial() {
    const body = readEditorBody();
    if (!body) return;
    void run(async () => {
      const note = await api<DayNote>(`/v1/days/${day}/notes`, {
        method: "POST",
        body: JSON.stringify({
          body,
          title: noteTitle.trim() || null,
          tags: ["yuque"],
        }),
      });
      await api<unknown>(`/v1/notes/${note.id}/ingest`, {
        method: "POST",
        body: JSON.stringify({ add_plan_item: true }),
      });
      clearEditor();
      setShowCompose(false);
    }, "已保存并整理成测验");
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-head">
          <div className="head-row">
            <div className="brand">
              <svg className="brand-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="9.25" stroke="currentColor" stroke-width="1.5" />
                <path
                  d="M7.5 12.3l3 3 6-6.6"
                  stroke="currentColor"
                  stroke-width="1.9"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
              <span>gotit</span>
            </div>
            <label className="day-picker">
              <input
                type="date"
                value={day}
                onChange={(e) => setDay(e.target.value)}
                disabled={busy}
              />
              <span className="day-label">{fmtDate(day)}</span>
            </label>
          </div>
        </div>

        <div className="side-section-label">今天要测 · {items.length}</div>
        <div className="queue-list">
          {items.length === 0 ? (
            <div className="queue-empty">还没有题目</div>
          ) : (
            items.map((item) => {
              const on = item.id === active?.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  className={on ? "queue-item active" : "queue-item"}
                  onClick={() => setSelectedId(item.id)}
                >
                  <span className={`queue-dot status-${item.status}`} />
                  <span className="queue-title">{item.title}</span>
                </button>
              );
            })
          )}
        </div>

        <div className="side-section-label">笔记 · {notes.length}</div>
        <div className="notes-list">
          {notes.length === 0 ? (
            <div className="notes-empty">还没有笔记</div>
          ) : (
            notes.map((note) => (
              <button
                key={note.id}
                type="button"
                className="note-item"
                onClick={() => onOpenNote(note.id)}
                disabled={busy}
              >
                <span className="note-title">{note.title || "未命名"}</span>
                <span className="note-hint">查看</span>
              </button>
            ))
          )}
        </div>

        <div className="sidebar-foot">
          <button
            type="button"
            className="btn-compose"
            disabled={busy}
            onClick={() => setShowCompose(true)}
          >
            + 添加测验
          </button>
        </div>
      </aside>

      <main className="main">
        <div className="main-head">
          {active ? (
            <>
              <div className="active-title">{active.title}</div>
              <button
                type="button"
                className="btn-delete-item"
                disabled={busy}
                onClick={onDeletePlanItem}
                aria-label="删除"
                title="删除这条"
              >
                删除
              </button>
            </>
          ) : (
            <div className="active-title muted">选左边一条开始测</div>
          )}
        </div>

        <div className="chat" ref={chatScrollRef}>
          {chat.length === 0 ? (
            <div className="chat-empty" />
          ) : (
            chat.map((m, i) => {
              const isExaminer = m.role === "examiner";
              return (
                <div
                  key={i}
                  className={
                    isExaminer ? "bubble-row examiner" : "bubble-row user"
                  }
                >
                  <div className={isExaminer ? "avatar avatar-e" : "avatar avatar-me"}>
                    {isExaminer ? "E" : "我"}
                  </div>
                  <div className="bubble">{m.text}</div>
                </div>
              );
            })
          )}
        </div>

        <div className="composer">
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="用你自己的话回答…"
            rows={2}
            disabled={busy || !active}
          />
          <div className="composer-actions">
            <button
              type="button"
              className="btn-ghost"
              disabled={busy || !active}
              onClick={onSkip}
            >
              跳过
            </button>
            <button
              type="button"
              className="btn-ink"
              disabled={busy || !active || !answer.trim()}
              onClick={onSubmitAnswer}
            >
              {busy ? "处理中…" : "提交回答"}
            </button>
          </div>
        </div>
      </main>

      {error && <div className="toast toast-error">{error}</div>}
      {flash && <div className="toast">{flash}</div>}

      {showCompose ? (
        <div className="overlay" onClick={() => setShowCompose(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <div className="modal-title">添加测验</div>
              <button
                type="button"
                className="modal-close"
                aria-label="关闭"
                onClick={() => setShowCompose(false)}
              >
                ×
              </button>
            </div>
            <div className="import-tabs" role="tablist">
              {(
                [
                  ["write", "手写"],
                  ["link", "链接"],
                  ["zip", "文件"],
                  ["manual", "手动加题"],
                  ["review", "回顾没过的"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  className={importTab === id ? "import-tab active" : "import-tab"}
                  aria-selected={importTab === id}
                  onClick={() => setImportTab(id)}
                >
                  {label}
                </button>
              ))}
            </div>

            {importTab === "write" ? (
              <div className="import-pane">
                <input
                  className="note-title-input"
                  value={noteTitle}
                  onChange={(e) => setNoteTitle(e.target.value)}
                  placeholder="标题（可选）"
                  disabled={busy}
                />
                <YuqueNoteEditor
                  ref={editorRef}
                  value={noteHtml}
                  onChange={setNoteHtml}
                  height={260}
                  onError={(err) => setError(String(err))}
                />
                <div className="modal-actions">
                  <button
                    type="button"
                    className="btn-ghost"
                    disabled={busy}
                    onClick={onSaveNote}
                  >
                    仅保存
                  </button>
                  <button
                    type="button"
                    className="btn-ink"
                    disabled={busy}
                    onClick={onGotItMaterial}
                  >
                    {busy ? "处理中…" : "出题考我"}
                  </button>
                </div>
              </div>
            ) : null}

            {importTab === "link" ? (
              <div className="import-pane">
                <input
                  value={linkUrl}
                  onChange={(e) => setLinkUrl(e.target.value)}
                  placeholder="https://www.yuque.com/…"
                  disabled={busy}
                />
                <div className="muted">链接导入即将支持</div>
                <div className="modal-actions">
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={() => setShowCompose(false)}
                  >
                    取消
                  </button>
                  <button type="button" className="btn-ink" disabled>
                    导入
                  </button>
                </div>
              </div>
            ) : null}

            {importTab === "zip" ? (
              <div className="import-pane">
                <div className="dropzone">把文件拖到这里，或点击选择</div>
                <div className="muted">支持 .zip / .md / .txt / .docx（即将支持）</div>
                <div className="modal-actions">
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={() => setShowCompose(false)}
                  >
                    取消
                  </button>
                  <button type="button" className="btn-ink" disabled>
                    上传
                  </button>
                </div>
              </div>
            ) : null}

            {importTab === "manual" ? (
              <div className="import-pane">
                <div className="muted">只填一道题的标题，不贴内容</div>
                <form onSubmit={onManualAdd}>
                  <input
                    value={manualTitle}
                    onChange={(e) => setManualTitle(e.target.value)}
                    placeholder="题目，例如：什么是上下文预算"
                    disabled={busy}
                  />
                  <div className="modal-actions">
                    <button
                      type="button"
                      className="btn-ghost"
                      onClick={() => setShowCompose(false)}
                    >
                      取消
                    </button>
                    <button
                      type="submit"
                      className="btn-ink"
                      disabled={busy || !manualTitle.trim()}
                    >
                      加入今天
                    </button>
                  </div>
                </form>
              </div>
            ) : null}

            {importTab === "review" ? (
              <div className="import-pane">
                <div className="muted">
                  把以前答错或过期的题目补到今天的测验队列
                </div>
                <div className="modal-actions">
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={() => setShowCompose(false)}
                  >
                    取消
                  </button>
                  <button
                    type="button"
                    className="btn-ink"
                    disabled={busy}
                    onClick={() => {
                      onFillQueue();
                      setShowCompose(false);
                    }}
                  >
                    补到今天
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {viewNote ? (
        <div className="overlay" onClick={() => setViewNote(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <div className="modal-title">{viewNote.title || "未命名笔记"}</div>
              <button
                type="button"
                className="modal-close"
                aria-label="关闭"
                onClick={() => setViewNote(null)}
              >
                ×
              </button>
            </div>
            <div
              className="note-body"
              dangerouslySetInnerHTML={{ __html: viewNote.body }}
            />
            <div className="modal-actions">
              <button
                type="button"
                className="btn-danger"
                disabled={busy}
                onClick={() => onDeleteNote(viewNote.id)}
              >
                删除
              </button>
              <button
                type="button"
                className="btn-ink"
                disabled={busy}
                onClick={() => {
                  onIngestNote(viewNote.id);
                  setViewNote(null);
                }}
              >
                整理成测验
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
