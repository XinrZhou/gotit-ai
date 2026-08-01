import {
  forwardRef,
  useImperativeHandle,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import type { YuqueEditorRef } from "yuque-editor-core/editor";
import { YuqueRichText } from "yuque-editor-core/react";

export type NoteDocScheme = "text/html" | "text/lake" | "text/markdown" | "text/plain";

export type YuqueNoteEditorHandle = {
  /** 读取正文；默认 HTML，便于后端 stub 入库 */
  getHtml: () => string;
  getLake: () => string;
  getPlainSummary: () => string;
  isEmpty: () => boolean;
  wordCount: () => number;
  setHtml: (html: string) => void;
  focus: () => void;
};

export type YuqueNoteEditorProps = {
  /** 初始正文；挂载后不再受控（避免 Markdown 转换时的空 contentchange 把内容冲掉） */
  value?: string;
  /** 存库格式；手写笔记默认 HTML */
  scheme?: NoteDocScheme;
  readOnly?: boolean;
  height?: number | string;
  className?: string;
  style?: CSSProperties;
  onChange?: (value: string) => void;
  onLoad?: () => void;
  onError?: (error: Error) => void;
};

function isBlankDoc(html: string): boolean {
  return html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim().length === 0;
}

/**
 * 语雀 Lake 编辑器薄封装（基于 yuque-editor-core）。
 * 静态资源由 Vite 插件拷到 /yuque-assets。
 *
 * 注意：`value` 只作初始种子。库内 YuqueRichText 会在 value 变化时
 * setContent 回写；Markdown「立即转换」会先派发一次空 contentchange，
 * 受控同步会把已转换正文清掉。外部重置请用 ref.setHtml 或 remount key。
 */
export const YuqueNoteEditor = forwardRef<YuqueNoteEditorHandle, YuqueNoteEditorProps>(
  function YuqueNoteEditor(
    {
      value = "",
      scheme = "text/html",
      readOnly = false,
      height = 360,
      className,
      style,
      onChange,
      onLoad,
      onError,
    },
    ref,
  ) {
    const innerRef = useRef<YuqueEditorRef>(null);
    const onChangeRef = useRef(onChange);
    onChangeRef.current = onChange;
    // Freeze seed so parent re-renders never re-enter controlled sync.
    const [seed] = useState(value);

    useImperativeHandle(ref, () => ({
      getHtml: () => innerRef.current?.getContent("text/html") ?? "",
      getLake: () => innerRef.current?.getContent("text/lake") ?? "",
      getPlainSummary: () => innerRef.current?.getSummaryContent() ?? "",
      isEmpty: () => innerRef.current?.isEmpty() ?? true,
      wordCount: () => innerRef.current?.wordCount() ?? 0,
      setHtml: (html: string) => {
        innerRef.current?.setContent(html, "text/html");
      },
      focus: () => {
        innerRef.current?.focusToStart(0);
      },
    }));

    return (
      <div
        className={className ? `yuque-note-editor ${className}` : "yuque-note-editor"}
        style={{ height, minHeight: typeof height === "number" ? height : undefined, ...style }}
      >
        <YuqueRichText
          ref={innerRef}
          value={seed}
          scheme={scheme}
          readOnly={readOnly}
          darkMode={false}
          showToolbar={!readOnly}
          defaultFontSize={15}
          onChange={(next) => {
            // Markdown 转换会先清空再写入；空闪烁不要往外传，避免宿主又受控写回。
            if (isBlankDoc(next)) {
              requestAnimationFrame(() => {
                const live = innerRef.current?.getContent(scheme) ?? "";
                if (!isBlankDoc(live)) {
                  onChangeRef.current?.(live);
                  return;
                }
                onChangeRef.current?.(next);
              });
              return;
            }
            onChangeRef.current?.(next);
          }}
          onLoad={onLoad}
          onError={onError}
        />
      </div>
    );
  },
);
