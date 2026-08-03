import type {
  CompanionToolCall,
  OpenDrillPayload,
  OpenExaminePayload,
  OpenTeachPayload,
} from "../../../types";
import styles from "./index.module.scss";

const TOOL_LABEL: Record<string, string> = {
  get_today: "今日",
  list_due_claims: "欠账",
  start_examine: "开考准备",
  start_verify: "开练准备",
  start_drill: "练习准备",
  get_failure_lessons: "教训",
  add_memory: "记下",
  get_upcoming_interview: "面试",
  close_day: "收工",
};

function labelFor(name: string): string {
  return TOOL_LABEL[name] ?? name;
}

function isOpenExamine(v: unknown): v is OpenExaminePayload {
  if (!v || typeof v !== "object") return false;
  const o = v as OpenExaminePayload;
  return Boolean(o.claim_id || o.note_id);
}

function isOpenTeach(v: unknown): v is OpenTeachPayload {
  if (!v || typeof v !== "object") return false;
  const o = v as OpenTeachPayload;
  return o.action === "open_teach" || Boolean(o.claim_id);
}

function isOpenDrill(v: unknown): v is OpenDrillPayload {
  if (!v || typeof v !== "object") return false;
  const o = v as OpenDrillPayload;
  return o.action === "open_drill" || Boolean(o.round);
}

/** Quiet companion tool chips + optional one-tap 开考 / 回讲 / 练深挖. */
export function CompanionToolTrail({
  calls,
  onOpenExamine,
  onOpenTeach,
  onOpenDrill,
  busy = false,
}: {
  calls: CompanionToolCall[];
  onOpenExamine?: (payload: OpenExaminePayload) => void;
  onOpenTeach?: (payload: OpenTeachPayload) => void;
  onOpenDrill?: (payload: OpenDrillPayload) => void;
  busy?: boolean;
}) {
  if (!calls.length) return null;

  const examine =
    [...calls]
      .reverse()
      .find((c) => c.ok && isOpenExamine(c.open_examine))?.open_examine ?? null;
  const teach =
    [...calls]
      .reverse()
      .find((c) => c.ok && isOpenTeach(c.open_teach))?.open_teach ?? null;
  const drill =
    [...calls]
      .reverse()
      .find((c) => c.ok && isOpenDrill(c.open_drill))?.open_drill ?? null;

  return (
    <div className={styles.wrap}>
      {calls.map((c, i) => (
        <span
          key={`${c.name}-${i}`}
          className={`${styles.chip} ${c.ok ? "" : styles.fail}`}
          title={c.summary || c.args_digest || c.name}
        >
          {labelFor(c.name)}
        </span>
      ))}
      {examine && onOpenExamine ? (
        <button
          type="button"
          className={styles.cta}
          disabled={busy}
          onClick={() => onOpenExamine(examine)}
        >
          开考
        </button>
      ) : null}
      {teach && onOpenTeach ? (
        <button
          type="button"
          className={styles.cta}
          disabled={busy}
          onClick={() => onOpenTeach(teach)}
        >
          回讲
        </button>
      ) : null}
      {drill && onOpenDrill ? (
        <button
          type="button"
          className={styles.cta}
          disabled={busy}
          onClick={() => onOpenDrill(drill)}
          title="练习场 · 不过门 · 不算掌握"
        >
          练深挖
        </button>
      ) : null}
    </div>
  );
}

export function toolCallsFromMeta(
  meta: Record<string, unknown> | null | undefined,
): CompanionToolCall[] | null {
  if (!meta) return null;
  const raw = meta.tool_calls;
  if (!Array.isArray(raw) || raw.length === 0) return null;
  const out: CompanionToolCall[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const o = item as Record<string, unknown>;
    if (typeof o.name !== "string") continue;
    out.push({
      name: o.name,
      args_digest: typeof o.args_digest === "string" ? o.args_digest : "",
      ok: Boolean(o.ok),
      summary: typeof o.summary === "string" ? o.summary : "",
      open_examine: isOpenExamine(o.open_examine) ? o.open_examine : null,
      open_teach: isOpenTeach(o.open_teach) ? o.open_teach : null,
      open_drill: isOpenDrill(o.open_drill) ? o.open_drill : null,
    });
  }
  return out.length ? out : null;
}
