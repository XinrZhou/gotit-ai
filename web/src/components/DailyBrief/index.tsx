import type { Claim, PlanItem } from "../../types";
import { stripHtml } from "../../lib/format";
import { useStore } from "../../store";
import styles from "./index.module.scss";

type Props = {
  onExamineClaim: (claim: Claim) => void;
  onExamineNoteId?: (noteId: string) => void;
  onViewAll?: () => void;
  variant?: "home" | "thread";
  maxItems?: number;
};

function cleanTitle(raw: string): string {
  return stripHtml(raw).replace(/\s+/g, " ").trim();
}

function claimFromPlan(item: PlanItem, dueClaims: Claim[]): Claim | null {
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
  };
}

type Row = {
  key: string;
  label: string;
  onOpen: () => void;
};

/** Home brief: today's owed/plan — click a row to examine. */
export function DailyBrief({
  onExamineClaim,
  onExamineNoteId,
  onViewAll,
  variant = "home",
  maxItems = 4,
}: Props) {
  const { dueClaims, items, notes, busy } = useStore();

  const owedIds = new Set(dueClaims.map((c) => c.id));
  const planOpen = items.filter(
    (i) =>
      i.status !== "verified" &&
      i.claim_id &&
      !owedIds.has(i.claim_id),
  );
  const noteEntries =
    variant === "home" && onExamineNoteId
      ? notes.filter((n) => n.claim_ids.length > 0)
      : [];

  const seen = new Set<string>();
  const rows: Row[] = [];

  const push = (key: string, label: string, onOpen: () => void) => {
    if (rows.length >= maxItems || !label) return;
    const norm = label.toLowerCase().slice(0, 96);
    if (seen.has(norm)) return;
    seen.add(norm);
    rows.push({ key, label, onOpen });
  };

  for (const c of dueClaims) {
    push(`due-${c.id}`, cleanTitle(c.text), () => onExamineClaim(c));
  }
  for (const item of planOpen) {
    const claim = claimFromPlan(
      {
        id: item.id,
        title: item.title,
        source: "manual",
        status: item.status,
        claim_id: item.claim_id,
        sort_order: 0,
        due_at: null,
        due_time: null,
        project_id: null,
        topic: item.topic,
      },
      dueClaims,
    );
    if (!claim) continue;
    push(`plan-${item.id}`, cleanTitle(item.title), () => onExamineClaim(claim));
  }
  for (const n of noteEntries) {
    push(
      `note-${n.id}`,
      cleanTitle(n.title?.trim() || n.excerpt || "未命名笔记"),
      () => onExamineNoteId?.(n.id),
    );
  }

  if (rows.length === 0) return null;

  const total = dueClaims.length + planOpen.length + noteEntries.length;
  const more = Math.max(0, total - rows.length);
  const allCount = more + rows.length;

  return (
    <div
      className={`${styles.brief} ${variant === "thread" ? styles.thread : styles.home}`}
    >
      <div className={styles.head}>
        <h2 className={styles.headTitle}>今天练这些</h2>
        <p className={styles.headHint}>过了才算</p>
      </div>

      <ul className={styles.list}>
        {rows.map((r) => (
          <li key={r.key}>
            <button
              type="button"
              className={styles.rowBtn}
              disabled={busy}
              onClick={r.onOpen}
            >
              <span className={styles.title} title={r.label}>
                {r.label}
              </span>
              <span className={styles.cta}>开考</span>
            </button>
          </li>
        ))}
      </ul>

      {more > 0 && onViewAll ? (
        <button
          type="button"
          className={styles.moreBtn}
          disabled={busy}
          onClick={onViewAll}
        >
          <span>查看全部</span>
          <span className={styles.moreMeta}>{allCount} →</span>
        </button>
      ) : null}
    </div>
  );
}
