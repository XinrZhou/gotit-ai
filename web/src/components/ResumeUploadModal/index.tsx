import { useState } from "react";
import { useStore } from "../../store";
import type { ResumeDocument, ResumeProject } from "../../types";
import { Modal } from "../Modal";
import styles from "./index.module.scss";

export function ResumeUploadModal() {
  const {
    showResumeModal,
    setShowResumeModal,
    busy,
    resume,
    onUploadResume,
    onApplyResume,
    setError,
  } = useStore();
  const [file, setFile] = useState<File | null>(null);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [filePath, setFilePath] = useState<string | null>(null);
  const [doc, setDoc] = useState<ResumeDocument | null>(null);
  const [stage, setStage] = useState<"pick" | "preview">("pick");
  const [uploading, setUploading] = useState(false);

  if (!showResumeModal) return null;

  function reset() {
    setFile(null);
    setUploadId(null);
    setFilePath(null);
    setDoc(null);
    setStage("pick");
    setUploading(false);
  }

  async function onUpload() {
    if (!file || uploading) return;
    setUploading(true);
    setError("");
    try {
      const res = await onUploadResume(file);
      setUploadId(res.upload_id);
      setFilePath(res.file_path);
      setDoc(res.document);
      setStage("preview");
    } catch (err) {
      setError(String(err));
    } finally {
      setUploading(false);
    }
  }

  function editProject(idx: number, patch: Partial<ResumeProject>) {
    if (!doc) return;
    const projects = doc.projects.map((p, i) => (i === idx ? { ...p, ...patch } : p));
    setDoc({ ...doc, projects });
  }

  function addProject() {
    if (!doc) return;
    setDoc({
      ...doc,
      projects: [
        ...doc.projects,
        { name: "", role: null, goal: null, tech_stack: [], description: "" },
      ],
    });
  }

  function removeProject(idx: number) {
    if (!doc) return;
    setDoc({ ...doc, projects: doc.projects.filter((_, i) => i !== idx) });
  }

  async function onApply() {
    if (!uploadId || !doc || !filePath) return;
    await onApplyResume(uploadId, doc, filePath);
    reset();
  }

  const parsing = uploading;

  return (
    <Modal
      title="导入简历"
      wide
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
            disabled={uploading || !file}
            onClick={onUpload}
          >
            {uploading ? "解析中…" : "上传并解析"}
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
              disabled={uploading}
            />
            <div className={styles.dropIcon}>↥</div>
            <div className={styles.dropText}>
              {file ? file.name : "把简历拖到这里，或点击选择"}
            </div>
            <div className={styles.dropHint}>
              支持 PDF / DOCX / TXT / MD，≤ 10MB
            </div>
          </label>
          {file ? (
            <div className={styles.fileMeta}>
              <span className={styles.fileName}>{file.name}</span>
              <span className={styles.fileSize}>{formatSize(file.size)}</span>
            </div>
          ) : null}
          {parsing ? <div className={styles.overlay}><Spinner label="正在解析…" /></div> : null}
        </div>
      ) : doc ? (
        <div className={styles.preview}>
          <div className={styles.muted}>解析结果可编辑，确认后再落库。</div>

          <div className={styles.section}>
            <div className={styles.sectionTitle}>基本信息</div>
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
          </div>

          <div className={styles.section}>
            <div className={styles.sectionTitle}>
              项目经历
              <span className={styles.sectionCount}>{doc.projects.length}</span>
            </div>
            {doc.projects.map((p, i) => (
              <div key={i} className={styles.projCard}>
                <div className={styles.projHead}>
                  <span>项目 {i + 1}</span>
                  <button
                    type="button"
                    className={styles.projRemove}
                    onClick={() => removeProject(i)}
                    aria-label="删除项目"
                    title="删除项目"
                  >
                    ×
                  </button>
                </div>
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
                  rows={5}
                />
              </div>
            ))}
            <button type="button" className={styles.addProj} onClick={addProject}>
              + 添加项目
            </button>
            {doc.projects.length === 0 ? (
              <div className={styles.emptyProjects}>
                没解析出项目。可点上方「+ 添加项目」手动新建，或换一份格式更清晰的简历重新解析。
              </div>
            ) : null}
          </div>

          {parsing ? <div className={styles.overlay}><Spinner label="正在解析…" /></div> : null}
        </div>
      ) : null}
    </Modal>
  );
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function Spinner({ label }: { label: string }) {
  return (
    <div className={styles.spinner}>
      <div className={styles.spinnerRing} />
      <div className={styles.spinnerLabel}>{label}</div>
    </div>
  );
}
