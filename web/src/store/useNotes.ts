import { useCallback, useState } from "react";
import { api } from "../api";
import type { DayNote } from "../types";
import type { Run } from "./types";

type Deps = {
  notes: DayNote[];
  run: Run;
  refresh: () => Promise<void>;
  setBusy: (b: boolean) => void;
  setError: (s: string) => void;
  setFlash: (s: string) => void;
};

export function useNotes({
  notes,
  run,
  refresh,
  setBusy,
  setError,
  setFlash,
}: Deps) {
  const [viewNote, setViewNote] = useState<DayNote | null>(null);
  const [showCompose, setShowCompose] = useState(false);

  const onOpenNote = useCallback(
    (id: string) => {
      void (async () => {
        setError("");
        try {
          const n = await api<DayNote>(`/v1/notes/${id}`);
          setViewNote(n);
        } catch (err) {
          setError(String(err));
        }
      })();
    },
    [setError],
  );

  const onDeleteNote = useCallback(
    (id: string) => {
      void run(async () => {
        await api<{ ok: boolean }>(`/v1/notes/${id}`, { method: "DELETE" });
        setViewNote(null);
      }, "笔记已删除");
    },
    [run],
  );

  const onIngestNote = useCallback(
    (id: string) => {
      void run(
        () =>
          api<unknown>(`/v1/notes/${id}/ingest`, {
            method: "POST",
            body: JSON.stringify({ add_plan_item: true }),
          }),
        "题出好了",
      );
    },
    [run],
  );

  const onIngestAll = useCallback(() => {
    const pending = notes.filter((n) => n.claim_ids.length === 0);
    if (pending.length === 0) return;
    void (async () => {
      setBusy(true);
      setError("");
      try {
        for (const n of pending) {
          await api<unknown>(`/v1/notes/${n.id}/ingest`, {
            method: "POST",
            body: JSON.stringify({ add_plan_item: true }),
          });
        }
        setFlash(`出好了，${pending.length} 条都变成题了`);
        await refresh();
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    })();
  }, [notes, refresh, setBusy, setError, setFlash]);

  return {
    viewNote,
    setViewNote,
    showCompose,
    setShowCompose,
    onOpenNote,
    onDeleteNote,
    onIngestNote,
    onIngestAll,
  };
}
