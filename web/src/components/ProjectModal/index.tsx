import { useEffect, useState } from "react";
import { useStore } from "../../store";
import type { Project } from "../../types";
import { Modal } from "../Modal";
import styles from "./index.module.scss";

export function ProjectModal() {
  const { showProjectModal, setShowProjectModal, editingProject, busy, saveProject } =
    useStore();
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [goal, setGoal] = useState("");
  const [stack, setStack] = useState("");

  useEffect(() => {
    if (!showProjectModal) return;
    setName(editingProject?.name ?? "");
    setRole(editingProject?.role ?? "");
    setGoal(editingProject?.goal ?? "");
    setStack(editingProject?.tech_stack.join(", ") ?? "");
  }, [showProjectModal, editingProject]);

  if (!showProjectModal) return null;

  function onSave() {
    if (!name.trim()) return;
    const fields = {
      name: name.trim(),
      role: role.trim(),
      goal: goal.trim(),
      tech_stack: stack
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    };
    saveProject(editingProject as Project | null, fields);
  }

  return (
    <Modal
      title={editingProject ? "编辑项目" : "新建项目"}
      onClose={() => setShowProjectModal(false)}
      actions={
        <>
          <button
            type="button"
            className="btn-ghost"
            onClick={() => setShowProjectModal(false)}
          >
            取消
          </button>
          <button
            type="button"
            className="btn-ink"
            disabled={busy || !name.trim()}
            onClick={onSave}
          >
            {busy ? "处理中…" : "保存"}
          </button>
        </>
      }
    >
      <div className="muted">
        项目可以是简历项目，也可以是工作主题。桑迪按面试官方式练你表达（练习场，不过掌握门）。
      </div>
      <input
        className="note-title-input"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="项目名称（必填）"
        disabled={busy}
      />
      <input
        className="note-title-input"
        value={role}
        onChange={(e) => setRole(e.target.value)}
        placeholder="你在项目里的角色（可选）"
        disabled={busy}
      />
      <textarea
        className={styles.goal}
        value={goal}
        onChange={(e) => setGoal(e.target.value)}
        placeholder="要备到的程度（可选，例如：能扛住 3 轮深挖）"
        rows={2}
        disabled={busy}
      />
      <input
        className="note-title-input"
        value={stack}
        onChange={(e) => setStack(e.target.value)}
        placeholder="技术栈，逗号分隔（可选）"
        disabled={busy}
      />
    </Modal>
  );
}
