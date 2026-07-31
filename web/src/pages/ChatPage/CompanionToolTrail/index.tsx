import type { CompanionToolCall, OpenExaminePayload } from "../../../types";
import styles from "./index.module.scss";

const TOOL_LABEL: Record<string, string> = {
  get_today: "今日",
  list_due_claims: "欠账",
  start_examine: "开考准备",
  get_failure_lessons: "教训",
  add_memory: "记下",
  get_upcoming_interview: "面试",
};

function labelFor(name: string): string {
  return TOOL_LABEL[name] ?? name;
}

function isOpenExamine(v: unknown): v is OpenExaminePayload {
  if (!v || typeof v !== "object") return false;
  const o = v as OpenExaminePayload;
  return Boolean(o.claim_id || o.note_id);
}

/** Quiet companion tool chips + optional one-tap 开考. */
export function CompanionToolTrail({
  calls,
  onOpenExamine,
  busy = false,
}: {
  calls: CompanionToolCall[];
  onOpenExamine?: (payload: OpenExaminePayload) => void;
  busy?: boolean;
}) {
  if (!calls.length) return null;

  const open =
    [...calls]
      .reverse()
      .find((c) => c.ok && isOpenExamine(c.open_examine))?.open_examine ?? null;

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
      {open && onOpenExamine ? (
        <button
          type="button"
          className={styles.cta}
          disabled={busy}
          onClick={() => onOpenExamine(open)}
        >
          开考
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
    });
  }
  return out.length ? out : null;
}

export function openExamineFromMeta(
  meta: Record<string, unknown> | null | undefined,
): OpenExaminePayload | null {
  if (!meta) return null;
  if (isOpenExamine(meta.open_examine)) return meta.open_examine;
  const calls = toolCallsFromMeta(meta);
  if (!calls) return null;
  for (let i = calls.length - 1; i >= 0; i--) {
    const c = calls[i];
    if (c.ok && isOpenExamine(c.open_examine)) return c.open_examine;
  }
  return null;
}
