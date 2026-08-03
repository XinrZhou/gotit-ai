import { useEffect, useRef, type ReactNode } from "react";
import type { ChatMsg } from "../../types";
import { useStore } from "../../store";
import {
  profileInitials,
  profileTint,
} from "../../lib/userProfile";
import { isMasteryVerdict, VerifyVerdictChip } from "../VerifyVerdict";
import { VerifyTrajectory } from "../VerifyTrajectory";
import styles from "./index.module.scss";

type Props = {
  messages: ChatMsg[];
  examinerAvatar: ReactNode;
  examinerName: string;
  empty?: ReactNode;
  /** Show a quiet「思考中」row under the last message while a turn is in flight. */
  busy?: boolean;
};

export function ChatLog({
  messages,
  examinerAvatar,
  examinerName,
  empty,
  busy = false,
}: Props) {
  const { userProfile } = useStore();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, busy]);

  if (messages.length === 0 && empty && !busy) {
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
        const isError = Boolean(m.error);
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
              style={
                !isExaminer && !userProfile.avatar
                  ? {
                      background: profileTint(userProfile.name),
                      color: "var(--ink)",
                      border: "none",
                    }
                  : undefined
              }
              title={isExaminer ? examinerName : userProfile.name}
            >
              {isExaminer ? (
                examinerAvatar
              ) : userProfile.avatar ? (
                <img src={userProfile.avatar} alt="" />
              ) : (
                profileInitials(userProfile.name)
              )}
            </div>
            <div className={styles.col}>
              <div className={styles.name}>
                {isExaminer ? examinerName : userProfile.name}
              </div>
              <div className={`${styles.bubble} ${isError ? styles.bubbleError : ""}`}>
                {m.text}
              </div>
              {isExaminer && m.failure_hint ? (
                <div className={styles.failureHint}>{m.failure_hint}</div>
              ) : null}
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
      {busy ? (
        <div className={`${styles.row} ${styles.examiner}`}>
          <div className={`${styles.avatar} ${styles.avatarE}`}>{examinerAvatar}</div>
          <div className={styles.col}>
            <div className={styles.name}>{examinerName}</div>
            <div className={styles.thinkingPending} aria-live="polite">
              <span className={styles.thinkingPulse} aria-hidden />
              <span className={styles.thinkingLabel}>
                思考中
                <span className={styles.thinkingDots} aria-hidden>
                  <span>.</span>
                  <span>.</span>
                  <span>.</span>
                </span>
              </span>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
