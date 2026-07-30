import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../../api";
import { stripHtml } from "../../../lib/format";
import { useStore } from "../../../store";
import type { MemoryEntry } from "../../../types";
import styles from "./index.module.scss";

type Category = "all" | "morning" | "evening" | "news" | "interest";
type TimePreset = "all" | "today" | "7d" | "30d" | "custom";

const CATEGORIES: { id: Category; label: string }[] = [
  { id: "all", label: "全部" },
  { id: "morning", label: "今日计划" },
  { id: "evening", label: "明日计划" },
  { id: "news", label: "资讯" },
  { id: "interest", label: "标记有用" },
];

const TIME_PRESETS: { id: TimePreset; label: string; short: string }[] = [
  { id: "all", label: "全部时间", short: "全部" },
  { id: "today", label: "今天", short: "今天" },
  { id: "7d", label: "近 7 天", short: "7 天" },
  { id: "30d", label: "近 30 天", short: "30 天" },
  { id: "custom", label: "自定义", short: "自定义" },
];

/** Content kind (what the push is about) — not “早/晚 cron” jargon. */
const JOB_LABEL: Record<string, string> = {
  morning: "今日计划",
  evening: "明日计划",
  news: "资讯",
};

function pad2(n: number) {
  return String(n).padStart(2, "0");
}

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function endOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 59, 59, 999);
}

function parseLocalISO(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function fmtShort(iso: string): string {
  const [y, m, d] = iso.split("-");
  if (!y || !m || !d) return iso;
  return `${Number(m)}/${Number(d)}`;
}

/** Compact relative clock for dense list rows. */
function fmtCompactAt(iso: string): string {
  const t = new Date(iso);
  if (Number.isNaN(t.getTime())) return "";
  const now = new Date();
  const hm = `${pad2(t.getHours())}:${pad2(t.getMinutes())}`;
  const sod = startOfDay(now).getTime();
  const day = startOfDay(t).getTime();
  if (day === sod) return hm;
  if (day === sod - 86400000) return `昨天 ${hm}`;
  if (t.getFullYear() === now.getFullYear()) {
    return `${t.getMonth() + 1}/${t.getDate()} ${hm}`;
  }
  return `${t.getFullYear()}/${t.getMonth() + 1}/${t.getDate()}`;
}

function categoryLabel(e: MemoryEntry): string {
  const cat = activityCategory(e);
  if (cat === "morning") return JOB_LABEL.morning;
  if (cat === "evening") return JOB_LABEL.evening;
  if (cat === "news") return JOB_LABEL.news;
  if (cat === "interest") return "标记有用";
  return "";
}

/** Secondary line: only non-redundant extras (more plans / news / errors). */
function activityExtra(e: MemoryEntry): string {
  const c = e.content ?? {};
  if (e.kind !== "shell_event") return "";
  const job = String(c.job ?? "");
  const cat = activityCategory(e);
  const plans = planSubjects(c);
  const items = digestItems(c);
  const errN = Array.isArray(c.errors) ? c.errors.length : 0;
  const bits: string[] = [];
  if (plans.length > 1) {
    bits.push(
      plans.slice(1, 3).join("；") + (plans.length > 3 ? ` 等 ${plans.length} 条` : ""),
    );
  } else if ((cat === "news" || job === "news") && items.length > 1) {
    const rest = items.slice(subjectOffset(e), 3);
    if (rest.length) {
      bits.push(
        rest.map((it) => it.title || it.label).join("；") +
          (items.length > 3 ? ` 等 ${items.length} 条` : ""),
      );
    }
  }
  if (errN) bits.push(`${errN} 源失败`);
  return bits.join(" · ");
}

function truncate(s: string, max: number): string {
  const t = stripHtml(s).replace(/\s+/g, " ").trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1)}…`;
}

function planSubjects(content: Record<string, unknown>): string[] {
  return Array.isArray(content.due_summary)
    ? (content.due_summary as unknown[])
        .map(String)
        .map((s) => stripHtml(s).replace(/\s+/g, " ").trim())
        .filter(Boolean)
    : [];
}

function activityCategory(e: MemoryEntry): Category | "other" {
  if (e.kind === "interest") return "interest";
  if (e.kind === "shell_event") {
    const c = e.content ?? {};
    const job = String(c.job ?? "");
    const plans = planSubjects(c);
    const items = digestItems(c);
    // Legacy / morning_include_news: job=morning|evening but only RSS in items
    // → surface under 资讯, not 今日/明日计划.
    if (
      (job === "morning" || job === "evening") &&
      plans.length === 0 &&
      items.length > 0
    ) {
      return "news";
    }
    if (job === "morning" || job === "evening" || job === "news") return job;
  }
  return "other";
}

function activitySubject(e: MemoryEntry): string | null {
  const c = e.content ?? {};
  const job = String(c.job ?? "");
  const plans = planSubjects(c);
  const items = digestItems(c);
  const newsTitles = new Set(items.map((it) => it.title).filter(Boolean));
  const explicit =
    typeof c.subject === "string"
      ? stripHtml(c.subject).replace(/\s+/g, " ").trim()
      : "";

  if (job === "morning" || job === "evening") {
    if (plans.length) return plans[0];
    // Ignore subject wrongly copied from an RSS headline.
    if (explicit && !newsTitles.has(explicit)) return explicit;
    // News-only morning writeback: show headline when categorized as 资讯.
    if (plans.length === 0 && items.length > 0 && items[0].title) {
      return items[0].title;
    }
    return null;
  }
  if (job === "news" || e.kind === "interest") {
    if (explicit) return explicit;
    if (items.length && items[0].title) return items[0].title;
    const t = stripHtml(String(c.title ?? "")).replace(/\s+/g, " ").trim();
    return t || null;
  }
  if (explicit) return explicit;
  if (plans.length) return plans[0];
  if (items.length && items[0].title) return items[0].title;
  return null;
}

function activityTitle(e: MemoryEntry): string {
  const subject = activitySubject(e);
  if (subject) return truncate(subject, 48);
  if (e.kind === "interest") return "标记有用";
  const cat = activityCategory(e);
  if (cat === "morning" || cat === "evening") return "暂无计划";
  if (cat === "news") return "暂无资讯";
  const job = String(e.content?.job ?? "");
  return JOB_LABEL[job] ?? (job ? `推送 · ${job}` : "推送");
}

function digestItems(content: Record<string, unknown>) {
  const items = Array.isArray(content.items) ? content.items : [];
  return items
    .map((raw, i) => {
      if (!raw || typeof raw !== "object") return null;
      const o = raw as Record<string, unknown>;
      return {
        n: Number(o.n ?? i + 1),
        title: stripHtml(String(o.title ?? "")).replace(/\s+/g, " ").trim(),
        label: stripHtml(String(o.label ?? "")).replace(/\s+/g, " ").trim(),
        link: typeof o.link === "string" ? o.link : null,
        feed_id: typeof o.feed_id === "string" ? o.feed_id : null,
      };
    })
    .filter((x): x is NonNullable<typeof x> => x !== null && Boolean(x.title || x.label));
}

function subjectOffset(e: MemoryEntry): number {
  // If title already shows first news item, start rest from 1.
  return activitySubject(e) ? 1 : 0;
}

function daysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

type Range = { from: string; to: string };

function MonthGrid({
  year,
  month,
  range,
  onPick,
}: {
  year: number;
  month: number;
  range: Range;
  onPick: (iso: string) => void;
}) {
  const first = new Date(year, month, 1).getDay();
  const total = daysInMonth(year, month);
  const cells: (number | null)[] = [
    ...Array.from({ length: first }, () => null),
    ...Array.from({ length: total }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  const from = range.from ? parseLocalISO(range.from) : null;
  const to = range.to ? parseLocalISO(range.to) : null;

  return (
    <div className={styles.calGrid}>
      {["日", "一", "二", "三", "四", "五", "六"].map((d) => (
        <span key={d} className={styles.calDow}>
          {d}
        </span>
      ))}
      {cells.map((day, i) => {
        if (day === null) return <span key={`e-${i}`} className={styles.calEmpty} />;
        const iso = `${year}-${pad2(month + 1)}-${pad2(day)}`;
        const date = parseLocalISO(iso);
        const inRange =
          from && to && date >= startOfDay(from) && date <= startOfDay(to);
        const isFrom = range.from === iso;
        const isTo = range.to === iso;
        const isEdge = isFrom || isTo;
        return (
          <button
            key={iso}
            type="button"
            className={[
              styles.calDay,
              inRange ? styles.calInRange : "",
              isEdge ? styles.calEdge : "",
            ]
              .filter(Boolean)
              .join(" ")}
            onClick={() => onPick(iso)}
          >
            {day}
          </button>
        );
      })}
    </div>
  );
}

function timeBounds(
  timePreset: TimePreset,
  customRange: Range,
): { fromBound: Date | null; toBound: Date | null } {
  const now = new Date();
  if (timePreset === "today") {
    return { fromBound: startOfDay(now), toBound: endOfDay(now) };
  }
  if (timePreset === "7d") {
    return {
      fromBound: startOfDay(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6)),
      toBound: endOfDay(now),
    };
  }
  if (timePreset === "30d") {
    return {
      fromBound: startOfDay(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 29)),
      toBound: endOfDay(now),
    };
  }
  if (timePreset === "custom" && customRange.from && customRange.to) {
    return {
      fromBound: startOfDay(parseLocalISO(customRange.from)),
      toBound: endOfDay(parseLocalISO(customRange.to)),
    };
  }
  return { fromBound: null, toBound: null };
}

function inTimeRange(
  e: MemoryEntry,
  fromBound: Date | null,
  toBound: Date | null,
): boolean {
  if (!fromBound || !toBound || !e.created_at) return true;
  const t = new Date(e.created_at);
  return t >= fromBound && t <= toBound;
}

export function ShellObsPanel() {
  const { setError } = useStore();
  const [activity, setActivity] = useState<MemoryEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [category, setCategory] = useState<Category>("all");
  const [timePreset, setTimePreset] = useState<TimePreset>("all");
  const [customRange, setCustomRange] = useState<Range>({ from: "", to: "" });
  const [picking, setPicking] = useState<"from" | "to">("from");
  const [timeOpen, setTimeOpen] = useState(false);
  const [calCursor, setCalCursor] = useState(() => {
    const n = new Date();
    return { year: n.getFullYear(), month: n.getMonth() };
  });
  const [selected, setSelected] = useState<MemoryEntry | null>(null);
  const calRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const act = await api<MemoryEntry[]>("/v1/shell/activity?limit=100");
      setActivity(act);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }, [setError]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!timeOpen) return;
    const onDown = (e: MouseEvent) => {
      if (calRef.current && !calRef.current.contains(e.target as Node)) {
        setTimeOpen(false);
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [timeOpen]);

  const onPickDay = (iso: string) => {
    if (picking === "from" || !customRange.from || iso < customRange.from) {
      setCustomRange({ from: iso, to: "" });
      setPicking("to");
      return;
    }
    setCustomRange({ from: customRange.from, to: iso });
    setPicking("from");
    setTimePreset("custom");
  };

  const filtered = useMemo(() => {
    const { fromBound, toBound } = timeBounds(timePreset, customRange);
    return [...activity]
      .filter((e) => {
        if (category !== "all" && activityCategory(e) !== category) return false;
        return inTimeRange(e, fromBound, toBound);
      })
      .sort((a, b) => {
        const ta = a.created_at ? new Date(a.created_at).getTime() : 0;
        const tb = b.created_at ? new Date(b.created_at).getTime() : 0;
        return tb - ta;
      });
  }, [activity, category, timePreset, customRange]);

  const visibleCategories = useMemo(() => {
    const { fromBound, toBound } = timeBounds(timePreset, customRange);
    const present = new Set<Category>();
    for (const e of activity) {
      if (!inTimeRange(e, fromBound, toBound)) continue;
      const cat = activityCategory(e);
      if (cat !== "other") present.add(cat);
    }
    return CATEGORIES.filter((c) => c.id === "all" || present.has(c.id));
  }, [activity, timePreset, customRange]);

  useEffect(() => {
    if (!visibleCategories.some((c) => c.id === category)) {
      setCategory("all");
    }
  }, [visibleCategories, category]);

  const timeLabel = (() => {
    if (timePreset === "custom" && customRange.from && customRange.to) {
      return `${fmtShort(customRange.from)} – ${fmtShort(customRange.to)}`;
    }
    return TIME_PRESETS.find((p) => p.id === timePreset)?.label ?? "全部时间";
  })();

  if (selected) {
    const c = selected.content ?? {};
    const job = String(c.job ?? "");
    const cat = activityCategory(selected);
    const jobLabel =
      cat === "news"
        ? JOB_LABEL.news
        : JOB_LABEL[job] ?? (job ? `推送 · ${job}` : "推送");
    const day = typeof c.day === "string" && c.day.trim() ? c.day.trim() : "";
    const items = digestItems(c);
    const due = planSubjects(c);
    const errors = Array.isArray(c.errors)
      ? (c.errors as unknown[]).map(String).filter(Boolean)
      : [];
    const link = typeof c.link === "string" ? c.link : null;
    const planLabel =
      job === "evening" ? "明日计划" : job === "morning" ? "今日计划" : "计划";

    return (
      <div className={styles.panel}>
        <div className={styles.sectionHead}>
          <button
            type="button"
            className={styles.backBtn}
            onClick={() => setSelected(null)}
          >
            ← 返回
          </button>
        </div>
        <div className={styles.detailCard}>
          <h3 className={styles.detailTitle}>{activityTitle(selected)}</h3>
          <p className={styles.detailMeta}>
            {[jobLabel, day, selected.created_at ? new Date(selected.created_at).toLocaleString() : ""]
              .filter(Boolean)
              .join(" · ")}
          </p>

          {selected.kind === "shell_event" ? (
            <>
              {due.length > 0 ? (
                <div className={styles.block}>
                  <p className={styles.blockLabel}>{planLabel}</p>
                  <ul className={styles.plainList}>
                    {due.map((d) => (
                      <li key={d}>{d}</li>
                    ))}
                  </ul>
                </div>
              ) : cat === "morning" || cat === "evening" ? (
                <p className={styles.mutedLine}>该日暂无计划</p>
              ) : null}
              {items.length > 0 ? (
                <div className={styles.block}>
                  <p className={styles.blockLabel}>资讯</p>
                  <ol className={styles.itemList}>
                    {items.map((it) => (
                      <li key={it.n} className={styles.itemRow}>
                        <span className={styles.itemIndex}>{it.n}</span>
                        <div className={styles.itemBody}>
                          <span className={styles.itemTitle}>
                            {it.label ? `${it.label} · ` : ""}
                            {it.title}
                          </span>
                          {it.link ? (
                            <a
                              className={styles.itemLink}
                              href={it.link}
                              target="_blank"
                              rel="noreferrer"
                            >
                              打开链接
                            </a>
                          ) : null}
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              ) : job === "news" ? (
                <p className={styles.mutedLine}>无资讯条目</p>
              ) : null}
              {errors.length > 0 ? (
                <div className={styles.block}>
                  <p className={styles.blockLabel}>源失败</p>
                  <ul className={styles.plainList}>
                    {errors.map((d) => (
                      <li key={d}>{d}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {c.delivery_ok === true || c.delivery_ok === false ? (
                <p className={styles.mutedLine}>
                  投递：{c.delivery_ok ? "成功" : "失败"}
                </p>
              ) : null}
            </>
          ) : null}

          {selected.kind === "interest" ? (
            <div className={styles.block}>
              <p className={styles.itemTitle}>{String(c.title ?? "")}</p>
              {link ? (
                <a className={styles.itemLink} href={link} target="_blank" rel="noreferrer">
                  打开链接
                </a>
              ) : null}
              {c.feed_id ? (
                <p className={styles.mutedLine}>来源 {String(c.feed_id)}</p>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      <div className={styles.toolbar}>
        <div className={styles.chips} role="tablist" aria-label="类别">
          {visibleCategories.map((c) => (
            <button
              key={c.id}
              type="button"
              role="tab"
              aria-selected={category === c.id}
              className={`${styles.chip} ${category === c.id ? styles.chipActive : ""}`}
              onClick={() => setCategory(c.id)}
            >
              {c.label}
            </button>
          ))}
        </div>

        <div className={styles.toolbarRight}>
          <div className={styles.timeWrap} ref={calRef}>
            <button
              type="button"
              className={`${styles.timeBtn} ${timeOpen ? styles.timeBtnOpen : ""} ${
                timePreset !== "all" ? styles.timeBtnActive : ""
              }`}
              aria-expanded={timeOpen}
              aria-haspopup="dialog"
              aria-label={`时间筛选：${timeLabel}`}
              onClick={() => setTimeOpen((o) => !o)}
            >
              <svg className={styles.timeIcon} viewBox="0 0 24 24" fill="none" aria-hidden>
                <rect
                  x="3.5"
                  y="5.5"
                  width="17"
                  height="15"
                  rx="2.5"
                  stroke="currentColor"
                  strokeWidth="1.5"
                />
                <path
                  d="M8 3.5v3M16 3.5v3M3.5 10h17"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
              <span className={styles.timeLabel}>{timeLabel}</span>
              <svg className={styles.timeCaret} viewBox="0 0 12 12" fill="none" aria-hidden>
                <path
                  d="M3 4.5 6 7.5 9 4.5"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>

            {timeOpen ? (
              <div className={styles.timePop} role="dialog" aria-label="时间筛选">
                <div className={styles.presetList}>
                  {TIME_PRESETS.filter((p) => p.id !== "custom").map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      className={`${styles.presetItem} ${
                        timePreset === p.id ? styles.presetItemActive : ""
                      }`}
                      onClick={() => {
                        setTimePreset(p.id);
                        setTimeOpen(false);
                      }}
                    >
                      {p.short}
                    </button>
                  ))}
                </div>

                <div className={styles.calBlock}>
                  <div className={styles.calHead}>
                    <button
                      type="button"
                      className={styles.calNav}
                      aria-label="上个月"
                      onClick={() =>
                        setCalCursor((c) => {
                          const m = c.month - 1;
                          return m < 0
                            ? { year: c.year - 1, month: 11 }
                            : { year: c.year, month: m };
                        })
                      }
                    >
                      ‹
                    </button>
                    <span className={styles.calMonth}>
                      {calCursor.year}年{calCursor.month + 1}月
                    </span>
                    <button
                      type="button"
                      className={styles.calNav}
                      aria-label="下个月"
                      onClick={() =>
                        setCalCursor((c) => {
                          const m = c.month + 1;
                          return m > 11
                            ? { year: c.year + 1, month: 0 }
                            : { year: c.year, month: m };
                        })
                      }
                    >
                      ›
                    </button>
                  </div>
                  <MonthGrid
                    year={calCursor.year}
                    month={calCursor.month}
                    range={customRange}
                    onPick={onPickDay}
                  />
                </div>

                <div className={styles.calActions}>
                  <span className={styles.calRangeHint}>
                    {picking === "from" || !customRange.from
                      ? "点选开始日"
                      : customRange.to
                        ? `${fmtShort(customRange.from)} – ${fmtShort(customRange.to)}`
                        : `${fmtShort(customRange.from)} 起 · 再选结束`}
                  </span>
                  <button
                    type="button"
                    className={styles.calActionGhost}
                    onClick={() => {
                      setCustomRange({ from: "", to: "" });
                      setPicking("from");
                      setTimePreset("all");
                    }}
                  >
                    清除
                  </button>
                  <button
                    type="button"
                    className={styles.calActionDone}
                    disabled={!customRange.from || !customRange.to}
                    onClick={() => {
                      setTimePreset("custom");
                      setTimeOpen(false);
                    }}
                  >
                    完成
                  </button>
                </div>
              </div>
            ) : null}
          </div>

          <button
            type="button"
            className={styles.refreshBtn}
            disabled={busy}
            onClick={() => void load()}
            aria-label="刷新"
            title="刷新"
          >
            <svg className={styles.refreshIcon} viewBox="0 0 24 24" fill="none" aria-hidden>
              <path
                d="M20 12a8 8 0 1 1-2.34-5.66"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
              <path
                d="M20 5v5h-5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
      </div>

      <ul className={styles.list}>
        {filtered.map((e) => {
          const cat = categoryLabel(e);
          const extra = activityExtra(e);
          return (
            <li key={e.id}>
              <button
                type="button"
                className={styles.row}
                onClick={() => setSelected(e)}
              >
                <div className={styles.rowBody}>
                  <span className={styles.title}>{activityTitle(e)}</span>
                  {extra ? <span className={styles.extra}>{extra}</span> : null}
                </div>
                <div className={styles.rowMeta}>
                  {cat && category === "all" ? (
                    <span className={styles.cat}>{cat}</span>
                  ) : null}
                  <span className={styles.time}>
                    {e.created_at ? fmtCompactAt(e.created_at) : ""}
                  </span>
                </div>
              </button>
            </li>
          );
        })}
        {filtered.length === 0 ? (
          <li className={styles.empty}>暂无动态</li>
        ) : null}
      </ul>
    </div>
  );
}
