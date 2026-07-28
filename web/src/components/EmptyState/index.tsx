import type { ReactNode } from "react";
import styles from "./index.module.scss";

type Props = {
  avatar: ReactNode;
  children: ReactNode;
};

export function EmptyState({ avatar, children }: Props) {
  return (
    <div className={styles.wrap}>
      <div className={styles.avatar}>{avatar}</div>
      <div className={styles.text}>{children}</div>
    </div>
  );
}
