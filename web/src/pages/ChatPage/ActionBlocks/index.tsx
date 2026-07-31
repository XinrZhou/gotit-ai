import type {
  ActionBlock,
  ActionBlockAction,
  MasteryVerdict,
  OpenDrillPayload,
  OpenExaminePayload,
} from "../../../types";
import { isMasteryVerdict } from "../../../components/VerifyVerdict";
import styles from "./index.module.scss";

const ACTION_BLOCKS_CAP = 5;

const VERDICT_LABEL: Record<MasteryVerdict, string> = {
  passed: "过了",
  almost: "还差点",
  owe_next: "欠着下次",
};

function isAction(v: unknown): v is ActionBlockAction {
  if (!v || typeof v !== "object") return false;
  const o = v as ActionBlockAction;
  return typeof o.id === "string" && typeof o.label === "string";
}

function parseBlock(raw: unknown): ActionBlock | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const actions = Array.isArray(o.actions)
    ? o.actions.filter(isAction)
    : [];
  if (o.type === "owed_claim" && typeof o.claim_id === "string") {
    const title = typeof o.title === "string" ? o.title.trim() : "";
    if (!title) return null;
    return {
      type: "owed_claim",
      claim_id: o.claim_id,
      title,
      due_reason_text:
        typeof o.due_reason_text === "string" ? o.due_reason_text : null,
      actions,
    };
  }
  if (o.type === "verdict" && isMasteryVerdict(o.gate_verdict)) {
    return {
      type: "verdict",
      gate_verdict: o.gate_verdict,
      claim_id: typeof o.claim_id === "string" ? o.claim_id : undefined,
      actions,
    };
  }
  return null;
}

/** Parse + cap ``metadata.action_blocks`` for bubble render. */
export function actionBlocksFromMeta(
  meta: Record<string, unknown> | null | undefined,
): ActionBlock[] | null {
  if (!meta) return null;
  const raw = meta.action_blocks;
  if (!Array.isArray(raw) || raw.length === 0) return null;
  const out: ActionBlock[] = [];
  for (const item of raw) {
    const block = parseBlock(item);
    if (!block) continue;
    out.push(block);
    if (out.length >= ACTION_BLOCKS_CAP) break;
  }
  return out.length ? out : null;
}

export function ActionBlocks({
  blocks,
  onOpenExamine,
  onOpenDrill,
  busy = false,
}: {
  blocks: ActionBlock[];
  onOpenExamine?: (payload: OpenExaminePayload) => void;
  onOpenDrill?: (payload: OpenDrillPayload) => void;
  busy?: boolean;
}) {
  if (!blocks.length) return null;

  const runAction = (block: ActionBlock, action: ActionBlockAction) => {
    if (action.id === "start_examine" && onOpenExamine) {
      if (block.type === "owed_claim") {
        onOpenExamine({
          claim_id: block.claim_id,
          claim_text: block.title,
        });
        return;
      }
      if (block.type === "verdict" && block.claim_id) {
        onOpenExamine({ claim_id: block.claim_id });
      }
      return;
    }
    if (action.id === "start_drill" && onOpenDrill) {
      onOpenDrill({ action: "open_drill" });
    }
  };

  return (
    <div className={styles.wrap}>
      {blocks.map((block, i) => {
        if (block.type === "owed_claim") {
          const key = `owed-${block.claim_id}-${i}`;
          const primary =
            block.actions.find((a) => a.id === "start_examine") ??
            block.actions[0];
          return (
            <div key={key} className={styles.card}>
              <div className={styles.body}>
                <div className={styles.title}>{block.title}</div>
                {block.due_reason_text ? (
                  <div className={styles.reason}>{block.due_reason_text}</div>
                ) : null}
              </div>
              {primary ? (
                <button
                  type="button"
                  className={styles.cta}
                  disabled={busy}
                  onClick={() => runAction(block, primary)}
                >
                  {primary.label}
                </button>
              ) : null}
            </div>
          );
        }
        const key = `verdict-${block.gate_verdict}-${block.claim_id ?? i}`;
        return (
          <div key={key} className={styles.card}>
            <div className={styles.body}>
              <div className={styles.verdictRow}>
                <span
                  className={`${styles.verdictChip} ${styles[block.gate_verdict]}`}
                >
                  {VERDICT_LABEL[block.gate_verdict]}
                </span>
              </div>
            </div>
            {block.actions.map((action) => (
              <button
                key={action.id}
                type="button"
                className={styles.cta}
                disabled={busy}
                onClick={() => runAction(block, action)}
              >
                {action.label}
              </button>
            ))}
          </div>
        );
      })}
    </div>
  );
}
