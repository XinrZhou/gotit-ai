import { useStore } from "../../store";
import { IngestOutcome } from "../IngestOutcome";
import { Modal } from "../Modal";
import styles from "./index.module.scss";

export function ViewNoteModal() {
  const {
    viewNote,
    setViewNote,
    busy,
    onDeleteNote,
    onIngestNote,
    ingestUi,
    clearIngestUi,
    dismissIngestReady,
    requestExamineFromIngest,
  } = useStore();

  if (!viewNote) return null;

  const surfaceActive =
    ingestUi != null &&
    ingestUi.surface === "view" &&
    (ingestUi.phase === "generating" ||
      (ingestUi.phase === "ready" && ingestUi.noteId === viewNote.id));

  const generating = surfaceActive && ingestUi.phase === "generating";
  const ready = surfaceActive && ingestUi.phase === "ready";

  function close() {
    if (generating) return;
    clearIngestUi();
    setViewNote(null);
  }

  return (
    <Modal
      title={
        ready
          ? "题出好了"
          : generating
            ? "正在出题"
            : viewNote.title || "未命名笔记"
      }
      wide={ready || generating}
      onClose={close}
      actions={
        ready || generating ? null : (
          <>
            <button
              type="button"
              className={`btn-ghost${viewNote.claim_ids.length === 0 ? " btn-start" : ""}`}
              disabled={busy}
              onClick={() => onDeleteNote(viewNote.id)}
            >
              删除
            </button>
            {viewNote.claim_ids.length > 0 ? null : (
              <button
                type="button"
                className="btn-ink"
                disabled={busy}
                onClick={() => onIngestNote(viewNote.id, { surface: "view" })}
              >
                出题
              </button>
            )}
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
        <div
          className={`note-body ${styles.body}`}
          dangerouslySetInnerHTML={{ __html: viewNote.body }}
        />
      )}
    </Modal>
  );
}
