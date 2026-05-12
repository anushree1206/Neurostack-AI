import { useQuery } from "@tanstack/react-query";
import { useLocation } from "wouter";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

interface JobRow {
  job_id: string;
  query: string;
  status: string;
  created_at: string | null;
  completed_at: string | null;
}

export default function JobHistoryPage() {
  const [, setLocation] = useLocation();
  const { data, isLoading, isError, error } = useQuery<{ jobs: JobRow[] }>({
    queryKey: ["jobs-history"],
    queryFn: async () => {
      const r = await fetch(`${BASE}/api/jobs`);
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
        <div className="text-[11px] font-semibold tracking-widest uppercase mb-1" style={{ color: "#4a5168" }}>
          Pipeline
        </div>
        <div className="text-[16px] font-semibold text-white">Job history</div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-4">
        {isLoading && <div className="font-mono text-[12px]" style={{ color: "#4a5168" }}>loading jobs...</div>}
        {isError && (
          <div className="font-mono text-[12px]" style={{ color: "var(--c-red)" }}>
            Could not load job history: {(error as Error)?.message || "unknown error"}
          </div>
        )}
        {!isLoading && !isError && (data?.jobs || []).length === 0 && (
          <div className="font-mono text-[12px]" style={{ color: "#4a5168" }}>no jobs yet</div>
        )}
        {!isError && (data?.jobs || []).map((j) => (
          <button
            key={j.job_id}
            onClick={() => setLocation(`/jobs/${j.job_id}`)}
            className="w-full text-left rounded border px-4 py-3 mb-2 transition-colors hover:bg-white/5"
            style={{ borderColor: "rgba(255,255,255,0.08)", background: "#10121a" }}
          >
            <div className="flex items-center gap-3">
              <span className="font-mono text-[11px]" style={{ color: "#4a5168" }}>{j.job_id.slice(0, 12)}</span>
              <span className="font-mono text-[11px]" style={{ color: j.status === "done" ? "var(--c-teal)" : j.status === "failed" ? "var(--c-red)" : "var(--c-purple)" }}>
                {j.status}
              </span>
            </div>
            <div className="text-[13px] text-white mt-1 truncate">{j.query}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
