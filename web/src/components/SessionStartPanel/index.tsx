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
    drillSessions,
    onSelectDrillSession,
    onDrillStartSession,
  } = useStore();

  return (
    <div className={styles.wrap}>
      <div className={styles.panel}>
        <div className={styles.title}>开始一轮模拟面试</div>
        <div className={styles.muted}>
          桑迪会看着你的简历（{resume?.document.projects.length ?? 0} 个项目）和深挖资料，像面试官一样深挖。
        </div>

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

        <div className={styles.field}>
          <div className={styles.fieldLabel}>聚焦项目（可选，不选就是整份简历）</div>
          <select
            className={styles.select}
            value={drillFocusProjectId ?? ""}
            onChange={(e) => setDrillFocusProjectId(e.target.value || null)}
            disabled={busy}
          >
            <option value="">整份简历</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
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
