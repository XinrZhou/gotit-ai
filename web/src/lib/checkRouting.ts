import type { Claim, CheckMode } from "../types";

/** Effective verify form — mirrors ``gotit.core.check_routing``. */
export function resolveCheckMode(claim: Pick<
  Claim,
  "preferred_check_mode" | "project_id"
>): CheckMode {
  const p = claim.preferred_check_mode ?? null;
  if (p === "teach_back") return "teach_back";
  if (p === "drill" && claim.project_id) return "drill";
  return "probe";
}

export function verifyCtaLabel(mode: CheckMode): string {
  if (mode === "teach_back") return "回讲";
  if (mode === "drill") return "练深挖";
  return "开考";
}

export function claimVerifyCta(claim: Pick<
  Claim,
  "preferred_check_mode" | "project_id"
>): string {
  return verifyCtaLabel(resolveCheckMode(claim));
}
