import { useState, useEffect } from "react";
import { useParams, useLocation } from "wouter";
import { ArrowLeft, Clock } from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

const AGENT_COLORS: Record<string, string> = {
  orchestrator: "var(--c-purple)", synthesis: "var(--c-purple)",
  rag: "var(--c-teal)", decomposition: "var(--c-blue)",
  critique: "var(--c-coral)", compression: "var(--c-amber)", meta: "var(--c-purple)",
};
const agentColor = (id: string) => AGENT_COLORS[id] || "#6b7280";

interface TraceEvent {
  sequence: number;
  agent_id: string;
  event_type: string;
  content: Record<string, unknown> | null;
  timestamp: string | null;
}

interface ToolCall {
  tool_name: string;
  agent_id: string;
  attempt: number;
  latency_ms: number | null;
  accepted: boolean | null;
  failure_mode: string | null;
  timestamp: string | null;
}

interface ProvenanceEntry {
  sentence: string;
  source_agent: string;
  source_chunk: string | null;
  confidence: number;
}

interface Trace {
  job_id: string;
  query: string;
  status: string;
  final_answer: string | null;
  provenance_map: ProvenanceEntry[] | null;
  created_at: string | null;
  completed_at: string | null;
  events: TraceEvent[];
  tool_calls: ToolCall[];
}

const STATUS_COLORS: Record<string, string> = {
  done: "var(--c-teal)", running: "var(--c-purple)",
  pending: "#6b7280", failed: "var(--c-red)",
};

export default function JobTracePage() {
  const { id } = useParams<{ id: string }>();
  const [, setLocation] = useLocation();
  const [trace, setTrace] = useState<Trace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"timeline" | "tools" | "provenance">("timeline");

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    fetch(`${BASE}/api/trace/${id}`)
      .then(r => { if (!r.ok) throw new Error(`Job not found`); return r.json(); })
      .then(d => { setTrace(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [id]);

  if (loading) return (
    <div className="h-full flex items-center justify-center font-mono text-[12px]" style={{ color: "#4a5168", background: "#0a0b0f" }}>
      loading trace...
    </div>
  );

  if (error || !trace) return (
    <div className="h-full flex items-center justify-center" style={{ background: "#0a0b0f" }}>
      <div className="text-center">
        <div className="font-mono text-[12px] mb-2" style={{ color: "var(--c-red)" }}>{error || "not found"}</div>
        <button onClick={() => setLocation("/")} className="font-mono text-[11px]" style={{ color: "var(--c-purple)" }}>← back</button>
      </div>
    </div>
  );

  const elapsed = trace.created_at && trace.completed_at
    ? ((new Date(trace.completed_at).getTime() - new Date(trace.created_at).getTime()) / 1000).toFixed(1)
    : null;

  return (
    <div className="flex flex-col h-full" style={{ background: "#0a0b0f" }}>
      {/* Header */}
      <div className="px-6 py-4 border-b" style={{ borderColor: "rgba(255,255,255,0.07)", background: "#10121a" }}>
        <button
          data-testid="button-back"
          onClick={() => setLocation("/")}
          className="flex items-center gap-1 font-mono text-[11px] mb-3 transition-colors hover:opacity-70"
          style={{ color: "#4a5168" }}
        >
          <ArrowLeft size={12} /> back to live run
        </button>
        <div className="flex items-start gap-4">
          <div className="flex-1 min-w-0">
            <div className="font-mono text-[11px] mb-1" style={{ color: "#4a5168" }}>
              job / {trace.job_id}
            </div>
            <div className="text-[15px] font-medium text-white truncate">{trace.query}</div>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <span className="font-mono text-[11px] px-2 py-0.5 rounded border"
              style={{ borderColor: `${STATUS_COLORS[trace.status]}40`, color: STATUS_COLORS[trace.status], background: `${STATUS_COLORS[trace.status]}10` }}>
              {trace.status}
            </span>
            {elapsed && (
              <span className="flex items-center gap-1 font-mono text-[11px]" style={{ color: "#4a5168" }}>
                <Clock size={11} /> {elapsed}s
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b" style={{ borderColor: "rgba(255,255,255,0.07)", background: "#10121a" }}>
        {(["timeline", "tools", "provenance"] as const).map(t => (
          <button
            key={t}
            data-testid={`tab-${t}`}
            onClick={() => setTab(t)}
            className="px-5 py-2.5 text-[12px] font-medium border-b-2 transition-colors"
            style={{
              borderColor: tab === t ? "var(--c-purple)" : "transparent",
              color: tab === t ? "var(--c-purple)" : "#6b7280",
              background: "transparent",
            }}
          >
            {t} {t === "tools" && `(${trace.tool_calls.length})`}
            {t === "provenance" && `(${trace.provenance_map?.length || 0})`}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-auto p-6">
        {/* Timeline */}
        {tab === "timeline" && (
          <div className="space-y-0">
            {trace.events.length === 0 && (
              <div className="font-mono text-[12px]" style={{ color: "#4a5168" }}>no events recorded</div>
            )}
            {trace.events.map(ev => (
              <div
                key={ev.sequence}
                data-testid={`event-${ev.sequence}`}
                className="flex items-start gap-3 py-1.5"
                style={{ borderBottom: "0.5px solid rgba(255,255,255,0.04)" }}
              >
                <span className="font-mono text-[10px] w-5 shrink-0 text-right" style={{ color: "#4a5168" }}>{ev.sequence}</span>
                <span className="font-mono text-[12px] font-medium shrink-0" style={{ color: agentColor(ev.agent_id) }}>
                  [{ev.agent_id}]
                </span>
                <span className="text-[11px] shrink-0" style={{ color: "rgba(255,255,255,0.6)" }}>{ev.event_type}</span>
                {ev.timestamp && (
                  <span className="font-mono text-[10px] ml-auto shrink-0" style={{ color: "#4a5168" }}>
                    {new Date(ev.timestamp).toLocaleTimeString()}
                  </span>
                )}
                {ev.content && (
                  <details className="flex-1 min-w-0">
                    <summary className="font-mono text-[10px] cursor-pointer" style={{ color: "#4a5168" }}>content</summary>
                    <pre className="mt-1 text-[10px] font-mono p-2 rounded overflow-auto max-h-32 whitespace-pre-wrap"
                      style={{ background: "#161923", color: "rgba(255,255,255,0.55)" }}>
                      {JSON.stringify(ev.content, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Tool calls */}
        {tab === "tools" && (
          <div>
            {trace.tool_calls.length === 0 && <div className="font-mono text-[12px]" style={{ color: "#4a5168" }}>no tool calls</div>}
            <table className="w-full text-[11px] font-mono">
              <thead>
                <tr style={{ borderBottom: "0.5px solid rgba(255,255,255,0.07)", color: "#4a5168" }}>
                  <th className="text-left font-normal pb-2 pr-4">tool</th>
                  <th className="text-left font-normal pb-2 pr-4">agent</th>
                  <th className="text-left font-normal pb-2 pr-4">hop</th>
                  <th className="text-left font-normal pb-2 pr-4">accepted</th>
                  <th className="text-left font-normal pb-2 pr-4">failure</th>
                  <th className="text-right font-normal pb-2">ms</th>
                </tr>
              </thead>
              <tbody>
                {trace.tool_calls.map((tc, i) => (
                  <tr key={i} data-testid={`tool-call-${i}`} style={{ borderBottom: "0.5px solid rgba(255,255,255,0.04)" }}>
                    <td className="py-1.5 pr-4 text-white">{tc.tool_name}</td>
                    <td className="py-1.5 pr-4" style={{ color: agentColor(tc.agent_id) }}>{tc.agent_id}</td>
                    <td className="py-1.5 pr-4" style={{ color: "var(--c-blue)" }}>#{tc.attempt}</td>
                    <td className="py-1.5 pr-4" style={{ color: tc.accepted ? "var(--c-teal)" : "var(--c-red)" }}>
                      {tc.accepted === null ? "—" : tc.accepted ? "yes" : "no"}
                    </td>
                    <td className="py-1.5 pr-4" style={{ color: "var(--c-red)" }}>{tc.failure_mode || "—"}</td>
                    <td className="py-1.5 text-right" style={{ color: "#6b7280" }}>
                      {tc.latency_ms ? Math.round(tc.latency_ms) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Provenance */}
        {tab === "provenance" && (
          <div>
            {trace.final_answer && (
              <div
                className="rounded border p-4 mb-4"
                style={{
                  background: "linear-gradient(165deg, rgba(124,106,247,0.08) 0%, #10121a 42%)",
                  borderColor: "rgba(124,106,247,0.25)",
                }}
              >
                <div className="text-[10px] font-semibold tracking-widest uppercase mb-2" style={{ color: "#4a5168" }}>Final answer</div>
                <div className="text-[13px] text-white leading-relaxed whitespace-pre-wrap font-sans">{trace.final_answer}</div>
              </div>
            )}
            {(!trace.provenance_map || trace.provenance_map.length === 0) && (
              <div className="font-mono text-[12px]" style={{ color: "#4a5168" }}>no provenance map</div>
            )}
            <table className="w-full text-[11px]">
              <thead>
                <tr style={{ borderBottom: "0.5px solid rgba(255,255,255,0.07)", color: "#4a5168" }}>
                  <th className="text-left font-mono font-normal pb-2 pr-4">sentence</th>
                  <th className="text-left font-mono font-normal pb-2 pr-4">agent</th>
                  <th className="text-left font-mono font-normal pb-2 pr-4">source</th>
                  <th className="text-right font-mono font-normal pb-2">conf</th>
                </tr>
              </thead>
              <tbody>
                {trace.provenance_map?.map((p, i) => (
                  <tr key={i} data-testid={`provenance-${i}`} style={{ borderBottom: "0.5px solid rgba(255,255,255,0.04)" }}>
                    <td className="py-1.5 pr-4 max-w-sm truncate" style={{ color: "rgba(255,255,255,0.65)" }}>{p.sentence}</td>
                    <td className="py-1.5 pr-4">
                      <span className="font-mono text-[10px] px-1.5 py-0.5 rounded" style={{ background: `${agentColor(p.source_agent)}15`, color: agentColor(p.source_agent) }}>
                        {p.source_agent}
                      </span>
                    </td>
                    <td className="py-1.5 pr-4">
                      {p.source_chunk && (
                        <span className="font-mono text-[10px] px-1.5 py-0.5 rounded" style={{ background: "rgba(45,212,191,0.1)", color: "var(--c-teal)" }}>
                          {p.source_chunk}
                        </span>
                      )}
                    </td>
                    <td className="py-1.5 text-right font-mono" style={{ color: p.confidence >= 0.7 ? "var(--c-teal)" : "var(--c-amber)" }}>
                      {(p.confidence * 100).toFixed(0)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
