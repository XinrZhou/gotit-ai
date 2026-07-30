import { useCallback, useState } from "react";
import { api } from "../api";
import type { TeachResponse } from "../types";
import type { ChatTurn } from "./types";

type Deps = {
  setBusy: (b: boolean) => void;
  setError: (s: string) => void;
  workflowThreadId: string | null;
};

export function useTeach({ setBusy, setError, workflowThreadId }: Deps) {
  const [teachTopic, setTeachTopic] = useState("");
  const [teachAnswer, setTeachAnswer] = useState("");
  const [teachChat, setTeachChat] = useState<ChatTurn[]>([]);
  const [teachDone, setTeachDone] = useState(false);

  const onTeachStart = useCallback(() => {
    if (!teachTopic.trim()) return;
    void (async () => {
      setBusy(true);
      setError("");
      try {
        const res = await api<TeachResponse>("/v1/teach", {
          method: "POST",
          body: JSON.stringify({
            topic: teachTopic.trim(),
            ...(workflowThreadId ? { thread_id: workflowThreadId } : {}),
          }),
        });
        const v = res.verdict;
        if (v.done) {
          const label = v.you_taught_well ? "讲得清楚 ✓" : "还有缺口";
          const gaps = v.gaps.length ? `\n缺口：${v.gaps.join("；")}` : "";
          setTeachChat([{ role: "examiner", text: label + gaps }]);
          setTeachDone(true);
        } else {
          setTeachChat([{ role: "examiner", text: v.next_question ?? "继续讲讲？" }]);
        }
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    })();
  }, [teachTopic, setBusy, setError, workflowThreadId]);

  const onTeachAnswer = useCallback(() => {
    if (!teachAnswer.trim() || teachDone) return;
    const userText = teachAnswer.trim();
    const history = teachChat.map((m) => ({ role: m.role, text: m.text }));
    setTeachChat((prev) => [...prev, { role: "user", text: userText }]);
    setTeachAnswer("");
    void (async () => {
      setBusy(true);
      try {
        const res = await api<TeachResponse>("/v1/teach", {
          method: "POST",
          body: JSON.stringify({
            topic: teachTopic.trim(),
            answer: userText,
            history,
            ...(workflowThreadId ? { thread_id: workflowThreadId } : {}),
          }),
        });
        const v = res.verdict;
        if (v.done) {
          const label = v.you_taught_well ? "讲得清楚 ✓" : "还有缺口";
          const gaps = v.gaps.length ? `\n缺口：${v.gaps.join("；")}` : "";
          setTeachChat((prev) => [
            ...prev,
            { role: "examiner", text: label + gaps },
          ]);
          setTeachDone(true);
        } else {
          setTeachChat((prev) => [
            ...prev,
            { role: "examiner", text: v.next_question ?? "继续讲讲？" },
          ]);
        }
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    })();
  }, [
    teachTopic,
    teachAnswer,
    teachChat,
    teachDone,
    setBusy,
    setError,
    workflowThreadId,
  ]);

  return {
    teachTopic,
    setTeachTopic,
    teachChat,
    teachAnswer,
    setTeachAnswer,
    teachDone,
    onTeachStart,
    onTeachAnswer,
  };
}
