import { PatrickAvatar, SandyAvatar, SquidwardAvatar } from "../Avatars";
import type { ReactNode } from "react";
import type { Mode } from "../../types";
import styles from "./index.module.scss";

type Props = {
  mode: Mode;
  onChange: (m: Mode) => void;
  examineCount: number;
};

export function SegmentedTabs({ mode, onChange, examineCount }: Props) {
  const tab = (id: Mode, label: string, avatar: ReactNode, count?: number) => (
    <button
      type="button"
      className={mode === id ? `${styles.tab} ${styles.active}` : styles.tab}
      onClick={() => onChange(id)}
    >
      <span className={styles.avatar}>{avatar}</span>
      {label}
      {count !== undefined ? ` · ${count}` : ""}
    </button>
  );

  return (
    <div className={styles.segmented}>
      {tab("examine", "考我", <SquidwardAvatar />, examineCount)}
      {tab("teach", "回讲", <PatrickAvatar />)}
      {tab("drill", "项目深挖", <SandyAvatar />)}
    </div>
  );
}
