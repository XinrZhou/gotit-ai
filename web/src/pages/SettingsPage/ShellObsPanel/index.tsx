import { useCallback, useEffect, useState } from "react";
import { api } from "../../../api";
import { useStore } from "../../../store";
import type { GraphView, MemoryEntry, ProfileView } from "../../../types";
import styles from "./index.module.scss";

function activitySummary(e: MemoryEntry): string {
  const c = e.content ?? {};
  if (e.kind === "shell_event") {
    const job = String(c.job ?? "?");
    const n = Array.isArray(c.items) ? c.items.length : 0;
    const errN = Array.isArray(c.errors) ? c.errors.length : 0;
    return `${job} · ${n} 条${errN ? ` · ${errN} 源失败` : ""}`;
  }
  if (e.kind === "interest") {
    return String(c.title ?? "兴趣");
  }
  return e.kind;
}

export function ShellObsPanel() {
  const { setError } = useStore();
  const [activity, setActivity] = useState<MemoryEntry[]>([]);
  const [profile, setProfile] = useState<ProfileView | null>(null);
  const [graph, setGraph] = useState<GraphView | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [act, prof, g] = await Promise.all([
        api<MemoryEntry[]>("/v1/shell/activity?limit=40"),
        api<ProfileView>("/v1/obs/profile"),
        api<GraphView>("/v1/obs/graph"),
      ]);
      setActivity(act);
      setProfile(prof);
      setGraph(g);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }, [setError]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className={styles.panel}>
      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <div>
            <h3 className={styles.sectionTitle}>外设动态</h3>
            <p className={styles.hint}>
              OpenClaw 简报写回（shell_event / interest），以 gotit 为观测真源
            </p>
          </div>
          <button type="button" className="btn-ghost" disabled={busy} onClick={() => void load()}>
            刷新
          </button>
        </div>
        <ul className={styles.list}>
          {activity.map((e) => (
            <li key={e.id} className={styles.row}>
              <span className={styles.kind}>{e.kind}</span>
              <span className={styles.summary}>{activitySummary(e)}</span>
              <span className={styles.time}>
                {e.created_at ? new Date(e.created_at).toLocaleString() : ""}
              </span>
            </li>
          ))}
          {activity.length === 0 ? (
            <li className={styles.empty}>暂无外设写回 — 跑一次 digest 或 cron</li>
          ) : null}
        </ul>
      </section>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>画像 v0</h3>
        {profile ? (
          <div className={styles.stats}>
            <span>轨迹 {profile.trajectory_total}</span>
            <span>兴趣 {profile.interest_total}</span>
            <span>简报 {profile.shell_event_total}</span>
            {profile.weak_topics.length > 0 ? (
              <p className={styles.hint}>弱点主题：{profile.weak_topics.join(" · ")}</p>
            ) : (
              <p className={styles.hint}>暂无弱点主题聚合</p>
            )}
          </div>
        ) : (
          <p className={styles.hint}>加载中…</p>
        )}
      </section>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>图谱 v0</h3>
        {graph ? (
          <p className={styles.hint}>
            {graph.nodes.length} 节点 · {graph.edges.length} 边（claim / topic / project；兴趣仅连
            topic）
          </p>
        ) : (
          <p className={styles.hint}>加载中…</p>
        )}
      </section>
    </div>
  );
}
