import { useRef, useState } from "react";
import { api } from "../../api";
import { stripHtml } from "../../format";
import { useStore } from "../../store";
import type { DayNote, ImportTab } from "../../types";
import { Modal } from "../Modal";
import {
  YuqueNoteEditor,
  type YuqueNoteEditorHandle,
} from "../YuqueNoteEditor";
import styles from "./index.module.scss";

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
  } = useStore();
  const editorRef = useRef<YuqueNoteEditorHandle>(null);
  const [noteHtml, setNoteHtml] = useState("<p></p>");
  const [noteTitle, setNoteTitle] = useState("");
  const [importTab, setImportTab] = useState<ImportTab>("write");
  const [linkUrl, setLinkUrl] = useState("");

  if (!showCompose) return null;

  function readEditorBody(): string {
    const html = editorRef.current?.getHtml() ?? noteHtml;
    return stripHtml(html).length > 0 ? html : "";
  }

  function clearEditor() {
    setNoteHtml("<p></p>");
    setNoteTitle("");
    editorRef.current?.setHtml("<p></p>");
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
    if (!body) return;
    setBusy(true);
    setError("");
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
      await api<unknown>(`/v1/notes/${note.id}/ingest`, {
        method: "POST",
        body: JSON.stringify({ add_plan_item: true }),
      });
      clearEditor();
      setShowCompose(false);
      setFlash("保存好了，题也出了");
      await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="添加资料" onClose={() => setShowCompose(false)}>
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
            className={importTab === id ? `${styles.tab} ${styles.active}` : styles.tab}
            aria-selected={importTab === id}
            onClick={() => setImportTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {importTab === "write" ? (
        <>
          <div className="muted">写点今天学的，我来帮你出题</div>
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
          <div className={styles.actions}>
            <button type="button" className="btn-ghost" disabled={busy} onClick={saveNoteOnly}>
              仅保存
            </button>
            <button type="button" className="btn-ink" disabled={busy} onClick={saveAndIngest}>
              {busy ? "处理中…" : "出题考我"}
            </button>
          </div>
        </>
      ) : null}

      {importTab === "link" ? (
        <>
          <div className="muted">丢个链接，抓完帮你出题</div>
          <input
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
            placeholder="https://www.yuque.com/…"
            disabled={busy}
          />
          <div className="muted">链接导入即将支持</div>
          <div className={styles.actions}>
            <button type="button" className="btn-ghost" onClick={() => setShowCompose(false)}>
              取消
            </button>
            <button type="button" className="btn-ink" disabled>
              导入
            </button>
          </div>
        </>
      ) : null}

      {importTab === "zip" ? (
        <>
          <div className="muted">传个文件，批量帮你出题</div>
          <div className={styles.dropzone}>把文件拖到这里，或点击选择</div>
          <div className="muted">支持 .zip / .md / .txt / .docx（即将支持）</div>
          <div className={styles.actions}>
            <button type="button" className="btn-ghost" onClick={() => setShowCompose(false)}>
              取消
            </button>
            <button type="button" className="btn-ink" disabled>
              上传
            </button>
          </div>
        </>
      ) : null}
    </Modal>
  );
}

