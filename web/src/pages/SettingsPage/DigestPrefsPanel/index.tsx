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

const emptyPrefs = (): DigestPrefs => ({
  timezone: "Asia/Shanghai",
  item_count: 3,
  morning_cron: "0 8 * * *",
  evening_cron: "0 21 * * *",
  news_cron: "0 12 * * *",
  news_enabled: false,
  morning_include_news: false,
  evening_include_news: false,
  keywords: [],
  feeds: [],
  notes_open_url: null,
});

export function DigestPrefsPanel() {
  const { setFlash, setError } = useStore();
  const [prefs, setPrefs] = useState<DigestPrefs>(emptyPrefs);
  const [keywordsText, setKeywordsText] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

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

  const save = async () => {
    setBusy(true);
    setError("");
    try {
      const body: DigestPrefs = {
        ...prefs,
        evening_include_news: false,
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
      const saved = await api<DigestPrefs>("/v1/shell/digest-prefs", {
        method: "PUT",
        body: JSON.stringify(body),
      });
      setPrefs({ ...emptyPrefs(), ...saved, feeds: saved.feeds ?? [] });
      setKeywordsText((saved.keywords ?? []).join(", "));
      setFlash("计划推送设置已保存");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const syncCron = async () => {
    setBusy(true);
    setError("");
    try {
      const r = await api<{
        ok: boolean;
        exit_code: number;
        stdout: string;
        stderr: string;
        detail: string | null;
      }>("/v1/shell/digest-cron/sync", { method: "POST" });
      if (r.ok) {
        setFlash("已同步到 OpenClaw cron");
      } else {
        setError(
          r.detail ||
            r.stderr?.trim() ||
            r.stdout?.trim() ||
            `同步失败（exit ${r.exit_code}）。请确认本机已装 openclaw 且 Gateway 在跑。`,
        );
      }
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
      const body: DigestPrefs = {
        ...prefs,
        evening_include_news: false,
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
      const saved = await api<DigestPrefs>("/v1/shell/digest-prefs", {
        method: "PUT",
        body: JSON.stringify(body),
      });
      setPrefs({ ...emptyPrefs(), ...saved, feeds: saved.feeds ?? [] });
      setKeywordsText((saved.keywords ?? []).join(", "));
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
    return <p className={styles.hint}>加载计划推送设置…</p>;
  }

  return (
    <div className={styles.digest}>
      <h3 className={styles.sectionTitle}>计划推送</h3>
      <p className={styles.hint}>
        早推当日计划、晚推明日计划询问；资讯默认独立且关闭。改时间或开关后点「保存并同步」，会在本机重注册
        OpenClaw cron（需 Gateway 在跑）。
      </p>

      <label className={styles.field}>
        <span>时区</span>
        <input
          value={prefs.timezone}
          onChange={(e) => setPrefs((p) => ({ ...p, timezone: e.target.value }))}
        />
      </label>

      <div className={styles.row2}>
        <label className={styles.field}>
          <span>早 cron（当日计划）</span>
          <input
            value={prefs.morning_cron}
            onChange={(e) =>
              setPrefs((p) => ({ ...p, morning_cron: e.target.value }))
            }
          />
        </label>
        <label className={styles.field}>
          <span>晚 cron（明日计划）</span>
          <input
            value={prefs.evening_cron}
            onChange={(e) =>
              setPrefs((p) => ({ ...p, evening_cron: e.target.value }))
            }
          />
        </label>
      </div>

      <label className={styles.check}>
        <input
          type="checkbox"
          checked={prefs.news_enabled}
          onChange={(e) =>
            setPrefs((p) => ({ ...p, news_enabled: e.target.checked }))
          }
        />
        <span>启用独立资讯推送（不与计划混推）</span>
      </label>

      {prefs.news_enabled ? (
        <div className={styles.row2}>
          <label className={styles.field}>
            <span>资讯 cron</span>
            <input
              value={prefs.news_cron ?? "0 12 * * *"}
              onChange={(e) =>
                setPrefs((p) => ({ ...p, news_cron: e.target.value }))
              }
            />
          </label>
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
      ) : null}

      <label className={styles.check}>
        <input
          type="checkbox"
          checked={prefs.morning_include_news}
          onChange={(e) =>
            setPrefs((p) => ({
              ...p,
              morning_include_news: e.target.checked,
            }))
          }
        />
        <span>早报附带少量资讯（仍不推荐；晚报永不附带）</span>
      </label>

      <label className={styles.field}>
        <span>兴趣关键词（逗号分隔，过滤资讯标题）</span>
        <input
          value={keywordsText}
          placeholder="LLM, Agent, 多模态"
          onChange={(e) => setKeywordsText(e.target.value)}
        />
      </label>

      <div className={styles.feedsHead}>
        <h4 className={styles.subTitle}>RSS / YouTube 源</h4>
        <button type="button" className={styles.linkBtn} onClick={addFeed}>
          添加
        </button>
      </div>
      <p className={styles.hint}>
        YouTube：填{" "}
        <code>
          https://www.youtube.com/feeds/videos.xml?channel_id=UC…
        </code>
      </p>

      <ul className={styles.feedList}>
        {prefs.feeds.map((f, idx) => (
          <li key={`${f.id}-${idx}`} className={styles.feedCard}>
            <label className={styles.check}>
              <input
                type="checkbox"
                checked={f.enabled}
                onChange={(e) => updateFeed(idx, { enabled: e.target.checked })}
              />
              <span>启用</span>
            </label>
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
            <input
              className={styles.feedInputWide}
              value={f.url}
              placeholder="RSS / Atom URL"
              onChange={(e) => updateFeed(idx, { url: e.target.value })}
            />
            <button
              type="button"
              className={styles.linkBtn}
              onClick={() => removeFeed(idx)}
            >
              删除
            </button>
          </li>
        ))}
      </ul>

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.secondaryBtn}
          disabled={busy}
          onClick={() => void syncCron()}
        >
          {busy ? "处理中…" : "仅同步 cron"}
        </button>
        <button
          type="button"
          className={styles.secondaryBtn}
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
