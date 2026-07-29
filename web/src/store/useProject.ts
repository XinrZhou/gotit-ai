import { useCallback, useMemo, useState } from "react";
import { api } from "../api";
import type { Project } from "../types";
import type { Run } from "./types";

type Deps = {
  projects: Project[];
  run: Run;
};

export function useProject({ projects, run }: Deps) {
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [projectPicked, setProjectPicked] = useState(false);
  const [showProjectModal, setShowProjectModal] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);

  const selectedProject = useMemo(
    () => projects.find((p) => p.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );

  const onOpenEditProject = useCallback((p: Project) => {
    setEditingProject(p);
    setShowProjectModal(true);
  }, []);

  const saveProject = useCallback(
    (
      editing: Project | null,
      fields: { name: string; role: string; goal: string; tech_stack: string[] },
    ) => {
      if (!editing || !fields.name.trim()) return;
      void run(async () => {
        await api<Project>(`/v1/projects/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            name: fields.name.trim(),
            role: fields.role.trim() || null,
            goal: fields.goal.trim() || null,
            tech_stack: fields.tech_stack,
          }),
        });
        setShowProjectModal(false);
      }, "项目已更新");
    },
    [run],
  );

  return {
    selectedProjectId,
    setSelectedProjectId,
    projectPicked,
    setProjectPicked,
    selectedProject,
    showProjectModal,
    setShowProjectModal,
    editingProject,
    onOpenEditProject,
    saveProject,
  };
}
