import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Play, RefreshCw } from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

const DIMENSIONS = [
  { key: "score_correctness",        label: "Correctness",             color: "var(--c-teal)",   weight: "30%" },
  { key: "score_citation",           label: "Citation accuracy",        color: "var(--c-blue)",   weight: "20%" },
  { key: "score_contradiction",      label: "Contradiction resolution", color: "var(--c-purple)", weight: "20%" },
  { key: "score_tool_efficiency",    label: "Tool efficiency",          color: "var(--c-amber)",  weight: "10%" },
  { key: "score_budget_compliance",  label: "Budget compliance",        color: "var(--c-teal)",   weight: "10%" },
  { key: "score_critique_agreement", label: "Critique agreement",       color: "var(--c-coral)",  weight: "10%" },
];

const CAT_COLORS: Record<string, string> = {
  straightforward: "var(--c-teal)",
  ambiguous: "var(--c-amber)",
  adversarial: "var(--c-red)",
};

interface EvalResult {
  case_id: string;
  case_category: string;
  query: string;
  score_overall: number;
  score_correctness: number;
  score_citation: number;
  score_contradiction: number;
  score_tool_efficiency: number;
  score_budget_compliance: number;
  score_critique_agreement: number;
  passed: boolean;
  justifications: Record<string, string>;
}

interface EvalData {
  run_id: string;
  run_label: string;
  created_at: string | null;
  summary: {
    total_cases: number;
    passed: number;
    failed: number;
    overall_avg: number;
    by_dimension: Record<string, number>;
    by_category: Record<string, { count: number; passed: number; avg_overall: number }>;
  };
  results: EvalResult[];
}

function ScoreBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
        <div className="h-full rounded-full" style={{ width: `${value * 100}%`, background: color }} />
      </div>
      <span className="font-mono text-[11px] w-8 text-right" style={{ color }}>
        {value.toFixed(2)}
      </span>
    </div>
  );
}

export default function EvalPage() {
  const [selected, setSelected] = useState<EvalResult | null>(null);
  const [filter, setFilter] = useState<"all" | "passed" | "failed">("all");
  const qc = useQueryClient();

  const { data, isLoading, refetch } = useQuery<EvalData>({
    queryKey: ["eval-latest"],
    queryFn: () => fetch(`${BASE}/api/eval/latest`).then(r => {
      if (!r.ok) throw new Error("no data");
      return r.json();
    }),
  });

  const rerunMutation = useMutation({
    mutationFn: () =>
      fetch(`${BASE}/api/eval/rerun`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }).then(r => r.json()),
    onSuccess: () => setTimeout(() => qc.invalidateQueries({ queryKey: ["eval-latest"] }), 60000),
  });

  const results = (data?.results || []).filter(r =>
    filter === "all" ? true : filter === "passed" ? r.passed : !r.passed
  );

  return (
    <div className="flex flex-col h-full" style={{ background: "#0a0b0f" }}>
      {/* Header */}
      <div
        className="px-6 py-4 border-b flex items-center justify-between"
        style={{ borderColor: "rgba(255,255,255,0.07)", background: "#10121a" }}
      >
        <div>
          <div className="text-[11px] font-semibold tracking-widest uppercase mb-1" style={{ color: "#4a5168" }}>Evaluation</div>
          <div className="text-[16px] font-semibold text-white">
            {data ? `${data.run_label} — ${new Date(data.created_at || "").toLocaleString()}` : "No eval run yet"}
          </div>
        </div>
        <div className="flex gap-2">
          <button
            data-testid="button-refresh"
            onClick={() => refetch()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] rounded border transition-colors hover:bg-white/5"
            style={{ borderColor: "rgba(255,255,255,0.1)", color: "#6b7280" }}
          >
            <RefreshCw size={12} /> Refresh
          </button>
          <button
            data-testid="button-run-eval"
            onClick={() => rerunMutation.mutate()}
            disabled={rerunMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium rounded border"
            style={{ background: "rgba(124,106,247,0.1)", borderColor: "rgba(124,106,247,0.4)", color: "var(--c-purple)" }}
          >
            <Play size={12} /> {rerunMutation.isPending ? "Running..." : "Run eval"}
          </button>
        </div>
      </div>

      {rerunMutation.isSuccess && (
        <div
          className="mx-6 mt-3 px-4 py-2 rounded border font-mono text-[12px]"
          style={{ background: "rgba(124,106,247,0.08)", borderColor: "rgba(124,106,247,0.3)", color: "var(--c-purple)" }}
        >
          Eval started — ~2 min for 15 cases. Click Refresh when done.
        </div>
      )}

      {isLoading && (
        <div className="flex-1 flex items-center justify-center font-mono text-[12px]" style={{ color: "#4a5168" }}>
          loading...
        </div>
      )}

      {!isLoading && !data && (
        <div className="m-6 p-4 rounded border" style={{ background: "#10121a", borderColor: "rgba(255,255,255,0.07)" }}>
          <div className="font-mono text-[12px] mb-3" style={{ color: "#4a5168" }}>No evaluation data yet.</div>
          <button
            data-testid="button-first-eval"
            onClick={() => rerunMutation.mutate()}
            disabled={rerunMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 text-[12px] font-medium rounded border"
            style={{ background: "rgba(124,106,247,0.1)", borderColor: "rgba(124,106,247,0.4)", color: "var(--c-purple)" }}
          >
            <Play size={12} /> {rerunMutation.isPending ? "Starting..." : "Run first eval"}
          </button>
        </div>
      )}

      {data && (
        <div className="flex flex-1 min-h-0">
          {/* Left column: summary + list */}
          <div className="flex-1 min-w-0 flex flex-col">
            {/* Summary */}
            <div className="px-6 py-4 border-b" style={{ borderColor: "rgba(255,255,255,0.07)", background: "#10121a" }}>
              <div className="grid grid-cols-4 gap-3 mb-4">
                {[
                  { label: "OVERALL AVG", value: `${((data.summary?.overall_avg || 0) * 100).toFixed(1)}%`, color: "var(--c-teal)" },
                  { label: "PASSED", value: String(data.summary?.passed || 0), color: "var(--c-teal)" },
                  { label: "FAILED", value: String(data.summary?.failed || 0), color: "var(--c-red)" },
                  { label: "TOTAL", value: String(data.summary?.total_cases || 0), color: "rgba(255,255,255,0.8)" },
                ].map(s => (
                  <div key={s.label} className="rounded border px-3 py-2" style={{ background: "#161923", borderColor: "rgba(255,255,255,0.07)" }}>
                    <div className="text-[10px] font-semibold tracking-widest uppercase mb-1" style={{ color: "#4a5168" }}>{s.label}</div>
                    <div className="font-mono text-[22px] font-medium" style={{ color: s.color }}>{s.value}</div>
                  </div>
                ))}
              </div>
              <div className="space-y-2">
                {DIMENSIONS.map(d => {
                  const val = (data.summary?.by_dimension || {})[d.key] || 0;
                  return (
                    <div key={d.key} className="flex items-center gap-4">
                      <span className="text-[11px] w-44 shrink-0" style={{ color: "rgba(255,255,255,0.6)" }}>
                        {d.label} <span style={{ color: "#4a5168" }}>{d.weight}</span>
                      </span>
                      <div className="flex-1">
                        <ScoreBar value={val} color={d.color} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Filter + list */}
            <div className="px-6 py-2 border-b flex items-center gap-2" style={{ borderColor: "rgba(255,255,255,0.07)", background: "#0a0b0f" }}>
              {(["all", "passed", "failed"] as const).map(f => (
                <button
                  key={f}
                  data-testid={`filter-${f}`}
                  onClick={() => setFilter(f)}
                  className="px-2 py-0.5 rounded text-[11px] font-mono transition-colors"
                  style={{
                    background: filter === f ? "rgba(124,106,247,0.15)" : "transparent",
                    color: filter === f ? "var(--c-purple)" : "#4a5168",
                  }}
                >
                  {f}
                </button>
              ))}
            </div>

            <div className="flex-1 overflow-auto">
              {results.map((r, i) => (
                <button
                  key={r.case_id}
                  data-testid={`case-${r.case_id}`}
                  onClick={() => setSelected(selected?.case_id === r.case_id ? null : r)}
                  className="w-full text-left px-6 py-2.5 transition-colors"
                  style={{
                    borderBottom: "0.5px solid rgba(255,255,255,0.04)",
                    background: selected?.case_id === r.case_id ? "#161923" : i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.01)",
                  }}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className="font-mono text-[11px] font-medium w-6"
                      style={{ color: CAT_COLORS[r.case_category] }}
                    >
                      {r.case_id}
                    </span>
                    <span
                      className="font-mono text-[10px] px-1.5 py-0.5 rounded shrink-0"
                      style={{ background: `${CAT_COLORS[r.case_category]}15`, color: CAT_COLORS[r.case_category] }}
                    >
                      {r.case_category}
                    </span>
                    <span className="text-[12px] flex-1 truncate" style={{ color: "rgba(255,255,255,0.65)" }}>
                      {r.query}
                    </span>
                    <span className="font-mono text-[12px] shrink-0" style={{ color: r.passed ? "var(--c-teal)" : "var(--c-red)" }}>
                      {((r.score_overall || 0) * 100).toFixed(0)}%
                    </span>
                    <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: r.passed ? "var(--c-teal)" : "var(--c-red)" }} />
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Right: case detail */}
          {selected && (
            <div
              className="w-72 border-l flex flex-col overflow-hidden shrink-0"
              style={{ borderColor: "rgba(255,255,255,0.07)", background: "#10121a" }}
            >
              <div className="px-4 py-3 border-b" style={{ borderColor: "rgba(255,255,255,0.07)" }}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-[13px] font-medium" style={{ color: CAT_COLORS[selected.case_category] }}>
                    {selected.case_id}
                  </span>
                  <span className="font-mono text-[10px] px-1.5 rounded" style={{ background: `${CAT_COLORS[selected.case_category]}15`, color: CAT_COLORS[selected.case_category] }}>
                    {selected.case_category}
                  </span>
                </div>
                <p className="text-[12px] leading-snug" style={{ color: "rgba(255,255,255,0.7)" }}>{selected.query}</p>
              </div>
              <div className="flex-1 overflow-auto px-4 py-3 space-y-3">
                {DIMENSIONS.map(d => {
                  const val = (selected as Record<string, number>)[d.key] || 0;
                  const just = selected.justifications?.[d.key.replace("score_", "")] || "";
                  return (
                    <div key={d.key}>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[11px]" style={{ color: "rgba(255,255,255,0.65)" }}>{d.label}</span>
                        <span className="font-mono text-[11px] ml-auto" style={{ color: d.color }}>{val.toFixed(2)}</span>
                      </div>
                      <div className="h-0.5 rounded-full mb-1" style={{ background: "rgba(255,255,255,0.06)" }}>
                        <div className="h-full rounded-full" style={{ width: `${val * 100}%`, background: d.color }} />
                      </div>
                      {just && <p className="text-[10px] leading-snug" style={{ color: "#4a5168" }}>{just}</p>}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
