import { useEffect, useState } from "react";
import { fetchBlob } from "../../api";
import { useStore } from "../../store";
import { Modal } from "../Modal";
import styles from "./index.module.scss";

type Kind = "pdf" | "docx" | "text" | "unknown";

function kindFromExt(ext: string): Kind {
  if (ext === "pdf") return "pdf";
  if (ext === "docx") return "docx";
  if (ext === "txt" || ext === "md") return "text";
  return "unknown";
}

function kindFromPath(filePath: string): Kind {
  const base = filePath.split(/[/\\]/).pop() ?? "";
  const dot = base.lastIndexOf(".");
  if (dot <= 0) return "unknown";
  return kindFromExt(base.slice(dot + 1).toLowerCase());
}

function kindFromContentType(contentType: string): Kind {
  const base = contentType.split(";")[0]?.trim().toLowerCase() ?? "";
  if (base === "application/pdf") return "pdf";
  if (base === "application/vnd.openxmlformats-officedocument.wordprocessingml.document") {
    return "docx";
  }
  if (base === "text/plain" || base === "text/markdown") return "text";
  return "unknown";
}

/** Prefer Content-Type from file endpoint (handles legacy paths without ext). */
function resolveKind(contentType: string, filePath: string): Kind {
  const fromCt = kindFromContentType(contentType);
  if (fromCt !== "unknown") return fromCt;
  return kindFromPath(filePath);
}

export function ResumeViewerModal() {
  const { showResumeViewer, setShowResumeViewer, resume } = useStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [text, setText] = useState<string | null>(null);
  const [kind, setKind] = useState<Kind>("unknown");

  useEffect(() => {
    if (!showResumeViewer || !resume) return;
    let cancelled = false;
    let url: string | null = null;
    setLoading(true);
    setError("");
    setText(null);
    setObjectUrl(null);
    setKind(kindFromPath(resume.file_path));
    (async () => {
      try {
        const { blob, contentType } = await fetchBlob("/v1/resumes/file");
        if (cancelled) return;
        const k = resolveKind(contentType || blob.type, resume.file_path);
        setKind(k);
        if (k === "text") {
          setText(await blob.text());
        } else if (k === "pdf" || k === "docx") {
          url = URL.createObjectURL(blob);
          setObjectUrl(url);
        } else {
          setError("无法识别的简历文件类型。");
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [showResumeViewer, resume]);

  if (!showResumeViewer) return null;

  return (
    <Modal
      title="查看简历"
      wide
      onClose={() => setShowResumeViewer(false)}
      actions={
        kind === "docx" && objectUrl ? (
          <a
            className="btn-ink"
            href={objectUrl}
            download="resume.docx"
            style={{ textDecoration: "none" }}
          >
            下载 DOCX
          </a>
        ) : null
      }
    >
    {loading ? (
        <div className={styles.state}>加载中…</div>
      ) : error ? (
        <div className={styles.stateError}>{error}</div>
      ) : kind === "pdf" && objectUrl ? (
        <iframe className={styles.pdfFrame} src={objectUrl} title="简历" />
      ) : kind === "text" && text !== null ? (
        <pre className={styles.textPre}>{text}</pre>
      ) : kind === "docx" ? (
        <div className={styles.docxHint}>
          浏览器无法直接预览 DOCX，点击右下角「下载 DOCX」用本地应用打开查看。
        </div>
      ) : (
        <div className={styles.stateError}>无法识别的简历文件类型。</div>
      )}
    </Modal>
  );
}
