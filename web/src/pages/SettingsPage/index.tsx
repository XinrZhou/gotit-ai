import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import { Modal } from "../../components/Modal";
import {
  fileToAvatarDataUrl,
  profileInitials,
  profileTint,
} from "../../lib/userProfile";
import { useStore } from "../../store";
import type { McpConnector, SkillDetail, SkillInfo } from "../../types";
import { DigestPrefsPanel } from "./DigestPrefsPanel";
import { InterviewsPanel } from "./InterviewsPanel";
import { ShellObsPanel } from "./ShellObsPanel";
import styles from "./index.module.scss";

type Tab = "general" | "skills" | "connectors" | "digest" | "shell";

const TABS: { id: Tab; label: string }[] = [
  { id: "general", label: "资料" },
  { id: "skills", label: "Skills" },
  { id: "connectors", label: "MCP" },
  { id: "digest", label: "计划推送" },
  { id: "shell", label: "动态" },
];

type SkillSheet =
  | { kind: "install" }
  | { kind: "detail"; name: string; markdown: string; editable: boolean };

type ConnSheet = "json" | "manual" | "edit" | null;

function connectorConfigFields(c: McpConnector) {
  const cfg = c.config ?? {};
  if (c.transport === "stdio") {
    const args = Array.isArray(cfg.args)
      ? (cfg.args as string[]).join(" ")
      : String(cfg.args ?? "");
    return {
      command: String(cfg.command ?? ""),
      args,
      url: "",
    };
  }
  return {
    command: "",
    args: "",
    url: String(cfg.url ?? ""),
  };
}

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
  const [skillSheet, setSkillSheet] = useState<SkillSheet | null>(null);
  const [skillMd, setSkillMd] = useState("");
  const [connOpen, setConnOpen] = useState<ConnSheet>(null);
  const [editingConnId, setEditingConnId] = useState<string | null>(null);
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

  const closeSheets = () => {
    setSkillSheet(null);
    setSkillMd("");
    setConnOpen(null);
    setEditingConnId(null);
  };

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

  const onOpenSkill = async (name: string) => {
    setBusy(true);
    try {
      const detail = await api<SkillDetail>(`/v1/skills/${encodeURIComponent(name)}`);
      setSkillMd(detail.markdown);
      setSkillSheet({
        kind: "detail",
        name: detail.name,
        markdown: detail.markdown,
        editable: detail.editable,
      });
      setConnOpen(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const onSaveSkill = () => {
    if (!skillSheet) return;
    if (skillSheet.kind === "install") {
      void run(async () => {
        await api("/v1/skills", {
          method: "POST",
          body: JSON.stringify({ markdown: skillMd }),
        });
        closeSheets();
      }, "Skill 已安装");
      return;
    }
    void run(async () => {
      await api(`/v1/skills/${encodeURIComponent(skillSheet.name)}`, {
        method: "PATCH",
        body: JSON.stringify({ markdown: skillMd }),
      });
      closeSheets();
    }, "Skill 已保存");
  };

  const onFileSkill = async (file: File) => {
    const text = await file.text();
    setSkillMd(text);
    setSkillSheet({ kind: "install" });
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

  const openConnEdit = (c: McpConnector) => {
    const fields = connectorConfigFields(c);
    setEditingConnId(c.id);
    setManualName(c.name);
    setManualTransport(c.transport);
    setManualCommand(fields.command);
    setManualArgs(fields.args);
    setManualUrl(fields.url);
    setConnOpen("edit");
    setSkillSheet(null);
  };

  const openConnAdd = () => {
    setEditingConnId(null);
    setManualName("");
    setManualTransport("stdio");
    setManualCommand("");
    setManualArgs("");
    setManualUrl("");
    setConnOpen("manual");
    setSkillSheet(null);
  };

  const onImportJson = () =>
    void run(async () => {
      const config = JSON.parse(jsonPaste) as Record<string, unknown>;
      await api("/v1/connectors/import", {
        method: "POST",
        body: JSON.stringify({ config }),
      });
      setJsonPaste("");
      closeSheets();
    }, "已导入 MCP");

  const onSaveConnector = () =>
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
      if (editingConnId) {
        await api(`/v1/connectors/${editingConnId}`, {
          method: "PATCH",
          body: JSON.stringify({
            name: manualName.trim(),
            transport: manualTransport,
            config,
          }),
        });
      } else {
        await api("/v1/connectors", {
          method: "POST",
          body: JSON.stringify({
            name: manualName.trim(),
            transport: manualTransport,
            config,
            enabled: true,
          }),
        });
      }
      closeSheets();
    }, editingConnId ? "已保存 MCP" : "已添加 MCP");

  const previewName = draftName.trim() || "学习者";
  const sheetOpen = skillSheet !== null || connOpen !== null;
  const skillEditable =
    skillSheet?.kind === "install" ||
    (skillSheet?.kind === "detail" && skillSheet.editable);

  return (
    <Modal onClose={() => setSettingsOpen(false)} wide flush titleless>
      <div className={styles.settings}>
        <nav className={styles.side} aria-label="设置分类">
          <h2 className={styles.sideTitle}>设置</h2>
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`${styles.tab} ${tab === t.id ? styles.tabActive : ""}`}
              onClick={() => {
                setTab(t.id);
                closeSheets();
              }}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div
          className={`${styles.pane}${sheetOpen ? ` ${styles.paneSheet}` : ""}${
            !sheetOpen && tab === "shell" ? ` ${styles.paneFill}` : ""
          }`}
        >
          {skillSheet ? (
            <div className={styles.sheet}>
              <h4 className={styles.sheetTitle}>
                {skillSheet.kind === "install"
                  ? "安装 Skill"
                  : skillSheet.editable
                    ? `编辑 · ${skillSheet.name}`
                    : `查看 · ${skillSheet.name}`}
              </h4>
              <textarea
                className={styles.textarea}
                value={skillMd}
                readOnly={!skillEditable}
                onChange={(e) => setSkillMd(e.target.value)}
                placeholder={"---\nskill: my-skill\nnotes: …\n---\n\n## Skill\n…"}
              />
              <div className={styles.sheetActions}>
                <button type="button" className="btn-ghost" onClick={closeSheets}>
                  {skillEditable ? "取消" : "关闭"}
                </button>
                {skillEditable ? (
                  <button
                    type="button"
                    className="btn-ink"
                    disabled={busy || !skillMd.trim()}
                    onClick={onSaveSkill}
                  >
                    {skillSheet.kind === "install" ? "安装" : "保存"}
                  </button>
                ) : null}
              </div>
            </div>
          ) : null}

          {connOpen === "json" ? (
            <div className={styles.sheet}>
              <h4 className={styles.sheetTitle}>粘贴 MCP JSON</h4>
              <textarea
                className={styles.textarea}
                value={jsonPaste}
                onChange={(e) => setJsonPaste(e.target.value)}
                placeholder={
                  '{\n  "mcpServers": {\n    "name": { "command": "npx", "args": [] }\n  }\n}'
                }
              />
              <div className={styles.sheetActions}>
                <button type="button" className="btn-ghost" onClick={closeSheets}>
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

          {connOpen === "manual" || connOpen === "edit" ? (
            <div className={styles.sheet}>
              <h4 className={styles.sheetTitle}>
                {connOpen === "edit" ? "编辑 MCP" : "添加 MCP"}
              </h4>
              <div className={styles.sheetBody}>
                <label className={styles.field}>
                  <span>名称</span>
                  <input value={manualName} onChange={(e) => setManualName(e.target.value)} />
                </label>
                <div className={styles.field}>
                  <span>传输</span>
                  <div className={styles.segment} role="radiogroup" aria-label="传输">
                    {(
                      [
                        { id: "stdio", label: "STDIO" },
                        { id: "http", label: "HTTP" },
                        { id: "sse", label: "SSE" },
                      ] as const
                    ).map((opt) => (
                      <button
                        key={opt.id}
                        type="button"
                        role="radio"
                        aria-checked={manualTransport === opt.id}
                        className={`${styles.segmentItem} ${
                          manualTransport === opt.id ? styles.segmentActive : ""
                        }`}
                        onClick={() => setManualTransport(opt.id)}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
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
              </div>
              <div className={styles.sheetActions}>
                <button type="button" className="btn-ghost" onClick={closeSheets}>
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
                  onClick={onSaveConnector}
                >
                  保存
                </button>
              </div>
            </div>
          ) : null}

          {!sheetOpen && tab === "general" ? (
            <>
              <div>
                <p className={styles.paneTitle}>称呼</p>
                <div className={styles.group}>
                  <div className={`${styles.groupRow} ${styles.groupRowStack}`}>
                    <div className={styles.profileRow}>
                      <div className={styles.profileLead}>
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
                        <input
                          className={styles.nameInput}
                          value={draftName}
                          maxLength={32}
                          placeholder="你的称呼"
                          aria-label="名称"
                          onChange={(e) => setDraftName(e.target.value)}
                        />
                      </div>
                      <div className={styles.avatarActions}>
                        <button
                          type="button"
                          className="btn-ghost"
                          onClick={() => avatarRef.current?.click()}
                        >
                          更换
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
                </div>
              </div>

              <div>
                <p className={styles.paneTitle}>简历</p>
                <div className={styles.group}>
                  <div className={styles.groupRow}>
                    <div className={styles.groupMain}>
                      <span className={styles.groupLabel}>
                        {resume ? "已导入" : "未导入"}
                      </span>
                      <span className={styles.groupMeta}>
                        {resume
                          ? "可查看或重新导入，给项目练习当上下文（练习场，不过门）"
                          : "导入后可用于项目练习（练习场，不过门）"}
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
              </div>

              <InterviewsPanel />

              <div>
                <p className={styles.paneTitle}>Apple 计划桥</p>
                <div className={styles.group}>
                  <div className={`${styles.groupRow} ${styles.groupRowStack}`}>
                    <div className={styles.groupMain}>
                      <span className={styles.groupLabel}>Mac 提醒事项 ↔ gotit 日计划</span>
                      <span className={styles.groupMeta}>
                        默认列表「学习计划」。对话建计划后 OpenClaw 会 push 到提醒事项；
                        也可在提醒事项改完回「导入计划」。浏览器不读 Apple。
                      </span>
                      <span className={styles.groupMeta}>
                        说明：docs/openclaw-apple-plan.md · skills/apple-plan/
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </>
          ) : null}

          {!sheetOpen && tab === "skills" ? (
            <>
              <div className={styles.sectionHead}>
                <p className={styles.paneTitle}>已安装</p>
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
                    上传
                  </button>
                  <button
                    type="button"
                    className="btn-ink"
                    disabled={busy}
                    onClick={() => {
                      setSkillMd("");
                      setSkillSheet({ kind: "install" });
                    }}
                  >
                    粘贴
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
                          {s.source === "builtin" ? "内置" : "自定义"}
                          {s.notes ? ` · ${s.notes}` : ""}
                        </span>
                      </div>
                      <div className={styles.listActions}>
                        <button
                          type="button"
                          className="btn-ghost"
                          disabled={busy}
                          onClick={() => void onOpenSkill(s.name)}
                        >
                          {s.source === "user" ? "编辑" : "查看"}
                        </button>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={s.enabled}
                          aria-label={s.enabled ? `关闭 ${s.name}` : `启用 ${s.name}`}
                          className={`${styles.switch} ${s.enabled ? styles.switchOn : ""}`}
                          disabled={busy}
                          onClick={() => onToggleSkill(s.name, !s.enabled)}
                        >
                          <span className={styles.switchKnob} />
                        </button>
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
                    <li className={styles.empty}>暂无 Skill</li>
                  ) : null}
                </ul>
              </div>
            </>
          ) : null}

          {!sheetOpen && tab === "connectors" ? (
            <>
              <div className={styles.sectionHead}>
                <p className={styles.paneTitle}>服务器</p>
                <div className={styles.row}>
                  <button
                    type="button"
                    className="btn-ghost"
                    disabled={busy}
                    onClick={() => {
                      setJsonPaste("");
                      setConnOpen("json");
                    }}
                  >
                    粘贴 JSON
                  </button>
                  <button
                    type="button"
                    className="btn-ink"
                    disabled={busy}
                    onClick={openConnAdd}
                  >
                    添加
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
                        <button
                          type="button"
                          className="btn-ghost"
                          disabled={busy}
                          onClick={() => openConnEdit(c)}
                        >
                          编辑
                        </button>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={c.enabled}
                          aria-label={c.enabled ? `关闭 ${c.name}` : `启用 ${c.name}`}
                          className={`${styles.switch} ${c.enabled ? styles.switchOn : ""}`}
                          disabled={busy}
                          onClick={() => onToggleConnector(c.id, !c.enabled)}
                        >
                          <span className={styles.switchKnob} />
                        </button>
                        <button
                          type="button"
                          className="btn-ghost"
                          disabled={busy}
                          onClick={() => onProbe(c.id)}
                        >
                          探测
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
                    <li className={styles.empty}>暂无 MCP</li>
                  ) : null}
                </ul>
              </div>
            </>
          ) : null}

          {!sheetOpen && tab === "digest" ? <DigestPrefsPanel /> : null}
          {!sheetOpen && tab === "shell" ? <ShellObsPanel /> : null}
        </div>
      </div>
    </Modal>
  );
}
