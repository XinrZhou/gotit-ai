import { useCallback, useState } from "react";
import type { Mode } from "../types";
import type { Run } from "./types";

/** UI chrome: mode, busy/flash/error, menus. `run` binds to a refresh fn. */
export function useShell() {
  const [mode, setMode] = useState<Mode>("chat");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  /** 资料/项目侧栏；默认收起，避免三栏空旷 */
  const [libraryOpen, setLibraryOpen] = useState(false);

  const bindRun = useCallback((refresh: () => Promise<void>): Run => {
    return async (action, okMessage) => {
      setBusy(true);
      setError("");
      try {
        await action();
        if (okMessage) setFlash(okMessage);
        await refresh();
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    };
  }, []);

  return {
    mode,
    setMode,
    busy,
    setBusy,
    error,
    setError,
    flash,
    setFlash,
    openMenuId,
    setOpenMenuId,
    libraryOpen,
    setLibraryOpen,
    bindRun,
  };
}
