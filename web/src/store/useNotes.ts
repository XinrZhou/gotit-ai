import { useCallback, useState } from "react";
import { api } from "../api";
import type { Claim, DayNote, IngestUi, NoteIngestResponse } from "../types";
import type { Run } from "./types";

type Deps = {
  notes: DayNote[];
  run: Run;
  refresh: () => Promise<void>;
  setBusy: (b: boolean) => void;
  setError: (s: string) => void;
  setFlash: (s: string) => void;
};

function asClaim(raw: Claim, noteId: string): Claim {
  return {
    id: raw.id,
    text: (raw.text || "").trim() || "可考主张",
    status: raw.status || "not_yet",
    topic: raw.topic ?? null,
    source_note_id: raw.source_note_id ?? noteId,
    next_review_at: raw.next_review_at ?? null,
  };
}

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
  const [ingestUi, setIngestUi] = useState<IngestUi | null>(null);
  const [pendingExamineClaim, setPendingExamineClaim] = useState<Claim | null>(
    null,
  );

  const clearIngestUi = useCallback(() => {
    setIngestUi(null);
  }, []);

  const clearPendingExamineClaim = useCallback(() => {
    setPendingExamineClaim(null);
  }, []);

  const dismissIngestReady = useCallback(() => {
    setIngestUi(null);
    setViewNote(null);
    setShowCompose(false);
  }, []);

  const requestExamineFromIngest = useCallback(() => {
    if (!ingestUi || ingestUi.phase !== "ready") return;
    const first = ingestUi.claims[0];
    if (!first) return;
    const claim = asClaim(first, ingestUi.noteId);
    setIngestUi(null);
    setViewNote(null);
    setShowCompose(false);
    setPendingExamineClaim(claim);
  }, [ingestUi]);

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
        setIngestUi(null);
      }, "笔记已删除");
    },
    [run],
  );

  const onDeleteNotes = useCallback(
    (ids: string[]) => {
      if (ids.length === 0) return;
      void run(async () => {
        await api<{ deleted: number }>("/v1/notes/batch-delete", {
          method: "POST",
          body: JSON.stringify({ ids }),
        });
        setViewNote((cur) => (cur && ids.includes(cur.id) ? null : cur));
        setIngestUi(null);
      }, ids.length === 1 ? "笔记已删除" : `已删除 ${ids.length} 条资料`);
    },
    [run],
  );

  const beginComposeIngest = useCallback(() => {
    setIngestUi({ phase: "generating", noteId: null, surface: "compose" });
  }, []);

  const runIngestOnSurface = useCallback(
    async (noteId: string, surface: "compose" | "view") => {
      setBusy(true);
      setError("");
      setIngestUi({ phase: "generating", noteId, surface });
      try {
        const res = await api<NoteIngestResponse>(`/v1/notes/${noteId}/ingest`, {
          method: "POST",
          body: JSON.stringify({ add_plan_item: true }),
        });
        const claims = (res.claims ?? []).map((c) => asClaim(c, noteId));
        if (claims.length === 0) {
          setIngestUi(null);
          setFlash("没抽出可考的句子，换一段再试");
          await refresh();
          return;
        }
        setIngestUi({
          phase: "ready",
          noteId: res.note_id || noteId,
          claims,
          surface,
        });
        await refresh();
      } catch (err) {
        setIngestUi(null);
        setError(String(err));
      } finally {
        setBusy(false);
      }
    },
    [refresh, setBusy, setError, setFlash],
  );

  const onIngestNote = useCallback(
    (
      id: string,
      opts?: { surface?: "compose" | "view" | "silent" },
    ): Promise<void> => {
      const surface = opts?.surface ?? "silent";
      if (surface === "silent") {
        return run(
          () =>
            api<NoteIngestResponse>(`/v1/notes/${id}/ingest`, {
              method: "POST",
              body: JSON.stringify({ add_plan_item: true }),
            }),
          "题出好了",
        );
      }
      return runIngestOnSurface(id, surface);
    },
    [run, runIngestOnSurface],
  );

  const onIngestAll = useCallback(() => {
    const pending = notes.filter((n) => n.claim_ids.length === 0);
    if (pending.length === 0) return;
    void (async () => {
      setBusy(true);
      setError("");
      try {
        for (const n of pending) {
          await api<NoteIngestResponse>(`/v1/notes/${n.id}/ingest`, {
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
    onDeleteNotes,
    onIngestNote,
    onIngestAll,
    ingestUi,
    beginComposeIngest,
    clearIngestUi,
    dismissIngestReady,
    requestExamineFromIngest,
    pendingExamineClaim,
    clearPendingExamineClaim,
  };
}
