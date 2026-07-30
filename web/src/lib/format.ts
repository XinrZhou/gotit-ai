export function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Parse API datetimes. SQLite/naive ISO (`2026-07-30T01:25:28`) is UTC wall
 * clock without offset — treat as UTC so local (e.g. Asia/Shanghai +8) is correct.
 */
export function parseApiDate(iso: string): Date {
  const s = iso.trim();
  if (!s) return new Date(NaN);
  if (/[zZ]$|[+-]\d{2}:\d{2}$/.test(s)) return new Date(s);
  // date-only stays calendar day; datetime without offset → UTC
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return new Date(`${s}T00:00:00Z`);
  return new Date(s.endsWith("Z") ? s : `${s}Z`);
}

export function stripHtml(html: string): string {
  return html
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Quiet one-line why a claim is owed today.
 * Prefer server `due_reason_text`; soft fallback only — never invent formulas.
 */
export function dueReasonLine(claim: {
  due_reason_text?: string | null;
  status?: string;
  next_review_at?: string | null;
}): string | null {
  const text = claim.due_reason_text?.trim();
  if (text) return text;
  const status = (claim.status || "").toLowerCase();
  if (status === "in_progress") return "上次还差点，今天接着练";
  if (claim.next_review_at) return "按计划该复习";
  return null;
}

export function fmtDate(iso: string): string {
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return iso;
  return `${parseInt(m[2], 10)} 月 ${parseInt(m[3], 10)} 日`;
}
