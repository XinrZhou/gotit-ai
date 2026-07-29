import { PatrickAvatar, SandyAvatar, SquidwardAvatar } from "../../../components/Avatars";
import type { Mode } from "../../../types";
import styles from "./index.module.scss";

const LABELS: Record<Exclude<Mode, "chat">, { title: string; avatar: "squid" | "patrick" | "sandy" }> = {
  examine: { title: "考我", avatar: "squid" },
  teach: { title: "回讲", avatar: "patrick" },
  drill: { title: "项目深挖", avatar: "sandy" },
};

type Props = {
  mode: Exclude<Mode, "chat">;
  onBack: () => void;
  examineCount?: number;
};

export function ModeHeader({ mode, onBack, examineCount }: Props) {
  const meta = LABELS[mode];
  const avatar =
    meta.avatar === "squid" ? (
      <SquidwardAvatar />
    ) : meta.avatar === "patrick" ? (
      <PatrickAvatar />
    ) : (
      <SandyAvatar />
    );

  return (
    <div className={styles.header}>
      <button type="button" className={styles.back} onClick={onBack}>
        ← 搭子
      </button>
      <div className={styles.current}>
        <span className={styles.avatar}>{avatar}</span>
        <span className={styles.title}>
          {meta.title}
          {mode === "examine" && examineCount !== undefined ? ` · ${examineCount}` : ""}
        </span>
      </div>
    </div>
  );
}
