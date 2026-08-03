import type { MasteryVerdict, VerifyOutcome, VerifyWriteback } from "../types";

function isMasteryVerdict(v: unknown): v is MasteryVerdict {
  return v === "passed" || v === "almost" || v === "owe_next";
}

function fmtReviewDay(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  return `${parseInt(m[2], 10)} 月 ${parseInt(m[3], 10)} 日`;
}

/** One quiet line: how this gate writeback changes the path. */
export function verifyImpactLine(outcome: VerifyOutcome): string {
  const v = outcome.gate_verdict;
  const wb = outcome.writeback;
  const reason = wb?.schedule_reason ?? null;
  const interval = wb?.interval_days;
  const next = wb?.claim?.next_review_at ?? null;
  const day = fmtReviewDay(next);

  if (v === "passed") {
    return "这条先清了 — 今天不再欠它";
  }
  if (v === "almost" || reason === "almost_today") {
    return "今天还接着 — 这条仍在今日欠账";
  }
  if (typeof interval === "number" && interval > 0) {
    return day
      ? `约 ${interval} 天后（${day}）再考`
      : `约 ${interval} 天后再考`;
  }
  if (day) return `${day} 再考`;
  return "下次还会碰到";
}

/** Prefer deterministic gate.reason; keep short. */
export function verifyWhyLine(outcome: VerifyOutcome): string | null {
  const raw = outcome.gate_reason?.trim();
  if (!raw) return null;
  // Gate reasons are already Chinese; trim signal suffix noise for UI.
  const cut = raw.length > 120 ? `${raw.slice(0, 118)}…` : raw;
  return cut;
}

export function outcomeFromWire(args: {
  gate_verdict: unknown;
  gate_reason?: string | null;
  writeback?: VerifyWriteback | null;
  claim_id?: string | null;
  claim_label?: string | null;
}): VerifyOutcome | null {
  if (!isMasteryVerdict(args.gate_verdict)) return null;
  const claim = args.writeback?.claim;
  return {
    gate_verdict: args.gate_verdict,
    gate_reason: args.gate_reason ?? null,
    writeback: args.writeback ?? null,
    claim_id: args.claim_id ?? claim?.id ?? null,
    claim_label: args.claim_label ?? claim?.text ?? null,
  };
}

export function gateReasonFromVerify(verify: {
  gate?: { reason?: string } | null;
} | null | undefined): string | null {
  const r = verify?.gate?.reason;
  return typeof r === "string" && r.trim() ? r.trim() : null;
}
