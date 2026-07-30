import type { MasteryVerdict, VerifyPath } from "../../types";
import { isMasteryVerdict } from "../VerifyVerdict";
import styles from "./index.module.scss";

const STEP_LABEL: Record<"examine" | "recheck" | "gate", string> = {
  examine: "考",
  recheck: "核",
  gate: "门",
};

const VERDICT_SHORT: Record<MasteryVerdict, string> = {
  passed: "过了",
  almost: "还差点",
  owe_next: "欠着",
};

type Props = {
  path: VerifyPath;
};

/** Quiet 考→核→门 step row — structured verify path, not bubble parse. */
export function VerifyTrajectory({ path }: Props) {
  const steps: { key: "examine" | "recheck" | "gate"; v: MasteryVerdict }[] = [
    { key: "examine", v: path.examine_verdict },
    { key: "recheck", v: path.recheck_verdict },
    { key: "gate", v: path.gate_verdict },
  ];
  if (!steps.every((s) => isMasteryVerdict(s.v))) return null;
  return (
    <div className={styles.row} title={path.gate?.reason || "考 → 核 → 门"}>
      {steps.map((s, i) => (
        <span key={s.key} className={styles.step}>
          {i > 0 ? <span className={styles.arrow} aria-hidden>
            →
          </span> : null}
          <span className={styles.label}>{STEP_LABEL[s.key]}</span>
          <span className={`${styles.chip} ${styles[s.v]}`}>
            {VERDICT_SHORT[s.v]}
          </span>
        </span>
      ))}
    </div>
  );
}

export function verifyPathFromMeta(
  meta: Record<string, unknown> | null | undefined,
): VerifyPath | null {
  if (!meta) return null;
  const examine = meta.examine_verdict;
  const recheck = meta.recheck_verdict;
  const gate = meta.gate_verdict ?? meta.verdict;
  if (
    !isMasteryVerdict(examine) ||
    !isMasteryVerdict(recheck) ||
    !isMasteryVerdict(gate)
  ) {
    return null;
  }
  const gateObj = meta.gate;
  return {
    examine_verdict: examine,
    recheck_verdict: recheck,
    gate_verdict: gate,
    gate:
      gateObj && typeof gateObj === "object"
        ? (gateObj as VerifyPath["gate"])
        : undefined,
  };
}
