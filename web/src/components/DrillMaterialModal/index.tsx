import { useRef, useState } from "react";
import { useStore } from "../../store";
import type { DrillMaterial } from "../../types";
import { Modal } from "../Modal";
import styles from "./index.module.scss";

export function DrillMaterialModal() {
  const {
    showMaterialModal,
    setShowMaterialModal,
    busy,
    drillMaterials,
    onUpsertMaterial,
    onImportMaterialFile,
    onDeleteMaterial,
  } = useStore();
  const [editing, setEditing] = useState<DrillMaterial | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [importing, setImporting] = useState(false);
  const [importErr, setImportErr] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  if (!showMaterialModal) return null;

  function startNew() {
    setEditing(null);
    setTitle("");
    setBody("");
    setImportErr("");
  }

  function startEdit(m: DrillMaterial) {
    setEditing(m);
    setTitle(m.title);
    setBody(m.body);
    setImportErr("");
  }

  async function save() {
    await onUpsertMaterial(editing?.id ?? null, title, body);
    setShowMaterialModal(false);
  }

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setImporting(true);
    setImportErr("");
    try {
      const out = await onImportMaterialFile(file);
      setEditing(null);
      setTitle(out.title);
      setBody(out.body);
    } catch (err) {
      setImportErr(err instanceof Error ? err.message : "导入失败");
    } finally {
      setImporting(false);
    }
  }

  async function remove(id: string) {
    await onDeleteMaterial(id);
    if (editing?.id === id) startNew();
  }

  const canSave = !busy && !importing && title.trim().length > 0 && body.trim().length > 0;

  return (
    <Modal
      title="深挖资料"
      onClose={() => setShowMaterialModal(false)}
      actions={
        editing === null ? (
          <button type="button" className="btn-ink" disabled={!canSave} onClick={save}>
            {busy ? "处理中…" : "添加"}
          </button>
        ) : (
          <>
            <button type="button" className="btn-ghost" onClick={startNew} disabled={busy}>
              新建
            </button>
            <button type="button" className="btn-ink" disabled={!canSave} onClick={save}>
              {busy ? "处理中…" : "保存"}
            </button>
          </>
        )
      }
    >
      <div className={styles.muted}>
        这些资料桑迪会一起消费，作为深挖的上下文（全局，所有 session 共用）。
      </div>

      <div className={styles.editor}>
        <div className={styles.importRow}>
          <button
            type="button"
            className={styles.importBtn}
            disabled={busy || importing}
            onClick={() => fileRef.current?.click()}
          >
            {importing ? "导入中…" : "导入文件"}
          </button>
          <span className={styles.importHint}>支持 PDF / DOCX / TXT / MD，导入后可编辑再保存</span>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.txt,.md"
            className={styles.fileInput}
            onChange={(e) => void onPickFile(e)}
          />
        </div>
        {importErr ? <div className={styles.importErr}>{importErr}</div> : null}
        <input
          className={styles.titleInput}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="标题，例如：订单中台深挖要点"
          disabled={busy || importing}
        />
        <textarea
          className={styles.bodyInput}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="内容，例如：事件驱动 vs 同步调用的取舍；Kafka 分区策略…"
          rows={6}
          disabled={busy || importing}
        />
      </div>

      <div className={styles.list}>
        <div className={styles.listLabel}>已有资料 · {drillMaterials.length}</div>
        {drillMaterials.map((m) => (
          <div key={m.id} className={styles.item}>
            <button type="button" className={styles.itemMain} onClick={() => startEdit(m)}>
              <span className={styles.itemTitle}>{m.title}</span>
              <span className={styles.itemBody}>{m.body.slice(0, 60)}</span>
            </button>
            <button
              type="button"
              className={styles.itemDel}
              onClick={() => void remove(m.id)}
              disabled={busy}
            >
              删除
            </button>
          </div>
        ))}
      </div>
    </Modal>
  );
}
