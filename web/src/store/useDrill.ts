import { useCallback, useEffect, useState } from "react";
import { api, uploadFile } from "../api";
import type {
  DrillMaterial,
  DrillRound,
  DrillSession,
  DrillSessionContinueResponse,
  DrillSessionStartResponse,
  Mode,
  Project,
  ProjectProgress,
  ResumeApplyResponse,
  ResumeDocument,
  ResumeUploadResponse,
} from "../types";
import type { ChatTurn, Run } from "./types";

type Deps = {
  mode: Mode;
  selectedProject: Project | null;
  run: Run;
  refresh: () => Promise<void>;
  setBusy: (b: boolean) => void;
  setError: (s: string) => void;
  setProjectPicked: (v: boolean) => void;
};

export function useDrill({
  mode,
  selectedProject,
  run,
  refresh,
  setBusy,
  setError,
  setProjectPicked,
}: Deps) {
  const [activeDrillSession, setActiveDrillSession] = useState<DrillSession | null>(
    null,
  );
  const [drillRound, setDrillRound] = useState<DrillRound>("tech_1");
  const [drillDirection, setDrillDirection] = useState("");
  const [drillFocusProjectId, setDrillFocusProjectId] = useState<string | null>(null);
  const [drillChat, setDrillChat] = useState<ChatTurn[]>([]);
  const [drillAnswer, setDrillAnswer] = useState("");
  const [drillDone, setDrillDone] = useState(false);
  const [progress, setProgress] = useState<ProjectProgress | null>(null);
  const [showResumeModal, setShowResumeModal] = useState(false);
  const [showMaterialModal, setShowMaterialModal] = useState(false);
  const [showResumeViewer, setShowResumeViewer] = useState(false);

  useEffect(() => {
    if (mode !== "drill") return;
    if (selectedProject) {
      setDrillFocusProjectId(selectedProject.id);
      void (async () => {
        try {
          const prog = await api<ProjectProgress>(
            `/v1/projects/${selectedProject.id}/progress`,
          );
          setProgress(prog);
        } catch {
          setProgress(null);
        }
      })();
    } else {
      setDrillFocusProjectId(null);
      setProgress(null);
    }
  }, [mode, selectedProject]);

  const onUploadResume = useCallback((file: File) => {
    return uploadFile<ResumeUploadResponse>("/v1/resumes/upload", file);
  }, []);

  const onApplyResume = useCallback(
    async (uploadId: string, document: ResumeDocument, filePath: string) => {
      await run(async () => {
        await api<ResumeApplyResponse>("/v1/resumes/apply", {
          method: "POST",
          body: JSON.stringify({
            upload_id: uploadId,
            file_path: filePath,
            document,
            ingest: false,
          }),
        });
        setShowResumeModal(false);
      }, "简历已导入，项目库已重建");
    },
    [run],
  );

  const onUpsertMaterial = useCallback(
    async (id: string | null, title: string, body: string) => {
      if (!title.trim() || !body.trim()) return;
      await run(async () => {
        await api<DrillMaterial>("/v1/drill/materials", {
          method: "POST",
          body: JSON.stringify({ id, title: title.trim(), body: body.trim() }),
        });
      }, id ? "资料已更新" : "资料已添加");
    },
    [run],
  );

  const onImportMaterialFile = useCallback(
    (file: File) =>
      uploadFile<{ title: string; body: string }>("/v1/drill/materials/upload", file),
    [],
  );

  const onDeleteMaterial = useCallback(
    async (id: string) => {
      await run(async () => {
        await api<{ status: string }>(`/v1/drill/materials/${id}`, {
          method: "DELETE",
        });
      }, "资料已删除");
    },
    [run],
  );

  const onDrillStartSession = useCallback(() => {
    void (async () => {
      setBusy(true);
      setError("");
      try {
        const res = await api<DrillSessionStartResponse>("/v1/drill/sessions", {
          method: "POST",
          body: JSON.stringify({
            round: drillRound,
            direction: drillDirection.trim() || null,
            project_id: drillFocusProjectId,
          }),
        });
        setActiveDrillSession(res.session);
        const v = res.verdict;
        if (v.done) {
          const gaps = v.gaps.length ? `\n缺口：${v.gaps.join("；")}` : "";
          setDrillChat([
            {
              role: "examiner",
              text: `深挖结束（深度 ${v.depth_reached}）${gaps}`,
            },
          ]);
          setDrillDone(true);
        } else {
          setDrillChat([
            { role: "examiner", text: v.follow_up ?? "说说你做了什么？" },
          ]);
          setDrillDone(false);
        }
        await refresh();
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    })();
  }, [
    drillRound,
    drillDirection,
    drillFocusProjectId,
    refresh,
    setBusy,
    setError,
  ]);

  const onDrillAnswer = useCallback(() => {
    if (!activeDrillSession || !drillAnswer.trim() || drillDone) return;
    const userText = drillAnswer.trim();
    setDrillChat((prev) => [...prev, { role: "user", text: userText }]);
    setDrillAnswer("");
    void (async () => {
      setBusy(true);
      try {
        const res = await api<DrillSessionContinueResponse>(
          `/v1/drill/sessions/${activeDrillSession.id}`,
          { method: "POST", body: JSON.stringify({ answer: userText }) },
        );
        const v = res.verdict;
        if (v.done) {
          const gaps = v.gaps.length ? `\n缺口：${v.gaps.join("；")}` : "";
          setDrillChat((prev) => [
            ...prev,
            {
              role: "examiner",
              text: `深挖结束（深度 ${v.depth_reached}）${gaps}`,
            },
          ]);
          setDrillDone(true);
        } else {
          setDrillChat((prev) => [
            ...prev,
            { role: "examiner", text: v.follow_up ?? "继续说？" },
          ]);
        }
        await refresh();
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    })();
  }, [activeDrillSession, drillAnswer, drillDone, refresh, setBusy, setError]);

  const onSelectDrillSession = useCallback(
    (s: DrillSession) => {
      setActiveDrillSession(s);
      setDrillChat(s.messages.map((m) => ({ role: m.role, text: m.text })));
      setDrillDone(s.status === "done");
      setDrillRound(s.round);
      setDrillDirection(s.direction ?? "");
      setDrillFocusProjectId(s.project_id);
      setProjectPicked(true);
    },
    [setProjectPicked],
  );

  const onBackToDrillStart = useCallback(() => {
    setActiveDrillSession(null);
    setDrillChat([]);
    setDrillAnswer("");
    setDrillDone(false);
  }, []);

  return {
    activeDrillSession,
    drillRound,
    setDrillRound,
    drillDirection,
    setDrillDirection,
    drillFocusProjectId,
    setDrillFocusProjectId,
    drillChat,
    drillAnswer,
    setDrillAnswer,
    drillDone,
    progress,
    showResumeModal,
    setShowResumeModal,
    showMaterialModal,
    setShowMaterialModal,
    showResumeViewer,
    setShowResumeViewer,
    onUploadResume,
    onApplyResume,
    onUpsertMaterial,
    onImportMaterialFile,
    onDeleteMaterial,
    onDrillStartSession,
    onDrillAnswer,
    onSelectDrillSession,
    onBackToDrillStart,
  };
}
