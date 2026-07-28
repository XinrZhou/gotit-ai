import { useEffect, useRef, useState } from "react";
import { useStore } from "../../store";
import type { DrillRound } from "../../types";
import styles from "./index.module.scss";

const ROUNDS: { value: DrillRound; label: string; hint: string }[] = [
  { value: "tech_1", label: "技术一面", hint: "基础 · 项目梳理" },
  { value: "tech_2", label: "技术二面", hint: "深度追问 · 系统设计" },
  { value: "tech_3", label: "技术三面", hint: "架构 · 跨项目" },
  { value: "tech_4", label: "技术四面", hint: "资深终面" },
  { value: "hr", label: "HR 面", hint: "行为面 · 职业规划" },
];

export function SessionStartPanel() {
  const {
    busy,
    resume,
    projects,
    drillRound,
    setDrillRound,
    drillDirection,
    setDrillDirection,
    drillFocusProjectId,
    setDrillFocusProjectId,
    projectPicked,
    drillSessions,
    onSelectDrillSession,
    onDrillStartSession,
  } = useStore();

  const [projOpen, setProjOpen] = useState(false);
  const projRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!projOpen) return;
    const onDown = (e: MouseEvent) => {
      if (projRef.current && !projRef.current.contains(e.target as Node)) {
        setProjOpen(false);
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [projOpen]);

  const focusLabel = drillFocusProjectId
    ? projects.find((p) => p.id === drillFocusProjectId)?.name ?? "整份简历"
    : "整份简历";

  const focusProject = drillFocusProjectId
    ? projects.find((p) => p.id === drillFocusProjectId) ?? null
    : null;
  // Match the focused project back to its resume-parsed content by name.
  const focusResumeProject = focusProject
    ? resume?.document.projects.find((rp) => rp.name === focusProject.name) ?? null
    : null;

  return (
    <div className={styles.wrap}>
      <div className={styles.panel}>
        <div className={styles.title}>开始一轮模拟面试</div>
        <div className={styles.muted}>
          桑迪会看着你的简历（{resume?.document.projects.length ?? 0} 个项目）和深挖资料，像面试官一样深挖。
        </div>

        {projectPicked && focusProject ? (
          <div className={styles.focusCtx}>
            <div className={styles.focusCtxHead}>
              <span className={styles.focusCtxTitle}>{focusProject.name}</span>
              <span className={styles.focusCtxTag}>即将深挖</span>
            </div>
            <div className={styles.focusCtxMeta}>
              {focusProject.role ? <span>{focusProject.role}</span> : null}
              {focusProject.tech_stack.length > 0 ? (
                <span className={styles.focusCtxStack}>
                  {focusProject.tech_stack.join(" · ")}
                </span>
              ) : null}
            </div>
            {focusResumeProject?.description ? (
              <pre className={styles.focusCtxDesc}>{focusResumeProject.description}</pre>
            ) : (
              <div className={styles.focusCtxEmpty}>这条项目没有简历描述，可直接开始或先补一段。</div>
            )}
          </div>
        ) : projectPicked && resume ? (
          <div className={styles.focusCtx}>
            <div className={styles.focusCtxHead}>
              <span className={styles.focusCtxTitle}>整份简历</span>
              <span className={styles.focusCtxTag}>即将深挖</span>
            </div>
            <div className={styles.focusCtxMeta}>
              {resume.document.basics.name ? <span>{resume.document.basics.name}</span> : null}
              {resume.document.basics.target_role ? (
                <span>{resume.document.basics.target_role}</span>
              ) : null}
              <span className={styles.focusCtxStack}>
                {resume.document.projects.length} 个项目
              </span>
            </div>
            <div className={styles.focusCtxEmpty}>
              不聚焦具体项目，桑迪会在整份简历范围内出题。
            </div>
          </div>
        ) : null}

        <div className={styles.field}>
          <div className={styles.fieldLabel}>面试轮次</div>
          <div className={styles.roundRow}>
            {ROUNDS.map((r) => (
              <button
                key={r.value}
                type="button"
                className={drillRound === r.value ? `${styles.roundBtn} ${styles.roundActive}` : styles.roundBtn}
                onClick={() => setDrillRound(r.value)}
                disabled={busy}
              >
                <span className={styles.roundLabel}>{r.label}</span>
                <span className={styles.roundHint}>{r.hint}</span>
              </button>
            ))}
          </div>
        </div>

        <div className={styles.field}>
          <div className={styles.fieldLabel}>补充方向（可选）</div>
          <input
            className={styles.directionInput}
            value={drillDirection}
            onChange={(e) => setDrillDirection(e.target.value)}
            placeholder="例如：偏架构 / 偏系统设计 / 偏工程落地"
            disabled={busy}
          />
        </div>

        <div className={styles.field} ref={projRef}>
          <div className={styles.fieldLabel}>聚焦项目（可选，不选就是整份简历）</div>
          <button
            type="button"
            className={styles.selectBtn}
            onClick={() => setProjOpen((v) => !v)}
            disabled={busy}
          >
            <span className={styles.selectValue}>{focusLabel}</span>
            <span className={styles.selectCaret}>{projOpen ? "▴" : "▾"}</span>
          </button>
          {projOpen ? (
            <div className={styles.selectMenu}>
              <button
                type="button"
                className={
                  drillFocusProjectId === null
                    ? `${styles.selectOption} ${styles.selectOptionActive}`
                    : styles.selectOption
                }
                onClick={() => {
                  setDrillFocusProjectId(null);
                  setProjOpen(false);
                }}
              >
                整份简历
              </button>
              {projects.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className={
                    drillFocusProjectId === p.id
                      ? `${styles.selectOption} ${styles.selectOptionActive}`
                      : styles.selectOption
                  }
                  onClick={() => {
                    setDrillFocusProjectId(p.id);
                    setProjOpen(false);
                  }}
                >
                  {p.name}
                </button>
              ))}
            </div>
          ) : null}
        </div>

        <button
          type="button"
          className="btn-ink"
          disabled={busy || !resume}
          onClick={onDrillStartSession}
        >
          {busy ? "处理中…" : "开始深挖"}
        </button>
      </div>

      {drillSessions.length > 0 ? (
        <div className={styles.history}>
          <div className={styles.historyLabel}>历史 session</div>
          {drillSessions.map((s) => (
            <button
              key={s.id}
              type="button"
              className={styles.historyItem}
              onClick={() => onSelectDrillSession(s)}
            >
              <span className={styles.historyRound}>
                {ROUNDS.find((r) => r.value === s.round)?.label ?? s.round}
              </span>
              {s.direction ? <span className={styles.historyDir}>{s.direction}</span> : null}
              <span className={styles.historyStatus}>
                {s.status === "done" ? "已结束" : "进行中"}
              </span>
              <span className={styles.historyMsgs}>{s.messages.length} 轮</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
