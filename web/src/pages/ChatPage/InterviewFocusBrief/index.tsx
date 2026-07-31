import type { InterviewFocusHint, OpenDrillPayload } from "../../../types";
import styles from "./index.module.scss";

type Props = {
  focus: InterviewFocusHint;
  busy?: boolean;
  /** After day close — quiet text link only. */
  quiet?: boolean;
  onOpenDrill: (payload: OpenDrillPayload) => void;
};

/** Quiet interview→drill hint for empty chat / today's brief. */
export function InterviewFocusBrief({
  focus,
  busy,
  quiet,
  onOpenDrill,
}: Props) {
  const featured = !quiet && focus.prominence === "featured";
  const label = quiet
    ? `抠一下「${focus.project_name?.trim() || "简历项目"}」`
    : "深挖";

  return (
    <section
      className={`${styles.focus} ${featured ? styles.featured : styles.quiet} ${quiet ? styles.closed : ""}`}
      aria-label="面试深挖建议"
    >
      {!quiet ? <p className={styles.prompt}>{focus.prompt}</p> : null}
      <button
        type="button"
        className={quiet ? styles.link : styles.cta}
        disabled={busy}
        onClick={() => onOpenDrill(focus.open_drill)}
      >
        {label}
      </button>
    </section>
  );
}
