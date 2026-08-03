import {
  createContext,
  useContext,
  useMemo,
  type ReactNode,
} from "react";
import type { Store } from "./types";
import { useDrill } from "./useDrill";
import { useExamine } from "./useExamine";
import { useNotes } from "./useNotes";
import { useProject } from "./useProject";
import { useShell } from "./useShell";
import { useTeach } from "./useTeach";
import { useWorkspace } from "./useWorkspace";

const Ctx = createContext<Store | null>(null);

export function useStore(): Store {
  const v = useContext(Ctx);
  if (!v) throw new Error("useStore must be inside StoreProvider");
  return v;
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const shell = useShell();
  const ws = useWorkspace(shell.setError);
  const run = useMemo(
    () => shell.bindRun(ws.refresh),
    [shell.bindRun, ws.refresh],
  );

  const notes = useNotes({
    notes: ws.notes,
    run,
    refresh: ws.refresh,
    setBusy: shell.setBusy,
    setError: shell.setError,
    setFlash: shell.setFlash,
  });

  const project = useProject({ projects: ws.projects, run });

  const examine = useExamine({
    refresh: ws.refresh,
    setBusy: shell.setBusy,
    setError: shell.setError,
    workflowThreadId: shell.workflowThreadId,
  });

  const teach = useTeach({
    refresh: ws.refresh,
    setBusy: shell.setBusy,
    setError: shell.setError,
    workflowThreadId: shell.workflowThreadId,
  });

  const drill = useDrill({
    mode: shell.mode,
    selectedProject: project.selectedProject,
    run,
    refresh: ws.refresh,
    setBusy: shell.setBusy,
    setError: shell.setError,
    setProjectPicked: project.setProjectPicked,
    workflowThreadId: shell.workflowThreadId,
  });

  const value: Store = {
    day: ws.day,
    setDay: ws.setDay,
    plan: ws.plan,
    notes: ws.notes,
    dueClaims: ws.dueClaims,
    dayClosed: ws.dayClosed,
    closeSuggested: ws.closeSuggested,
    closeSummary: ws.closeSummary,
    closeToday: ws.closeToday,
    interviewFocus: ws.interviewFocus,
    bootcamp: ws.bootcamp,
    setBootcampStatus: ws.setBootcampStatus,
    noteScope: ws.noteScope,
    setNoteScope: ws.setNoteScope,
    projects: ws.projects,
    items: ws.items,
    resume: ws.resume,
    drillMaterials: ws.drillMaterials,
    drillSessions: ws.drillSessions,
    refresh: ws.refresh,
    run,
    mode: shell.mode,
    setMode: shell.setMode,
    busy: shell.busy,
    setBusy: shell.setBusy,
    error: shell.error,
    flash: shell.flash,
    setFlash: shell.setFlash,
    setError: shell.setError,
    openMenuId: shell.openMenuId,
    setOpenMenuId: shell.setOpenMenuId,
    libraryOpen: shell.libraryOpen,
    setLibraryOpen: shell.setLibraryOpen,
    masteryGraphOpen: shell.masteryGraphOpen,
    setMasteryGraphOpen: shell.setMasteryGraphOpen,
    shellActivityOpen: shell.shellActivityOpen,
    setShellActivityOpen: shell.setShellActivityOpen,
    settingsOpen: shell.settingsOpen,
    setSettingsOpen: shell.setSettingsOpen,
    workflowThreadId: shell.workflowThreadId,
    setWorkflowThreadId: shell.setWorkflowThreadId,
    userProfile: shell.userProfile,
    setUserProfile: shell.setUserProfile,
    ...notes,
    ...project,
    ...examine,
    ...teach,
    ...drill,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
