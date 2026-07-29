import type { ReactNode } from "react";
import styles from "./index.module.scss";

type ModalProps = {
  title: ReactNode;
  onClose: () => void;
  children?: ReactNode;
  actions?: ReactNode;
  wide?: boolean;
  /** Children own padding/layout (e.g. settings split pane). */
  flush?: boolean;
};

export function Modal({ title, onClose, children, actions, wide, flush }: ModalProps) {
  const shell = [
    styles.modal,
    wide ? styles.modalWide : "",
    flush ? styles.modalFlush : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={shell} onClick={(e) => e.stopPropagation()}>
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
        {children ? <div className={styles.modalBody}>{children}</div> : null}
        {actions ? <div className={styles.modalActions}>{actions}</div> : null}
      </div>
    </div>
  );
}
