import { ChatLog } from "../../components/ChatLog";
import { Composer } from "../../components/Composer";
import { EmptyState } from "../../components/EmptyState";
import { PatrickAvatar } from "../../components/Avatars";
import { useStore } from "../../store";

export function TeachPage() {
  const {
    busy,
    teachTopic,
    setTeachTopic,
    teachChat,
    teachAnswer,
    setTeachAnswer,
    teachDone,
    onTeachStart,
    onTeachAnswer,
  } = useStore();

  return (
    <>
      <ChatLog
        messages={teachChat}
        examinerAvatar={<PatrickAvatar />}
        examinerName="派大星"
        empty={
          <EmptyState avatar={<PatrickAvatar />}>
            说一个主题，讲给派大星听。讲不清的地方，他会接着问。
          </EmptyState>
        }
        busy={busy}
      />

      {teachChat.length === 0 ? (
        <Composer
          kind="topic"
          value={teachTopic}
          onChange={setTeachTopic}
          placeholder="例如：上下文预算"
          onSubmit={onTeachStart}
          submitLabel="开始讲"
          busy={busy}
        />
      ) : !teachDone ? (
        <Composer
          kind="textarea"
          value={teachAnswer}
          onChange={setTeachAnswer}
          placeholder="继续讲…"
          onSubmit={onTeachAnswer}
          submitLabel="回答"
          busy={busy}
        />
      ) : null}
    </>
  );
}
