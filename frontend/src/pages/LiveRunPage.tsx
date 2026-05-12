import { useRef, useEffect, useState } from "react";
import { useLocation } from "wouter";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useApp, type SSEEvent, type AgentState } from "@/context/AppContext";
import { Copy, ExternalLink, Plus, ChevronRight } from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

// ─── Shared primitives ───────────────────────────────────────────────────────

const AGENT_COLORS: Record<string, string> = {
  orchestrator: "var(--c-purple)",
  synthesis:    "var(--c-purple)",
  rag:          "var(--c-teal)",
  decomposition:"var(--c-blue)",
  critique:     "var(--c-coral)",
  compression:  "var(--c-amber)",
  meta:         "var(--c-purple)",
};
const agentColor = (id: string) => AGENT_COLORS[id] || "var(--c-muted)";

function Tag({ children, color }: { children: React.ReactNode; color: string }) {
  return (
    <span className="font-mono text-[11px] px-1 rounded" style={{ color, background: `${color}18` }}>
      {children}
    </span>
  );
}

function Panel({ title, right, children, className = "" }: {
  title: string;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col border rounded ${className}`}
      style={{ background: "#10121a", borderColor: "rgba(255,255,255,0.07)" }}
    >
      <div
        className="flex items-center justify-between px-3 py-2 border-b shrink-0"
        style={{ borderColor: "rgba(255,255,255,0.07)" }}
      >
        <span className="text-[10px] font-semibold tracking-widest uppercase" style={{ color: "#4a5168" }}>
          {title}
        </span>
        {right}
      </div>
      {children}
    </div>
  );
}

// ─── Panel 1: Agent Pipeline Bar ─────────────────────────────────────────────

const PIPELINE_ORDER = ["decomposition", "rag", "critique", "synthesis"];
const PIPELINE_LABELS: Record<string, string> = {
  decomposition: "Decomposition",
  rag: "RAG",
  critique: "Critique",
  synthesis: "Synthesis",
};

function PipelineBar({ agents }: { agents: AgentState[] }) {
  const agentMap = Object.fromEntries(agents.map(a => [a.id, a]));

  return (
    <Panel title="Agent Pipeline">
      <div className="flex items-center gap-0 px-4 py-3 overflow-x-auto">
        {PIPELINE_ORDER.map((id, i) => {
          const agent = agentMap[id];
          const status = agent?.status || "idle";
          const latency = agent?.latencyMs ? (agent.latencyMs / 1000).toFixed(1) + "s" : null;
          const color = agentColor(id);

          let borderColor = "rgba(255,255,255,0.08)";
          let bgColor = "#161923";
          let statusText = "waiting";
          let statusColor = "#4a5168";

          if (status === "done") {
            borderColor = "var(--c-teal)";
            bgColor = "rgba(45,212,191,0.06)";
            statusText = latency ? `done · ${latency}` : "done";
            statusColor = "var(--c-teal)";
          } else if (status === "skipped") {
            borderColor = "rgba(255,255,255,0.12)";
            bgColor = "rgba(74,81,104,0.12)";
            statusText = "skipped";
            statusColor = "#6b7280";
          } else if (status === "running") {
            borderColor = color;
            bgColor = `${color}0f`;
            statusText = "running...";
            statusColor = color;
          }

          return (
            <div key={id} className="flex items-center gap-0">
              <div
                className="flex flex-col items-center justify-center rounded border px-5 py-3 shrink-0"
                style={{ minWidth: 120, background: bgColor, borderColor, borderWidth: "0.5px" }}
              >
                {/* Status indicator */}
                <div className="flex items-center gap-1.5 mb-2">
                  {status === "done" && (
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M2 6l3 3 5-5" stroke="var(--c-teal)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                  {status === "skipped" && (
                    <span className="font-mono text-[10px] leading-none" style={{ color: "#6b7280" }}>—</span>
                  )}
                  {status === "running" && (
                    <span className="w-2 h-2 rounded-full pulse-dot" style={{ background: color }} />
                  )}
                  {status === "idle" && (
                    <span className="w-2 h-2 rounded-full opacity-30" style={{ background: "#4a5168" }} />
                  )}
                </div>
                <span className="text-[13px] font-medium text-white">{PIPELINE_LABELS[id]}</span>
                <span className="font-mono text-[11px] mt-0.5" style={{ color: statusColor }}>
                  {statusText}
                </span>
              </div>
              {i < PIPELINE_ORDER.length - 1 && (
                <ChevronRight size={14} className="mx-1 shrink-0" style={{ color: "#4a5168" }} />
              )}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

// ─── Panel 2: SSE Token Stream + Event Log ────────────────────────────────────

function renderToken(token: string, agentId: string): React.ReactNode {
  const color = agentColor(agentId);
  return <span style={{ color }}>{token}</span>;
}

function EventLogLine({ evt }: { evt: SSEEvent }) {
  if (evt.type === "routing") {
    return (
      <div className="flex items-start gap-2 py-0.5">
        <span className="font-mono text-[11px]" style={{ color: "#4a5168" }}>route</span>
        <Tag color="var(--c-purple)">{evt.from_agent} → {evt.to_agent}</Tag>
        <span className="font-mono text-[11px] text-white/50 flex-1 min-w-0 truncate">{evt.justification?.slice(0, 80)}</span>
      </div>
    );
  }
  if (evt.type === "tool_call") {
    const ok = evt.status === "success";
    const retry = (evt.attempt || 0) > 0;
    return (
      <div className="flex items-center gap-2 py-0.5">
        <span className="font-mono text-[11px]" style={{ color: "#4a5168" }}>tool</span>
        <Tag color={agentColor(evt.agent_id || "")}>[{evt.agent_id}]</Tag>
        <span className="font-mono text-[11px] text-white">{evt.tool_name}</span>
        <span className="font-mono text-[11px]" style={{ color: ok ? "var(--c-teal)" : "var(--c-red)" }}>
          {retry ? `retry#${evt.attempt}` : ok ? "200" : evt.status}
        </span>
      </div>
    );
  }
  if (evt.type === "policy_violation") {
    return (
      <div className="flex items-center gap-2 py-0.5">
        <span className="font-mono text-[11px]" style={{ color: "var(--c-red)" }}>VIOLATION</span>
        <Tag color="var(--c-red)">[{evt.agent_id}]</Tag>
        <span className="font-mono text-[11px]" style={{ color: "var(--c-red)" }}>{evt.message?.slice(0, 100)}</span>
      </div>
    );
  }
  if (evt.type === "agent_start") {
    return (
      <div className="flex items-center gap-2 py-0.5">
        <span className="font-mono text-[11px]" style={{ color: "#4a5168" }}>start</span>
        <Tag color={agentColor(evt.agent_id || "")}>[{evt.agent_id}]</Tag>
        <span className="font-mono text-[11px] text-white/40">budget {evt.budget_remaining || evt.budget} tok</span>
      </div>
    );
  }
  if (evt.type === "agent_done") {
    return (
      <div className="flex items-center gap-2 py-0.5">
        <span className="font-mono text-[11px]" style={{ color: "var(--c-teal)" }}>done</span>
        <Tag color={agentColor(evt.agent_id || "")}>[{evt.agent_id}]</Tag>
        <span className="font-mono text-[11px] text-white/40">{evt.summary?.slice(0, 80)}</span>
      </div>
    );
  }
  if (evt.type === "budget") {
    const used = evt.used || 0;
    const budget = evt.budget || 8000;
    const pct = Math.round((used / budget) * 100);
    return (
      <div className="flex items-center gap-2 py-0.5">
        <span className="font-mono text-[11px]" style={{ color: "#4a5168" }}>budget</span>
        <Tag color={agentColor(evt.agent_id || "")}>[{evt.agent_id}]</Tag>
        <span className="font-mono text-[11px]" style={{ color: pct > 85 ? "var(--c-red)" : "var(--c-amber)" }}>
          {pct}% used
        </span>
      </div>
    );
  }
  if (evt.type === "done") {
    return (
      <div className="py-0.5">
        <span className="font-mono text-[11px]" style={{ color: "var(--c-teal)" }}>── pipeline complete ──</span>
      </div>
    );
  }
  return null;
}

function TokenStreamPanel() {
  const { tokenBuffers, activity, streaming, finalAnswer } = useApp();
  const streamRef = useRef<HTMLDivElement>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (streamRef.current) streamRef.current.scrollTop = streamRef.current.scrollHeight;
  }, [tokenBuffers]);
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [activity]);

  const activeAgent = Object.keys(tokenBuffers).find(k => tokenBuffers[k]);
  const displayTokens = activeAgent ? tokenBuffers[activeAgent] : (finalAnswer || "");

  return (
    <Panel
      title="SSE Token Stream"
      right={streaming && <span className="font-mono text-[10px]" style={{ color: "var(--c-purple)" }}>● live</span>}
      className="flex-1 min-h-0"
    >
      {/* Token display */}
      <div
        ref={streamRef}
        className={`px-3 py-2 font-mono text-[12px] leading-relaxed overflow-auto border-b ${streaming && activeAgent ? "cursor-blink" : ""}`}
        style={{
          height: 140,
          borderColor: "rgba(255,255,255,0.07)",
          color: "rgba(255,255,255,0.85)",
          wordBreak: "break-word",
        }}
      >
        {!displayTokens && !streaming && (
          <span style={{ color: "#4a5168" }}>Waiting for tokens...</span>
        )}
        {activeAgent && tokenBuffers[activeAgent] && (
          <>
            <Tag color={agentColor(activeAgent)}>[{activeAgent}]</Tag>{" "}
            <span style={{ color: "rgba(255,255,255,0.85)" }}>{tokenBuffers[activeAgent].slice(-3000)}</span>
          </>
        )}
        {!activeAgent && finalAnswer && (
          <>
            <Tag color="var(--c-teal)">[synthesis]</Tag>{" "}
            <span style={{ color: "rgba(255,255,255,0.85)" }}>{finalAnswer.slice(-3000)}</span>
          </>
        )}
      </div>
      {/* Event log */}
      <div ref={logRef} className="flex-1 overflow-auto px-3 py-2 min-h-0" style={{ minHeight: 80 }}>
        {activity.length === 0 && (
          <span className="font-mono text-[11px]" style={{ color: "#4a5168" }}>Submit a query to see events...</span>
        )}
        {activity.map((evt, i) => <EventLogLine key={i} evt={evt} />)}
      </div>
    </Panel>
  );
}

// ─── Panel 3: Tool Calls + Budget Bars ────────────────────────────────────────

function ToolCallsPanel() {
  const { activity, budgets } = useApp();
  const toolCalls = activity.filter(e => e.type === "tool_call");

  return (
    <Panel title="Tool Calls" className="flex-1 min-h-0">
      <div className="flex-1 overflow-auto min-h-0">
        {/* Tool calls table */}
        <table className="w-full text-[11px] font-mono">
          <thead>
            <tr style={{ borderBottom: "0.5px solid rgba(255,255,255,0.07)", color: "#4a5168" }}>
              <th className="text-left px-3 py-1.5 font-normal">tool</th>
              <th className="text-left px-2 py-1.5 font-normal">agent</th>
              <th className="text-left px-2 py-1.5 font-normal">hop</th>
              <th className="text-left px-2 py-1.5 font-normal">status</th>
              <th className="text-right px-3 py-1.5 font-normal">ms</th>
            </tr>
          </thead>
          <tbody>
            {toolCalls.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-2 text-center" style={{ color: "#4a5168" }}>
                  no tool calls yet
                </td>
              </tr>
            )}
            {toolCalls.map((tc, i) => {
              const ok = tc.status === "success";
              const retry = (tc.attempt || 0) > 0;
              return (
                <tr key={i} style={{ borderBottom: "0.5px solid rgba(255,255,255,0.04)" }}>
                  <td className="px-3 py-1 text-white">{tc.tool_name}</td>
                  <td className="px-2 py-1">
                    <span style={{ color: agentColor(tc.agent_id || "") }}>{tc.agent_id}</span>
                  </td>
                  <td className="px-2 py-1">
                    <span
                      className="px-1 rounded text-[10px]"
                      style={{ background: "rgba(96,165,250,0.12)", color: "var(--c-blue)" }}
                    >
                      hop{tc.attempt || 0}
                    </span>
                  </td>
                  <td className="px-2 py-1">
                    <span
                      className="px-1.5 py-0.5 rounded text-[10px]"
                      style={{
                        background: ok ? "rgba(45,212,191,0.12)" : retry ? "rgba(245,158,11,0.12)" : "rgba(239,68,68,0.12)",
                        color: ok ? "var(--c-teal)" : retry ? "var(--c-amber)" : "var(--c-red)",
                      }}
                    >
                      {ok ? "200" : retry ? "retry" : tc.status || "err"}
                    </span>
                  </td>
                  <td className="px-3 py-1 text-right text-white/40">—</td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {/* Context budget bars */}
        {Object.keys(budgets).length > 0 && (
          <div className="px-3 py-2 border-t" style={{ borderColor: "rgba(255,255,255,0.07)" }}>
            <div className="text-[10px] font-semibold tracking-widest uppercase mb-2" style={{ color: "#4a5168" }}>
              Context Budgets
            </div>
            {Object.entries(budgets).map(([agentId, b]) => {
              const pct = Math.min(100, (b.used / b.budget) * 100);
              const color = pct > 85 ? "var(--c-red)" : pct > 65 ? "var(--c-amber)" : agentColor(agentId);
              return (
                <div key={agentId} className="mb-2">
                  <div className="flex justify-between mb-0.5">
                    <span className="font-mono text-[11px]" style={{ color: agentColor(agentId) }}>{agentId}</span>
                    <span className="font-mono text-[11px]" style={{ color }}>
                      {b.used} / {b.budget}
                    </span>
                  </div>
                  <div className="h-1 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${pct}%`, background: color }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ─── Panel 4: Eval Scores ─────────────────────────────────────────────────────

const DIMENSIONS = [
  { key: "score_correctness",         label: "Correctness",             color: "var(--c-teal)" },
  { key: "score_citation",            label: "Citation accuracy",        color: "var(--c-blue)" },
  { key: "score_contradiction",       label: "Contradiction resolution", color: "var(--c-purple)" },
  { key: "score_tool_efficiency",     label: "Tool efficiency",          color: "var(--c-amber)" },
  { key: "score_budget_compliance",   label: "Budget compliance",        color: "var(--c-teal)" },
  { key: "score_critique_agreement",  label: "Critique agreement",       color: "var(--c-coral)" },
];

type EvalTab = "all" | "straightforward" | "ambiguous" | "adversarial";

interface EvalResult {
  case_id: string;
  case_category: string;
  score_overall: number;
  score_correctness: number;
  score_citation: number;
  score_contradiction: number;
  score_tool_efficiency: number;
  score_budget_compliance: number;
  score_critique_agreement: number;
  passed: boolean;
}

interface EvalData {
  summary?: {
    overall_avg?: number;
    passed?: number;
    total_cases?: number;
    by_dimension?: Record<string, number>;
  };
  results?: EvalResult[];
}

function EvalScoresPanel() {
  const [tab, setTab] = useState<EvalTab>("all");
  const { data } = useQuery<EvalData>({
    queryKey: ["eval-latest"],
    queryFn: () => fetch(`${BASE}/api/eval/latest`).then(r => r.ok ? r.json() : null),
    refetchInterval: 30000,
  });

  const results = data?.results || [];
  const filtered = tab === "all" ? results : results.filter(r => r.case_category === tab);

  const dimAvg = (key: string) => {
    const vals = filtered.map(r => (r as Record<string, number>)[key] || 0);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
  };

  const TABS: { key: EvalTab; label: string }[] = [
    { key: "all", label: "All" },
    { key: "straightforward", label: "Straight" },
    { key: "ambiguous", label: "Ambiguous" },
    { key: "adversarial", label: "Adversarial" },
  ];

  return (
    <Panel
      title="Eval Scores"
      right={
        <div className="flex gap-1">
          {TABS.map(t => (
            <button
              key={t.key}
              data-testid={`eval-tab-${t.key}`}
              onClick={() => setTab(t.key)}
              className="px-2 py-0.5 rounded text-[10px] font-medium transition-colors"
              style={{
                background: tab === t.key ? "rgba(124,106,247,0.2)" : "transparent",
                color: tab === t.key ? "var(--c-purple)" : "#4a5168",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
      }
    >
      <div className="flex-1 overflow-auto px-3 py-3">
        {!data && (
          <div className="text-[11px] font-mono" style={{ color: "#4a5168" }}>
            No eval data — run POST /api/eval/rerun
          </div>
        )}
        {data && (
          <>
            <div className="flex items-center gap-3 mb-3">
              <span className="font-mono text-[11px]" style={{ color: "#4a5168" }}>
                {filtered.filter(r => r.passed).length}/{filtered.length} passed
              </span>
              <span
                className="font-mono text-[13px] font-medium"
                style={{ color: "var(--c-teal)" }}
              >
                {filtered.length
                  ? ((filtered.reduce((s, r) => s + r.score_overall, 0) / filtered.length) * 100).toFixed(1)
                  : "—"}%
              </span>
            </div>
            <div className="space-y-2.5">
              {DIMENSIONS.map(d => {
                const val = dimAvg(d.key);
                return (
                  <div key={d.key}>
                    <div className="flex justify-between mb-1">
                      <span className="text-[11px]" style={{ color: "rgba(255,255,255,0.65)" }}>{d.label}</span>
                      <span className="font-mono text-[11px]" style={{ color: d.color }}>
                        {val.toFixed(2)}
                      </span>
                    </div>
                    <div className="h-1 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${val * 100}%`, background: d.color }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </Panel>
  );
}

// ─── Panel 5: Meta-Agent Rewrite ──────────────────────────────────────────────

interface PromptVersion {
  id: string;
  agent_id: string;
  dimension: string;
  status: string;
  justification: string | null;
  diff: string | null;
  original_prompt: string;
  proposed_prompt: string;
  delta_score: number | null;
}

function DiffLine({ line }: { line: string }) {
  if (line.startsWith("+") && !line.startsWith("+++")) {
    return <div className="font-mono text-[11px] leading-snug" style={{ color: "var(--c-teal)", background: "rgba(45,212,191,0.06)" }}>{line}</div>;
  }
  if (line.startsWith("-") && !line.startsWith("---")) {
    return <div className="font-mono text-[11px] leading-snug" style={{ color: "var(--c-red)", background: "rgba(239,68,68,0.06)" }}>{line}</div>;
  }
  if (line.startsWith("@@")) {
    return <div className="font-mono text-[11px] leading-snug" style={{ color: "var(--c-blue)" }}>{line}</div>;
  }
  return <div className="font-mono text-[11px] leading-snug" style={{ color: "rgba(255,255,255,0.3)" }}>{line || "\u00a0"}</div>;
}

function MetaAgentPanel() {
  const qc = useQueryClient();
  const { data } = useQuery<{ prompts: PromptVersion[] }>({
    queryKey: ["prompts-list"],
    queryFn: () => fetch(`${BASE}/api/prompts`).then(r => r.json()),
    refetchInterval: 30000,
  });

  const pending = data?.prompts?.filter(p => p.status === "pending")[0] || null;

  const reviewMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" }) =>
      fetch(`${BASE}/api/prompts/${id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      }).then(r => r.json()),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts-list"] }),
  });

  return (
    <Panel
      title="Meta-Agent Rewrite"
      right={
        pending && (
          <span
            className="font-mono text-[10px] px-1.5 rounded"
            style={{ background: "rgba(245,158,11,0.12)", color: "var(--c-amber)" }}
          >
            pending
          </span>
        )
      }
    >
      <div className="flex-1 overflow-auto px-3 py-3">
        {!pending && (
          <div className="text-[11px] font-mono" style={{ color: "#4a5168" }}>
            No pending rewrites — run eval to generate
          </div>
        )}
        {pending && (
          <div className="space-y-3">
            <div className="flex items-start gap-2 flex-wrap">
              <span className="font-mono text-[11px]" style={{ color: "#4a5168" }}>target</span>
              <span className="font-mono text-[11px]" style={{ color: agentColor(pending.agent_id) }}>
                [{pending.agent_id}]
              </span>
              <span className="font-mono text-[11px]" style={{ color: "var(--c-amber)" }}>
                {pending.dimension}
              </span>
            </div>
            {pending.justification && (
              <p className="text-[12px] leading-relaxed" style={{ color: "rgba(255,255,255,0.6)" }}>
                {pending.justification.slice(0, 200)}
              </p>
            )}
            {pending.diff && (
              <div
                className="rounded border overflow-auto"
                style={{ maxHeight: 120, background: "#0a0b0f", borderColor: "rgba(255,255,255,0.07)" }}
              >
                {pending.diff.split("\n").map((line, i) => <DiffLine key={i} line={line} />)}
              </div>
            )}
            <div className="flex gap-2 pt-1">
              <button
                data-testid="button-approve-meta"
                onClick={() => reviewMutation.mutate({ id: pending.id, action: "approve" })}
                disabled={reviewMutation.isPending}
                className="flex-1 text-[12px] font-medium py-1.5 rounded border transition-colors"
                style={{ background: "rgba(45,212,191,0.1)", borderColor: "var(--c-teal)", color: "var(--c-teal)" }}
              >
                Approve
              </button>
              <button
                data-testid="button-reject-meta"
                onClick={() => reviewMutation.mutate({ id: pending.id, action: "reject" })}
                disabled={reviewMutation.isPending}
                className="flex-1 text-[12px] font-medium py-1.5 rounded border transition-colors"
                style={{ background: "rgba(239,68,68,0.08)", borderColor: "rgba(239,68,68,0.4)", color: "var(--c-red)" }}
              >
                Reject
              </button>
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}

// ─── Provenance Map ───────────────────────────────────────────────────────────

interface ProvenanceEntry {
  sentence: string;
  source_agent: string;
  source_chunk: string | null;
  confidence: number;
}

function ProvenanceMap({ jobId }: { jobId: string | null }) {
  const { data } = useQuery({
    queryKey: ["job-trace", jobId],
    queryFn: () => fetch(`${BASE}/api/trace/${jobId}`).then(r => r.json()),
    enabled: !!jobId,
  });

  const provenance: ProvenanceEntry[] = data?.provenance_map || [];
  if (!jobId || provenance.length === 0) return null;

  return (
    <Panel title="Provenance Map">
      <div className="overflow-auto px-3 py-2">
        <table className="w-full text-[11px]">
          <thead>
            <tr style={{ borderBottom: "0.5px solid rgba(255,255,255,0.07)", color: "#4a5168" }}>
              <th className="text-left font-mono font-normal py-1.5 pr-3">sentence</th>
              <th className="text-left font-mono font-normal py-1.5 pr-3 shrink-0">source agent</th>
              <th className="text-left font-mono font-normal py-1.5 pr-3 shrink-0">chunk</th>
              <th className="text-right font-mono font-normal py-1.5 shrink-0">confidence</th>
            </tr>
          </thead>
          <tbody>
            {provenance.map((p, i) => (
              <tr key={i} style={{ borderBottom: "0.5px solid rgba(255,255,255,0.04)" }}>
                <td className="py-1.5 pr-3 text-white/70 max-w-xs truncate">{p.sentence}</td>
                <td className="py-1.5 pr-3">
                  <span
                    className="font-mono px-1.5 py-0.5 rounded text-[10px]"
                    style={{ background: `${agentColor(p.source_agent)}18`, color: agentColor(p.source_agent) }}
                  >
                    {p.source_agent}
                  </span>
                </td>
                <td className="py-1.5 pr-3">
                  {p.source_chunk && (
                    <span
                      className="font-mono px-1.5 py-0.5 rounded text-[10px]"
                      style={{ background: "rgba(45,212,191,0.1)", color: "var(--c-teal)" }}
                    >
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
    </Panel>
  );
}

// ─── Header (job info + stats + actions) ──────────────────────────────────────

function JobHeader() {
  const { jobId, query, streaming, startTime, totalToolCalls, violations, budgets, finalAnswer, resetJob, error, agents } = useApp();
  const [, setLocation] = useLocation();
  const [copied, setCopied] = useState(false);

  const elapsed = startTime ? ((Date.now() - startTime) / 1000).toFixed(1) + "s" : null;
  const budgetVals = Object.values(budgets);
  const avgBudgetPct = budgetVals.length
    ? Math.round(budgetVals.reduce((s, b) => s + (b.used / b.budget) * 100, 0) / budgetVals.length)
    : 0;
  const pipelineTotal = agents.length || 4;
  const ranCount = agents.filter(a => a.status === "done").length;
  const skippedCount = agents.filter(a => a.status === "skipped").length;
  const allStepsSettled =
    !streaming &&
    agents.length > 0 &&
    agents.every(a => a.status === "done" || a.status === "skipped" || a.status === "error");

  const copyJob = () => {
    if (jobId) {
      navigator.clipboard.writeText(jobId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  if (!jobId && !streaming) {
    return (
      <div
        className="px-6 py-5 border-b"
        style={{ borderColor: "rgba(255,255,255,0.07)", background: "#10121a" }}
      >
        <div className="text-[13px]" style={{ color: "#4a5168" }}>
          No active run — type a query in the search bar and press Enter.
        </div>
      </div>
    );
  }

  return (
    <div
      className="px-6 py-4 border-b"
      style={{ borderColor: "rgba(255,255,255,0.07)", background: "#10121a" }}
    >
      {/* Title + actions row */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h1 className="text-[18px] font-semibold text-white tracking-tight">
            {streaming ? "Live pipeline" : error ? "Pipeline failed" : "Pipeline complete"}{" "}
            {jobId && (
              <span className="font-mono text-[14px]" style={{ color: "#4a5168" }}>
                — {jobId.slice(0, 12)}
              </span>
            )}
          </h1>
          <p className="text-[12px] mt-0.5" style={{ color: "#4a5168" }}>
            {elapsed && `${elapsed} elapsed`}
            {query && ` · query: "${query.slice(0, 60)}"`}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {jobId && (
            <button
              data-testid="button-view-trace"
              onClick={() => setLocation(`/jobs/${jobId}`)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] rounded border transition-colors hover:bg-white/5"
              style={{ borderColor: "rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.7)" }}
            >
              <ExternalLink size={12} /> View trace
            </button>
          )}
          {jobId && (
            <button
              data-testid="button-copy-job"
              onClick={copyJob}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] rounded border transition-colors hover:bg-white/5"
              style={{ borderColor: "rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.7)" }}
            >
              <Copy size={12} /> {copied ? "Copied!" : "Copy job ID"}
            </button>
          )}
          <button
            data-testid="button-new-query"
            onClick={resetJob}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] rounded border font-medium transition-colors"
            style={{ borderColor: "rgba(124,106,247,0.4)", background: "rgba(124,106,247,0.1)", color: "var(--c-purple)" }}
          >
            <Plus size={12} /> New query
          </button>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-3 gap-3">
        {[
          {
            label: "AGENTS INVOKED",
            value: `${ranCount}/${pipelineTotal}`,
            valueColor: error ? "var(--c-red)" : "var(--c-teal)",
            sub: streaming ? (
              <span style={{ color: "var(--c-blue)" }}>running...</span>
            ) : error ? (
              <span style={{ color: "#4a5168" }}>see event log</span>
            ) : (
              <span style={{ color: "#4a5168" }}>
                {allStepsSettled && skippedCount > 0
                  ? `${skippedCount} skipped (routing) · ${ranCount} ran`
                  : "pipeline stages done"}
              </span>
            ),
          },
          {
            label: "ELAPSED",
            value: elapsed || "—",
            valueColor: "var(--c-amber)",
            sub: <span style={{ color: "#4a5168" }}>Tool calls: <span className="text-white font-mono">{totalToolCalls}</span></span>,
          },
          {
            label: "BUDGET USED",
            value: avgBudgetPct ? `${avgBudgetPct}%` : "—",
            valueColor: violations > 0 ? "var(--c-red)" : "rgba(255,255,255,0.85)",
            sub: <span style={{ color: violations > 0 ? "var(--c-red)" : "#4a5168" }}>Violations: {violations}</span>,
          },
        ].map(card => (
          <div
            key={card.label}
            className="rounded border px-4 py-3"
            style={{ background: "#161923", borderColor: "rgba(255,255,255,0.07)" }}
          >
            <div className="text-[10px] font-semibold tracking-widest uppercase mb-2" style={{ color: "#4a5168" }}>
              {card.label}
            </div>
            <div className="font-mono text-[24px] font-medium leading-none mb-1" style={{ color: card.valueColor }}>
              {card.value}
            </div>
            <div className="text-[11px]">{card.sub}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main LiveRunPage ─────────────────────────────────────────────────────────

export default function LiveRunPage() {
  const { agents, jobId } = useApp();

  return (
    <div className="flex flex-col h-full min-h-0" style={{ background: "#0a0b0f" }}>
      <JobHeader />

      <div className="flex-1 min-h-0 overflow-auto p-4 space-y-3">
        {/* Pipeline bar */}
        <PipelineBar agents={agents} />

        {/* Middle row: token stream + tool calls */}
        <div className="grid grid-cols-[1fr_340px] gap-3" style={{ minHeight: 260 }}>
          <TokenStreamPanel />
          <ToolCallsPanel />
        </div>

        {/* Bottom row: eval scores + meta-agent */}
        <div className="grid grid-cols-2 gap-3" style={{ minHeight: 220 }}>
          <EvalScoresPanel />
          <MetaAgentPanel />
        </div>

        {/* Provenance map (appears after done) */}
        <ProvenanceMap jobId={jobId} />
      </div>
    </div>
  );
}
