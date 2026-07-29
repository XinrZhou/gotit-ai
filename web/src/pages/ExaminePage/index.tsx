import { ChatLog } from "../../components/ChatLog";
import { Composer } from "../../components/Composer";
import { EmptyState } from "../../components/EmptyState";
import { SquidwardAvatar } from "../../components/Avatars";
import { useStore } from "../../store";
import styles from "./index.module.scss";

export function ExaminePage() {
  const {
    notes,
    busy,
    examineNote,
    onExamineStart,
    examineChat,
    examineAnswer,
    setExamineAnswer,
    examineSessionDone,
    onExamineAnswer,
  } = useStore();

  const noteTitle = (n: { title: string | null }) => n.title?.trim() || "未命名笔记";
  const entries = notes.filter((n) => n.claim_ids.length > 0);

  // Session active -> chat view
  if (examineNote) {
    return (
      <>
        <ChatLog
          messages={examineChat}
          examinerAvatar={<SquidwardAvatar />}
          examinerName="章鱼哥"
          empty={<span>章鱼哥准备开场了…</span>}
        />
        {!examineSessionDone ? (
          <Composer
            kind="textarea"
            value={examineAnswer}
            onChange={setExamineAnswer}
            placeholder={`和章鱼哥聊「${noteTitle(examineNote)}」…`}
            onSubmit={onExamineAnswer}
            submitLabel="发送"
            busy={busy}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                onExamineAnswer();
              }
            }}
          />
        ) : null}
      </>
    );
  }

  // No session -> pick a note to start (only notes already turned into quizzes)
  return (
    <div className={styles.picker}>
      {entries.length === 0 ? (
        <EmptyState avatar={<SquidwardAvatar />}>
          <strong>我准备好了！</strong>
          <div>先把左侧笔记出成题，章鱼哥就能考你了～</div>
        </EmptyState>
      ) : (
        <>
          <div className={styles.pickerHead}>
            <div className={styles.pickerAvatar}>
              <SquidwardAvatar />
            </div>
            <div className={styles.pickerTitle}>选一条，章鱼哥开考</div>
            <div className={styles.pickerSub}>围绕它的考点一条条问你，直接聊就行</div>
          </div>
          <div className={styles.entryList}>
            {entries.map((n) => (
              <button
                key={n.id}
                type="button"
                className={styles.entry}
                disabled={busy}
                onClick={() => onExamineStart(n)}
              >
                <span className={styles.entryIcon}>📝</span>
                <span className={styles.entryTitle}>{noteTitle(n)}</span>
                <span className={styles.entryCount}>{n.claim_ids.length} 题</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
