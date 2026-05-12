import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

const AGENT_COLORS: Record<string, string> = {
  orchestrator: "var(--c-purple)",
  synthesis:    "var(--c-purple)",
  rag:          "var(--c-teal)",
  decomposition:"var(--c-blue)",
  critique:     "var(--c-coral)",
  meta:         "var(--c-purple)",
};
const agentColor = (id: string) => AGENT_COLORS[id] || "#6b7280";

const STATUS_COLORS: Record<string, string> = {
  pending:  "var(--c-amber)",
  approved: "var(--c-teal)",
  rejected: "#4a5168",
};

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
  created_at: string | null;
  reviewed_at: string | null;
}

function DiffPreview({ diff }: { diff: string }) {
  return (
    <div
      className="rounded border overflow-auto font-mono"
      style={{ maxHeight: 180, background: "#0a0b0f", borderColor: "rgba(255,255,255,0.07)" }}
    >
      {diff.split("\n").map((line, i) => {
        let color = "rgba(255,255,255,0.28)";
        let bg = "transparent";
        if (line.startsWith("+") && !line.startsWith("+++")) { color = "var(--c-teal)"; bg = "rgba(45,212,191,0.06)"; }
        else if (line.startsWith("-") && !line.startsWith("---")) { color = "var(--c-red)"; bg = "rgba(239,68,68,0.06)"; }
        else if (line.startsWith("@@")) { color = "var(--c-blue)"; }
        return (
          <div key={i} className="text-[11px] leading-snug px-2 py-px" style={{ color, background: bg }}>
            {line || "\u00a0"}
          </div>
        );
      })}
    </div>
  );
}

export default function PromptsPage() {
  const [selected, setSelected] = useState<PromptVersion | null>(null);
  const [filter, setFilter] = useState<"all" | "pending" | "approved" | "rejected">("all");
  const qc = useQueryClient();

  const { data, isLoading, refetch } = useQuery<{ prompts: PromptVersion[] }>({
    queryKey: ["prompts"],
    queryFn: () => fetch(`${BASE}/api/prompts`).then(r => r.json()),
  });

  const reviewMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" }) =>
      fetch(`${BASE}/api/prompts/${id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      }).then(r => r.json()),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["prompts"] }); setSelected(null); },
  });

  const prompts = (data?.prompts || []).filter(p => filter === "all" ? true : p.status === filter);
  const pendingCount = (data?.prompts || []).filter(p => p.status === "pending").length;

  return (
    <div className="flex flex-col h-full" style={{ background: "#0a0b0f" }}>
      <div
        className="px-6 py-4 border-b flex items-center justify-between"
        style={{ borderColor: "rgba(255,255,255,0.07)", background: "#10121a" }}
      >
        <div>
          <div className="text-[11px] font-semibold tracking-widest uppercase mb-1" style={{ color: "#4a5168" }}>Prompt Rewrites</div>
          <div className="text-[16px] font-semibold text-white">
            {pendingCount > 0
              ? <span style={{ color: "var(--c-amber)" }}>{pendingCount} pending review</span>
              : "No pending rewrites"}
          </div>
        </div>
        <button
          data-testid="button-refresh"
          onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] rounded border hover:bg-white/5"
          style={{ borderColor: "rgba(255,255,255,0.1)", color: "#6b7280" }}
        >
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      <div className="px-6 py-2 border-b flex items-center gap-2" style={{ borderColor: "rgba(255,255,255,0.07)" }}>
        {(["all", "pending", "approved", "rejected"] as const).map(s => (
          <button
            key={s}
            data-testid={`filter-${s}`}
            onClick={() => setFilter(s)}
            className="px-2 py-0.5 rounded text-[11px] font-mono transition-colors"
            style={{
              background: filter === s ? "rgba(124,106,247,0.15)" : "transparent",
              color: filter === s ? "var(--c-purple)" : "#4a5168",
            }}
          >
            {s}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="flex-1 flex items-center justify-center font-mono text-[12px]" style={{ color: "#4a5168" }}>
          loading...
        </div>
      )}

      {!isLoading && prompts.length === 0 && (
        <div className="m-6 p-4 rounded border font-mono text-[12px]" style={{ background: "#10121a", borderColor: "rgba(255,255,255,0.07)", color: "#4a5168" }}>
          No rewrites yet. Run eval to generate meta-agent proposals.
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        {/* List */}
        <div className="flex-1 overflow-auto">
          {prompts.map((p, i) => (
            <button
              key={p.id}
              data-testid={`prompt-${p.id}`}
              onClick={() => setSelected(selected?.id === p.id ? null : p)}
              className="w-full text-left px-6 py-3 transition-colors"
              style={{
                borderBottom: "0.5px solid rgba(255,255,255,0.04)",
                background: selected?.id === p.id ? "#161923" : i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.01)",
              }}
            >
              <div className="flex items-center gap-3 mb-1">
                <span className="font-mono text-[12px] font-medium" style={{ color: agentColor(p.agent_id) }}>
                  [{p.agent_id}]
                </span>
                <span className="text-[11px]" style={{ color: "#6b7280" }}>{p.dimension}</span>
                <span
                  className="font-mono text-[10px] px-1.5 py-0.5 rounded ml-auto"
                  style={{ background: `${STATUS_COLORS[p.status] || "#4a5168"}18`, color: STATUS_COLORS[p.status] || "#4a5168" }}
                >
                  {p.status}
                </span>
                {p.delta_score !== null && (
                  <span className="font-mono text-[11px]" style={{ color: p.delta_score >= 0 ? "var(--c-teal)" : "var(--c-red)" }}>
                    {p.delta_score >= 0 ? "+" : ""}{(p.delta_score * 100).toFixed(1)}%
                  </span>
                )}
              </div>
              <p className="text-[11px] truncate" style={{ color: "rgba(255,255,255,0.4)" }}>
                {p.justification?.slice(0, 100)}
              </p>
              {p.created_at && (
                <div className="font-mono text-[10px] mt-0.5" style={{ color: "#4a5168" }}>
                  {new Date(p.created_at).toLocaleString()}
                </div>
              )}
            </button>
          ))}
        </div>

        {/* Detail panel */}
        {selected && (
          <div
            className="w-96 border-l flex flex-col overflow-hidden shrink-0"
            style={{ borderColor: "rgba(255,255,255,0.07)", background: "#10121a" }}
          >
            <div className="px-4 py-3 border-b" style={{ borderColor: "rgba(255,255,255,0.07)" }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="font-mono text-[13px] font-medium" style={{ color: agentColor(selected.agent_id) }}>
                  [{selected.agent_id}]
                </span>
                <span className="text-[12px]" style={{ color: "#6b7280" }}>{selected.dimension}</span>
                <span
                  className="font-mono text-[10px] px-1.5 py-0.5 rounded ml-auto"
                  style={{ background: `${STATUS_COLORS[selected.status]}18`, color: STATUS_COLORS[selected.status] || "#4a5168" }}
                >
                  {selected.status}
                </span>
              </div>
              <p className="text-[12px] leading-relaxed" style={{ color: "rgba(255,255,255,0.6)" }}>
                {selected.justification}
              </p>
            </div>

            <div className="flex-1 overflow-auto px-4 py-3 space-y-3">
              {selected.diff && (
                <div>
                  <div className="text-[10px] font-semibold tracking-widest uppercase mb-1.5" style={{ color: "#4a5168" }}>Diff</div>
                  <DiffPreview diff={selected.diff} />
                </div>
              )}
              <div>
                <div className="text-[10px] font-semibold tracking-widest uppercase mb-1.5" style={{ color: "#4a5168" }}>Original</div>
                <div
                  className="font-mono text-[11px] p-2 rounded border overflow-auto max-h-28 leading-snug whitespace-pre-wrap"
                  style={{ background: "#0a0b0f", borderColor: "rgba(255,255,255,0.07)", color: "rgba(255,255,255,0.4)" }}
                >
                  {selected.original_prompt}
                </div>
              </div>
              <div>
                <div className="text-[10px] font-semibold tracking-widest uppercase mb-1.5" style={{ color: "#4a5168" }}>Proposed</div>
                <div
                  className="font-mono text-[11px] p-2 rounded border overflow-auto max-h-28 leading-snug whitespace-pre-wrap"
                  style={{ background: "rgba(124,106,247,0.04)", borderColor: "rgba(124,106,247,0.2)", color: "rgba(255,255,255,0.75)" }}
                >
                  {selected.proposed_prompt}
                </div>
              </div>
            </div>

            {selected.status === "pending" && (
              <div className="px-4 py-3 border-t flex gap-2" style={{ borderColor: "rgba(255,255,255,0.07)" }}>
                <button
                  data-testid="button-approve"
                  onClick={() => reviewMutation.mutate({ id: selected.id, action: "approve" })}
                  disabled={reviewMutation.isPending}
                  className="flex-1 py-2 text-[12px] font-medium rounded border transition-colors"
                  style={{ background: "rgba(45,212,191,0.1)", borderColor: "var(--c-teal)", color: "var(--c-teal)" }}
                >
                  Approve
                </button>
                <button
                  data-testid="button-reject"
                  onClick={() => reviewMutation.mutate({ id: selected.id, action: "reject" })}
                  disabled={reviewMutation.isPending}
                  className="flex-1 py-2 text-[12px] font-medium rounded border transition-colors"
                  style={{ background: "rgba(239,68,68,0.08)", borderColor: "rgba(239,68,68,0.4)", color: "var(--c-red)" }}
                >
                  Reject
                </button>
              </div>
            )}

            {selected.status !== "pending" && (
              <div className="px-4 py-3 border-t" style={{ borderColor: "rgba(255,255,255,0.07)" }}>
                <div className="font-mono text-[11px]" style={{ color: "#4a5168" }}>
                  {selected.status} {selected.reviewed_at ? `· ${new Date(selected.reviewed_at).toLocaleString()}` : ""}
                  {selected.delta_score !== null && (
                    <span style={{ color: selected.delta_score >= 0 ? "var(--c-teal)" : "var(--c-red)", marginLeft: 8 }}>
                      delta: {selected.delta_score >= 0 ? "+" : ""}{(selected.delta_score * 100).toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
