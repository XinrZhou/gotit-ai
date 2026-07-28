import { useState } from "react";
import { useStore } from "../../store";
import type { ResumeDocument, ResumeProject } from "../../types";
import { Modal } from "../Modal";
import styles from "./index.module.scss";

export function ResumeUploadModal() {
  const { showResumeModal, setShowResumeModal, busy, resume, onUploadResume, onApplyResume } =
    useStore();
  const [file, setFile] = useState<File | null>(null);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [doc, setDoc] = useState<ResumeDocument | null>(null);
  const [stage, setStage] = useState<"pick" | "preview">("pick");

  if (!showResumeModal) return null;

  function reset() {
    setFile(null);
    setUploadId(null);
    setDoc(null);
    setStage("pick");
  }

  async function onUpload() {
    if (!file) return;
    try {
      const res = await onUploadResume(file);
      setUploadId(res.upload_id);
      setDoc(res.document);
      setStage("preview");
    } catch {
      // error surfaced via store
    }
  }

  function editProject(idx: number, patch: Partial<ResumeProject>) {
    if (!doc) return;
    const projects = doc.projects.map((p, i) => (i === idx ? { ...p, ...patch } : p));
    setDoc({ ...doc, projects });
  }

  async function onApply() {
    if (!uploadId || !doc) return;
    await onApplyResume(uploadId, doc);
    reset();
  }

  return (
    <Modal
      title="导入简历"
      onClose={() => {
        setShowResumeModal(false);
        reset();
      }}
      actions={
        stage === "preview" ? (
          <>
            <button
              type="button"
              className="btn-ghost"
              onClick={() => setStage("pick")}
              disabled={busy}
            >
              重新选
            </button>
            <button
              type="button"
              className="btn-ink"
              disabled={busy || !doc}
              onClick={onApply}
            >
              {busy ? "处理中…" : resume ? "确认覆盖重建" : "确认创建"}
            </button>
          </>
        ) : (
          <button
            type="button"
            className="btn-ink"
            disabled={busy || !file}
            onClick={onUpload}
          >
            {busy ? "解析中…" : "上传并解析"}
          </button>
        )
      }
    >
      {resume ? (
        <div className={styles.warn}>
          已有简历（{resume.document.projects.length} 个项目）。再次导入会<b>清空重建</b>项目库，你手写的笔记和考题会保留（仅脱离旧项目）。
        </div>
      ) : null}

      {stage === "pick" ? (
        <div className={styles.pick}>
          <label className={styles.dropzone}>
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              className={styles.hiddenInput}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              disabled={busy}
            />
            <div className={styles.dropIcon}>↥</div>
            <div className={styles.dropText}>
              {file ? file.name : "把简历拖到这里，或点击选择"}
            </div>
            <div className={styles.dropHint}>
              支持 PDF / DOCX / TXT / MD，≤ 10MB
            </div>
          </label>
        </div>
      ) : doc ? (
        <div className={styles.preview}>
          <div className={styles.muted}>解析结果可编辑，确认后再落库。</div>
          <input
            className={styles.basicsInput}
            value={doc.basics.name ?? ""}
            onChange={(e) => setDoc({ ...doc, basics: { ...doc.basics, name: e.target.value } })}
            placeholder="姓名"
          />
          <input
            className={styles.basicsInput}
            value={doc.basics.target_role ?? ""}
            onChange={(e) =>
              setDoc({ ...doc, basics: { ...doc.basics, target_role: e.target.value } })
            }
            placeholder="目标岗位"
          />
          {doc.projects.map((p, i) => (
            <div key={i} className={styles.projCard}>
              <input
                className={styles.projInput}
                value={p.name}
                onChange={(e) => editProject(i, { name: e.target.value })}
                placeholder="项目名"
              />
              <input
                className={styles.projInput}
                value={p.role ?? ""}
                onChange={(e) => editProject(i, { role: e.target.value })}
                placeholder="角色"
              />
              <input
                className={styles.projInput}
                value={p.tech_stack.join(", ")}
                onChange={(e) =>
                  editProject(i, {
                    tech_stack: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                  })
                }
                placeholder="技术栈，逗号分隔"
              />
              <textarea
                className={styles.projBody}
                value={p.description}
                onChange={(e) => editProject(i, { description: e.target.value })}
                placeholder="项目描述"
                rows={3}
              />
            </div>
          ))}
          {doc.projects.length === 0 ? (
            <div className={styles.muted}>没解析出项目，可以手动改上面的字段再确认。</div>
          ) : null}
        </div>
      ) : null}
    </Modal>
  );
}
