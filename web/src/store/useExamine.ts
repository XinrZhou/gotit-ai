import { useCallback, useState } from "react";
import { api } from "../api";
import type { Claim, DayNote, TopicExamineResponse, VerifyPath } from "../types";
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

  const threadBody = useCallback(
    () => (workflowThreadId ? { thread_id: workflowThreadId } : {}),
    [workflowThreadId],
  );

  const onExamineStart = useCallback(
    (note: DayNote) => {
      setExamineNote(note);
      setExamineClaimId(null);
      setExamineLabel(note.title?.trim() || "未命名笔记");
      setExamineChat([]);
      setExamineAnswer("");
      setExamineSessionDone(false);
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
            },
          ]);
          if (res.verdict.session_done) setExamineSessionDone(true);
        } catch (err) {
          setError(String(err));
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
            },
          ]);
          if (res.verdict.session_done || res.verdict.done) {
            setExamineSessionDone(true);
          }
        } catch (err) {
          setError(String(err));
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
        if (done) setExamineSessionDone(true);
        await refresh();
      } catch (err) {
        setError(String(err));
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
    onExamineStart,
    onExamineStartClaim,
    onExamineAnswer,
  };
}
