import { useCallback, useEffect, useState } from "react";
import { api } from "../../../api";
import { parseApiDate } from "../../../lib/format";
import { useStore } from "../../../store";
import type {
  InterviewEvent,
  InterviewRampPrefs,
  InterviewStatus,
  InterviewUpcoming,
} from "../../../types";
import styles from "./index.module.scss";

const ROUNDS: { id: string; label: string }[] = [
  { id: "", label: "未指定" },
  { id: "tech_1", label: "技术一面" },
  { id: "tech_2", label: "技术二面" },
  { id: "tech_3", label: "技术三面" },
  { id: "tech_4", label: "技术四面" },
  { id: "hr", label: "HR 面" },
];

function roundLabel(round: string | null): string {
  if (!round) return "";
  return ROUNDS.find((r) => r.id === round)?.label ?? round;
}

function toLocalInput(iso: string): string {
  const d = parseApiDate(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromLocalInput(value: string): string {
  if (!value) return "";
  const d = new Date(value);
  return d.toISOString();
}

function fmtScheduled(iso: string): string {
  const d = parseApiDate(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

type Draft = {
  company: string;
  role_title: string;
  scheduled_at: string;
  round: string;
  notes: string;
};

const emptyDraft = (): Draft => ({
  company: "",
  role_title: "",
  scheduled_at: "",
  round: "",
  notes: "",
});

export function InterviewsPanel() {
  const { setFlash, setError } = useStore();
  const [items, setItems] = useState<InterviewEvent[]>([]);
  const [upcomingById, setUpcomingById] = useState<
    Record<string, InterviewUpcoming>
  >({});
  const [rampPrefs, setRampPrefs] = useState<InterviewRampPrefs>({
    enabled: true,
    max_nudges_per_week: 2,
  });
  const [includeDone, setIncludeDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>(emptyDraft);

  const refresh = useCallback(async () => {
    try {
      const q = includeDone ? "?include_done=true" : "";
      const [data, upcoming, prefs] = await Promise.all([
        api<InterviewEvent[]>(`/v1/interviews${q}`),
        api<InterviewUpcoming[]>("/v1/interviews/upcoming"),
        api<InterviewRampPrefs>("/v1/interviews/ramp-prefs"),
      ]);
      setItems(data);
      const map: Record<string, InterviewUpcoming> = {};
      for (const u of upcoming) map[u.interview_id] = u;
      setUpcomingById(map);
      setRampPrefs(prefs);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [includeDone, setError]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const run = async (action: () => Promise<void>, ok?: string) => {
    setBusy(true);
    try {
      await action();
      if (ok) setFlash(ok);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onToggleRamp = () =>
    void run(async () => {
      const next = {
        ...rampPrefs,
        enabled: !rampPrefs.enabled,
      };
      await api<InterviewRampPrefs>("/v1/interviews/ramp-prefs", {
        method: "PUT",
        body: JSON.stringify(next),
      });
    }, rampPrefs.enabled ? "已关闭倒计时升温" : "已开启倒计时升温");

  const openCreate = () => {
    setEditingId(null);
    setDraft(emptyDraft());
    setSheetOpen(true);
  };

  const openEdit = (item: InterviewEvent) => {
    setEditingId(item.id);
    setDraft({
      company: item.company,
      role_title: item.role_title,
      scheduled_at: toLocalInput(item.scheduled_at),
      round: item.round ?? "",
      notes: item.notes ?? "",
    });
    setSheetOpen(true);
  };

  const closeSheet = () => {
    setSheetOpen(false);
    setEditingId(null);
    setDraft(emptyDraft());
  };

  const onSave = () =>
    void run(async () => {
      const body = {
        id: editingId ?? undefined,
        company: draft.company.trim(),
        role_title: draft.role_title.trim(),
        scheduled_at: fromLocalInput(draft.scheduled_at),
        round: draft.round || null,
        notes: draft.notes.trim() || null,
      };
      await api("/v1/interviews", {
        method: "POST",
        body: JSON.stringify(body),
      });
      closeSheet();
    }, editingId ? "已更新面试" : "已添加面试");

  const onStatus = (id: string, status: InterviewStatus) =>
    void run(
      () =>
        api(`/v1/interviews/${id}`, {
          method: "PATCH",
          body: JSON.stringify({ status }),
        }),
      status === "done" ? "已标记完成" : "已取消",
    );

  const onDelete = (id: string) =>
    void run(
      () => api(`/v1/interviews/${id}`, { method: "DELETE" }),
      "已删除",
    );

  if (sheetOpen) {
    return (
      <div className={styles.panel}>
        <h4 className={styles.sheetTitle}>
          {editingId ? "编辑面试" : "添加面试"}
        </h4>
        <div className={styles.sheetBody}>
          <label className={styles.field}>
            <span>公司</span>
            <input
              value={draft.company}
              onChange={(e) => setDraft({ ...draft, company: e.target.value })}
              placeholder="公司名"
            />
          </label>
          <label className={styles.field}>
            <span>岗位</span>
            <input
              value={draft.role_title}
              onChange={(e) => setDraft({ ...draft, role_title: e.target.value })}
              placeholder="岗位名称"
            />
          </label>
          <label className={styles.field}>
            <span>时间</span>
            <input
              type="datetime-local"
              value={draft.scheduled_at}
              onChange={(e) =>
                setDraft({ ...draft, scheduled_at: e.target.value })
              }
            />
          </label>
          <div className={styles.field}>
            <span>轮次</span>
            <div className={styles.segment} role="radiogroup" aria-label="轮次">
              {ROUNDS.map((opt) => (
                <button
                  key={opt.id || "none"}
                  type="button"
                  role="radio"
                  aria-checked={draft.round === opt.id}
                  className={`${styles.segmentItem} ${
                    draft.round === opt.id ? styles.segmentActive : ""
                  }`}
                  onClick={() => setDraft({ ...draft, round: opt.id })}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          <label className={styles.field}>
            <span>备注</span>
            <textarea
              className={styles.textarea}
              value={draft.notes}
              onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
              placeholder="地点、面试官、JD 链接…"
              rows={3}
            />
          </label>
        </div>
        <div className={styles.sheetActions}>
          <button type="button" className="btn-ghost" onClick={closeSheet}>
            取消
          </button>
          <button
            type="button"
            className="btn-ink"
            disabled={
              busy ||
              !draft.company.trim() ||
              !draft.role_title.trim() ||
              !draft.scheduled_at
            }
            onClick={onSave}
          >
            保存
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      <div className={styles.head}>
        <p className={styles.sectionTitle}>面试安排</p>
        <div className={styles.headActions}>
          <button
            type="button"
            className={`${styles.filterChip} ${includeDone ? styles.filterActive : ""}`}
            onClick={() => setIncludeDone((v) => !v)}
          >
            含已完成
          </button>
          <button
            type="button"
            className="btn-ink"
            disabled={busy}
            onClick={openCreate}
          >
            添加
          </button>
        </div>
      </div>
      <p className={styles.hint}>
        记录真实面试时间；OpenClaw 会按提前 24h / 2h 推送提醒。临近 3～7
        天可另发低频「升温」提示（可关），建议练项目表达（练习场，不过门）。
      </p>
      <div className={styles.rampRow}>
        <button
          type="button"
          className={`${styles.filterChip} ${rampPrefs.enabled ? styles.filterActive : ""}`}
          disabled={busy}
          onClick={onToggleRamp}
        >
          倒计时升温 {rampPrefs.enabled ? "开" : "关"}
        </button>
        <span className={styles.rampMeta}>
          每周最多 {rampPrefs.max_nudges_per_week} 条 · 关了仍保留 24h/2h 提醒
        </span>
      </div>
      <ul className={styles.list}>
        {items.map((item) => {
          const ramp = upcomingById[item.id];
          return (
          <li key={item.id} className={styles.listItem}>
            <button
              type="button"
              className={styles.listMain}
              onClick={() => openEdit(item)}
            >
              <span className={styles.listTitle}>
                {item.company} · {item.role_title}
              </span>
              <span className={styles.listMeta}>
                {fmtScheduled(item.scheduled_at)}
                {item.round ? ` · ${roundLabel(item.round)}` : ""}
                {item.status !== "scheduled" ? ` · ${item.status}` : ""}
                {ramp?.tier_hint ? ` · ${ramp.tier_hint}` : ""}
              </span>
            </button>
            <div className={styles.listActions}>
              {item.status === "scheduled" ? (
                <>
                  <button
                    type="button"
                    className="btn-ghost"
                    disabled={busy}
                    onClick={() => onStatus(item.id, "done")}
                  >
                    完成
                  </button>
                  <button
                    type="button"
                    className="btn-ghost"
                    disabled={busy}
                    onClick={() => onStatus(item.id, "cancelled")}
                  >
                    取消
                  </button>
                </>
              ) : null}
              <button
                type="button"
                className="btn-ghost"
                disabled={busy}
                onClick={() => onDelete(item.id)}
              >
                删除
              </button>
            </div>
          </li>
          );
        })}
        {items.length === 0 ? (
          <li className={styles.empty}>暂无面试安排</li>
        ) : null}
      </ul>
    </div>
  );
}
