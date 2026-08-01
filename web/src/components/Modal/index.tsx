import type { ReactNode } from "react";
import styles from "./index.module.scss";

type ModalProps = {
  title?: ReactNode;
  onClose: () => void;
  children?: ReactNode;
  actions?: ReactNode;
  wide?: boolean;
  /** Near-viewport shell for writing / preview (overrides wide width). */
  fill?: boolean;
  /** Children own padding/layout (e.g. settings split pane). */
  flush?: boolean;
  /** Flush split panes: hide title row, float close over content. */
  titleless?: boolean;
};

export function Modal({
  title,
  onClose,
  children,
  actions,
  wide,
  fill,
  flush,
  titleless,
}: ModalProps) {
  const shell = [
    styles.modal,
    wide && !fill ? styles.modalWide : "",
    fill ? styles.modalFill : "",
    flush ? styles.modalFlush : "",
    titleless ? styles.modalTitleless : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={shell} onClick={(e) => e.stopPropagation()}>
        {titleless ? (
          <button
            type="button"
            className={styles.modalCloseFloat}
            aria-label="关闭"
            onClick={onClose}
          >
            ×
          </button>
        ) : (
          <div className={styles.modalHead}>
            <div className={styles.modalTitle}>{title}</div>
            <button
              type="button"
              className={styles.modalClose}
              aria-label="关闭"
              onClick={onClose}
            >
              ×
            </button>
          </div>
        )}
        {children ? <div className={styles.modalBody}>{children}</div> : null}
        {actions ? <div className={styles.modalActions}>{actions}</div> : null}
      </div>
    </div>
  );
}
