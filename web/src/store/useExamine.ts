import { useCallback, useState } from "react";
import { api } from "../api";
import {
  gateReasonFromVerify,
  outcomeFromWire,
} from "../lib/verifyOutcome";
import type {
  Claim,
  DayNote,
  TopicExamineResponse,
  VerifyOutcome,
  VerifyPath,
} from "../types";
import type { ChatTurn } from "./types";

type Deps = {
  refresh: () => Promise<void>;
  setBusy: (b: boolean) => void;
  setError: (s: string) => void;
  workflowThreadId: string | null;
};

function asVerify(v: TopicExamineResponse["verify"]): VerifyPath | null {
  if (!v?.examine_verdict || !v.recheck_verdict || !v.gate_verdict) return null;
  return v;
}

function formatExamineError(e: unknown): string {
  const raw = String(e).replace(/^Error:\s*/, "");
  const jsonMatch = raw.match(/\{[\s\S]*\}/);
  if (jsonMatch) {
    try {
      const parsed = JSON.parse(jsonMatch[0]) as { detail?: unknown };
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        return parsed.detail.trim();
      }
    } catch {
      /* keep raw */
    }
  }
  return raw.trim() || "刚才没判上，请再试一次。";
}

function outcomeFromExamineRes(
  res: TopicExamineResponse,
  fallbackClaimId: string | null,
  fallbackLabel: string,
): VerifyOutcome | null {
  const gate =
    res.verify?.gate_verdict ??
    (res.verdict.done ? res.verdict.verdict : null);
  return outcomeFromWire({
    gate_verdict: gate,
    gate_reason: gateReasonFromVerify(res.verify),
    writeback: res.writeback,
    claim_id: res.verdict.current_claim_id ?? fallbackClaimId,
    claim_label: res.writeback?.claim?.text ?? fallbackLabel,
  });
}

export function useExamine({
  refresh,
  setBusy,
  setError,
  workflowThreadId,
}: Deps) {
  const [examineNote, setExamineNote] = useState<DayNote | null>(null);
  const [examineClaimId, setExamineClaimId] = useState<string | null>(null);
  const [examineLabel, setExamineLabel] = useState("");
  const [examineChat, setExamineChat] = useState<ChatTurn[]>([]);
  const [examineAnswer, setExamineAnswer] = useState("");
  const [examineSessionDone, setExamineSessionDone] = useState(false);
  const [examineOutcome, setExamineOutcome] = useState<VerifyOutcome | null>(
    null,
  );

  const threadBody = useCallback(
    () => (workflowThreadId ? { thread_id: workflowThreadId } : {}),
    [workflowThreadId],
  );

  const clearExamineSession = useCallback(() => {
    setExamineNote(null);
    setExamineClaimId(null);
    setExamineLabel("");
    setExamineChat([]);
    setExamineAnswer("");
    setExamineSessionDone(false);
    setExamineOutcome(null);
  }, []);

  const onExamineStart = useCallback(
    (note: DayNote) => {
      setExamineNote(note);
      setExamineClaimId(null);
      setExamineLabel(note.title?.trim() || "未命名笔记");
      setExamineChat([]);
      setExamineAnswer("");
      setExamineSessionDone(false);
      setExamineOutcome(null);
      void (async () => {
        setBusy(true);
        setError("");
        try {
          const res = await api<TopicExamineResponse>("/v1/examine", {
            method: "POST",
            body: JSON.stringify({
              note_id: note.id,
              ...threadBody(),
            }),
          });
          setExamineChat([
            {
              role: "examiner",
              text: res.verdict.follow_up,
              verify: asVerify(res.verify),
              failure_hint: res.failure_hint ?? null,
            },
          ]);
          if (res.verdict.session_done) {
            setExamineSessionDone(true);
            setExamineOutcome(
              outcomeFromExamineRes(res, null, note.title?.trim() || "考点"),
            );
          }
        } catch (err) {
          const msg = formatExamineError(err);
          setError(msg);
          setExamineChat([
            { role: "examiner", text: msg, error: true },
          ]);
        } finally {
          setBusy(false);
        }
      })();
    },
    [setBusy, setError, threadBody],
  );

  const onExamineStartClaim = useCallback(
    (claim: Claim) => {
      setExamineNote(null);
      setExamineClaimId(claim.id);
      setExamineLabel(claim.text.slice(0, 80));
      setExamineChat([]);
      setExamineAnswer("");
      setExamineSessionDone(false);
      setExamineOutcome(null);
      void (async () => {
        setBusy(true);
        setError("");
        try {
          const res = await api<TopicExamineResponse>("/v1/examine", {
            method: "POST",
            body: JSON.stringify({
              claim_id: claim.id,
              ...threadBody(),
            }),
          });
          setExamineChat([
            {
              role: "examiner",
              text: res.verdict.follow_up,
              verify: asVerify(res.verify),
              verdict: res.verdict.done ? res.verdict.verdict : null,
              session_done: res.verdict.session_done ?? res.verdict.done,
              failure_hint: res.failure_hint ?? null,
            },
          ]);
          if (res.verdict.session_done || res.verdict.done) {
            setExamineSessionDone(true);
            setExamineOutcome(
              outcomeFromExamineRes(res, claim.id, claim.text.slice(0, 80)),
            );
          }
        } catch (err) {
          const msg = formatExamineError(err);
          setError(msg);
          setExamineChat([
            { role: "examiner", text: msg, error: true },
          ]);
        } finally {
          setBusy(false);
        }
      })();
    },
    [setBusy, setError, threadBody],
  );

  const onExamineAnswer = useCallback(() => {
    if (
      (!examineNote && !examineClaimId) ||
      !examineAnswer.trim() ||
      examineSessionDone
    ) {
      return;
    }
    const userText = examineAnswer.trim();
    const history = examineChat.map((m) => ({ role: m.role, text: m.text }));
    setExamineChat((prev) => [...prev, { role: "user", text: userText }]);
    setExamineAnswer("");
    void (async () => {
      setBusy(true);
      setError("");
      try {
        const payload = examineNote
          ? { note_id: examineNote.id, answer: userText, history, ...threadBody() }
          : {
              claim_id: examineClaimId,
              answer: userText,
              history,
              ...threadBody(),
            };
        const res = await api<TopicExamineResponse>("/v1/examine", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        const done =
          Boolean(res.verdict.session_done) ||
          (Boolean(examineClaimId) && Boolean(res.verdict.done));
        setExamineChat((prev) => [
          ...prev,
          {
            role: "examiner",
            text: res.verdict.follow_up,
            verdict: res.verdict.done ? res.verdict.verdict : null,
            session_done: done,
            verify: asVerify(res.verify),
          },
        ]);
        if (done) {
          setExamineSessionDone(true);
          setExamineOutcome(
            outcomeFromExamineRes(
              res,
              examineClaimId,
              examineLabel || "考点",
            ),
          );
        }
        await refresh();
      } catch (err) {
        const msg = formatExamineError(err);
        setError(msg);
        setExamineChat((prev) => [
          ...prev,
          { role: "examiner", text: msg, error: true },
        ]);
      } finally {
        setBusy(false);
      }
    })();
  }, [
    examineNote,
    examineClaimId,
    examineAnswer,
    examineChat,
    examineSessionDone,
    examineLabel,
    refresh,
    setBusy,
    setError,
    threadBody,
  ]);

  return {
    examineNote,
    examineClaimId,
    examineLabel,
    examineChat,
    examineAnswer,
    setExamineAnswer,
    examineSessionDone,
    examineOutcome,
    clearExamineSession,
    onExamineStart,
    onExamineStartClaim,
    onExamineAnswer,
  };
}
