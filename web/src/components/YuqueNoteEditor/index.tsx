import {
  forwardRef,
  useImperativeHandle,
  useRef,
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

/**
 * 语雀 Lake 编辑器薄封装（基于 yuque-editor-core）。
 * 静态资源由 Vite 插件拷到 /yuque-assets。
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
          value={value}
          scheme={scheme}
          readOnly={readOnly}
          darkMode={false}
          showToolbar={!readOnly}
          defaultFontSize={15}
          onChange={onChange}
          onLoad={onLoad}
          onError={onError}
        />
      </div>
    );
  },
);
