import { ChatLog } from "../../components/ChatLog";
import { Composer } from "../../components/Composer";
import { EmptyState } from "../../components/EmptyState";
import { SessionStartPanel } from "../../components/SessionStartPanel";
import { SandyAvatar } from "../../components/Avatars";
import { useStore } from "../../store";
import styles from "./index.module.scss";

export function DrillPage() {
  const {
    busy,
    resume,
    drillMaterials,
    activeDrillSession,
    drillChat,
    drillAnswer,
    setDrillAnswer,
    drillDone,
    setShowMaterialModal,
    setShowResumeViewer,
    onBackToDrillStart,
    onDrillAnswer,
  } = useStore();

  return (
    <>
      <div className={styles.topBar}>
        <div className={styles.resumeStatus}>
          {resume ? (
            <>
              <span className={styles.dot} />
              <span>
                简历已导入 · {resume.document.projects.length} 个项目
                {resume.document.basics.name ? ` · ${resume.document.basics.name}` : ""}
              </span>
              <button
                type="button"
                className={styles.viewResumeBtn}
                disabled={busy}
                onClick={() => setShowResumeViewer(true)}
                title="查看简历原文件"
              >
                查看简历
              </button>
            </>
          ) : (
            <span className={styles.muted}>还没导入简历（点左侧「项目」旁的 + 导入）</span>
          )}
        </div>
        <div className={styles.topActions}>
          <button
            type="button"
            className={styles.materialBtn}
            disabled={busy}
            onClick={() => setShowMaterialModal(true)}
            title="管理深挖资料"
          >
            <svg className={styles.materialIcon} viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M4 6.5C4 5.67 4.67 5 5.5 5h4.17l2 2.5H18.5c.83 0 1.5.67 1.5 1.5v8.5c0 .83-.67 1.5-1.5 1.5h-13c-.83 0-1.5-.67-1.5-1.5V6.5z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
              <path d="M8 12h8M8 15h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <span>资料管理 · {drillMaterials.length}</span>
          </button>
        </div>
      </div>

      {!resume ? (
        <ChatLog
          messages={[]}
          examinerAvatar={<SandyAvatar />}
          examinerName="桑迪"
          empty={
            <EmptyState avatar={<SandyAvatar />}>
              先点左侧「项目」旁的 + 导入简历，桑迪就能像面试官一样深挖你的项目了。
            </EmptyState>
          }
        />
      ) : !activeDrillSession ? (
        <SessionStartPanel />
      ) : (
        <>
          <div className={styles.sessionHead}>
            <span className={styles.sessionRound}>{activeDrillSession.round}</span>
            {activeDrillSession.direction ? (
              <span className={styles.sessionDir}>偏 {activeDrillSession.direction}</span>
            ) : null}
            <button
              type="button"
              className={styles.backBtn}
              onClick={onBackToDrillStart}
              disabled={busy}
            >
              ← 开新 session
            </button>
          </div>
          <ChatLog
            messages={drillChat}
            examinerAvatar={<SandyAvatar />}
            examinerName="桑迪"
            empty={
              <EmptyState avatar={<SandyAvatar />}>桑迪准备开始深挖了。</EmptyState>
            }
          />
          {!drillDone ? (
            <Composer
              kind="textarea"
              value={drillAnswer}
              onChange={setDrillAnswer}
              placeholder="回答桑迪的追问…"
              onSubmit={onDrillAnswer}
              submitLabel="回答"
              busy={busy}
            />
          ) : null}
        </>
      )}
    </>
  );
}
