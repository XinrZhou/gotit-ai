import { useEffect, useRef, useState } from "react";
import { ChatLog } from "../../components/ChatLog";
import { Composer } from "../../components/Composer";
import { EmptyState } from "../../components/EmptyState";
import { PatrickAvatar } from "../../components/Avatars";
import { dueReasonLine, stripHtml } from "../../lib/format";
import { useStore } from "../../store";
import type { Claim } from "../../types";
import styles from "./index.module.scss";

const MAX_PICK = 6;

function clean(raw: string): string {
  return stripHtml(raw).replace(/\s+/g, " ").trim();
}

function TeachAnswerBar() {
  const {
    busy,
    teachAnswer,
    setTeachAnswer,
    teachDone,
    teachSttAvailable,
    teachTranscribing,
    onTeachAnswer,
    onTeachTranscribe,
  } = useStore();

  const [recording, setRecording] = useState(false);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    return () => {
      const rec = mediaRef.current;
      if (rec && rec.state !== "inactive") rec.stop();
      mediaRef.current = null;
    };
  }, []);

  const stopRecording = () => {
    const rec = mediaRef.current;
    if (rec && rec.state !== "inactive") rec.stop();
  };

  const startRecording = async () => {
    if (!teachSttAvailable || busy || teachDone || teachTranscribing) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : undefined;
      const rec = mime
        ? new MediaRecorder(stream, { mimeType: mime })
        : new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        mediaRef.current = null;
        setRecording(false);
        const blob = new Blob(chunksRef.current, {
          type: rec.mimeType || "audio/webm",
        });
        chunksRef.current = [];
        if (blob.size === 0) return;
        const file = new File([blob], "teach.webm", {
          type: blob.type || "audio/webm",
        });
        void onTeachTranscribe(file);
      };
      mediaRef.current = rec;
      rec.start();
      setRecording(true);
    } catch (err) {
      setRecording(false);
      console.error(err);
    }
  };

  return (
    <div className={styles.answerWrap}>
      {teachSttAvailable ? (
        <div className={styles.voiceRow}>
          <button
            type="button"
            className={`${styles.voiceBtn} ${recording ? styles.voiceBtnActive : ""}`}
            disabled={busy || teachDone || teachTranscribing}
            onClick={() => (recording ? stopRecording() : void startRecording())}
          >
            {recording
              ? "停止并转写"
              : teachTranscribing
                ? "转写中…"
                : "录音回讲"}
          </button>
          <span className={styles.voiceHint}>
            转写后可改稿再提交；也可直接粘贴文字
          </span>
        </div>
      ) : (
        <p className={styles.voiceHintOnly}>无转写密钥时走文本回讲</p>
      )}
      <Composer
        kind="textarea"
        value={teachAnswer}
        onChange={setTeachAnswer}
        placeholder="继续讲…（可粘贴转写稿）"
        onSubmit={onTeachAnswer}
        submitLabel="提交"
        busy={busy || teachTranscribing || recording}
      />
    </div>
  );
}

export function TeachPage() {
  const {
    busy,
    dueClaims,
    items,
    teachTopic,
    setTeachTopic,
    teachClaimId,
    setTeachClaimId,
    teachChat,
    teachDone,
    onTeachStart,
    onTeachStartClaim,
  } = useStore();

  const inSession = teachChat.length > 0 || Boolean(teachClaimId);

  if (inSession) {
    return (
      <>
        <ChatLog
          messages={teachChat}
          examinerAvatar={<PatrickAvatar />}
          examinerName="派大星"
          empty={
            <EmptyState avatar={<PatrickAvatar />}>
              讲给派大星听。讲不清的地方，他会接着问。
            </EmptyState>
          }
          busy={busy}
        />
        {!teachDone ? <TeachAnswerBar /> : null}
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

  const seen = new Set<string>();
  const rows: Claim[] = [];
  const pushClaim = (claim: Claim) => {
    if (rows.length >= MAX_PICK) return;
    const label = clean(claim.text);
    if (!label) return;
    const norm = label.toLowerCase().slice(0, 96);
    if (seen.has(norm)) return;
    seen.add(norm);
    rows.push(claim);
  };
  for (const c of dueClaims) pushClaim(c);
  for (const c of planClaims) pushClaim(c);

  return (
    <div className={styles.picker}>
      <div className={styles.pickerInner}>
        <header className={styles.pickerHead}>
          <div className={styles.pickerAvatar}>
            <PatrickAvatar />
          </div>
          <div className={styles.pickerCopy}>
            <div className={styles.pickerTitle}>选一条回讲</div>
            <div className={styles.pickerSub}>口说或打字 · 同一套过了 / 欠着下次</div>
          </div>
        </header>

        {rows.length > 0 ? (
          <ul className={styles.list}>
            {rows.map((c) => {
              const label = clean(c.text);
              const reason = dueReasonLine(c);
              return (
                <li key={c.id}>
                  <button
                    type="button"
                    className={styles.row}
                    disabled={busy}
                    onClick={() => onTeachStartClaim(c)}
                  >
                    <span className={styles.rowMain}>
                      <span className={styles.rowTitle} title={label}>
                        {label}
                      </span>
                      {reason ? (
                        <span className={styles.rowMeta} title={reason}>
                          {reason}
                        </span>
                      ) : null}
                    </span>
                    <span className={styles.rowCta}>回讲</span>
                  </button>
                </li>
              );
            })}
          </ul>
        ) : (
          <EmptyState avatar={<PatrickAvatar />}>
            <strong>还没有可回讲的题</strong>
            <div>先出题进计划，或用下面自由主题</div>
          </EmptyState>
        )}

        <div className={styles.freeTopic}>
          <div className={styles.freeLabel}>或自由主题（不写回掌握）</div>
          <Composer
            kind="topic"
            value={teachTopic}
            onChange={(s) => {
              setTeachClaimId(null);
              setTeachTopic(s);
            }}
            placeholder="例如：上下文预算"
            onSubmit={onTeachStart}
            submitLabel="开始讲"
            busy={busy}
          />
        </div>
      </div>
    </div>
  );
}
