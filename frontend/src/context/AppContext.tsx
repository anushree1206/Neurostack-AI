import { createContext, useContext, useState, useCallback, useRef, ReactNode } from "react";

const SYNTHESIS_JSON_MARKER = "<<<STRUCT_JSON>>>";

/** Hide trailing structured JSON from live synthesis token stream (server also filters). */
function appendSynthesisVisible(prev: string, token: string): string {
  const combined = prev + token;
  const i = combined.indexOf(SYNTHESIS_JSON_MARKER);
  return i === -1 ? combined : combined.slice(0, i);
}

export interface SSEEvent {
  type: string;
  agent_id?: string;
  token?: string;
  budget_remaining?: number;
  section?: string;
  progress_percent?: number;
  tool_name?: string;
  attempt?: number;
  status?: string;
  from_agent?: string;
  to_agent?: string;
  justification?: string;
  used?: number;
  budget?: number;
  remaining?: number;
  message?: string;
  job_id?: string;
  answer?: string;
  summary?: string;
  data?: Record<string, unknown>;
}

export interface AgentState {
  id: string;
  status: "idle" | "running" | "done" | "error" | "skipped";
  startedAt?: number;
  doneAt?: number;
  latencyMs?: number;
  toolCalls?: number;
}

export interface AppState {
  query: string;
  setQuery: (q: string) => void;
  streaming: boolean;
  jobId: string | null;
  activity: SSEEvent[];
  agents: AgentState[];
  budgets: Record<string, { used: number; budget: number }>;
  tokenBuffers: Record<string, string>;
  finalAnswer: string | null;
  error: string | null;
  totalToolCalls: number;
  violations: number;
  startTime: number | null;
  submitQuery: (q: string) => void;
  resetJob: () => void;
}

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

const AppContext = createContext<AppState | null>(null);

const PIPELINE_AGENTS = ["decomposition", "rag", "critique", "synthesis"];

export function AppProvider({ children }: { children: ReactNode }) {
  const [query, setQuery] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [activity, setActivity] = useState<SSEEvent[]>([]);
  const [agents, setAgents] = useState<AgentState[]>([]);
  const [budgets, setBudgets] = useState<Record<string, { used: number; budget: number }>>({});
  const [tokenBuffers, setTokenBuffers] = useState<Record<string, string>>({});
  const [finalAnswer, setFinalAnswer] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [totalToolCalls, setTotalToolCalls] = useState(0);
  const [violations, setViolations] = useState(0);
  const [startTime, setStartTime] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const resetJob = useCallback(() => {
    setStreaming(false);
    setJobId(null);
    setActivity([]);
    setAgents([]);
    setBudgets({});
    setTokenBuffers({});
    setFinalAnswer(null);
    setError(null);
    setTotalToolCalls(0);
    setViolations(0);
    setStartTime(null);
  }, []);

  const submitQuery = useCallback(async (q: string) => {
    if (!q.trim() || streaming) return;
    if (abortRef.current) abortRef.current.abort();

    resetJob();
    setQuery(q);
    setStreaming(true);
    setStartTime(Date.now());
    setAgents(PIPELINE_AGENTS.map(id => ({ id, status: "idle" })));

    abortRef.current = new AbortController();

    try {
      const resp = await fetch(`${BASE}/api/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q.trim() }),
        signal: abortRef.current.signal,
      });

      if (!resp.ok) {
        const err = await resp.json();
        setError(err?.detail?.message || "Request failed");
        setStreaming(false);
        return;
      }

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let streamCompleted = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";

        for (const part of parts) {
          if (!part.trim()) continue;
          const lines = part.split("\n");
          let data = "";
          for (const line of lines) {
            if (line.startsWith("data: ")) data = line.slice(6).trim();
          }
          if (!data) continue;
          try {
            const evt = JSON.parse(data) as SSEEvent;

            if (evt.type === "job_created" && evt.job_id) {
              setJobId(evt.job_id);
            } else if (evt.type === "token" && evt.agent_id) {
              setTokenBuffers(prev => {
                const prior = prev[evt.agent_id!] || "";
                const addition = evt.token || "";
                const next =
                  evt.agent_id === "synthesis"
                    ? appendSynthesisVisible(prior, addition)
                    : prior + addition;
                return { ...prev, [evt.agent_id!]: next };
              });
            } else if (evt.type === "budget" && evt.agent_id) {
              setBudgets(prev => ({
                ...prev,
                [evt.agent_id!]: { used: evt.used || 0, budget: evt.budget || 8000 },
              }));
            } else if (evt.type === "agent_start" && evt.agent_id) {
              setAgents(prev => prev.map(a =>
                a.id === evt.agent_id ? { ...a, status: "running", startedAt: Date.now() } : a
              ));
              setActivity(prev => [...prev, evt]);
            } else if (evt.type === "agent_done" && evt.agent_id) {
              const now = Date.now();
              setAgents(prev => prev.map(a =>
                a.id === evt.agent_id
                  ? { ...a, status: "done", doneAt: now, latencyMs: a.startedAt ? now - a.startedAt : undefined }
                  : a
              ));
              setActivity(prev => [...prev, evt]);
            } else if (evt.type === "tool_call") {
              setTotalToolCalls(prev => prev + 1);
              setActivity(prev => [...prev, evt]);
            } else if (evt.type === "policy_violation") {
              setViolations(prev => prev + 1);
              setActivity(prev => [...prev, evt]);
            } else if (evt.type === "done") {
              streamCompleted = true;
              const ans = evt.answer || "";
              const cut = ans.indexOf(SYNTHESIS_JSON_MARKER);
              setFinalAnswer(cut === -1 ? ans : ans.slice(0, cut).trim());
              setError(null);
              setStreaming(false);
              // Dynamic routing may omit agents (e.g. rag→critique→synthesis). Never leave them stuck on "waiting".
              setAgents(prev =>
                prev.map(a => (a.status === "idle" ? { ...a, status: "skipped" as const } : a)),
              );
              setActivity(prev => [...prev, evt]);
            } else if (evt.type === "error") {
              if (streamCompleted) {
                setActivity(prev => [...prev, evt]);
                continue;
              }
              setError(evt.message || "Unknown error");
              setFinalAnswer(`Pipeline failed: ${evt.message || "Unknown error"}`);
              setActivity(prev => [...prev, evt]);
              setStreaming(false);
            } else {
              setActivity(prev => [...prev, evt]);
            }
          } catch { /* skip */ }
        }
      }
    } catch (e: unknown) {
      if ((e as Error)?.name !== "AbortError") {
        setError((e as Error)?.message || "Connection failed");
      }
    } finally {
      setStreaming(false);
    }
  }, [streaming, resetJob]);

  return (
    <AppContext.Provider value={{
      query, setQuery,
      streaming, jobId, activity, agents,
      budgets, tokenBuffers, finalAnswer, error,
      totalToolCalls, violations, startTime,
      submitQuery, resetJob,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
