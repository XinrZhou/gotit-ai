import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import styles from "../index.module.scss";

type Props = {
  text: string;
  /** Agent bubbles get markdown; user stays plain. */
  markdown?: boolean;
};

export function MessageBody({ text, markdown = false }: Props) {
  if (!markdown) {
    return <>{text}</>;
  }
  return (
    <div className={styles.md}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}
