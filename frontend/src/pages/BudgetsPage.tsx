import { useQuery } from "@tanstack/react-query";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

interface BudgetRow {
  agent_id: string;
  job_id: string;
  used: number;
  budget: number;
  remaining: number;
  timestamp: string | null;
}

interface ViolationRow {
  job_id: string;
  agent_id: string;
  message: string | null;
  timestamp: string | null;
}

export default function BudgetsPage() {
  const { data } = useQuery<{ latest_by_agent: BudgetRow[]; violations: ViolationRow[] }>({
    queryKey: ["budgets"],
    queryFn: () => fetch(`${BASE}/api/budgets`).then(r => r.json()),
    refetchInterval: 5000,
  });

  return (
    <div className="h-full flex flex-col" style={{ background: "#0a0b0f" }}>
      <div className="px-6 py-4 border-b" style={{ borderColor: "rgba(255,255,255,0.07)", background: "#10121a" }}>
        <div className="text-[16px] font-semibold text-white">Context budgets</div>
      </div>

      <div className="grid grid-cols-2 gap-4 p-6">
        <div className="rounded border p-4" style={{ borderColor: "rgba(255,255,255,0.08)", background: "#10121a" }}>
          <div className="text-[11px] font-semibold tracking-widest uppercase mb-3" style={{ color: "#4a5168" }}>Latest usage by agent</div>
          {(data?.latest_by_agent || []).map((b) => {
            const pct = b.budget ? Math.round((b.used / b.budget) * 100) : 0;
            return (
              <div key={`${b.agent_id}-${b.job_id}`} className="mb-3">
                <div className="flex justify-between text-[12px]">
                  <span style={{ color: "#fff" }}>{b.agent_id}</span>
                  <span style={{ color: pct > 85 ? "var(--c-red)" : "var(--c-amber)" }}>{b.used}/{b.budget}</span>
                </div>
                <div className="h-1 mt-1 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.08)" }}>
                  <div className="h-full" style={{ width: `${Math.min(100, pct)}%`, background: pct > 85 ? "var(--c-red)" : "var(--c-teal)" }} />
                </div>
              </div>
            );
          })}
        </div>

        <div className="rounded border p-4" style={{ borderColor: "rgba(255,255,255,0.08)", background: "#10121a" }}>
          <div className="text-[11px] font-semibold tracking-widest uppercase mb-3" style={{ color: "#4a5168" }}>Policy violations</div>
          {(data?.violations || []).length === 0 && (
            <div className="font-mono text-[12px]" style={{ color: "#4a5168" }}>no violations</div>
          )}
          {(data?.violations || []).map((v, i) => (
            <div key={`${v.job_id}-${i}`} className="text-[12px] mb-2" style={{ color: "var(--c-red)" }}>
              [{v.agent_id}] {v.message || "budget policy violation"}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
