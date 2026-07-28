import styles from "./index.module.scss";

export function Toast({ error, flash }: { error: string; flash: string }) {
  if (!error && !flash) return null;
  if (error) return <div className={`${styles.toast} ${styles.error}`}>{error}</div>;
  return <div className={styles.toast}>{flash}</div>;
}
