import { useEffect, useRef, useState } from "react";
import { useStore } from "../../store";
import { Modal } from "../Modal";
import styles from "./index.module.scss";

export function Sidebar() {
  const {
    busy,
    notes,
    noteScope,
    setNoteScope,
    projects,
    selectedProjectId,
    setSelectedProjectId,
    projectPicked,
    setProjectPicked,
    setMode,
    resume,
    setShowResumeModal,
    onOpenEditProject,
    openMenuId,
    setOpenMenuId,
    onOpenNote,
    onIngestNote,
    onIngestAll,
    onDeleteNote,
    onDeleteNotes,
    setShowCompose,
    setLibraryOpen,
  } = useStore();

  const listRef = useRef<HTMLDivElement>(null);
  const totallyEmpty = projects.length === 0 && notes.length === 0;
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [pendingDeleteIds, setPendingDeleteIds] = useState<string[] | null>(null);

  useEffect(() => {
    if (!openMenuId) return;
    const onDown = (e: MouseEvent) => {
      if (listRef.current && !listRef.current.contains(e.target as Node)) {
        setOpenMenuId(null);
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [openMenuId, setOpenMenuId]);

  useEffect(() => {
    setSelected((prev) => {
      const ids = new Set(notes.map((n) => n.id));
      const next = new Set([...prev].filter((id) => ids.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [notes]);

  function exitSelect() {
    setSelecting(false);
    setSelected(new Set());
  }

  function toggleOne(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    if (selected.size === notes.length) setSelected(new Set());
    else setSelected(new Set(notes.map((n) => n.id)));
  }

  function confirmBatchDelete() {
    if (!pendingDeleteIds?.length) return;
    const ids = pendingDeleteIds;
    setPendingDeleteIds(null);
    onDeleteNotes(ids);
    exitSelect();
  }

  return (
    <aside className={styles.sidebar}>
      <div className={styles.sidebarHead}>
        <div className={styles.headRow}>
          <span className={styles.libraryTitle}>资料库</span>
          <button
            type="button"
            className={styles.closeBtn}
            onClick={() => setLibraryOpen(false)}
            aria-label="关闭资料栏"
          >
            收起
          </button>
        </div>
      </div>

      {totallyEmpty ? (
        <div className={styles.empty}>
          <p className={styles.emptyText}>还没资料。写一条笔记，或导入简历建项目，我来帮你出题考你。</p>
          <button
            type="button"
            className={styles.btnCompose}
            disabled={busy}
            onClick={() => setShowCompose(true)}
          >
            + 添加资料
          </button>
          <button
            type="button"
            className={styles.btnQuiet}
            disabled={busy}
            onClick={() => setShowResumeModal(true)}
          >
            {resume ? "重新导入简历" : "导入简历"}
          </button>
        </div>
      ) : (
        <>
          <div className={styles.sectionLabel}>
            <span>项目 · {projects.length}</span>
            <button
              type="button"
              className={styles.sectionAdd}
              onClick={() => setShowResumeModal(true)}
              disabled={busy}
              title={resume ? "重新导入简历" : "导入简历"}
              aria-label={resume ? "重新导入简历" : "导入简历"}
            >
              +
            </button>
          </div>
          <div className={styles.projectList}>
            <button
              type="button"
              className={
                projectPicked && selectedProjectId === null
                  ? `${styles.projItem} ${styles.projActive}`
                  : styles.projItem
              }
              onClick={() => {
                setSelectedProjectId(null);
                setProjectPicked(true);
                setMode("drill");
              }}
            >
              <span className={styles.projName}>全部</span>
            </button>
            {projects.map((p) => (
              <button
                key={p.id}
                type="button"
                className={selectedProjectId === p.id ? `${styles.projItem} ${styles.projActive}` : styles.projItem}
                onClick={() => {
                  setSelectedProjectId(p.id);
                  setProjectPicked(true);
                  setMode("drill");
                }}
                onDoubleClick={() => onOpenEditProject(p)}
                title="双击编辑"
              >
                <span className={styles.projName}>{p.name}</span>
              </button>
            ))}
          </div>

          <div className={styles.sectionLabel}>
            <span>
              {selecting
                ? selected.size > 0
                  ? `已选 · ${selected.size}`
                  : "选择资料"
                : noteScope === "all"
                  ? `全部资料 · ${notes.length}`
                  : `今日资料 · ${notes.length}`}
            </span>
            <div className={styles.sectionTools}>
              {notes.length > 0 ? (
                <button
                  type="button"
                  className={styles.sectionTool}
                  disabled={busy}
                  onClick={() => {
                    if (selecting) exitSelect();
                    else {
                      setOpenMenuId(null);
                      setSelecting(true);
                    }
                  }}
                >
                  {selecting ? "取消" : "选择"}
                </button>
              ) : null}
              {!selecting ? (
                <div className={styles.scopeToggle}>
                  <button
                    type="button"
                    className={noteScope === "today" ? `${styles.scopeBtn} ${styles.scopeActive}` : styles.scopeBtn}
                    onClick={() => setNoteScope("today")}
                  >
                    今日
                  </button>
                  <button
                    type="button"
                    className={noteScope === "all" ? `${styles.scopeBtn} ${styles.scopeActive}` : styles.scopeBtn}
                    onClick={() => setNoteScope("all")}
                  >
                    全部
                  </button>
                </div>
              ) : null}
            </div>
          </div>

          {selecting && notes.length > 0 ? (
            <div className={styles.selectBar}>
              <label className={styles.selectAll}>
                <input
                  type="checkbox"
                  checked={selected.size === notes.length && notes.length > 0}
                  disabled={busy}
                  onChange={toggleAll}
                />
                <span>{selected.size === notes.length ? "取消全选" : "全选"}</span>
              </label>
            </div>
          ) : null}

          <div className={styles.notesList} ref={listRef}>
            {notes.length === 0 ? (
              <div className={styles.empty}>
                <p className={styles.emptyText}>还没资料。写一条，我来帮你出题考你。</p>
                <button
                  type="button"
                  className={styles.btnCompose}
                  disabled={busy}
                  onClick={() => setShowCompose(true)}
                >
                  + 添加资料
                </button>
              </div>
            ) : (
              (() => {
                const ready = notes.filter((n) => n.claim_ids.length > 0);
                const pending = notes.filter((n) => n.claim_ids.length === 0);
                const renderNote = (note: (typeof notes)[number]) => {
                  const count = note.claim_ids.length;
                  const isReady = count > 0;
                  const checked = selected.has(note.id);
                  return (
                    <div
                      key={note.id}
                      className={`${styles.noteItem} ${checked ? styles.noteItemSelected : ""}`}
                    >
                      {selecting ? (
                        <label className={styles.noteCheck}>
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={busy}
                            onChange={() => toggleOne(note.id)}
                          />
                        </label>
                      ) : null}
                      <button
                        type="button"
                        className={styles.noteMain}
                        onClick={() => {
                          if (selecting) toggleOne(note.id);
                          else onOpenNote(note.id);
                        }}
                        disabled={busy}
                      >
                        <span className={styles.noteTitle}>{note.title || "未命名"}</span>
                        {noteScope === "all" && note.day ? (
                          <span className={styles.noteDate}>{note.day.slice(5)}</span>
                        ) : null}
                        {isReady ? <span className={styles.noteBadge}>{count}题可考</span> : null}
                      </button>
                      {selecting ? null : (
                        <>
                          <button
                            type="button"
                            className={styles.noteMenu}
                            aria-label="更多操作"
                            disabled={busy}
                            onClick={() => setOpenMenuId(openMenuId === note.id ? null : note.id)}
                          >
                            ⋯
                          </button>
                          {openMenuId === note.id ? (
                            <div className={styles.menuPop}>
                              <button
                                type="button"
                                onClick={() => {
                                  setOpenMenuId(null);
                                  onOpenNote(note.id);
                                }}
                              >
                                查看
                              </button>
                              {isReady ? null : (
                                <button
                                  type="button"
                                  onClick={() => {
                                    setOpenMenuId(null);
                                    onIngestNote(note.id);
                                  }}
                                >
                                  出题
                                </button>
                              )}
                              <button
                                type="button"
                                className={styles.menuDanger}
                                onClick={() => {
                                  setOpenMenuId(null);
                                  onDeleteNote(note.id);
                                }}
                              >
                                删除
                              </button>
                            </div>
                          ) : null}
                        </>
                      )}
                    </div>
                  );
                };
                return (
                  <>
                    {ready.map(renderNote)}
                    {pending.length > 0 ? (
                      <div className={styles.listDivider}>
                        <span>还没出题 · {pending.length}</span>
                        {!selecting ? (
                          <button
                            type="button"
                            className={styles.dividerAction}
                            disabled={busy}
                            onClick={onIngestAll}
                          >
                            一键出题
                          </button>
                        ) : null}
                      </div>
                    ) : null}
                    {pending.map(renderNote)}
                  </>
                );
              })()
            )}
          </div>

          {notes.length > 0 ? (
            <div className={styles.foot}>
              {selecting ? (
                <button
                  type="button"
                  className={styles.batchAction}
                  disabled={busy || selected.size === 0}
                  onClick={() => setPendingDeleteIds([...selected])}
                >
                  删除{selected.size > 0 ? ` ${selected.size} 条` : ""}
                </button>
              ) : (
                <button
                  type="button"
                  className="btn-compose"
                  disabled={busy}
                  onClick={() => setShowCompose(true)}
                >
                  + 添加资料
                </button>
              )}
            </div>
          ) : null}
        </>
      )}

      {pendingDeleteIds ? (
        <Modal
          title="删除资料"
          onClose={() => setPendingDeleteIds(null)}
          actions={
            <>
              <button type="button" className="btn-ghost" onClick={() => setPendingDeleteIds(null)}>
                取消
              </button>
              <button type="button" className="btn-ink" disabled={busy} onClick={confirmBatchDelete}>
                删除 {pendingDeleteIds.length} 条
              </button>
            </>
          }
        >
          <p className={styles.deleteCopy}>
            确定删除选中的 {pendingDeleteIds.length} 条资料？删除后无法恢复。
          </p>
        </Modal>
      ) : null}
    </aside>
  );
}
