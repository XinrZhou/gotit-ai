import { ChatLog } from "../../components/ChatLog";
import { Composer } from "../../components/Composer";
import { EmptyState } from "../../components/EmptyState";
import { SquidwardAvatar } from "../../components/Avatars";
import { dueReasonLine, stripHtml } from "../../lib/format";
import { useStore } from "../../store";
import type { Claim } from "../../types";
import styles from "./index.module.scss";

type PickRow =
  | {
      key: string;
      kind: "claim";
      label: string;
      reason: string | null;
      claim: Claim;
    }
  | { key: string; kind: "note"; label: string; noteId: string; count: number };

function clean(raw: string): string {
  return stripHtml(raw).replace(/\s+/g, " ").trim();
}

export function ExaminePage() {
  const {
    notes,
    dueClaims,
    items,
    busy,
    examineNote,
    examineClaimId,
    examineLabel,
    onExamineStart,
    onExamineStartClaim,
    examineChat,
    examineAnswer,
    setExamineAnswer,
    examineSessionDone,
    onExamineAnswer,
    setShowCompose,
  } = useStore();

  const inSession = Boolean(examineNote || examineClaimId);

  if (inSession) {
    return (
      <>
        <ChatLog
          messages={examineChat}
          examinerAvatar={<SquidwardAvatar />}
          examinerName="章鱼哥"
          empty={<span>章鱼哥在等你答</span>}
          busy={busy}
        />
        {!examineSessionDone ? (
          <Composer
            kind="textarea"
            value={examineAnswer}
            onChange={setExamineAnswer}
            placeholder={`聊聊「${examineLabel || "考点"}」…`}
            onSubmit={onExamineAnswer}
            submitLabel="发送"
            busy={busy}
          />
        ) : null}
      </>
    );
  }

  const owedIds = new Set(dueClaims.map((c) => c.id));
  const planClaims = items
    .filter((i) => i.status !== "verified" && i.claim_id && !owedIds.has(i.claim_id))
    .map((i) => ({
      id: i.claim_id!,
      text: i.title,
      status: i.status,
      topic: i.topic,
      source_note_id: null,
      next_review_at: null,
    }));
  const noteEntries = notes.filter((n) => n.claim_ids.length > 0);

  const seen = new Set<string>();
  const rows: PickRow[] = [];
  const pushClaim = (claim: Claim) => {
    const label = clean(claim.text);
    if (!label) return;
    const norm = label.toLowerCase().slice(0, 96);
    if (seen.has(norm)) return;
    seen.add(norm);
    rows.push({
      key: `c-${claim.id}`,
      kind: "claim",
      label,
      reason: dueReasonLine(claim),
      claim,
    });
  };

  for (const c of dueClaims) pushClaim(c);
  for (const c of planClaims) pushClaim(c);

  for (const n of noteEntries) {
    const label = clean(n.title?.trim() || n.excerpt || "未命名笔记");
    if (!label) continue;
    const norm = `note:${label.toLowerCase().slice(0, 96)}`;
    if (seen.has(norm)) continue;
    seen.add(norm);
    rows.push({
      key: `n-${n.id}`,
      kind: "note",
      label,
      noteId: n.id,
      count: n.claim_ids.length,
    });
  }

  if (rows.length === 0) {
    return (
      <div className={styles.picker}>
        <EmptyState avatar={<SquidwardAvatar />}>
          <strong>还没有可考的题</strong>
          <div>先添加资料，抽出能考的一句再过门</div>
          <button
            type="button"
            className={styles.emptyPrimary}
            disabled={busy}
            onClick={() => setShowCompose(true)}
          >
            添加资料
          </button>
        </EmptyState>
      </div>
    );
  }

  return (
    <div className={styles.picker}>
      <div className={styles.pickerInner}>
        <header className={styles.pickerHead}>
          <div className={styles.pickerAvatar}>
            <SquidwardAvatar />
          </div>
          <div className={styles.pickerCopy}>
            <div className={styles.pickerTitle}>选一条开考</div>
            <div className={styles.pickerSub}>
              共 {rows.length} 条可考 · 过关才算会
            </div>
          </div>
        </header>

        <ul className={styles.list}>
          {rows.map((r) => (
            <li key={r.key}>
              <button
                type="button"
                className={styles.row}
                disabled={busy}
                onClick={() => {
                  if (r.kind === "claim") onExamineStartClaim(r.claim);
                  else {
                    const n = notes.find((x) => x.id === r.noteId);
                    if (n) onExamineStart(n);
                  }
                }}
              >
                <span className={styles.rowMain}>
                  <span className={styles.rowTitle} title={r.label}>
                    {r.label}
                  </span>
                  {r.kind === "claim" && r.reason ? (
                    <span className={styles.rowMeta} title={r.reason}>
                      {r.reason}
                    </span>
                  ) : null}
                  {r.kind === "note" ? (
                    <span className={styles.rowMeta}>{r.count} 题</span>
                  ) : null}
                </span>
                <span className={styles.rowCta}>开考</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
