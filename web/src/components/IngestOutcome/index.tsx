import styles from "./index.module.scss";

type Props = {
  phase: "generating" | "ready";
  claimTexts: string[];
  busy?: boolean;
  onExamine: () => void;
  onDismiss: () => void;
};

export function IngestOutcome({
  phase,
  claimTexts,
  busy,
  onExamine,
  onDismiss,
}: Props) {
  if (phase === "generating") {
    return (
      <div className={styles.panel} role="status" aria-live="polite">
        <p className={styles.sub}>从笔记里抽出能考的句子，稍等一下</p>
        <div className={styles.pulse} aria-hidden="true" />
      </div>
    );
  }

  const n = claimTexts.length;

  return (
    <div className={styles.panel} role="status" aria-live="polite">
      <p className={styles.sub}>
        {n > 0 ? `共 ${n} 道 · ` : ""}过一遍门，才算真会了
      </p>

      {n > 0 ? (
        <ol className={styles.list} aria-label="可考题目">
          {claimTexts.map((t, i) => (
            <li key={`${i}-${t.slice(0, 32)}`} className={styles.item}>
              <span className={styles.idx} aria-hidden="true">
                {i + 1}
              </span>
              <span className={styles.text}>{t}</span>
            </li>
          ))}
        </ol>
      ) : null}

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.secondary}
          disabled={busy}
          onClick={onDismiss}
        >
          先不考
        </button>
        <button
          type="button"
          className={styles.primary}
          disabled={busy || n === 0}
          onClick={onExamine}
        >
          去开考
        </button>
      </div>
    </div>
  );
}
