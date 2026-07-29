import { forceCollide, forceLink, forceManyBody, forceCenter, forceX, forceY } from "d3-force";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { api } from "../../api";
import { useStore } from "../../store";
import type { GraphEdge, GraphNode, GraphView } from "../../types";
import styles from "./index.module.scss";

type FGNode = GraphNode & {
  name: string;
  x?: number;
  y?: number;
  failCount: number;
  topicKey: string;
  val: number;
};
type FGLink = {
  source: string | FGNode;
  target: string | FGNode;
  rel: GraphEdge["rel"];
  weight: number;
  active?: boolean;
};

type FocusMode = "weak" | "all";

type FGApi = {
  d3Force: (name: string, force?: unknown) => unknown;
  d3ReheatSimulation: () => void;
  zoomToFit: (ms?: number, padding?: number) => void;
};

/** Quiet palette — topic tint via hash; claims inherit topic hue. */
const TOPIC_HUES = [210, 155, 28, 275, 335, 185, 48];

function topicHue(topic: string): number {
  let h = 0;
  for (let i = 0; i < topic.length; i++) h = (h * 31 + topic.charCodeAt(i)) >>> 0;
  return TOPIC_HUES[h % TOPIC_HUES.length];
}

function nodeFill(n: FGNode): string {
  if (n.type === "topic") return `hsl(${topicHue(n.label)} 22% 38%)`;
  if (n.type === "project") return "hsl(0 0% 48%)";
  if (n.type === "interest") return "hsl(0 0% 68%)";
  const hue = n.topicKey ? topicHue(n.topicKey) : 210;
  const fails = n.failCount;
  if (fails >= 3) return `hsl(${hue} 32% 26%)`;
  if (fails >= 1) return `hsl(${hue} 24% 34%)`;
  return `hsl(${hue} 10% 52%)`;
}

function shortLabel(text: string, max = 12): string {
  const t = text.replace(/\s+/g, " ").trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max)}…`;
}

/** 薄弱：优先易混簇；去掉无边孤立点，避免全屏大片空白. */
function filterWeakGraph(raw: GraphView): GraphView {
  const confused = raw.edges.filter((e) => e.rel === "confused_with");
  const keepClaim = new Set<string>();
  for (const e of confused) {
    keepClaim.add(e.source);
    keepClaim.add(e.target);
  }
  // 没有易混边时，退回「有失败的 claim」
  if (keepClaim.size === 0) {
    for (const n of raw.nodes) {
      if (n.type === "claim" && Number(n.meta?.fail_count ?? 0) > 0) {
        keepClaim.add(n.id);
      }
    }
  }
  if (keepClaim.size === 0) {
    const claims = raw.nodes.filter((n) => n.type === "claim").slice(0, 24);
    const ids = new Set(claims.map((c) => c.id));
    const topics = new Set<string>();
    for (const e of raw.edges) {
      if (e.rel === "has_topic" && ids.has(e.source)) topics.add(e.target);
    }
    const nodes = raw.nodes.filter(
      (n) =>
        (n.type === "claim" && ids.has(n.id)) ||
        (n.type === "topic" && topics.has(n.id)),
    );
    const nodeIds = new Set(nodes.map((n) => n.id));
    return {
      nodes,
      edges: raw.edges.filter(
        (e) =>
          (e.rel === "has_topic" || e.rel === "confused_with") &&
          nodeIds.has(e.source) &&
          nodeIds.has(e.target),
      ),
    };
  }

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
        (e.rel === "confused_with" || e.rel === "has_topic") &&
        nodeIds.has(e.source) &&
        nodeIds.has(e.target),
    ),
  };
}

function filterAllGraph(raw: GraphView): GraphView {
  const nodes = raw.nodes.filter((n) => n.type === "claim" || n.type === "topic");
  const nodeIds = new Set(nodes.map((n) => n.id));
  return {
    nodes,
    edges: raw.edges.filter(
      (e) =>
        (e.rel === "confused_with" || e.rel === "has_topic") &&
        nodeIds.has(e.source) &&
        nodeIds.has(e.target),
    ),
  };
}

export function MasteryGraphPanel({
  fullscreen = false,
  onClose,
}: {
  fullscreen?: boolean;
  onClose?: () => void;
}) {
  const { setError } = useStore();
  const wrapRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<FGApi | null>(null);
  const [raw, setRaw] = useState<GraphView | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [focus, setFocus] = useState<FocusMode>("weak");
  const [size, setSize] = useState({ w: 400, h: 480 });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const g = await api<GraphView>("/v1/obs/graph");
      setRaw(g);
      setSelected(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [setError]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!fullscreen || !onClose) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [fullscreen, onClose]);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const cr = entries[0]?.contentRect;
      if (!cr) return;
      setSize({
        w: Math.max(240, Math.floor(cr.width)),
        h: Math.max(240, Math.floor(cr.height)),
      });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const graph = useMemo(() => {
    if (!raw) return null;
    return focus === "weak" ? filterWeakGraph(raw) : filterAllGraph(raw);
  }, [raw, focus]);

  const data = useMemo(() => {
    const nodes: FGNode[] = (graph?.nodes ?? []).map((n) => {
      const failCount = Number(n.meta?.fail_count ?? 0);
      let val = 1;
      if (n.type === "topic") val = 4;
      else if (n.type === "claim") val = 1.2 + Math.min(3, failCount * 0.7);
      return {
        ...n,
        name: n.label,
        failCount,
        topicKey: String(n.meta?.topic ?? (n.type === "topic" ? n.label : "")),
        val,
      };
    });
    const links: FGLink[] = (graph?.edges ?? []).map((e) => ({
      source: e.source,
      target: e.target,
      rel: e.rel,
      weight: e.weight ?? 1,
      active: Boolean(e.meta?.active),
    }));
    return { nodes, links };
  }, [graph]);

  useEffect(() => {
    const fg = fgRef.current;
    if (!fg || data.nodes.length === 0) return;

    // Tighter packing: short links, mild charge, strong centering.
    fg.d3Force(
      "link",
      forceLink<FGNode, FGLink>()
        .id((d) => d.id)
        .distance((l) => {
          if (l.rel === "confused_with") {
            return l.active || l.weight >= 2 ? 38 : 46;
          }
          return 56; // has_topic — keep claim near hub
        })
        .strength((l) => {
          if (l.rel === "confused_with") {
            return l.active || l.weight >= 2 ? 1.1 : 0.75;
          }
          return 0.55;
        }),
    );
    fg.d3Force(
      "charge",
      forceManyBody()
        .strength((d) => {
          const n = d as FGNode;
          return n.type === "topic" ? -140 : -90;
        })
        .distanceMax(280),
    );
    fg.d3Force(
      "collide",
      forceCollide<FGNode>()
        .radius((d) => 8 + d.val * 2.4)
        .strength(0.9)
        .iterations(2),
    );
    fg.d3Force("center", forceCenter(0, 0).strength(0.18));
    fg.d3Force("x", forceX(0).strength(0.12));
    fg.d3Force("y", forceY(0).strength(0.12));
    fg.d3ReheatSimulation();

    const pad = fullscreen ? 40 : 28;
    const t1 = window.setTimeout(() => fg.zoomToFit(400, pad), 180);
    const t2 = window.setTimeout(() => fg.zoomToFit(280, pad), 700);
    const t3 = window.setTimeout(() => fg.zoomToFit(220, Math.max(24, pad - 8)), 1200);
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
      window.clearTimeout(t3);
    };
  }, [data, size.w, size.h, focus, fullscreen]);

  const stats = useMemo(() => {
    const nodes = graph?.nodes ?? [];
    const edges = graph?.edges ?? [];
    const confused = edges.filter((e) => e.rel === "confused_with");
    const active = confused.filter((e) => e.meta?.active);
    const fails = nodes
      .filter((n) => n.type === "claim")
      .reduce((s, n) => s + Number(n.meta?.fail_count ?? 0), 0);
    return {
      claims: nodes.filter((n) => n.type === "claim").length,
      confused: confused.length,
      active: active.length,
      fails,
    };
  }, [graph]);

  const body = (
    <>
      <div className={styles.toolbar}>
        <div className={styles.toolbarLeft}>
          {fullscreen ? <h2 className={styles.fsTitle}>掌握图谱</h2> : null}
          <div className={styles.focusToggle} role="tablist" aria-label="图谱范围">
            <button
              type="button"
              role="tab"
              aria-selected={focus === "weak"}
              className={focus === "weak" ? styles.focusActive : styles.focusBtn}
              onClick={() => setFocus("weak")}
            >
              薄弱
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={focus === "all"}
              className={focus === "all" ? styles.focusActive : styles.focusBtn}
              onClick={() => setFocus("all")}
            >
              全部
            </button>
          </div>
          <div className={styles.stats}>
            <span>{stats.claims} 题</span>
            <span>{stats.fails} 次挂</span>
            <span>
              {stats.active}/{stats.confused} 易混
            </span>
          </div>
        </div>
        <div className={styles.toolbarRight}>
          <button type="button" className={styles.refresh} onClick={() => void load()}>
            刷新
          </button>
          {fullscreen && onClose ? (
            <button
              type="button"
              className={styles.closeFs}
              onClick={onClose}
              aria-label="关闭图谱"
            >
              关闭
            </button>
          ) : null}
        </div>
      </div>

      <div className={styles.canvasWrap} ref={wrapRef}>
        {loading ? (
          <p className={styles.empty}>加载中…</p>
        ) : data.nodes.length === 0 ? (
          <p className={styles.empty}>暂无薄弱点。考挂几次后，易混关系会出现在这里。</p>
        ) : (
          <ForceGraph2D
            ref={fgRef as never}
            width={size.w}
            height={size.h}
            graphData={data}
            nodeId="id"
            nodeVal="val"
            nodeLabel={(n) => (n as FGNode).label}
            linkDirectionalArrowLength={0}
            cooldownTicks={160}
            warmupTicks={50}
            enableNodeDrag
            backgroundColor="rgba(0,0,0,0)"
            linkCanvasObjectMode={() => "replace"}
            linkCanvasObject={(link, ctx, globalScale) => {
              const l = link as FGLink;
              const src = l.source as FGNode;
              const tgt = l.target as FGNode;
              if (
                src?.x == null ||
                src?.y == null ||
                tgt?.x == null ||
                tgt?.y == null
              ) {
                return;
              }
              const active = l.rel === "confused_with" && (l.active || l.weight >= 2);
              ctx.beginPath();
              ctx.moveTo(src.x, src.y);
              ctx.lineTo(tgt.x, tgt.y);
              if (l.rel === "confused_with") {
                ctx.strokeStyle = active
                  ? "rgba(29,29,31,0.72)"
                  : "rgba(29,29,31,0.32)";
                ctx.lineWidth =
                  (active ? Math.min(4.2, 2 + l.weight * 0.4) : 1.4) / globalScale;
                ctx.setLineDash([]);
              } else {
                ctx.strokeStyle = "rgba(0,0,0,0.14)";
                ctx.lineWidth = 1.1 / globalScale;
                ctx.setLineDash([4 / globalScale, 4 / globalScale]);
              }
              ctx.stroke();
              ctx.setLineDash([]);
            }}
            nodeCanvasObject={(node, ctx, globalScale) => {
              const n = node as FGNode;
              const x = n.x ?? 0;
              const y = n.y ?? 0;
              const isSel = selected?.id === n.id;
              const isHover = hoverId === n.id;
              const showLabel = true; // dense graph: always label

              let r = 5.5;
              if (n.type === "topic") r = 10;
              else r = 5.5 + Math.min(5.5, n.failCount * 1.15);

              if (n.type === "topic" || isSel || isHover) {
                ctx.beginPath();
                ctx.arc(x, y, r + 4 / globalScale, 0, 2 * Math.PI);
                ctx.fillStyle = isSel || isHover
                  ? "rgba(29,29,31,0.12)"
                  : "rgba(29,29,31,0.06)";
                ctx.fill();
              }

              ctx.beginPath();
              ctx.arc(x, y, r, 0, 2 * Math.PI, false);
              ctx.fillStyle = nodeFill(n);
              ctx.fill();
              if (isSel || isHover) {
                ctx.strokeStyle = "rgba(29,29,31,0.75)";
                ctx.lineWidth = 1.8 / globalScale;
                ctx.stroke();
              }

              if (showLabel) {
                const max = n.type === "topic" ? 12 : isSel || isHover ? 28 : 16;
                const label = shortLabel(n.label, max);
                const fontSize = Math.max(
                  11.5,
                  Math.min(15, (n.type === "topic" ? 14 : 12.5) / Math.sqrt(globalScale)),
                );
                ctx.font = `${n.type === "topic" ? 600 : 500} ${fontSize}px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
                ctx.textAlign = "center";
                ctx.textBaseline = "top";
                const ty = y + r + 4 / globalScale;
                ctx.lineWidth = 3.5 / globalScale;
                ctx.strokeStyle = "rgba(245,245,247,0.92)";
                ctx.strokeText(label, x, ty);
                ctx.fillStyle =
                  n.type === "topic"
                    ? "rgba(29,29,31,0.92)"
                    : "rgba(50,50,55,0.94)";
                ctx.fillText(label, x, ty);
              }
            }}
            onNodeClick={(node) => setSelected(node as FGNode)}
            onNodeHover={(node) => setHoverId(node ? (node as FGNode).id : null)}
            onBackgroundClick={() => setSelected(null)}
            onEngineStop={() => {
              fgRef.current?.zoomToFit(260, fullscreen ? 36 : 24);
            }}
          />
        )}
      </div>

      <div className={styles.footer}>
        <p className={styles.legend}>
          实线=易混 · 虚线=主题 · 点节点看全文
          {fullscreen ? " · Esc 关闭" : null}
        </p>
        {selected ? (
          <div className={styles.detail}>
            <p className={styles.detailType}>
              {selected.type === "claim"
                ? "命题"
                : selected.type === "topic"
                  ? "主题"
                  : selected.type}
            </p>
            <p className={styles.detailLabel}>{selected.label}</p>
            {selected.type === "claim" ? (
              <p className={styles.detailMeta}>
                失败 {Number(selected.meta?.fail_count ?? 0)} 次
                {selected.meta?.topic ? ` · ${String(selected.meta.topic)}` : null}
                {selected.meta?.status
                  ? ` · ${String(selected.meta.status)}`
                  : null}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </>
  );

  if (fullscreen) {
    return (
      <div className={styles.fsRoot} role="dialog" aria-modal="true" aria-label="掌握图谱">
        <div className={styles.fsPanel}>{body}</div>
      </div>
    );
  }

  return <div className={styles.panel}>{body}</div>;
}
