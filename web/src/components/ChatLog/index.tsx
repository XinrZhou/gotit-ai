import { useEffect, useRef, type ReactNode } from "react";
import type { ChatMsg } from "../../types";
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
        return (
          <div
            key={i}
            className={isExaminer ? `${styles.row} ${styles.examiner}` : `${styles.row} ${styles.user}`}
          >
            <div className={isExaminer ? `${styles.avatar} ${styles.avatarE}` : `${styles.avatar} ${styles.avatarMe}`}>
              {isExaminer ? examinerAvatar : "我"}
            </div>
            <div className={styles.col}>
              <div className={styles.name}>{isExaminer ? examinerName : "我"}</div>
              <div className={styles.bubble}>{m.text}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
