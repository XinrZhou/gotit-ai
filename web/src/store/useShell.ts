import { useCallback, useRef, useState } from "react";
import {
  loadUserProfile,
  saveUserProfile,
  type UserProfile,
} from "../lib/userProfile";
import type { Mode } from "../types";
import type { Run } from "./types";

const FLASH_MS = 2400;

/** UI chrome: mode, busy/flash/error, menus. `run` binds to a refresh fn. */
export function useShell() {
  const [mode, setMode] = useState<Mode>("chat");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [flash, setFlashState] = useState("");
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  /** 资料/项目侧栏；默认收起，避免三栏空旷 */
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [masteryGraphOpen, setMasteryGraphOpen] = useState(false);
  const [shellActivityOpen, setShellActivityOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [workflowThreadId, setWorkflowThreadId] = useState<string | null>(null);
  const [userProfile, setUserProfileState] = useState<UserProfile>(() =>
    loadUserProfile(),
  );

  const setUserProfile = useCallback((next: UserProfile) => {
    saveUserProfile(next);
    setUserProfileState(loadUserProfile());
  }, []);

  const setFlash = useCallback((s: string) => {
    if (flashTimer.current) {
      clearTimeout(flashTimer.current);
      flashTimer.current = null;
    }
    setFlashState(s);
    if (s) {
      flashTimer.current = setTimeout(() => {
        setFlashState("");
        flashTimer.current = null;
      }, FLASH_MS);
    }
  }, []);

  const bindRun = useCallback(
    (refresh: () => Promise<void>): Run => {
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
    },
    [setFlash],
  );

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
    masteryGraphOpen,
    setMasteryGraphOpen,
    shellActivityOpen,
    setShellActivityOpen,
    settingsOpen,
    setSettingsOpen,
    workflowThreadId,
    setWorkflowThreadId,
    userProfile,
    setUserProfile,
    bindRun,
  };
}
