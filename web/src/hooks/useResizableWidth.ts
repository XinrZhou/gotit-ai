import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

type Options = {
  storageKey: string;
  defaultWidth: number;
  min: number;
  max: number;
};

function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n));
}

function readStored(key: string, fallback: number, min: number, max: number): number {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    const n = Number(raw);
    if (!Number.isFinite(n)) return fallback;
    return clamp(Math.round(n), min, max);
  } catch {
    return fallback;
  }
}

/** Drag a vertical edge to resize a panel; persists width in localStorage. */
export function useResizableWidth({ storageKey, defaultWidth, min, max }: Options) {
  const [width, setWidth] = useState(() => readStored(storageKey, defaultWidth, min, max));
  const [dragging, setDragging] = useState(false);
  const widthRef = useRef(width);
  widthRef.current = width;

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, String(width));
    } catch {
      /* ignore quota / private mode */
    }
  }, [storageKey, width]);

  const onResizePointerDown = useCallback(
    (e: ReactPointerEvent<HTMLElement>) => {
      if (e.button !== 0) return;
      e.preventDefault();
      const startX = e.clientX;
      const startW = widthRef.current;
      setDragging(true);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";

      const onMove = (ev: PointerEvent) => {
        setWidth(clamp(Math.round(startW + (ev.clientX - startX)), min, max));
      };
      const onUp = () => {
        setDragging(false);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [min, max],
  );

  return { width, dragging, onResizePointerDown };
}
