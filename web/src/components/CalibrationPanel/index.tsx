import { useCallback, useState } from "react";
import { api } from "../../api";
import { Modal } from "../Modal";
import type {
  CalibrationOutcome,
  CalibrationSession,
} from "../../types";
import styles from "./index.module.scss";

type Props = {
  open: boolean;
  onClose: () => void;
  onFinished?: () => void;
  noteId?: string | null;
};

const STOP_LABEL: Record<string, string> = {
  converged: "估计已收敛",
  stable: "水平已稳定",
  max_items: "已达题数上限",
  exhausted: "题库已用完",
};

export function CalibrationPanel({ open, onClose, onFinished, noteId }: Props) {
  const [session, setSession] = useState<CalibrationSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [started, setStarted] = useState(false);

  const reset = useCallback(() => {
    setSession(null);
    setBusy(false);
    setError("");
    setStarted(false);
  }, []);

  const handleClose = () => {
    reset();
    onClose();
  };

  const start = async () => {
    setBusy(true);
    setError("");
    try {
      const body: { note_id?: string } = {};
      if (noteId) body.note_id = noteId;
      const view = await api<CalibrationSession>("/v1/calibration/start", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setSession(view);
      setStarted(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const answer = async (outcome: CalibrationOutcome) => {
    if (!session?.current_item) return;
    setBusy(true);
    setError("");
    try {
      const view = await api<CalibrationSession>(
        `/v1/calibration/${session.id}/answer`,
        {
          method: "POST",
          body: JSON.stringify({
            claim_id: session.current_item.claim_id,
            outcome,
          }),
        },
      );
      setSession(view);
      if (view.done) onFinished?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  const item = session?.current_item;
  const summary = session?.summary;
  const done = Boolean(session?.done);

  return (
    <Modal onClose={handleClose} title="摸底一下" wide>
      <div className={styles.wrap}>
        {!started ? (
          <>
            <p className={styles.lead}>
              用几道题摸清当前档位，初始化复习排程和弱点关系。不是正式考试。
            </p>
            <p className={styles.hint}>一般 4–10 题，答对升难、答错降难。</p>
            {error ? <p className={styles.error}>{error}</p> : null}
            <div className={styles.actions}>
              <button
                type="button"
                className={styles.primary}
                disabled={busy}
                onClick={() => void start()}
              >
                {busy ? "准备中…" : "开始"}
              </button>
              <button
                type="button"
                className={styles.ghost}
                disabled={busy}
                onClick={handleClose}
              >
                以后再说
              </button>
            </div>
          </>
        ) : null}

        {started && !done && item ? (
          <>
            <div className={styles.progress}>
              <span>
                第 {item.n} 题
                <span className={styles.faint}> / 最多 {item.max_items}</span>
              </span>
              {item.topic ? (
                <span className={styles.topic}>{item.topic}</span>
              ) : null}
            </div>
            <p className={styles.prompt}>{item.text}</p>
            {error ? <p className={styles.error}>{error}</p> : null}
            <div className={styles.actions}>
              <button
                type="button"
                className={styles.primary}
                disabled={busy}
                onClick={() => void answer("correct")}
              >
                会
              </button>
              <button
                type="button"
                className={styles.secondary}
                disabled={busy}
                onClick={() => void answer("incorrect")}
              >
                不会
              </button>
            </div>
          </>
        ) : null}

        {started && done && summary ? (
          <>
            <p className={styles.lead}>摸底结束</p>
            <ul className={styles.summary}>
              <li>
                {STOP_LABEL[summary.stop_reason ?? ""] ??
                  summary.stop_reason ??
                  "完成"}
                · 共 {summary.item_count} 题
              </li>
              <li>
                过了 {summary.passed_count} · 欠着下次 {summary.failed_count}
              </li>
              <li>今天欠账约 {summary.due_count} 条</li>
              {summary.confused_edges_seeded > 0 ? (
                <li>易混关系种子 {summary.confused_edges_seeded} 条</li>
              ) : null}
            </ul>
            <div className={styles.actions}>
              <button
                type="button"
                className={styles.primary}
                onClick={handleClose}
              >
                去看今天欠的
              </button>
            </div>
          </>
        ) : null}
      </div>
    </Modal>
  );
}
