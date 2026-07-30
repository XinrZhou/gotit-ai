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
  /** Extra key handling; default Enter-to-send still applies unless you preventDefault. */
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
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement | HTMLInputElement>) => {
    onKeyDown?.(e);
    if (e.defaultPrevented) return;
    if (e.nativeEvent.isComposing || e.keyCode === 229) return;
    const isEnter = e.key === "Enter" || e.code === "NumpadEnter";
    if (!isEnter) return;
    if (kind === "textarea" && e.shiftKey) return; // Shift+Enter = 换行
    e.preventDefault();
    if (!busy && !disabled && value.trim()) onSubmit();
  };

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
            onKeyDown={handleKeyDown}
          />
        ) : (
          <input
            className={styles.topicInput}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            disabled={busy || disabled}
            onKeyDown={handleKeyDown}
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
