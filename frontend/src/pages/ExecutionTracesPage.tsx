import { useQuery } from "@tanstack/react-query";
import { useLocation } from "wouter";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

interface TraceSummary {
  job_id: string;
  query: string;
  status: string;
  event_count: number;
  tool_call_count: number;
  created_at: string | null;
}

export default function ExecutionTracesPage() {
  const [, setLocation] = useLocation();
  const { data, isLoading, isError, error } = useQuery<{ traces: TraceSummary[] }>({
    queryKey: ["execution-traces"],
    queryFn: async () => {
      const r = await fetch(`${BASE}/api/traces`);
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error((body as { detail?: { message?: string } })?.detail?.message || `HTTP ${r.status}`);
      }
      return r.json();
    },
    refetchInterval: 5000,
  });

  return (
    <div className="h-full flex flex-col" style={{ background: "#0a0b0f" }}>
      <div className="px-6 py-4 border-b" style={{ borderColor: "rgba(255,255,255,0.07)", background: "#10121a" }}>
        <div className="text-[16px] font-semibold text-white">Execution traces</div>
      </div>
      <div className="flex-1 overflow-auto px-6 py-4">
        {isLoading && <div className="font-mono text-[12px]" style={{ color: "#4a5168" }}>loading traces...</div>}
        {isError && (
          <div className="font-mono text-[12px]" style={{ color: "var(--c-red)" }}>
            Could not load traces: {(error as Error)?.message || "unknown error"}
          </div>
        )}
        {!isLoading && !isError && (data?.traces || []).length === 0 && (
          <div className="font-mono text-[12px]" style={{ color: "#4a5168" }}>no traces yet</div>
        )}
        {!isError && (data?.traces || []).map((t) => (
          <div key={t.job_id} className="rounded border p-3 mb-2" style={{ borderColor: "rgba(255,255,255,0.08)", background: "#10121a" }}>
            <div className="flex items-center gap-3">
              <span className="font-mono text-[11px]" style={{ color: "#4a5168" }}>{t.job_id.slice(0, 12)}</span>
              <span className="font-mono text-[11px]" style={{ color: "var(--c-blue)" }}>events {t.event_count}</span>
              <span className="font-mono text-[11px]" style={{ color: "var(--c-amber)" }}>tools {t.tool_call_count}</span>
              <button
                onClick={() => setLocation(`/jobs/${t.job_id}`)}
                className="ml-auto text-[11px] font-mono"
                style={{ color: "var(--c-purple)" }}
              >
                view trace
              </button>
            </div>
            <div className="text-[13px] text-white mt-1 truncate">{t.query}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
