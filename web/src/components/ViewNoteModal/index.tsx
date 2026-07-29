import { useStore } from "../../store";
import { Modal } from "../Modal";

export function ViewNoteModal() {
  const { viewNote, setViewNote, busy, onDeleteNote, onIngestNote } = useStore();
  if (!viewNote) return null;
  return (
    <Modal
      title={viewNote.title || "未命名笔记"}
      onClose={() => setViewNote(null)}
      actions={
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
              onClick={() => {
                onIngestNote(viewNote.id);
                setViewNote(null);
              }}
            >
              出题
            </button>
          )}
        </>
      }
    >
      <div className="note-body" dangerouslySetInnerHTML={{ __html: viewNote.body }} />
    </Modal>
  );
}
