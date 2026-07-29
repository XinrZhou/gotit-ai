import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import { Modal } from "../../components/Modal";
import {
  fileToAvatarDataUrl,
  profileInitials,
  profileTint,
} from "../../lib/userProfile";
import { useStore } from "../../store";
import type { McpConnector, SkillInfo } from "../../types";
import { ShellObsPanel } from "./ShellObsPanel";
import styles from "./index.module.scss";

type Tab = "general" | "skills" | "connectors" | "shell";

const TABS: { id: Tab; label: string }[] = [
  { id: "general", label: "通用" },
  { id: "skills", label: "Skills" },
  { id: "connectors", label: "MCP" },
  { id: "shell", label: "外设" },
];

export function SettingsPage() {
  const {
    settingsOpen,
    setSettingsOpen,
    resume,
    setShowResumeModal,
    setShowResumeViewer,
    setError,
    setFlash,
    userProfile,
    setUserProfile,
  } = useStore();
  const [tab, setTab] = useState<Tab>("general");
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [connectors, setConnectors] = useState<McpConnector[]>([]);
  const [busy, setBusy] = useState(false);
  const [draftName, setDraftName] = useState(userProfile.name);
  const [draftAvatar, setDraftAvatar] = useState(userProfile.avatar);
  const [installOpen, setInstallOpen] = useState(false);
  const [installMd, setInstallMd] = useState("");
  const [connOpen, setConnOpen] = useState<"json" | "manual" | null>(null);
  const [jsonPaste, setJsonPaste] = useState("");
  const [manualName, setManualName] = useState("");
  const [manualTransport, setManualTransport] = useState<"stdio" | "http" | "sse">(
    "stdio",
  );
  const [manualCommand, setManualCommand] = useState("");
  const [manualArgs, setManualArgs] = useState("");
  const [manualUrl, setManualUrl] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const avatarRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const [sk, conn] = await Promise.all([
        api<SkillInfo[]>("/v1/skills"),
        api<McpConnector[]>("/v1/connectors"),
      ]);
      setSkills(sk);
      setConnectors(conn);
    } catch (e) {
      setError(String(e));
    }
  }, [setError]);

  useEffect(() => {
    if (!settingsOpen) return;
    setDraftName(userProfile.name);
    setDraftAvatar(userProfile.avatar);
    void load();
  }, [settingsOpen, load, userProfile.name, userProfile.avatar]);

  if (!settingsOpen) return null;

  const run = async (action: () => Promise<void>, ok?: string) => {
    setBusy(true);
    try {
      await action();
      if (ok) setFlash(ok);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const profileDirty =
    draftName.trim() !== userProfile.name || draftAvatar !== userProfile.avatar;

  const onSaveProfile = () => {
    setUserProfile({ name: draftName, avatar: draftAvatar });
    setFlash("已保存资料");
  };

  const onPickAvatar = async (file: File) => {
    try {
      const url = await fileToAvatarDataUrl(file);
      setDraftAvatar(url);
    } catch (e) {
      setError(String(e));
    }
  };

  const onToggleSkill = (name: string, enabled: boolean) =>
    void run(
      () =>
        api(`/v1/skills/${encodeURIComponent(name)}`, {
          method: "PATCH",
          body: JSON.stringify({ enabled }),
        }),
      enabled ? "已启用 Skill" : "已关闭 Skill",
    );

  const onDeleteSkill = (name: string) =>
    void run(
      () =>
        api(`/v1/skills/${encodeURIComponent(name)}`, { method: "DELETE" }),
      "已移除 Skill",
    );

  const onInstallSkill = () =>
    void run(async () => {
      await api("/v1/skills", {
        method: "POST",
        body: JSON.stringify({ markdown: installMd }),
      });
      setInstallMd("");
      setInstallOpen(false);
    }, "Skill 已安装");

  const onFileSkill = async (file: File) => {
    const text = await file.text();
    setInstallMd(text);
    setInstallOpen(true);
  };

  const onToggleConnector = (id: string, enabled: boolean) =>
    void run(
      () =>
        api(`/v1/connectors/${id}`, {
          method: "PATCH",
          body: JSON.stringify({ enabled }),
        }),
      enabled ? "已启用 MCP" : "已关闭 MCP",
    );

  const onDeleteConnector = (id: string) =>
    void run(
      () => api(`/v1/connectors/${id}`, { method: "DELETE" }),
      "已删除 MCP",
    );

  const onProbe = (id: string) =>
    void run(
      () => api(`/v1/connectors/${id}/probe`, { method: "POST" }),
      "探测完成",
    );

  const onImportJson = () =>
    void run(async () => {
      const config = JSON.parse(jsonPaste) as Record<string, unknown>;
      await api("/v1/connectors/import", {
        method: "POST",
        body: JSON.stringify({ config }),
      });
      setJsonPaste("");
      setConnOpen(null);
    }, "已导入 MCP");

  const onAddManual = () =>
    void run(async () => {
      const config =
        manualTransport === "stdio"
          ? {
              command: manualCommand.trim(),
              args: manualArgs
                .split(/\s+/)
                .map((s) => s.trim())
                .filter(Boolean),
              env: {},
            }
          : { url: manualUrl.trim(), headers: {} };
      await api("/v1/connectors", {
        method: "POST",
        body: JSON.stringify({
          name: manualName.trim(),
          transport: manualTransport,
          config,
          enabled: true,
        }),
      });
      setManualName("");
      setManualCommand("");
      setManualArgs("");
      setManualUrl("");
      setConnOpen(null);
    }, "已添加 MCP");

  const previewName = draftName.trim() || "学习者";

  return (
    <Modal title="设置" onClose={() => setSettingsOpen(false)} wide flush>
      <div className={styles.settings}>
        <nav className={styles.side} aria-label="设置分类">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`${styles.tab} ${tab === t.id ? styles.tabActive : ""}`}
              onClick={() => {
                setTab(t.id);
                setInstallOpen(false);
                setConnOpen(null);
              }}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div className={styles.pane}>
          {installOpen ? (
            <div className={styles.sheet}>
              <h4 className={styles.sheetTitle}>Install Skill</h4>
              <p className={styles.hint}>粘贴含 frontmatter 的 SKILL.md</p>
              <textarea
                className={styles.textarea}
                rows={10}
                value={installMd}
                onChange={(e) => setInstallMd(e.target.value)}
                placeholder={"---\nskill: my-skill\nnotes: …\n---\n\n## Skill\n…"}
              />
              <div className={styles.sheetActions}>
                <button type="button" className="btn-ghost" onClick={() => setInstallOpen(false)}>
                  取消
                </button>
                <button
                  type="button"
                  className="btn-ink"
                  disabled={busy || !installMd.trim()}
                  onClick={onInstallSkill}
                >
                  安装
                </button>
              </div>
            </div>
          ) : null}

          {connOpen === "json" ? (
            <div className={styles.sheet}>
              <h4 className={styles.sheetTitle}>Paste MCP JSON</h4>
              <p className={styles.hint}>Claude / Cursor 风格的 mcpServers 配置</p>
              <textarea
                className={styles.textarea}
                rows={10}
                value={jsonPaste}
                onChange={(e) => setJsonPaste(e.target.value)}
                placeholder={
                  '{\n  "mcpServers": {\n    "name": { "command": "npx", "args": [] }\n  }\n}'
                }
              />
              <div className={styles.sheetActions}>
                <button type="button" className="btn-ghost" onClick={() => setConnOpen(null)}>
                  取消
                </button>
                <button
                  type="button"
                  className="btn-ink"
                  disabled={busy || !jsonPaste.trim()}
                  onClick={onImportJson}
                >
                  导入
                </button>
              </div>
            </div>
          ) : null}

          {connOpen === "manual" ? (
            <div className={styles.sheet}>
              <h4 className={styles.sheetTitle}>Add MCP Server</h4>
              <label className={styles.field}>
                <span>Name</span>
                <input value={manualName} onChange={(e) => setManualName(e.target.value)} />
              </label>
              <label className={styles.field}>
                <span>Transport</span>
                <select
                  value={manualTransport}
                  onChange={(e) =>
                    setManualTransport(e.target.value as "stdio" | "http" | "sse")
                  }
                >
                  <option value="stdio">STDIO</option>
                  <option value="http">HTTP</option>
                  <option value="sse">SSE</option>
                </select>
              </label>
              {manualTransport === "stdio" ? (
                <>
                  <label className={styles.field}>
                    <span>Command</span>
                    <input
                      value={manualCommand}
                      onChange={(e) => setManualCommand(e.target.value)}
                      placeholder="npx"
                    />
                  </label>
                  <label className={styles.field}>
                    <span>Args</span>
                    <input
                      value={manualArgs}
                      onChange={(e) => setManualArgs(e.target.value)}
                      placeholder="-y some-mcp-server"
                    />
                  </label>
                </>
              ) : (
                <label className={styles.field}>
                  <span>URL</span>
                  <input
                    value={manualUrl}
                    onChange={(e) => setManualUrl(e.target.value)}
                    placeholder="https://…"
                  />
                </label>
              )}
              <div className={styles.sheetActions}>
                <button type="button" className="btn-ghost" onClick={() => setConnOpen(null)}>
                  取消
                </button>
                <button
                  type="button"
                  className="btn-ink"
                  disabled={
                    busy ||
                    !manualName.trim() ||
                    (manualTransport === "stdio"
                      ? !manualCommand.trim()
                      : !manualUrl.trim())
                  }
                  onClick={onAddManual}
                >
                  添加
                </button>
              </div>
            </div>
          ) : null}

          {!installOpen && !connOpen && tab === "general" ? (
            <>
              <p className={styles.paneTitle}>资料</p>
              <div className={styles.group}>
                <div className={`${styles.groupRow} ${styles.groupRowStack}`}>
                  <div className={styles.profileRow}>
                    <button
                      type="button"
                      className={styles.avatarBtn}
                      style={
                        draftAvatar
                          ? undefined
                          : { background: profileTint(previewName) }
                      }
                      onClick={() => avatarRef.current?.click()}
                      title="更换头像"
                      aria-label="更换头像"
                    >
                      {draftAvatar ? (
                        <img src={draftAvatar} alt="" />
                      ) : (
                        <span>{profileInitials(previewName)}</span>
                      )}
                    </button>
                    <input
                      ref={avatarRef}
                      type="file"
                      accept="image/*"
                      hidden
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) void onPickAvatar(f);
                        e.target.value = "";
                      }}
                    />
                    <div className={styles.profileFields}>
                      <input
                        className={styles.nameInput}
                        value={draftName}
                        maxLength={32}
                        placeholder="你的称呼"
                        aria-label="名称"
                        onChange={(e) => setDraftName(e.target.value)}
                      />
                      <div className={styles.avatarActions}>
                        <button
                          type="button"
                          className="btn-ghost"
                          onClick={() => avatarRef.current?.click()}
                        >
                          更换头像
                        </button>
                        {draftAvatar ? (
                          <button
                            type="button"
                            className="btn-ghost"
                            onClick={() => setDraftAvatar("")}
                          >
                            使用缩写
                          </button>
                        ) : null}
                      </div>
                    </div>
                    {profileDirty ? (
                      <button
                        type="button"
                        className={`btn-ink ${styles.profileSave}`}
                        onClick={onSaveProfile}
                      >
                        保存
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>

              <p className={styles.paneTitle}>简历</p>
              <div className={styles.group}>
                <div className={styles.groupRow}>
                  <div className={styles.groupMain}>
                    <span className={styles.groupLabel}>
                      {resume ? "已导入" : "未导入"}
                    </span>
                    <span className={styles.groupMeta}>
                      {resume
                        ? "可查看或重新导入，用于项目深挖"
                        : "导入后可用于项目深挖"}
                    </span>
                  </div>
                  <div className={styles.row}>
                    {resume ? (
                      <button
                        type="button"
                        className="btn-ghost"
                        disabled={busy}
                        onClick={() => {
                          setSettingsOpen(false);
                          setShowResumeViewer(true);
                        }}
                      >
                        查看
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="btn-ghost"
                      disabled={busy}
                      onClick={() => {
                        setSettingsOpen(false);
                        setShowResumeModal(true);
                      }}
                    >
                      {resume ? "重新导入" : "导入"}
                    </button>
                  </div>
                </div>
              </div>
            </>
          ) : null}

          {!installOpen && !connOpen && tab === "skills" ? (
            <>
              <div className={styles.sectionHead}>
                <div>
                  <p className={styles.paneTitle}>Installed</p>
                  <p className={styles.hint}>上传 SKILL.md，无市场</p>
                </div>
                <div className={styles.row}>
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".md,text/markdown,text/plain"
                    hidden
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) void onFileSkill(f);
                      e.target.value = "";
                    }}
                  />
                  <button
                    type="button"
                    className="btn-ghost"
                    disabled={busy}
                    onClick={() => fileRef.current?.click()}
                  >
                    Upload
                  </button>
                  <button
                    type="button"
                    className="btn-ink"
                    disabled={busy}
                    onClick={() => setInstallOpen(true)}
                  >
                    Paste
                  </button>
                </div>
              </div>
              <div className={styles.group}>
                <ul className={styles.list}>
                  {skills.map((s) => (
                    <li key={s.name} className={styles.listItem}>
                      <div className={styles.listMain}>
                        <span className={styles.listName}>{s.name}</span>
                        <span className={styles.listMeta}>
                          {s.source === "builtin" ? "builtin" : "user"}
                          {s.notes ? ` · ${s.notes}` : ""}
                        </span>
                      </div>
                      <div className={styles.listActions}>
                        <label className={styles.toggle}>
                          <input
                            type="checkbox"
                            checked={s.enabled}
                            disabled={busy}
                            onChange={(e) => onToggleSkill(s.name, e.target.checked)}
                          />
                          <span>{s.enabled ? "On" : "Off"}</span>
                        </label>
                        {s.source === "user" ? (
                          <button
                            type="button"
                            className="btn-ghost"
                            disabled={busy}
                            onClick={() => onDeleteSkill(s.name)}
                          >
                            删除
                          </button>
                        ) : null}
                      </div>
                    </li>
                  ))}
                  {skills.length === 0 ? (
                    <li className={styles.empty}>No skills yet</li>
                  ) : null}
                </ul>
              </div>
            </>
          ) : null}

          {!installOpen && !connOpen && tab === "connectors" ? (
            <>
              <div className={styles.sectionHead}>
                <div>
                  <p className={styles.paneTitle}>Servers</p>
                  <p className={styles.hint}>挂给搭子当工具</p>
                </div>
                <div className={styles.row}>
                  <button
                    type="button"
                    className="btn-ghost"
                    disabled={busy}
                    onClick={() => setConnOpen("json")}
                  >
                    Paste JSON
                  </button>
                  <button
                    type="button"
                    className="btn-ink"
                    disabled={busy}
                    onClick={() => setConnOpen("manual")}
                  >
                    Add
                  </button>
                </div>
              </div>
              <div className={styles.group}>
                <ul className={styles.list}>
                  {connectors.map((c) => (
                    <li key={c.id} className={styles.listItem}>
                      <div className={styles.listMain}>
                        <span className={styles.listName}>
                          <span
                            className={`${styles.dot} ${
                              c.last_status === "ok"
                                ? styles.dotOk
                                : c.last_status === "error"
                                  ? styles.dotErr
                                  : ""
                            }`}
                            title={c.last_error ?? c.last_status}
                          />
                          {c.name}
                        </span>
                        <span className={styles.listMeta}>
                          {c.transport}
                          {c.last_status !== "unknown" ? ` · ${c.last_status}` : ""}
                          {c.last_error ? ` · ${c.last_error}` : ""}
                        </span>
                      </div>
                      <div className={styles.listActions}>
                        <label className={styles.toggle}>
                          <input
                            type="checkbox"
                            checked={c.enabled}
                            disabled={busy}
                            onChange={(e) => onToggleConnector(c.id, e.target.checked)}
                          />
                          <span>{c.enabled ? "On" : "Off"}</span>
                        </label>
                        <button
                          type="button"
                          className="btn-ghost"
                          disabled={busy}
                          onClick={() => onProbe(c.id)}
                        >
                          Probe
                        </button>
                        <button
                          type="button"
                          className="btn-ghost"
                          disabled={busy}
                          onClick={() => onDeleteConnector(c.id)}
                        >
                          删除
                        </button>
                      </div>
                    </li>
                  ))}
                  {connectors.length === 0 ? (
                    <li className={styles.empty}>No MCP servers</li>
                  ) : null}
                </ul>
              </div>
            </>
          ) : null}

          {!installOpen && !connOpen && tab === "shell" ? <ShellObsPanel /> : null}
        </div>
      </div>
    </Modal>
  );
}
