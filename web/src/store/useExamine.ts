import { useCallback, useState } from "react";
import { api } from "../api";
import type { DayNote, TopicExamineResponse } from "../types";
import type { ChatTurn } from "./types";

type Deps = {
  refresh: () => Promise<void>;
  setBusy: (b: boolean) => void;
  setError: (s: string) => void;
  workflowThreadId: string | null;
};

export function useExamine({
  refresh,
  setBusy,
  setError,
  workflowThreadId,
}: Deps) {
  const [examineNote, setExamineNote] = useState<DayNote | null>(null);
  const [examineChat, setExamineChat] = useState<ChatTurn[]>([]);
  const [examineAnswer, setExamineAnswer] = useState("");
  const [examineSessionDone, setExamineSessionDone] = useState(false);

  const onExamineStart = useCallback(
    (note: DayNote) => {
      setExamineNote(note);
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
              ...(workflowThreadId ? { thread_id: workflowThreadId } : {}),
            }),
          });
          setExamineChat([{ role: "examiner", text: res.verdict.follow_up }]);
          if (res.verdict.session_done) setExamineSessionDone(true);
        } catch (err) {
          setError(String(err));
        } finally {
          setBusy(false);
        }
      })();
    },
    [setBusy, setError, workflowThreadId],
  );

  const onExamineAnswer = useCallback(() => {
    if (!examineNote || !examineAnswer.trim() || examineSessionDone) return;
    const userText = examineAnswer.trim();
    const history = examineChat.map((m) => ({ role: m.role, text: m.text }));
    setExamineChat((prev) => [...prev, { role: "user", text: userText }]);
    setExamineAnswer("");
    void (async () => {
      setBusy(true);
      try {
        const res = await api<TopicExamineResponse>("/v1/examine", {
          method: "POST",
          body: JSON.stringify({
            note_id: examineNote.id,
            answer: userText,
            history,
            ...(workflowThreadId ? { thread_id: workflowThreadId } : {}),
          }),
        });
        setExamineChat((prev) => [
          ...prev,
          {
            role: "examiner",
            text: res.verdict.follow_up,
            verdict: res.verdict.done ? res.verdict.verdict : null,
            session_done: res.verdict.session_done,
          },
        ]);
        if (res.verdict.session_done) setExamineSessionDone(true);
        await refresh();
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    })();
  }, [
    examineNote,
    examineAnswer,
    examineChat,
    examineSessionDone,
    refresh,
    setBusy,
    setError,
    workflowThreadId,
  ]);

  return {
    examineNote,
    examineChat,
    examineAnswer,
    setExamineAnswer,
    examineSessionDone,
    onExamineStart,
    onExamineAnswer,
  };
}
