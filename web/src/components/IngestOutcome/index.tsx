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
        <p className={styles.lead}>正在出题…</p>
        <p className={styles.hint}>从笔记里抽出能考的句子，稍等一下</p>
        <div className={styles.pulse} aria-hidden="true" />
      </div>
    );
  }

  const n = claimTexts.length;
  const preview = claimTexts.slice(0, 3);

  return (
    <div className={styles.panel} role="status" aria-live="polite">
      <p className={styles.lead}>
        出好了{n > 0 ? ` · ${n} 道可考` : ""}
      </p>
      <p className={styles.hint}>过一遍门，才算真会了</p>
      {preview.length > 0 ? (
        <ul className={styles.list}>
          {preview.map((t, i) => (
            <li key={`${i}-${t.slice(0, 24)}`} className={styles.item}>
              {t}
            </li>
          ))}
          {n > preview.length ? (
            <li className={styles.more}>还有 {n - preview.length} 道</li>
          ) : null}
        </ul>
      ) : null}
      <div className={styles.actions}>
        <button
          type="button"
          className="btn-ghost"
          disabled={busy}
          onClick={onDismiss}
        >
          先不考
        </button>
        <button
          type="button"
          className="btn-ink"
          disabled={busy || n === 0}
          onClick={onExamine}
        >
          去开考
        </button>
      </div>
    </div>
  );
}
