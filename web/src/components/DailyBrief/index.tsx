import type { Claim } from "../../types";
import { claimVerifyCta } from "../../lib/checkRouting";
import { dueReasonLine, stripHtml } from "../../lib/format";
import { planOpenItems } from "../../lib/owed";
import { useStore } from "../../store";
import styles from "./index.module.scss";

type Props = {
  onExamineClaim: (claim: Claim) => void;
  onViewAll?: () => void;
  variant?: "home" | "thread";
  maxItems?: number;
};

function cleanTitle(raw: string): string {
  return stripHtml(raw).replace(/\s+/g, " ").trim();
}

type PlanRow = {
  id: string;
  title: string;
  status: string;
  claim_id: string | null;
  topic: string | null;
  project_id?: string | null;
  due_reason_code?: string | null;
  due_reason_text?: string | null;
};

function claimFromPlan(item: PlanRow, dueClaims: Claim[]): Claim | null {
  if (!item.claim_id) return null;
  const found = dueClaims.find((c) => c.id === item.claim_id);
  if (found) return found;
  return {
    id: item.claim_id,
    text: item.title,
    status: item.status,
    topic: item.topic,
    source_note_id: null,
    next_review_at: null,
    project_id: item.project_id ?? null,
    due_reason_code: item.due_reason_code ?? "plan_open",
    due_reason_text: item.due_reason_text ?? "今日计划",
  };
}

/** Plan-open rows: prefer server reason on the plan item. */
function planOpenReason(item: PlanRow, claim: Claim): string {
  const fromPlan = item.due_reason_text?.trim();
  if (fromPlan) return fromPlan;
  return dueReasonLine(claim) || "今日计划";
}

type Row = {
  key: string;
  label: string;
  reason: string | null;
  lesson: string | null;
  cta: string;
  onOpen: () => void;
};

/** Today's owed (due + plan-open) — notes are not「欠」. */
export function DailyBrief({
  onExamineClaim,
  onViewAll,
  variant = "home",
  maxItems = 4,
}: Props) {
  const { dueClaims, items, busy } = useStore();

  const owedIds = new Set(dueClaims.map((c) => c.id));
  const planOpen = planOpenItems(items as PlanRow[], owedIds);

  const seen = new Set<string>();
  const rows: Row[] = [];

  const push = (
    key: string,
    label: string,
    reason: string | null,
    lesson: string | null,
    cta: string,
    onOpen: () => void,
  ) => {
    if (rows.length >= maxItems || !label) return;
    const norm = label.toLowerCase().slice(0, 96);
    if (seen.has(norm)) return;
    seen.add(norm);
    rows.push({ key, label, reason, lesson, cta, onOpen });
  };

  for (const c of dueClaims) {
    push(
      `due-${c.id}`,
      cleanTitle(c.text),
      dueReasonLine(c),
      c.failure_hint?.trim() || null,
      claimVerifyCta(c),
      () => onExamineClaim(c),
    );
  }
  for (const item of planOpen) {
    const claim = claimFromPlan(item, dueClaims);
    if (!claim) continue;
    push(
      `plan-${item.id}`,
      cleanTitle(item.title),
      planOpenReason(item, claim),
      claim.failure_hint?.trim() || null,
      claimVerifyCta(claim),
      () => onExamineClaim(claim),
    );
  }

  if (rows.length === 0) return null;

  const total = dueClaims.length + planOpen.length;
  const more = Math.max(0, total - rows.length);
  const allCount = more + rows.length;

  return (
    <section
      className={`${styles.brief} ${variant === "thread" ? styles.thread : styles.home}`}
      aria-label="今日欠账"
    >
      <header className={styles.head}>
        <div className={styles.headText}>
          <h2 className={styles.headTitle}>今天还欠这些</h2>
          <p className={styles.headSub}>从下面挑一条开考，过关才算会</p>
        </div>
        {more > 0 && onViewAll ? (
          <button
            type="button"
            className={styles.headAction}
            disabled={busy}
            onClick={onViewAll}
          >
            全部 {allCount}
          </button>
        ) : (
          <span className={styles.headCount}>{allCount}</span>
        )}
      </header>

      <ul className={styles.list}>
        {rows.map((r, i) => {
          const metaTitle = [r.reason, r.lesson].filter(Boolean).join(" · ");
          return (
            <li key={r.key}>
              <button
                type="button"
                className={`${styles.row}${i === 0 ? ` ${styles.rowPrimary}` : ""}`}
                disabled={busy}
                onClick={r.onOpen}
              >
                <span className={styles.rowBody}>
                  <span className={styles.title} title={r.label}>
                    {r.label}
                  </span>
                  {metaTitle ? (
                    <span className={styles.meta} title={metaTitle}>
                      {r.reason ? <span>{r.reason}</span> : null}
                      {r.reason && r.lesson ? " · " : null}
                      {r.lesson ? (
                        <span className={styles.metaLesson}>{r.lesson}</span>
                      ) : null}
                    </span>
                  ) : null}
                </span>
                <span className={styles.cta}>{r.cta}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
