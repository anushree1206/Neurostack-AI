import { useQuery } from "@tanstack/react-query";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

interface ToolCall {
  job_id: string;
  agent_id: string;
  tool_name: string;
  attempt: number;
  latency_ms: number | null;
  accepted: boolean | null;
  failure_mode: string | null;
  timestamp: string | null;
}

export default function ToolCallsPage() {
  const { data } = useQuery<{ tool_calls: ToolCall[] }>({
    queryKey: ["tool-calls"],
    queryFn: () => fetch(`${BASE}/api/tool-calls`).then(r => r.json()),
    refetchInterval: 5000,
  });

  return (
    <div className="h-full flex flex-col" style={{ background: "#0a0b0f" }}>
      <div className="px-6 py-4 border-b" style={{ borderColor: "rgba(255,255,255,0.07)", background: "#10121a" }}>
        <div className="text-[16px] font-semibold text-white">Tool calls</div>
      </div>
      <div className="flex-1 overflow-auto px-6 py-4">
        {(data?.tool_calls || []).map((c, i) => (
          <div key={i} className="font-mono text-[12px] py-1 border-b" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
            <span style={{ color: "var(--c-blue)" }}>{c.tool_name}</span>{" "}
            <span style={{ color: "#6b7280" }}>[{c.agent_id}]</span>{" "}
            <span style={{ color: c.accepted ? "var(--c-teal)" : "var(--c-red)" }}>
              {c.accepted ? "accepted" : "rejected"}
            </span>
            {c.failure_mode ? <span style={{ color: "var(--c-red)" }}> · {c.failure_mode}</span> : null}
          </div>
        ))}
      </div>
    </div>
  );
}
