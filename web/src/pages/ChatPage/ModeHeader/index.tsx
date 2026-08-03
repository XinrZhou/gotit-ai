import { PatrickAvatar, SandyAvatar, SquidwardAvatar } from "../../../components/Avatars";
import type { Mode } from "../../../types";
import styles from "./index.module.scss";

const LABELS: Record<
  Exclude<Mode, "chat">,
  { title: string; hint: string; avatar: "squid" | "patrick" | "sandy" }
> = {
  examine: { title: "考我", hint: "过了 / 还差点 / 欠着下次", avatar: "squid" },
  teach: { title: "回讲", hint: "讲不清就追问 · 同一套门禁", avatar: "patrick" },
  drill: {
    title: "项目深挖",
    hint: "练习场 · 不过门 · 不算掌握",
    avatar: "sandy",
  },
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
