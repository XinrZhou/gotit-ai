import type { Claim } from "../types";

/** Minimal plan row for owed math (store may omit full PlanItem fields). */
export type PlanOpenSource = {
  status: string;
  claim_id: string | null;
};

/** Today's plan items with a claim that are not yet verified and not already in due. */
export function planOpenItems<T extends PlanOpenSource>(
  items: T[],
  dueClaimIds: Set<string>,
): T[] {
  return items.filter(
    (i) =>
      i.status !== "verified" &&
      Boolean(i.claim_id) &&
      !dueClaimIds.has(i.claim_id!),
  );
}

/**
 * True owed for DailyBrief: due ∪ plan-open.
 * Notes with claims are library availability — not owed.
 */
export function countOwed(
  dueClaims: Claim[],
  items: PlanOpenSource[],
): number {
  const dueIds = new Set(dueClaims.map((c) => c.id));
  return dueClaims.length + planOpenItems(items, dueIds).length;
}

export function hasOwedForBrief(
  dueClaims: Claim[],
  items: PlanOpenSource[],
): boolean {
  return countOwed(dueClaims, items) > 0;
}
