import type { VerifyOutcome } from "../../types";
import { verifyImpactLine, verifyWhyLine } from "../../lib/verifyOutcome";
import { isMasteryVerdict, VerifyVerdictChip } from "../VerifyVerdict";
import styles from "./index.module.scss";

type Props = {
  outcome: VerifyOutcome;
  busy?: boolean;
  onBackToToday: () => void;
  /** almost only — re-open same claim. */
  onContinue?: () => void;
};

/**
 * Quiet post-verify bar: result already on chips above; here = impact + CTA.
 * No new domain state — only surfaces writeback / gate.reason.
 */
export function VerifyDoneBar({
  outcome,
  busy,
  onBackToToday,
  onContinue,
}: Props) {
  if (!isMasteryVerdict(outcome.gate_verdict)) return null;
  const why = verifyWhyLine(outcome);
  const impact = verifyImpactLine(outcome);
  const showContinue =
    outcome.gate_verdict === "almost" && typeof onContinue === "function";

  return (
    <section className={styles.bar} aria-label="本轮结果">
      <div className={styles.head}>
        <VerifyVerdictChip verdict={outcome.gate_verdict} sessionDone />
      </div>
      {why ? <p className={styles.why}>{why}</p> : null}
      <p className={styles.impact}>{impact}</p>
      <div className={styles.actions}>
        <button
          type="button"
          className={styles.primary}
          disabled={busy}
          onClick={onBackToToday}
        >
          回今天
        </button>
        {showContinue ? (
          <button
            type="button"
            className={styles.secondary}
            disabled={busy}
            onClick={onContinue}
          >
            接着练
          </button>
        ) : null}
      </div>
    </section>
  );
}
