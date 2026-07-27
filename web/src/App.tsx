import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export function App() {
  const [material, setMaterial] = useState("");
  const [result, setResult] = useState<string>("");
  const [busy, setBusy] = useState(false);

  async function onGotIt() {
    setBusy(true);
    setResult("");
    try {
      const key = import.meta.env.VITE_GOTIT_API_KEY ?? "dev-change-me";
      const res = await fetch(`${API_BASE}/v1/ingest`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${key}`,
        },
        body: JSON.stringify({ material }),
      });
      const data = await res.json();
      setResult(JSON.stringify(data, null, 2));
    } catch (err) {
      setResult(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page">
      <header className="hero">
        <p className="brand">gotit-ai</p>
        <h1>Got it? Prove it.</h1>
        <p className="lede">Paste what you studied. We check — we do not just summarize.</p>
      </header>

      <section className="panel">
        <label htmlFor="material">Study material</label>
        <textarea
          id="material"
          rows={10}
          value={material}
          onChange={(e) => setMaterial(e.target.value)}
          placeholder="Paste notes, a chapter summary, or a claim you think you know…"
        />
        <button type="button" disabled={busy || !material.trim()} onClick={onGotIt}>
          {busy ? "Checking…" : "Got it?"}
        </button>
      </section>

      {result ? (
        <section className="panel">
          <h2>Result</h2>
          <pre>{result}</pre>
        </section>
      ) : null}
    </main>
  );
}
