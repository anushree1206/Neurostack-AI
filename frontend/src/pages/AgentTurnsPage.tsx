import { useQuery } from "@tanstack/react-query";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

interface AgentEvent {
  job_id: string;
  agent_id: string;
  event_type: string;
  timestamp: string | null;
}

export default function AgentTurnsPage() {
  const { data } = useQuery<{ events: AgentEvent[] }>({
    queryKey: ["agent-turns"],
    queryFn: () => fetch(`${BASE}/api/agent-turns`).then(r => r.json()),
    refetchInterval: 5000,
  });

  return (
    <div className="h-full flex flex-col" style={{ background: "#0a0b0f" }}>
      <div className="px-6 py-4 border-b" style={{ borderColor: "rgba(255,255,255,0.07)", background: "#10121a" }}>
        <div className="text-[16px] font-semibold text-white">Agent turns</div>
      </div>
      <div className="flex-1 overflow-auto px-6 py-4">
        {(data?.events || []).map((e, i) => (
          <div key={i} className="font-mono text-[12px] py-1 border-b" style={{ borderColor: "rgba(255,255,255,0.05)", color: "rgba(255,255,255,0.75)" }}>
            [{e.agent_id}] {e.event_type} · {e.job_id.slice(0, 8)}
          </div>
        ))}
      </div>
    </div>
  );
}
