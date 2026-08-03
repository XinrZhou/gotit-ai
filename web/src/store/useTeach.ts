import { useCallback, useEffect, useState } from "react";
import { api, uploadFile } from "../api";
import type { Claim, MasteryVerdict, TeachResponse, VerifyPath } from "../types";
import type { ChatTurn } from "./types";

type Deps = {
  refresh: () => Promise<void>;
  setBusy: (b: boolean) => void;
  setError: (s: string) => void;
  workflowThreadId: string | null;
};

function asVerify(v: TeachResponse["verify"]): VerifyPath | null {
  if (!v?.examine_verdict || !v.recheck_verdict || !v.gate_verdict) return null;
  return v;
}

function displayVerdict(res: TeachResponse): MasteryVerdict | null {
  const gate = res.verify?.gate_verdict;
  if (gate === "passed" || gate === "almost" || gate === "owe_next") return gate;
  const v = res.verdict;
  if (!v.done || v.you_taught_well == null) return null;
  return v.you_taught_well ? "passed" : "owe_next";
}

function doneLabel(res: TeachResponse): string {
  const v = res.verdict;
  const label = v.you_taught_well ? "讲得清楚 ✓" : "还有缺口";
  const gaps = v.gaps.length ? `\n缺口：${v.gaps.join("；")}` : "";
  return label + gaps;
}

export function useTeach({ refresh, setBusy, setError, workflowThreadId }: Deps) {
  const [teachTopic, setTeachTopic] = useState("");
  const [teachClaimId, setTeachClaimId] = useState<string | null>(null);
  const [teachAnswer, setTeachAnswer] = useState("");
  const [teachChat, setTeachChat] = useState<ChatTurn[]>([]);
  const [teachDone, setTeachDone] = useState(false);
  const [teachSttAvailable, setTeachSttAvailable] = useState(false);
  const [teachTranscribing, setTeachTranscribing] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const caps = await api<{ stt_available: boolean }>("/v1/teach/capabilities");
        setTeachSttAvailable(Boolean(caps.stt_available));
      } catch {
        setTeachSttAvailable(false);
      }
    })();
  }, []);

  const threadBody = useCallback(
    () => (workflowThreadId ? { thread_id: workflowThreadId } : {}),
    [workflowThreadId],
  );

  const claimBody = useCallback(
    () => (teachClaimId ? { claim_id: teachClaimId } : {}),
    [teachClaimId],
  );

  const applyVerdict = useCallback(
    (res: TeachResponse, prependUser?: string) => {
      const v = res.verdict;
      const verify = asVerify(res.verify);
      const verdict = displayVerdict(res);
      if (v.done) {
        setTeachChat((prev) => {
          const base = prependUser
            ? [...prev, { role: "user" as const, text: prependUser }]
            : prev;
          return [
            ...base,
            {
              role: "examiner",
              text: doneLabel(res),
              verdict,
              session_done: true,
              verify,
            },
          ];
        });
        setTeachDone(true);
        if (res.writeback) void refresh();
      } else {
        setTeachChat((prev) => {
          const base = prependUser
            ? [...prev, { role: "user" as const, text: prependUser }]
            : prev;
          const isFirst = base.length === 0;
          return [
            ...base,
            {
              role: "examiner",
              text: v.next_question ?? "继续讲讲？",
              failure_hint: isFirst ? res.failure_hint ?? null : null,
            },
          ];
        });
      }
    },
    [refresh],
  );

  const onTeachStart = useCallback(() => {
    if (!teachTopic.trim()) return;
    void (async () => {
      setBusy(true);
      setError("");
      setTeachChat([]);
      setTeachDone(false);
      try {
        const res = await api<TeachResponse>("/v1/teach", {
          method: "POST",
          body: JSON.stringify({
            topic: teachTopic.trim(),
            ...claimBody(),
            ...threadBody(),
          }),
        });
        applyVerdict(res);
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    })();
  }, [
    teachTopic,
    claimBody,
    threadBody,
    applyVerdict,
    setBusy,
    setError,
  ]);

  const onTeachStartClaim = useCallback(
    (claim: Claim) => {
      const topic = claim.text.slice(0, 120).trim() || "回讲";
      setTeachClaimId(claim.id);
      setTeachTopic(topic);
      setTeachAnswer("");
      setTeachChat([]);
      setTeachDone(false);
      void (async () => {
        setBusy(true);
        setError("");
        try {
          const res = await api<TeachResponse>("/v1/teach", {
            method: "POST",
            body: JSON.stringify({
              topic,
              claim_id: claim.id,
              ...threadBody(),
            }),
          });
          applyVerdict(res);
        } catch (err) {
          setError(String(err));
        } finally {
          setBusy(false);
        }
      })();
    },
    [applyVerdict, setBusy, setError, threadBody],
  );

  const onTeachAnswer = useCallback(() => {
    if (!teachAnswer.trim() || teachDone) return;
    const userText = teachAnswer.trim();
    const history = teachChat.map((m) => ({ role: m.role, text: m.text }));
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
            ...claimBody(),
            ...threadBody(),
          }),
        });
        applyVerdict(res, userText);
      } catch (err) {
        setError(String(err));
        setTeachChat((prev) => [...prev, { role: "user", text: userText }]);
      } finally {
        setBusy(false);
      }
    })();
  }, [
    teachTopic,
    teachAnswer,
    teachChat,
    teachDone,
    claimBody,
    threadBody,
    applyVerdict,
    setBusy,
    setError,
  ]);

  const onTeachTranscribe = useCallback(
    async (file: File) => {
      setTeachTranscribing(true);
      setError("");
      try {
        const res = await uploadFile<{ transcript: string }>(
          "/v1/teach/transcribe",
          file,
        );
        const text = (res.transcript || "").trim();
        if (text) setTeachAnswer(text);
      } catch (err) {
        setError(String(err));
      } finally {
        setTeachTranscribing(false);
      }
    },
    [setError],
  );

  return {
    teachTopic,
    setTeachTopic,
    teachClaimId,
    setTeachClaimId,
    teachChat,
    teachAnswer,
    setTeachAnswer,
    teachDone,
    teachSttAvailable,
    teachTranscribing,
    onTeachStart,
    onTeachStartClaim,
    onTeachAnswer,
    onTeachTranscribe,
  };
}
