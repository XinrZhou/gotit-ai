import { useEffect, useRef, useState } from "react";
import { api } from "../../api";
import { stripHtml } from "../../lib/format";
import { useStore } from "../../store";
import type { DayNote, ImportTab } from "../../types";
import { IngestOutcome } from "../IngestOutcome";
import { Modal } from "../Modal";
import {
  YuqueNoteEditor,
  type YuqueNoteEditorHandle,
} from "../YuqueNoteEditor";
import styles from "./index.module.scss";

function ExpandIcon({ collapse }: { collapse?: boolean }) {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" aria-hidden="true">
      <path
        d={
          collapse
            ? "M5 2v3H2M11 2v3h3M2 11h3v3M14 11h-3v3"
            : "M6 2H2v4M10 2h4v4M14 10v4h-4M6 14H2v-4"
        }
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function NoteComposeModal() {
  const {
    showCompose,
    setShowCompose,
    busy,
    setBusy,
    setError,
    setFlash,
    refresh,
    day,
    selectedProjectId,
    onIngestNote,
    ingestUi,
    beginComposeIngest,
    clearIngestUi,
    dismissIngestReady,
    requestExamineFromIngest,
  } = useStore();
  const editorRef = useRef<YuqueNoteEditorHandle>(null);
  const [noteTitle, setNoteTitle] = useState("");
  const [importTab, setImportTab] = useState<ImportTab>("write");
  const [linkUrl, setLinkUrl] = useState("");
  const [editorExpanded, setEditorExpanded] = useState(false);

  const surfaceActive =
    ingestUi != null &&
    ingestUi.surface === "compose" &&
    (ingestUi.phase === "generating" || ingestUi.phase === "ready");
  const generating = surfaceActive && ingestUi.phase === "generating";
  const ready = surfaceActive && ingestUi.phase === "ready";

  useEffect(() => {
    if (!showCompose || !editorExpanded) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        setEditorExpanded(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [showCompose, editorExpanded]);

  if (!showCompose) return null;

  function readEditorBody(): string {
    const html = editorRef.current?.getHtml() ?? "";
    return stripHtml(html).length > 0 ? html : "";
  }

  function clearEditor() {
    setNoteTitle("");
    editorRef.current?.setHtml("<p></p>");
  }

  function selectTab(id: ImportTab) {
    if (generating || ready) return;
    setImportTab(id);
    if (id !== "write") setEditorExpanded(false);
  }

  function close() {
    if (generating) return;
    setEditorExpanded(false);
    clearIngestUi();
    setShowCompose(false);
  }

  async function saveNoteOnly() {
    const body = readEditorBody();
    if (!body) return;
    setBusy(true);
    setError("");
    try {
      await api<DayNote>(`/v1/days/${day}/notes`, {
        method: "POST",
        body: JSON.stringify({
          body,
          title: noteTitle.trim() || null,
          tags: ["yuque"],
          project_id: selectedProjectId,
        }),
      });
      clearEditor();
      setFlash("笔记已保存");
      await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function saveAndIngest() {
    const body = readEditorBody();
    if (!body || busy || generating || ready) return;
    setBusy(true);
    setError("");
    setEditorExpanded(false);
    beginComposeIngest();
    try {
      const note = await api<DayNote>(`/v1/days/${day}/notes`, {
        method: "POST",
        body: JSON.stringify({
          body,
          title: noteTitle.trim() || null,
          tags: ["yuque"],
          project_id: selectedProjectId,
        }),
      });
      clearEditor();
      await onIngestNote(note.id, { surface: "compose" });
    } catch (err) {
      clearIngestUi();
      setError(String(err));
      setBusy(false);
    }
  }

  const writeActions =
    generating || ready ? null : (
      <>
        <button
          type="button"
          className={`${styles.iconBtn} btn-start`}
          disabled={busy}
          aria-label={editorExpanded ? "收起" : "放大编辑"}
          aria-pressed={editorExpanded}
          title={editorExpanded ? "收起" : "放大编辑"}
          onClick={() => setEditorExpanded((v) => !v)}
        >
          <ExpandIcon collapse={editorExpanded} />
        </button>
        <button
          type="button"
          className="btn-ghost"
          disabled={busy}
          onClick={saveNoteOnly}
        >
          仅保存
        </button>
        <button
          type="button"
          className="btn-ink"
          disabled={busy}
          onClick={() => void saveAndIngest()}
        >
          {busy ? "正在出题…" : "出题考我"}
        </button>
      </>
    );

  return (
    <Modal
      title={ready ? "题出好了" : generating ? "正在出题" : "添加资料"}
      wide={!editorExpanded && !generating && !ready}
      fill={editorExpanded && !generating && !ready}
      onClose={close}
      actions={
        importTab === "write" || generating || ready ? (
          writeActions
        ) : (
          <>
            <button type="button" className="btn-ghost" onClick={close}>
              取消
            </button>
            <button type="button" className="btn-ink" disabled>
              {importTab === "link" ? "导入" : "上传"}
            </button>
          </>
        )
      }
    >
      {generating || ready ? (
        <IngestOutcome
          phase={generating ? "generating" : "ready"}
          claimTexts={
            ingestUi?.phase === "ready"
              ? ingestUi.claims.map((c) => c.text)
              : []
          }
          busy={busy}
          onExamine={requestExamineFromIngest}
          onDismiss={dismissIngestReady}
        />
      ) : (
        <>
          <div className={styles.importTabs} role="tablist">
            {(
              [
                ["write", "手写"],
                ["link", "链接"],
                ["zip", "文件"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                className={
                  importTab === id ? `${styles.tab} ${styles.active}` : styles.tab
                }
                aria-selected={importTab === id}
                onClick={() => selectTab(id)}
              >
                {label}
              </button>
            ))}
          </div>

          {importTab === "write" ? (
            <div className={editorExpanded ? styles.writeExpanded : styles.write}>
              {!editorExpanded ? (
                <p className={styles.hint}>写点今天学的，我来帮你出题</p>
              ) : null}
              <input
                className={`note-title-input ${styles.title}`}
                value={noteTitle}
                onChange={(e) => setNoteTitle(e.target.value)}
                placeholder="标题（可选）"
                disabled={busy}
              />
              <YuqueNoteEditor
                ref={editorRef}
                value="<p></p>"
                height={editorExpanded ? "100%" : 340}
                className={styles.editor}
                onError={(err) => setError(String(err))}
              />
            </div>
          ) : null}

          {importTab === "link" ? (
            <div className={styles.pane}>
              <p className={styles.hint}>丢个链接，抓完帮你出题</p>
              <input
                value={linkUrl}
                onChange={(e) => setLinkUrl(e.target.value)}
                placeholder="https://www.yuque.com/…"
                disabled={busy}
              />
              <p className={styles.hint}>链接导入即将支持</p>
            </div>
          ) : null}

          {importTab === "zip" ? (
            <div className={styles.pane}>
              <p className={styles.hint}>传个文件，批量帮你出题</p>
              <div className={styles.dropzone}>把文件拖到这里，或点击选择</div>
              <p className={styles.hint}>
                支持 .zip / .md / .txt / .docx（即将支持）
              </p>
            </div>
          ) : null}
        </>
      )}
    </Modal>
  );
}
