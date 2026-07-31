import { useState } from "react";
import { api } from "../../../api";
import type {
  ActionBlock,
  BootcampView,
  DayNote,
  MasteryVerdict,
  OpenExaminePayload,
} from "../../../types";
import { ActionBlocks } from "../ActionBlocks";
import styles from "./index.module.scss";

type Props = {
  bootcamp: BootcampView;
  day: string;
  busy?: boolean;
  onStatus: (status: "in_progress" | "done" | "skipped") => Promise<void>;
  onRefresh: () => Promise<void>;
  onOpenExamine: (payload: OpenExaminePayload) => void;
  onCalibrate?: () => void;
};

const VERDICT_HINT: Record<MasteryVerdict, string> = {
  passed: "过了 — 这条就算有证据了",
  almost: "还差点 — 下次还会碰到",
  owe_next: "欠着下次 — 先记着，不急",
};

/** SessionStart first-pass guide: note → claim → examine → quiet celebrate. */
export function BootcampPanel({
  bootcamp,
  day,
  busy,
  onStatus,
  onRefresh,
  onOpenExamine,
  onCalibrate,
}: Props) {
  const [draft, setDraft] = useState("");
  const [localBusy, setLocalBusy] = useState(false);
  const working = Boolean(busy || localBusy);
  const step = bootcamp.step ?? "ingest";

  async function ingestPaste() {
    const text = draft.trim();
    if (!text || working) return;
    setLocalBusy(true);
    try {
      await onStatus("in_progress");
      const note = await api<DayNote>(`/v1/days/${day}/notes`, {
        method: "POST",
        body: JSON.stringify({
          body: `<p>${escapeHtml(text)}</p>`,
          title: null,
          tags: ["bootcamp"],
        }),
      });
      await api<unknown>(`/v1/notes/${note.id}/ingest`, {
        method: "POST",
        body: JSON.stringify({ add_plan_item: true }),
      });
      setDraft("");
      await onRefresh();
    } finally {
      setLocalBusy(false);
    }
  }

  const owedBlocks: ActionBlock[] =
    step === "verify" && bootcamp.claim_id && bootcamp.claim_text
      ? [
          {
            type: "owed_claim",
            claim_id: bootcamp.claim_id,
            title: bootcamp.claim_text,
            due_reason_text: "第一次过关",
            actions: [{ id: "start_examine", label: "开考" }],
          },
        ]
      : [];

  const verdictBlocks: ActionBlock[] =
    step === "celebrate" && bootcamp.gate_verdict
      ? [
          {
            type: "verdict",
            gate_verdict: bootcamp.gate_verdict,
            claim_id: bootcamp.claim_id ?? undefined,
            actions: [],
          },
        ]
      : [];

  return (
    <section className={styles.panel} aria-label="第一次过关">
      {step === "ingest" ? (
        <>
          <p className={styles.lead}>先拿一段笔记</p>
          <p className={styles.hint}>我们抽出能考的一句，再一起过一遍门</p>
          <textarea
            className={styles.paste}
            rows={4}
            value={draft}
            disabled={working}
            placeholder="粘贴或写一两句你刚学的…"
            onChange={(e) => setDraft(e.target.value)}
          />
          <button
            type="button"
            className={styles.primary}
            disabled={working || !draft.trim()}
            onClick={() => void ingestPaste()}
          >
            抽出能考的一句
          </button>
        </>
      ) : null}

      {step === "verify" ? (
        <>
          <p className={styles.lead}>有一句能考了</p>
          <p className={styles.hint}>开考走完整门禁；也可以先摸底一下</p>
          {owedBlocks.length ? (
            <ActionBlocks
              blocks={owedBlocks}
              busy={working}
              onOpenExamine={onOpenExamine}
            />
          ) : null}
          {onCalibrate ? (
            <button
              type="button"
              className={styles.secondary}
              disabled={working}
              onClick={onCalibrate}
            >
              先摸底一下
            </button>
          ) : null}
        </>
      ) : null}

      {step === "celebrate" ? (
        <>
          <p className={styles.lead}>第一次证据链跑通了</p>
          <p className={styles.hint}>
            {bootcamp.gate_verdict
              ? VERDICT_HINT[bootcamp.gate_verdict]
              : "结果已记下"}
          </p>
          {verdictBlocks.length ? (
            <ActionBlocks blocks={verdictBlocks} busy={working} />
          ) : null}
          <button
            type="button"
            className={styles.primary}
            disabled={working}
            onClick={() => void onStatus("done")}
          >
            好的
          </button>
        </>
      ) : null}

      {step !== "celebrate" ? (
        <button
          type="button"
          className={styles.skip}
          disabled={working}
          onClick={() => void onStatus("skipped")}
        >
          跳过
        </button>
      ) : null}
    </section>
  );
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
