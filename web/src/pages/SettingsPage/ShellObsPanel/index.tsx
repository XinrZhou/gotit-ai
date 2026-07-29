import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../../api";
import { useStore } from "../../../store";
import type { MemoryEntry } from "../../../types";
import styles from "./index.module.scss";

type Category = "all" | "morning" | "evening" | "interest";
type TimePreset = "all" | "today" | "7d" | "30d" | "custom";

const CATEGORIES: { id: Category; label: string }[] = [
  { id: "all", label: "全部" },
  { id: "morning", label: "早间简报" },
  { id: "evening", label: "晚间简报" },
  { id: "interest", label: "标记有用" },
];

const TIME_PRESETS: { id: TimePreset; label: string }[] = [
  { id: "all", label: "全部时间" },
  { id: "today", label: "今天" },
  { id: "7d", label: "近 7 天" },
  { id: "30d", label: "近 30 天" },
  { id: "custom", label: "自定义" },
];

const JOB_LABEL: Record<string, string> = {
  morning: "早间简报",
  evening: "晚间简报",
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

function activityCategory(e: MemoryEntry): Category | "other" {
  if (e.kind === "interest") return "interest";
  if (e.kind === "shell_event") {
    const job = String(e.content?.job ?? "");
    if (job === "morning" || job === "evening") return job;
  }
  return "other";
}

function activityTitle(e: MemoryEntry): string {
  const c = e.content ?? {};
  if (e.kind === "shell_event") {
    const job = String(c.job ?? "");
    return JOB_LABEL[job] ?? (job ? `简报 · ${job}` : "简报推送");
  }
  if (e.kind === "interest") return "标记有用";
  return e.kind;
}

function digestItems(content: Record<string, unknown>) {
  const items = Array.isArray(content.items) ? content.items : [];
  return items
    .map((raw, i) => {
      if (!raw || typeof raw !== "object") return null;
      const o = raw as Record<string, unknown>;
      return {
        n: Number(o.n ?? i + 1),
        title: String(o.title ?? "").trim(),
        label: String(o.label ?? "").trim(),
        link: typeof o.link === "string" ? o.link : null,
        feed_id: typeof o.feed_id === "string" ? o.feed_id : null,
      };
    })
    .filter((x): x is NonNullable<typeof x> => x !== null && Boolean(x.title || x.label));
}

function activitySummary(e: MemoryEntry): string {
  const c = e.content ?? {};
  if (e.kind === "shell_event") {
    const items = digestItems(c);
    const due = Array.isArray(c.due_summary)
      ? (c.due_summary as unknown[]).map(String).filter(Boolean)
      : [];
    const errN = Array.isArray(c.errors) ? c.errors.length : 0;
    const parts: string[] = [];
    if (items.length) {
      parts.push(items.slice(0, 3).map((it) => it.title || it.label).join("；"));
      if (items.length > 3) parts[0] += ` 等 ${items.length} 条`;
    } else {
      parts.push("无条目");
    }
    if (due.length) parts.push(`待检 ${due.length}`);
    if (errN) parts.push(`${errN} 源失败`);
    return parts.join(" · ");
  }
  if (e.kind === "interest") return String(c.title ?? "一条资讯");
  return "";
}

function daysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

type Range = { from: string; to: string };

function MonthGrid({
  year,
  month,
  range,
  picking,
  onPick,
}: {
  year: number;
  month: number;
  range: Range;
  picking: "from" | "to";
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
              picking === "from" && !range.from ? styles.calHint : "",
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
    const now = new Date();
    let fromBound: Date | null = null;
    let toBound: Date | null = null;
    if (timePreset === "today") {
      fromBound = startOfDay(now);
      toBound = endOfDay(now);
    } else if (timePreset === "7d") {
      fromBound = startOfDay(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6));
      toBound = endOfDay(now);
    } else if (timePreset === "30d") {
      fromBound = startOfDay(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 29));
      toBound = endOfDay(now);
    } else if (timePreset === "custom" && customRange.from && customRange.to) {
      fromBound = startOfDay(parseLocalISO(customRange.from));
      toBound = endOfDay(parseLocalISO(customRange.to));
    }

    return [...activity]
      .filter((e) => {
        if (category !== "all" && activityCategory(e) !== category) return false;
        if (!fromBound || !toBound || !e.created_at) return true;
        const t = new Date(e.created_at);
        return t >= fromBound && t <= toBound;
      })
      .sort((a, b) => {
        const ta = a.created_at ? new Date(a.created_at).getTime() : 0;
        const tb = b.created_at ? new Date(b.created_at).getTime() : 0;
        return tb - ta;
      });
  }, [activity, category, timePreset, customRange]);

  const timeLabel = (() => {
    if (timePreset === "custom" && customRange.from && customRange.to) {
      return `${fmtShort(customRange.from)} – ${fmtShort(customRange.to)}`;
    }
    return TIME_PRESETS.find((p) => p.id === timePreset)?.label ?? "全部时间";
  })();

  if (selected) {
    const c = selected.content ?? {};
    const items = digestItems(c);
    const due = Array.isArray(c.due_summary)
      ? (c.due_summary as unknown[]).map(String).filter(Boolean)
      : [];
    const errors = Array.isArray(c.errors)
      ? (c.errors as unknown[]).map(String).filter(Boolean)
      : [];
    const link = typeof c.link === "string" ? c.link : null;

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
            {selected.created_at ? new Date(selected.created_at).toLocaleString() : ""}
          </p>

          {selected.kind === "shell_event" ? (
            <>
              {items.length > 0 ? (
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
              ) : (
                <p className={styles.mutedLine}>无资讯条目</p>
              )}
              {due.length > 0 ? (
                <div className={styles.block}>
                  <p className={styles.blockLabel}>今日待检</p>
                  <ul className={styles.plainList}>
                    {due.map((d) => (
                      <li key={d}>{d}</li>
                    ))}
                  </ul>
                </div>
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
      <h3 className={styles.sectionTitle}>动态</h3>

      <div className={styles.toolbar}>
        <div className={styles.chips} role="tablist" aria-label="类别">
          {CATEGORIES.map((c) => (
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
                      {p.label}
                    </button>
                  ))}
                </div>

                <div className={styles.timeDivider} />

                <p className={styles.calHintText}>
                  {picking === "from" || !customRange.from
                    ? "自定义范围 · 先选开始"
                    : customRange.to
                      ? `${fmtShort(customRange.from)} – ${fmtShort(customRange.to)}`
                      : `开始 ${fmtShort(customRange.from)} · 再选结束`}
                </p>
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
                    {calCursor.year} 年 {calCursor.month + 1} 月
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
                  picking={picking}
                  onPick={onPickDay}
                />
                <div className={styles.calActions}>
                  <button
                    type="button"
                    className="btn-ghost"
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
                    className="btn-ink"
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
        {filtered.map((e) => (
          <li key={e.id}>
            <button
              type="button"
              className={styles.row}
              onClick={() => setSelected(e)}
            >
              <div className={styles.rowMain}>
                <div className={styles.rowTop}>
                  <span className={styles.title}>{activityTitle(e)}</span>
                  <span className={styles.time}>
                    {e.created_at ? new Date(e.created_at).toLocaleString() : ""}
                  </span>
                </div>
                <span className={styles.detail}>{activitySummary(e)}</span>
              </div>
            </button>
          </li>
        ))}
        {filtered.length === 0 ? (
          <li className={styles.empty}>暂无动态</li>
        ) : null}
      </ul>
    </div>
  );
}
