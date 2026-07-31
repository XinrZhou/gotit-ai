import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type {
  BootcampView,
  Claim,
  DayCloseSummary,
  DayNote,
  DayPlan,
  DrillMaterial,
  DrillSession,
  InterviewFocusHint,
  Project,
  ResumeRecord,
} from "../types";

type TodaySnap = {
  date: string;
  plan: DayPlan;
  notes: DayNote[];
  due_claims: Claim[];
  day_closed?: boolean;
  close_suggested?: boolean;
  close_summary?: DayCloseSummary | null;
  interview_focus?: InterviewFocusHint | null;
  bootcamp?: BootcampView | null;
};

/** Shared day snapshot: plan/notes/due claims/projects/resume/drill + refresh. */
export function useWorkspace(setError: (s: string) => void) {
  const [day, setDay] = useState(() => new Date().toISOString().slice(0, 10));
  const [plan, setPlan] = useState<DayPlan | null>(null);
  const [dayNotes, setDayNotes] = useState<DayNote[]>([]);
  const [allNotes, setAllNotes] = useState<DayNote[]>([]);
  const [dueClaims, setDueClaims] = useState<Claim[]>([]);
  const [dayClosed, setDayClosed] = useState(false);
  const [closeSuggested, setCloseSuggested] = useState(false);
  const [closeSummary, setCloseSummary] = useState<DayCloseSummary | null>(null);
  const [interviewFocus, setInterviewFocus] = useState<InterviewFocusHint | null>(
    null,
  );
  const [bootcamp, setBootcamp] = useState<BootcampView | null>(null);
  const [noteScope, setNoteScope] = useState<"today" | "all">("today");
  const [projects, setProjects] = useState<Project[]>([]);
  const [resume, setResume] = useState<ResumeRecord | null>(null);
  const [drillMaterials, setDrillMaterials] = useState<DrillMaterial[]>([]);
  const [drillSessions, setDrillSessions] = useState<DrillSession[]>([]);

  const items = plan?.items ?? [];
  const notes = useMemo(
    () => (noteScope === "all" ? allNotes : dayNotes),
    [noteScope, allNotes, dayNotes],
  );

  const refresh = useCallback(async () => {
    setError("");
    const fetches: Promise<unknown>[] = [
      api<TodaySnap>(`/v1/today?day=${encodeURIComponent(day)}`),
      api<Project[]>(`/v1/projects`),
      api<ResumeRecord | null>(`/v1/resumes`),
      api<DrillMaterial[]>(`/v1/drill/materials`),
      api<DrillSession[]>(`/v1/drill/sessions`),
    ];
    if (noteScope === "all") {
      fetches.push(api<DayNote[]>(`/v1/notes`));
    }
    const results = await Promise.all(fetches);
    const today = results[0] as TodaySnap;
    setPlan(today.plan);
    setDayNotes(today.notes);
    setDueClaims(today.due_claims ?? []);
    setDayClosed(Boolean(today.day_closed));
    setCloseSuggested(Boolean(today.close_suggested));
    setCloseSummary(today.close_summary ?? null);
    setInterviewFocus(today.interview_focus ?? null);
    setBootcamp(today.bootcamp ?? null);
    setProjects(results[1] as Project[]);
    setResume(results[2] as ResumeRecord | null);
    setDrillMaterials(results[3] as DrillMaterial[]);
    setDrillSessions(results[4] as DrillSession[]);
    if (results[5]) setAllNotes(results[5] as DayNote[]);
  }, [day, noteScope, setError]);

  const closeToday = useCallback(
    async (note?: string) => {
      setError("");
      await api<DayCloseSummary>(
        `/v1/days/today/close?day=${encodeURIComponent(day)}`,
        {
          method: "POST",
          body: JSON.stringify(note ? { note } : {}),
        },
      );
      await refresh();
    },
    [day, refresh, setError],
  );

  const setBootcampStatus = useCallback(
    async (status: "in_progress" | "done" | "skipped") => {
      setError("");
      const view = await api<BootcampView>("/v1/bootcamp", {
        method: "PUT",
        body: JSON.stringify({ status }),
      });
      setBootcamp(view);
    },
    [setError],
  );

  useEffect(() => {
    void refresh().catch((err: unknown) => setError(String(err)));
  }, [refresh, setError]);

  return {
    day,
    setDay,
    plan,
    notes,
    dueClaims,
    dayClosed,
    closeSuggested,
    closeSummary,
    closeToday,
    interviewFocus,
    bootcamp,
    setBootcampStatus,
    noteScope,
    setNoteScope,
    projects,
    items: items as {
      id: string;
      title: string;
      topic: string | null;
      status: string;
      claim_id: string | null;
    }[],
    resume,
    drillMaterials,
    drillSessions,
    refresh,
  };
}
