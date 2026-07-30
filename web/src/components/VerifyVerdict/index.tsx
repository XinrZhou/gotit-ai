import type { MasteryVerdict } from "../../types";
import styles from "./index.module.scss";

const LABELS: Record<MasteryVerdict, string> = {
  passed: "过了",
  almost: "还差点",
  owe_next: "欠着下次",
};

/** Quiet companion note beside non-pass chips — honest, not pep talk. */
const SIDE_HINT: Partial<Record<MasteryVerdict, string>> = {
  almost: "下次再碰",
  owe_next: "下次还会碰到",
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
  const side = SIDE_HINT[verdict];
  return (
    <div className={styles.wrap}>
      <span className={`${styles.chip} ${styles[verdict]}`}>{LABELS[verdict]}</span>
      {side ? <span className={styles.side}>{side}</span> : null}
      {sessionDone ? <span className={styles.session}>这轮考完了</span> : null}
    </div>
  );
}
