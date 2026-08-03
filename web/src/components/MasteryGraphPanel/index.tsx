import cytoscape, { type Core, type ElementDefinition, type StylesheetJson } from "cytoscape";
import fcose from "cytoscape-fcose";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api";
import { stripHtml } from "../../lib/format";
import { useStore } from "../../store";
import type { CheckMode, Claim, GraphEdge, GraphNode, GraphView } from "../../types";
import styles from "./index.module.scss";

try {
  cytoscape.use(fcose);
} catch {
  /* already registered (HMR) */
}

type FocusMode = "weak" | "all" | "recent";

type Sel =
  | { kind: "claim"; node: GraphNode }
  | { kind: "topic"; node: GraphNode }
  | { kind: "edge"; edge: GraphEdge; blurb: string }
  | null;

/** Quiet slate tints by topic — Apple-like, no shouty accent. */
const TOPIC_TONES = [
  { fill: "#d9e4f0", border: "#9eb4c9", claim: "#c5d5e6", claimBorder: "#8aa3bb" },
  { fill: "#dde8e3", border: "#9fb8ae", claim: "#c8d9d1", claimBorder: "#8aada0" },
  { fill: "#e4e2ea", border: "#b0aec0", claim: "#d2d0dc", claimBorder: "#9b99ad" },
  { fill: "#e6e1db", border: "#b8aea4", claim: "#d6cfc6", claimBorder: "#a89a8d" },
  { fill: "#dce5ea", border: "#a5b7c2", claim: "#c8d5dd", claimBorder: "#8ea4b2" },
] as const;

function cleanLabel(text: string): string {
  return stripHtml(text).replace(/\s+/g, " ").trim();
}

function shortLabel(text: string, max = 16): string {
  const t = cleanLabel(text);
  if (!t) return "·";
  if (t.length <= max) return t;
  return `${t.slice(0, max)}…`;
}

function hashTone(key: string): number {
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) | 0;
  return Math.abs(h) % TOPIC_TONES.length;
}

function claimFromNode(n: GraphNode): Claim | null {
  if (n.type !== "claim") return null;
  const meta = n.meta ?? {};
  const id = String(meta.claim_id ?? "").trim() || n.id.replace(/^claim:/, "");
  if (!id) return null;
  const mode = meta.preferred_check_mode;
  const preferred =
    mode === "probe" || mode === "drill" || mode === "teach_back"
      ? (mode as CheckMode)
      : null;
  const projectRaw = meta.project_id;
  return {
    id,
    text: cleanLabel(n.label) || "可考主张",
    status: String(meta.status ?? "not_yet"),
    topic: meta.topic != null ? String(meta.topic) : null,
    source_note_id: null,
    next_review_at: null,
    project_id: projectRaw != null && String(projectRaw) ? String(projectRaw) : null,
    preferred_check_mode: preferred,
    failure_hint:
      meta.last_fail_reason != null ? String(meta.last_fail_reason) : null,
  };
}

function ctaForClaim(claim: Claim): { label: string; note?: string } {
  if (claim.preferred_check_mode === "teach_back") return { label: "回讲" };
  if (claim.preferred_check_mode === "drill") {
    return { label: "练深挖", note: "练习场，不算正式掌握" };
  }
  return { label: "开考" };
}

function filterClaimCluster(raw: GraphView, keepClaim: Set<string>): GraphView {
  const topics = new Set<string>();
  for (const e of raw.edges) {
    if (e.rel === "has_topic" && keepClaim.has(e.source)) topics.add(e.target);
  }
  const nodes = raw.nodes.filter(
    (n) =>
      (n.type === "claim" && keepClaim.has(n.id)) ||
      (n.type === "topic" && topics.has(n.id)),
  );
  const nodeIds = new Set(nodes.map((n) => n.id));
  return {
    nodes,
    edges: raw.edges.filter(
      (e) =>
        (e.rel === "confused_with" ||
          e.rel === "depends_on" ||
          e.rel === "has_topic") &&
        nodeIds.has(e.source) &&
        nodeIds.has(e.target),
    ),
  };
}

function filterWeakGraph(raw: GraphView): GraphView {
  const claimLinks = raw.edges.filter(
    (e) => e.rel === "confused_with" || e.rel === "depends_on",
  );
  const keepClaim = new Set<string>();
  for (const e of claimLinks) {
    keepClaim.add(e.source);
    keepClaim.add(e.target);
  }
  if (keepClaim.size === 0) {
    for (const n of raw.nodes) {
      if (n.type === "claim" && Number(n.meta?.fail_event_count ?? n.meta?.fail_count ?? 0) > 0) {
        keepClaim.add(n.id);
      }
    }
  }
  if (keepClaim.size === 0) {
    const claims = raw.nodes.filter((n) => n.type === "claim").slice(0, 24);
    return filterClaimCluster(raw, new Set(claims.map((c) => c.id)));
  }
  return filterClaimCluster(raw, keepClaim);
}

function filterAllGraph(raw: GraphView): GraphView {
  const nodes = raw.nodes.filter((n) => n.type === "claim" || n.type === "topic");
  const nodeIds = new Set(nodes.map((n) => n.id));
  return {
    nodes,
    edges: raw.edges.filter(
      (e) =>
        (e.rel === "confused_with" ||
          e.rel === "depends_on" ||
          e.rel === "has_topic") &&
        nodeIds.has(e.source) &&
        nodeIds.has(e.target),
    ),
  };
}

function filterRecentGraph(raw: GraphView): GraphView {
  const recent = new Set(
    raw.nodes
      .filter((n) => n.type === "claim" && Boolean(n.meta?.recent))
      .map((n) => n.id),
  );
  if (recent.size === 0) return { nodes: [], edges: [] };
  const keep = new Set(recent);
  for (const e of raw.edges) {
    if (e.rel !== "confused_with" && e.rel !== "depends_on") continue;
    if (recent.has(e.source) || recent.has(e.target)) {
      keep.add(e.source);
      keep.add(e.target);
    }
  }
  return filterClaimCluster(raw, keep);
}

function edgeBlurb(e: GraphEdge): string {
  const meta = e.meta ?? {};
  if (e.rel === "confused_with") {
    const bits: string[] = [
      meta.cross_topic ? "分属不同主题，但容易搞混" : "这两条经常一起搞混",
    ];
    if (meta.source_topic && meta.target_topic) {
      bits.push(
        `${cleanLabel(String(meta.source_topic))} ↔ ${cleanLabel(String(meta.target_topic))}`,
      );
    }
    if (meta.reason_summary) bits.push(String(meta.reason_summary));
    return bits.join("。");
  }
  if (e.rel === "depends_on") {
    const prereq = meta.prereq_label
      ? cleanLabel(String(meta.prereq_label))
      : null;
    if (meta.unmet) {
      return prereq
        ? `还没过：「${prereq}」。建议先练这条。`
        : "箭头指向的那条还没过，建议先练它。";
    }
    return prereq ? `前置已过：「${prereq}」。` : "这条前置已经过了。";
  }
  return e.rel;
}

function claimSize(fails: number): number {
  if (fails >= 4) return 42;
  if (fails >= 2) return 36;
  if (fails >= 1) return 32;
  return 28;
}

function toElements(view: GraphView): ElementDefinition[] {
  const topicKeyByClaim = new Map<string, string>();
  for (const e of view.edges) {
    if (e.rel === "has_topic") topicKeyByClaim.set(e.source, e.target);
  }

  const els: ElementDefinition[] = [];
  for (const n of view.nodes) {
    if (n.type !== "claim" && n.type !== "topic") continue;
    const fails = Number(n.meta?.fail_event_count ?? n.meta?.fail_count ?? 0);
    const label = cleanLabel(n.label) || (n.type === "topic" ? "主题" : "命题");
    const topicKey =
      n.type === "topic"
        ? n.id
        : topicKeyByClaim.get(n.id) ||
          (n.meta?.topic != null ? String(n.meta.topic) : n.id);
    const tone = TOPIC_TONES[hashTone(topicKey)];
    const size = n.type === "claim" ? claimSize(fails) : 0;
    els.push({
      group: "nodes",
      data: {
        id: n.id,
        label,
        shortLabel: shortLabel(label, n.type === "topic" ? 14 : 16),
        type: n.type,
        fails,
        size,
        topic: n.meta?.topic != null ? String(n.meta.topic) : "",
        recent: Boolean(n.meta?.recent),
        fill: n.type === "topic" ? tone.fill : tone.claim,
        border: n.type === "topic" ? tone.border : tone.claimBorder,
        raw: n,
      },
      classes: [
        n.type,
        n.type === "claim" && fails > 0 ? "hasFail" : "",
        n.type === "claim" && fails >= 3 ? "hasFailMore" : "",
        n.type === "claim" && Boolean(n.meta?.recent) ? "recent" : "",
      ]
        .filter(Boolean)
        .join(" "),
    });
  }
  const ids = new Set(els.map((e) => String(e.data?.id)));
  for (const e of view.edges) {
    if (!ids.has(e.source) || !ids.has(e.target)) continue;
    if (
      e.rel !== "confused_with" &&
      e.rel !== "depends_on" &&
      e.rel !== "has_topic"
    ) {
      continue;
    }
    const w = e.weight ?? 1;
    els.push({
      group: "edges",
      data: {
        id: `${e.rel}:${e.source}->${e.target}`,
        source: e.source,
        target: e.target,
        rel: e.rel,
        weight: w,
        width: e.rel === "has_topic" ? 1 : Math.min(1.2 + w * 0.55, 3.2),
        raw: e,
      },
      classes: [
        e.rel,
        e.meta?.cross_topic ? "crossTopic" : "",
        e.meta?.unmet ? "unmet" : "",
        e.meta?.active || w >= 2 ? "strong" : "",
      ]
        .filter(Boolean)
        .join(" "),
    });
  }
  return els;
}

const STYLE = [
  {
    selector: "node",
    style: {
      "background-color": "data(fill)",
      "border-width": 1.5,
      "border-color": "data(border)",
      color: "#3a3a3c",
      "font-size": 11,
      "font-weight": 500,
      "font-family":
        "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', sans-serif",
      "text-valign": "bottom",
      "text-halign": "center",
      "text-margin-y": 8,
      "text-max-width": 112,
      "text-wrap": "wrap",
      "text-opacity": 1,
      "overlay-opacity": 0,
      "transition-property":
        "background-color, border-color, border-width, opacity, width, height",
      "transition-duration": "0.15s",
    },
  },
  {
    selector: "node.topic",
    style: {
      shape: "round-rectangle",
      label: "data(shortLabel)",
      width: "label",
      height: 30,
      padding: "10px",
      color: "#1d1d1f",
      "font-size": 12,
      "font-weight": 600,
      "text-valign": "center",
      "text-halign": "center",
      "text-margin-y": 0,
      "text-max-width": 140,
      "border-width": 1,
    },
  },
  {
    selector: "node.claim",
    style: {
      shape: "ellipse",
      label: "data(shortLabel)",
      width: "data(size)",
      height: "data(size)",
      color: "#1d1d1f",
      "font-size": 11,
      "font-weight": 500,
      "text-background-color": "#f5f5f7",
      "text-background-opacity": 0.85,
      "text-background-padding": "2px",
      "text-background-shape": "round-rectangle",
    },
  },
  {
    selector: "node.claim.hasFailMore",
    style: {
      "border-width": 2,
      color: "#1d1d1f",
    },
  },
  {
    selector: "node.claim.recent",
    style: {
      "border-width": 2,
    },
  },
  {
    selector: "node:selected",
    style: {
      "border-width": 2.5,
      "border-color": "#1d1d1f",
      "z-index": 20,
    },
  },
  {
    selector: "node.claim:selected, node.claim.hover",
    style: {
      "font-weight": 600,
      "z-index": 20,
    },
  },
  {
    selector: "node.topic:selected, node.topic.hover",
    style: {
      "border-color": "#1d1d1f",
      "border-width": 1.5,
      "z-index": 20,
    },
  },
  {
    selector: "node.dim",
    style: {
      opacity: 0.22,
    },
  },
  {
    selector: "edge",
    style: {
      width: "data(width)",
      "line-color": "#b8c0c8",
      "curve-style": "bezier",
      "target-arrow-shape": "none",
      opacity: 0.95,
      "overlay-opacity": 0,
      "transition-property": "line-color, opacity, width",
      "transition-duration": "0.15s",
    },
  },
  {
    selector: "edge.has_topic",
    style: {
      width: 1,
      "line-color": "#d8d8dd",
      opacity: 0.55,
      "curve-style": "haystack",
      "haystack-radius": 0.4,
    },
  },
  {
    selector: "edge.confused_with",
    style: {
      "line-color": "#7d92a8",
      opacity: 0.9,
    },
  },
  {
    selector: "edge.confused_with.strong",
    style: {
      "line-color": "#5f7a94",
      opacity: 1,
    },
  },
  {
    selector: "edge.confused_with.crossTopic",
    style: {
      "line-color": "#6a849c",
      "line-style": "solid",
    },
  },
  {
    selector: "edge.depends_on",
    style: {
      "line-color": "#9a9aa1",
      "line-style": "dashed",
      "target-arrow-shape": "triangle",
      "target-arrow-color": "#9a9aa1",
      "arrow-scale": 0.85,
    },
  },
  {
    selector: "edge.depends_on.unmet",
    style: {
      "line-color": "#6e6e73",
      "target-arrow-color": "#6e6e73",
    },
  },
  {
    selector: "edge:selected",
    style: {
      "line-color": "#1d1d1f",
      "target-arrow-color": "#1d1d1f",
      width: 2.5,
      opacity: 1,
      "z-index": 15,
    },
  },
  {
    selector: "edge.dim",
    style: {
      opacity: 0.12,
    },
  },
] as StylesheetJson;

function focusNeighborhood(cy: Core, ele: cytoscape.SingularElementArgument | null) {
  cy.elements().removeClass("dim");
  if (!ele) return;
  const closed = ele.closedNeighborhood();
  cy.elements().not(closed).addClass("dim");
}

export function MasteryGraphPanel({ embedded = true }: { embedded?: boolean }) {
  const { setError, queueVerifyClaim, setMasteryGraphOpen } = useStore();
  const hostRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [raw, setRaw] = useState<GraphView | null>(null);
  const [loading, setLoading] = useState(true);
  const [focus, setFocus] = useState<FocusMode>("weak");
  const [sel, setSel] = useState<Sel>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const g = await api<GraphView>("/v1/obs/graph");
      setRaw(g);
      setSel(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [setError]);

  useEffect(() => {
    void load();
  }, [load]);

  const view = useMemo(() => {
    if (!raw) return null;
    if (focus === "recent") return filterRecentGraph(raw);
    if (focus === "all") return filterAllGraph(raw);
    return filterWeakGraph(raw);
  }, [raw, focus]);

  const claimCount = useMemo(
    () => (view?.nodes ?? []).filter((n) => n.type === "claim").length,
    [view],
  );

  const edgeStats = useMemo(() => {
    const edges = view?.edges ?? [];
    return {
      confuse: edges.filter((e) => e.rel === "confused_with").length,
      depends: edges.filter((e) => e.rel === "depends_on").length,
    };
  }, [view]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !view) return;

    const elements = toElements(view);
    if (cyRef.current) {
      cyRef.current.destroy();
      cyRef.current = null;
    }

    const cy = cytoscape({
      container: host,
      elements,
      style: STYLE,
      minZoom: 0.4,
      maxZoom: 2.6,
      wheelSensitivity: 0.22,
      boxSelectionEnabled: false,
      autoungrabify: false,
      layout: {
        name: "fcose",
        animate: true,
        animationDuration: 420,
        animationEasing: "ease-out",
        randomize: true,
        fit: true,
        padding: 48,
        nodeSeparation: 72,
        idealEdgeLength: 110,
        edgeElasticity: 0.28,
        nestingFactor: 0.08,
        gravity: 0.28,
        gravityRange: 3.8,
        quality: "proof",
        nodeDimensionsIncludeLabels: true,
        packComponents: true,
        tile: true,
      } as cytoscape.LayoutOptions,
    });
    cyRef.current = cy;

    const clearHover = () => {
      cy.nodes().removeClass("hover");
    };

    cy.on("tap", "node", (evt) => {
      const n = evt.target;
      cy.elements().unselect();
      n.select();
      focusNeighborhood(cy, n);
      const rawNode = n.data("raw") as GraphNode;
      if (rawNode.type === "claim") setSel({ kind: "claim", node: rawNode });
      else setSel({ kind: "topic", node: rawNode });
    });
    cy.on("tap", "edge", (evt) => {
      const e = evt.target;
      if (e.data("rel") === "has_topic") return;
      cy.elements().unselect();
      e.select();
      focusNeighborhood(cy, e);
      const rawEdge = e.data("raw") as GraphEdge;
      setSel({ kind: "edge", edge: rawEdge, blurb: edgeBlurb(rawEdge) });
    });
    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        cy.elements().unselect();
        focusNeighborhood(cy, null);
        setSel(null);
      }
    });
    cy.on("mouseover", "node", (evt) => {
      clearHover();
      evt.target.addClass("hover");
      if (cy.$(":selected").empty()) focusNeighborhood(cy, evt.target);
    });
    cy.on("mouseout", "node", () => {
      clearHover();
      const selected = cy.$(":selected");
      if (selected.nonempty()) focusNeighborhood(cy, selected[0]!);
      else focusNeighborhood(cy, null);
    });

    const onResize = () => {
      cy.resize();
      cy.fit(undefined, 44);
    };
    const ro = new ResizeObserver(onResize);
    ro.observe(host);

    return () => {
      ro.disconnect();
      cy.destroy();
      if (cyRef.current === cy) cyRef.current = null;
    };
  }, [view]);

  const onLaunch = useCallback(() => {
    if (!sel || sel.kind !== "claim") return;
    const claim = claimFromNode(sel.node);
    if (!claim) return;
    queueVerifyClaim(claim);
    setMasteryGraphOpen(false);
  }, [sel, queueVerifyClaim, setMasteryGraphOpen]);

  const selectedClaim =
    sel?.kind === "claim" ? claimFromNode(sel.node) : null;
  const cta = selectedClaim ? ctaForClaim(selectedClaim) : null;
  const failCount =
    sel?.kind === "claim"
      ? Number(
          sel.node.meta?.fail_event_count ?? sel.node.meta?.fail_count ?? 0,
        )
      : 0;

  const emptyLine =
    focus === "recent" ? "近 14 天暂无还差点" : "暂时没有要盯的弱点";

  return (
    <div className={`${styles.root} ${embedded ? styles.embedded : ""}`}>
      <div className={styles.toolbar}>
        <div className={styles.filters} role="tablist" aria-label="显示范围">
          {(
            [
              ["weak", "还没过"],
              ["recent", "近14天"],
              ["all", "全部"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={focus === id}
              className={focus === id ? styles.filterOn : styles.filter}
              onClick={() => setFocus(id)}
            >
              {label}
              {focus === id && !loading && claimCount > 0 ? (
                <span className={styles.filterCount}>{claimCount}</span>
              ) : null}
            </button>
          ))}
        </div>
        <button
          type="button"
          className={styles.refresh}
          onClick={() => void load()}
        >
          刷新
        </button>
      </div>

      <div className={styles.body}>
        <div className={styles.canvas}>
          {loading ? <p className={styles.empty}>加载中…</p> : null}
          {!loading && claimCount === 0 ? (
            <p className={styles.empty}>{emptyLine}</p>
          ) : null}
          {!loading && claimCount > 0 ? (
            <div className={styles.legend} aria-hidden>
              <span className={styles.legendItem}>
                <span className={`${styles.legendSwatch} ${styles.legendConfuse}`} />
                容易搞混
                {edgeStats.confuse ? ` · ${edgeStats.confuse}` : ""}
              </span>
              <span className={styles.legendItem}>
                <span className={`${styles.legendSwatch} ${styles.legendDepends}`} />
                还差前置
                {edgeStats.depends ? ` · ${edgeStats.depends}` : ""}
              </span>
              <span className={styles.legendItem}>
                <span className={`${styles.legendSwatch} ${styles.legendTopic}`} />
                主题
              </span>
            </div>
          ) : null}
          <div
            ref={hostRef}
            className={styles.cy}
            style={{
              visibility: !loading && claimCount > 0 ? "visible" : "hidden",
            }}
          />
        </div>

        <aside className={styles.side} aria-label="选中详情">
          {!sel ? (
            <div className={styles.sideIdle}>
              <p className={styles.sideIdleTitle}>还没选</p>
              <p className={styles.sideIdleBody}>
                点左边的圆点，这里会显示内容，并可以开考。
              </p>
            </div>
          ) : null}

          {sel?.kind === "claim" && selectedClaim ? (
            <div className={styles.sideCard}>
              <p className={styles.sideLabel}>{cleanLabel(sel.node.label)}</p>
              <div className={styles.sideChips}>
                {failCount > 0 ? (
                  <span className={styles.chipWarn}>失手 {failCount} 次</span>
                ) : (
                  <span className={styles.chip}>还没考过</span>
                )}
                {sel.node.meta?.topic ? (
                  <span className={styles.chip}>
                    {cleanLabel(String(sel.node.meta.topic))}
                  </span>
                ) : null}
                {sel.node.meta?.recent ? (
                  <span className={styles.chip}>近 14 天</span>
                ) : null}
              </div>
              {sel.node.meta?.last_fail_reason ? (
                <p className={styles.sideMeta}>
                  上次：{String(sel.node.meta.last_fail_reason)}
                </p>
              ) : null}
              {cta ? (
                <div className={styles.sideActions}>
                  <button type="button" className={styles.cta} onClick={onLaunch}>
                    {cta.label}
                  </button>
                  {cta.note ? (
                    <span className={styles.ctaNote}>{cta.note}</span>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}

          {sel?.kind === "topic" ? (
            <div className={styles.sideCard}>
              <p className={styles.sideEyebrow}>主题</p>
              <p className={styles.sideLabel}>{cleanLabel(sel.node.label)}</p>
              <p className={styles.sideMeta}>再点旁边的圆点，就能开考。</p>
            </div>
          ) : null}

          {sel?.kind === "edge" ? (
            <div className={styles.sideCard}>
              <p className={styles.sideEyebrow}>
                {sel.edge.rel === "confused_with" ? "容易搞混" : "还差前置"}
              </p>
              <p className={styles.sideMeta}>{sel.blurb}</p>
            </div>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
