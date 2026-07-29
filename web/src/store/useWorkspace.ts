import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type {
  DayNote,
  DayPlan,
  DrillMaterial,
  DrillSession,
  Project,
  ResumeRecord,
} from "../types";

/** Shared day snapshot: plan/notes/projects/resume/drill lists + refresh. */
export function useWorkspace(setError: (s: string) => void) {
  const [day, setDay] = useState(() => new Date().toISOString().slice(0, 10));
  const [plan, setPlan] = useState<DayPlan | null>(null);
  const [dayNotes, setDayNotes] = useState<DayNote[]>([]);
  const [allNotes, setAllNotes] = useState<DayNote[]>([]);
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
      api<DayPlan>(`/v1/days/${day}/plan`),
      api<DayNote[]>(`/v1/days/${day}/notes`),
      api<Project[]>(`/v1/projects`),
      api<ResumeRecord | null>(`/v1/resumes`),
      api<DrillMaterial[]>(`/v1/drill/materials`),
      api<DrillSession[]>(`/v1/drill/sessions`),
    ];
    if (noteScope === "all") {
      fetches.push(api<DayNote[]>(`/v1/notes`));
    }
    const results = await Promise.all(fetches);
    setPlan(results[0] as DayPlan);
    setDayNotes(results[1] as DayNote[]);
    setProjects(results[2] as Project[]);
    setResume(results[3] as ResumeRecord | null);
    setDrillMaterials(results[4] as DrillMaterial[]);
    setDrillSessions(results[5] as DrillSession[]);
    if (results[6]) setAllNotes(results[6] as DayNote[]);
  }, [day, noteScope, setError]);

  useEffect(() => {
    void refresh().catch((err: unknown) => setError(String(err)));
  }, [refresh, setError]);

  return {
    day,
    setDay,
    plan,
    notes,
    noteScope,
    setNoteScope,
    projects,
    items: items as {
      id: string;
      title: string;
      topic: string | null;
      status: string;
    }[],
    resume,
    drillMaterials,
    drillSessions,
    refresh,
  };
}
