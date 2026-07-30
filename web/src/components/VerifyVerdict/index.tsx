import type { MasteryVerdict } from "../../types";
import styles from "./index.module.scss";

const LABELS: Record<MasteryVerdict, string> = {
  passed: "过了",
  almost: "还差点",
  owe_next: "欠着下次",
};

export function isMasteryVerdict(v: unknown): v is MasteryVerdict {
  return v === "passed" || v === "almost" || v === "owe_next";
}

type Props = {
  verdict: MasteryVerdict;
  sessionDone?: boolean;
};

/** Quiet Apple chip for examine mastery outcomes — not an ink pill. */
export function VerifyVerdictChip({ verdict, sessionDone }: Props) {
  return (
    <div className={styles.wrap}>
      <span className={`${styles.chip} ${styles[verdict]}`}>{LABELS[verdict]}</span>
      {sessionDone ? <span className={styles.session}>本主题考完</span> : null}
    </div>
  );
}
