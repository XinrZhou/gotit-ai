import type { KeyboardEvent } from "react";
import styles from "./index.module.scss";

type Props = {
  kind: "textarea" | "topic";
  value: string;
  onChange: (s: string) => void;
  placeholder?: string;
  onSubmit: () => void;
  submitLabel: string;
  busy: boolean;
  disabled?: boolean;
  onKeyDown?: (e: KeyboardEvent) => void;
};

export function Composer({
  kind,
  value,
  onChange,
  placeholder,
  onSubmit,
  submitLabel,
  busy,
  disabled,
  onKeyDown,
}: Props) {
  return (
    <div className={styles.composer}>
      <div className={kind === "textarea" ? styles.field : `${styles.field} ${styles.fieldRow}`}>
        {kind === "textarea" ? (
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            rows={3}
            disabled={busy || disabled}
            onKeyDown={onKeyDown}
          />
        ) : (
          <input
            className={styles.topicInput}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            disabled={busy || disabled}
          />
        )}
        <button
          type="button"
          className={styles.sendBtn}
          disabled={busy || disabled || !value.trim()}
          onClick={onSubmit}
        >
          {busy ? "处理中…" : submitLabel}
        </button>
      </div>
    </div>
  );
}
