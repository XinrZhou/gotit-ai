import { useEffect, useRef } from "react";
import { fmtDate } from "../../lib/format";
import { useStore } from "../../store";
import styles from "./index.module.scss";

export function Sidebar() {
  const {
    day,
    setDay,
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
    setShowCompose,
  } = useStore();

  const listRef = useRef<HTMLDivElement>(null);

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

  return (
    <aside className={styles.sidebar}>
      <div className={styles.sidebarHead}>
        <div className={styles.headRow}>
          <div className={styles.brand}>
            <svg className={styles.brandIcon} viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="12" r="9.25" stroke="currentColor" strokeWidth="1.5" />
              <path
                d="M7.5 12.3l3 3 6-6.6"
                stroke="currentColor"
                strokeWidth="1.9"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <span>gotit</span>
          </div>
          <label className={styles.dayPicker}>
            <input
              type="date"
              value={day}
              onChange={(e) => setDay(e.target.value)}
              disabled={busy}
            />
            <span className={styles.dayLabel}>{fmtDate(day)}</span>
          </label>
        </div>
      </div>

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
          className={projectPicked && selectedProjectId === null ? `${styles.projItem} ${styles.projActive}` : styles.projItem}
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
        <span>{noteScope === "all" ? "全部资料" : "今日资料"} · {notes.length}</span>
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
      </div>
      <div className={styles.notesList} ref={listRef}>
        {notes.length === 0 ? (
          <div className={styles.empty}>
            还没资料。点 + 写一条，我来帮你出题考你。
          </div>
        ) : (
          (() => {
            const ready = notes.filter((n) => n.claim_ids.length > 0);
            const pending = notes.filter((n) => n.claim_ids.length === 0);
            const renderNote = (note: typeof notes[number]) => {
              const count = note.claim_ids.length;
              const isReady = count > 0;
              return (
                <div key={note.id} className={styles.noteItem}>
                  <button
                    type="button"
                    className={styles.noteMain}
                    onClick={() => onOpenNote(note.id)}
                    disabled={busy}
                  >
                    <span className={styles.noteTitle}>{note.title || "未命名"}</span>
                    {noteScope === "all" && note.day ? (
                      <span className={styles.noteDate}>{note.day.slice(5)}</span>
                    ) : null}
                    {isReady ? <span className={styles.noteBadge}>{count}题可考</span> : null}
                  </button>
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
                </div>
              );
            };
            return (
              <>
                {ready.map(renderNote)}
                {pending.length > 0 ? (
                  <div className={styles.listDivider}>
                    <span>还没出题 · {pending.length}</span>
                    <button
                      type="button"
                      className={styles.dividerAction}
                      disabled={busy}
                      onClick={onIngestAll}
                    >
                      一键出题
                    </button>
                  </div>
                ) : null}
                {pending.map(renderNote)}
              </>
            );
          })()
        )}
      </div>

      <div className={styles.foot}>
        <button
          type="button"
          className="btn-compose"
          disabled={busy}
          onClick={() => setShowCompose(true)}
        >
          + 添加资料
        </button>
      </div>
    </aside>
  );
}
