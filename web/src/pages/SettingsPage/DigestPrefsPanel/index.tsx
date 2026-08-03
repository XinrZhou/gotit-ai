import { useCallback, useEffect, useState } from "react";
import { api } from "../../../api";
import { useStore } from "../../../store";
import styles from "./index.module.scss";

export type DigestFeed = {
  id: string;
  label: string;
  url: string;
  enabled: boolean;
};

export type DigestPrefs = {
  timezone: string;
  item_count: number;
  morning_cron: string;
  evening_cron: string;
  news_cron: string | null;
  news_enabled: boolean;
  morning_include_news: boolean;
  evening_include_news: boolean;
  keywords: string[];
  feeds: DigestFeed[];
  notes_open_url: string | null;
};

type CronTarget = "morning" | "evening" | "news";

const emptyPrefs = (): DigestPrefs => ({
  timezone: "Asia/Shanghai",
  item_count: 3,
  morning_cron: "0 8 * * *",
  evening_cron: "0 21 * * *",
  news_cron: "0 20 * * *",
  news_enabled: true,
  morning_include_news: false,
  evening_include_news: false,
  keywords: [],
  feeds: [],
  notes_open_url: null,
});

function buildBody(prefs: DigestPrefs, keywordsText: string): DigestPrefs {
  return {
    ...prefs,
    evening_include_news: false,
    morning_include_news: false,
    notes_open_url: prefs.notes_open_url?.trim() || null,
    keywords: keywordsText
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean),
    feeds: prefs.feeds.map((f) => ({
      ...f,
      id: f.id.trim() || f.label.trim() || "feed",
      label: f.label.trim() || f.id.trim() || "feed",
      url: f.url.trim(),
    })),
  };
}

export function DigestPrefsPanel() {
  const { setFlash, setError } = useStore();
  const [prefs, setPrefs] = useState<DigestPrefs>(emptyPrefs);
  const [keywordsText, setKeywordsText] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [cronHints, setCronHints] = useState<Record<CronTarget, string>>({
    morning: "",
    evening: "",
    news: "",
  });
  const [suggestBusy, setSuggestBusy] = useState<CronTarget | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await api<DigestPrefs>("/v1/shell/digest-prefs");
      setPrefs({ ...emptyPrefs(), ...data, feeds: data.feeds ?? [] });
      setKeywordsText((data.keywords ?? []).join(", "));
      setLoaded(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [setError]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const applySaved = (saved: DigestPrefs) => {
    setPrefs({ ...emptyPrefs(), ...saved, feeds: saved.feeds ?? [] });
    setKeywordsText((saved.keywords ?? []).join(", "));
  };

  const save = async () => {
    setBusy(true);
    setError("");
    try {
      const saved = await api<DigestPrefs>("/v1/shell/digest-prefs", {
        method: "PUT",
        body: JSON.stringify(buildBody(prefs, keywordsText)),
      });
      applySaved(saved);
      setFlash("提醒设置已保存");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const saveAndSync = async () => {
    setBusy(true);
    setError("");
    try {
      const saved = await api<DigestPrefs>("/v1/shell/digest-prefs", {
        method: "PUT",
        body: JSON.stringify(buildBody(prefs, keywordsText)),
      });
      applySaved(saved);
      const r = await api<{
        ok: boolean;
        exit_code: number;
        stdout: string;
        stderr: string;
        detail: string | null;
      }>("/v1/shell/digest-cron/sync", { method: "POST" });
      if (r.ok) {
        setFlash("已保存，并同步到 OpenClaw cron");
      } else {
        setFlash("设置已保存，但 OpenClaw cron 同步失败");
        setError(
          r.detail ||
            r.stderr?.trim() ||
            r.stdout?.trim() ||
            `同步失败（exit ${r.exit_code}）`,
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const suggestCron = async (target: CronTarget) => {
    const text = cronHints[target].trim();
    if (!text) {
      setError("先写一句时间，例如「每天早上九点半」");
      return;
    }
    if (target === "news" && !prefs.news_enabled) {
      setError("请先开启独立资讯推送");
      return;
    }
    setSuggestBusy(target);
    setError("");
    try {
      const r = await api<{ cron: string; explanation: string | null; source: string }>(
        "/v1/shell/digest-cron/suggest",
        {
          method: "POST",
          body: JSON.stringify({ text, target }),
        },
      );
      setPrefs((p) => {
        if (target === "morning") return { ...p, morning_cron: r.cron };
        if (target === "evening") return { ...p, evening_cron: r.cron };
        return { ...p, news_cron: r.cron };
      });
      setCronHints((h) => ({ ...h, [target]: "" }));
      setFlash(r.explanation || `已填入 ${r.cron}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSuggestBusy(null);
    }
  };

  const cronAiRow = (target: CronTarget, placeholder: string) => (
    <div className={styles.cronAi}>
      <input
        className={styles.cronAiInput}
        value={cronHints[target]}
        placeholder={placeholder}
        onChange={(e) =>
          setCronHints((h) => ({ ...h, [target]: e.target.value }))
        }
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            void suggestCron(target);
          }
        }}
      />
      <button
        type="button"
        className={styles.cronAiBtn}
        disabled={suggestBusy !== null || busy}
        onClick={() => void suggestCron(target)}
      >
        {suggestBusy === target ? "生成中…" : "AI 生成"}
      </button>
    </div>
  );

  const updateFeed = (idx: number, patch: Partial<DigestFeed>) => {
    setPrefs((p) => ({
      ...p,
      feeds: p.feeds.map((f, i) => (i === idx ? { ...f, ...patch } : f)),
    }));
  };

  const addFeed = () => {
    setPrefs((p) => ({
      ...p,
      feeds: [
        ...p.feeds,
        {
          id: `feed-${p.feeds.length + 1}`,
          label: "新源",
          url: "https://www.youtube.com/feeds/videos.xml?channel_id=UC",
          enabled: true,
        },
      ],
    }));
  };

  const removeFeed = (idx: number) => {
    setPrefs((p) => ({ ...p, feeds: p.feeds.filter((_, i) => i !== idx) }));
  };

  if (!loaded) {
    return <p className={styles.hint}>加载提醒设置…</p>;
  }

  return (
    <div className={styles.digest}>
      <header className={styles.header}>
        <h3 className={styles.sectionTitle}>计划提醒</h3>
        <p className={styles.hint}>
          早推当日计划，晚推今日复盘+明日安排；资讯默认晚上八点单独推（不与计划混发）。改完点「保存并同步」。
        </p>
      </header>

      <section className={styles.block}>
        <h4 className={styles.blockLabel}>时间</h4>
        <label className={styles.field}>
          <span>时区</span>
          <input
            value={prefs.timezone}
            onChange={(e) => setPrefs((p) => ({ ...p, timezone: e.target.value }))}
          />
        </label>

        <div className={styles.field}>
          <span>早推 cron</span>
          <input
            className={styles.mono}
            value={prefs.morning_cron}
            onChange={(e) =>
              setPrefs((p) => ({ ...p, morning_cron: e.target.value }))
            }
            spellCheck={false}
          />
          {cronAiRow("morning", "自然语言，如「每天早上九点半」")}
        </div>
        <div className={styles.field}>
          <span>晚推 cron</span>
          <input
            className={styles.mono}
            value={prefs.evening_cron}
            onChange={(e) =>
              setPrefs((p) => ({ ...p, evening_cron: e.target.value }))
            }
            spellCheck={false}
          />
          {cronAiRow("evening", "自然语言，如「每天晚上九点」")}
        </div>
      </section>

      <section className={styles.block}>
        <h4 className={styles.blockLabel}>资讯（独立推送）</h4>
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={prefs.news_enabled}
            onChange={(e) => {
              const on = e.target.checked;
              setPrefs((p) => ({
                ...p,
                news_enabled: on,
                news_cron: on ? (p.news_cron ?? "0 20 * * *") : p.news_cron,
              }));
            }}
          />
          <span>启用资讯推送（独立 cron，绝不并入早/晚报）</span>
        </label>

        {prefs.news_enabled ? (
          <>
            <div className={styles.row2}>
              <div className={styles.field}>
                <span>资讯 cron</span>
                <input
                  className={styles.mono}
                  value={prefs.news_cron ?? "0 20 * * *"}
                  onChange={(e) =>
                    setPrefs((p) => ({ ...p, news_cron: e.target.value }))
                  }
                  spellCheck={false}
                />
                {cronAiRow("news", "自然语言，如「每天晚上八点」")}
              </div>
              <label className={styles.field}>
                <span>条数</span>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={prefs.item_count}
                  onChange={(e) =>
                    setPrefs((p) => ({
                      ...p,
                      item_count: Number(e.target.value) || 3,
                    }))
                  }
                />
              </label>
            </div>

            <label className={styles.field}>
              <span>兴趣关键词（逗号分隔）</span>
              <input
                value={keywordsText}
                placeholder="LLM, Agent, 多模态"
                onChange={(e) => setKeywordsText(e.target.value)}
              />
            </label>

            <div className={styles.feedsHead}>
              <span className={styles.subTitle}>RSS / YouTube 源</span>
              <button type="button" className={styles.linkBtn} onClick={addFeed}>
                添加
              </button>
            </div>
            <p className={styles.hintTight}>
              YouTube Atom：
              <code>…/feeds/videos.xml?channel_id=UC…</code>
            </p>

            <ul className={styles.feedList}>
              {prefs.feeds.map((f, idx) => (
                <li key={`${f.id}-${idx}`} className={styles.feedCard}>
                  <div className={styles.feedTop}>
                    <label className={styles.check}>
                      <input
                        type="checkbox"
                        checked={f.enabled}
                        onChange={(e) =>
                          updateFeed(idx, { enabled: e.target.checked })
                        }
                      />
                      <span>启用</span>
                    </label>
                    <button
                      type="button"
                      className={styles.linkBtn}
                      onClick={() => removeFeed(idx)}
                    >
                      删除
                    </button>
                  </div>
                  <div className={styles.row2}>
                    <input
                      className={styles.feedInput}
                      value={f.label}
                      placeholder="名称"
                      onChange={(e) => updateFeed(idx, { label: e.target.value })}
                    />
                    <input
                      className={styles.feedInput}
                      value={f.id}
                      placeholder="id"
                      onChange={(e) => updateFeed(idx, { id: e.target.value })}
                    />
                  </div>
                  <input
                    className={styles.feedInputWide}
                    value={f.url}
                    placeholder="RSS / Atom URL"
                    onChange={(e) => updateFeed(idx, { url: e.target.value })}
                  />
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </section>

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.ghostBtn}
          disabled={busy}
          onClick={() => void save()}
        >
          仅保存
        </button>
        <button
          type="button"
          className="btn-ink"
          disabled={busy}
          onClick={() => void saveAndSync()}
        >
          {busy ? "处理中…" : "保存并同步"}
        </button>
      </div>
    </div>
  );
}
