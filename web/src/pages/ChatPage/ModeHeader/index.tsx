import { PatrickAvatar, SandyAvatar, SquidwardAvatar } from "../../../components/Avatars";
import type { Mode } from "../../../types";
import styles from "./index.module.scss";

const LABELS: Record<
  Exclude<Mode, "chat">,
  { title: string; hint: string; avatar: "squid" | "patrick" | "sandy" }
> = {
  examine: { title: "考我", hint: "过了 / 还差点 / 欠着", avatar: "squid" },
  teach: { title: "回讲", hint: "讲不清他会追问", avatar: "patrick" },
  drill: { title: "项目深挖", hint: "按简历往下挖", avatar: "sandy" },
};

type Props = {
  mode: Exclude<Mode, "chat">;
  onBack: () => void;
};

export function ModeHeader({ mode, onBack }: Props) {
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
        <span className={styles.title}>{meta.title}</span>
        <span className={styles.sep} aria-hidden>
          ·
        </span>
        <span className={styles.hint}>{meta.hint}</span>
      </div>
    </div>
  );
}
