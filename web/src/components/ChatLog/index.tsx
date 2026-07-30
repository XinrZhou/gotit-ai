import { useEffect, useRef, type ReactNode } from "react";
import type { ChatMsg } from "../../types";
import { isMasteryVerdict, VerifyVerdictChip } from "../VerifyVerdict";
import { VerifyTrajectory } from "../VerifyTrajectory";
import styles from "./index.module.scss";

type Props = {
  messages: ChatMsg[];
  examinerAvatar: ReactNode;
  examinerName: string;
  empty?: ReactNode;
};

export function ChatLog({ messages, examinerAvatar, examinerName, empty }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  if (messages.length === 0 && empty) {
    return (
      <div className={styles.chat}>
        <div className={styles.empty}>{empty}</div>
      </div>
    );
  }
  return (
    <div className={styles.chat} ref={ref}>
      {messages.map((m, i) => {
        const isExaminer = m.role === "examiner";
        const showVerdict = isExaminer && isMasteryVerdict(m.verdict);
        return (
          <div
            key={i}
            className={
              isExaminer
                ? `${styles.row} ${styles.examiner}`
                : `${styles.row} ${styles.user}`
            }
          >
            <div
              className={
                isExaminer
                  ? `${styles.avatar} ${styles.avatarE}`
                  : `${styles.avatar} ${styles.avatarMe}`
              }
            >
              {isExaminer ? examinerAvatar : "我"}
            </div>
            <div className={styles.col}>
              <div className={styles.name}>{isExaminer ? examinerName : "我"}</div>
              <div className={styles.bubble}>{m.text}</div>
              {showVerdict ? (
                <VerifyVerdictChip
                  verdict={m.verdict!}
                  sessionDone={Boolean(m.session_done)}
                />
              ) : null}
              {isExaminer && m.verify ? <VerifyTrajectory path={m.verify} /> : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
