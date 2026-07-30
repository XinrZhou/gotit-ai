import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type {
  Claim,
  DayNote,
  DayPlan,
  DrillMaterial,
  DrillSession,
  Project,
  ResumeRecord,
} from "../types";

type TodaySnap = {
  date: string;
  plan: DayPlan;
  notes: DayNote[];
  due_claims: Claim[];
};

/** Shared day snapshot: plan/notes/due claims/projects/resume/drill + refresh. */
export function useWorkspace(setError: (s: string) => void) {
  const [day, setDay] = useState(() => new Date().toISOString().slice(0, 10));
  const [plan, setPlan] = useState<DayPlan | null>(null);
  const [dayNotes, setDayNotes] = useState<DayNote[]>([]);
  const [allNotes, setAllNotes] = useState<DayNote[]>([]);
  const [dueClaims, setDueClaims] = useState<Claim[]>([]);
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
    setProjects(results[1] as Project[]);
    setResume(results[2] as ResumeRecord | null);
    setDrillMaterials(results[3] as DrillMaterial[]);
    setDrillSessions(results[4] as DrillSession[]);
    if (results[5]) setAllNotes(results[5] as DayNote[]);
  }, [day, noteScope, setError]);

  useEffect(() => {
    void refresh().catch((err: unknown) => setError(String(err)));
  }, [refresh, setError]);

  return {
    day,
    setDay,
    plan,
    notes,
    dueClaims,
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
