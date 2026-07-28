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
    setShowResumeModal,
    setShowMaterialModal,
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
            </>
          ) : (
            <span className={styles.muted}>还没导入简历</span>
          )}
        </div>
        <div className={styles.topActions}>
          <button
            type="button"
            className="btn-ghost"
            disabled={busy}
            onClick={() => setShowResumeModal(true)}
          >
            {resume ? "重新导入" : "导入简历"}
          </button>
          <button
            type="button"
            className="btn-ghost"
            disabled={busy}
            onClick={() => setShowMaterialModal(true)}
          >
            深挖资料 · {drillMaterials.length}
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
              先导入简历，桑迪就能像面试官一样深挖你的项目了。
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
