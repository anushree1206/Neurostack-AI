import { useState, useRef } from "react";
import { useApp } from "@/context/AppContext";
import { MoreHorizontal } from "lucide-react";

export default function TopBar() {
  const { query, setQuery, streaming, submitQuery, jobId, error } = useApp();
  const [draft, setDraft] = useState(query);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = () => {
    if (!draft.trim() || streaming) return;
    submitQuery(draft.trim());
  };

  return (
    <header
      className="flex items-center gap-3 px-4 shrink-0 border-b"
      style={{ height: 48, background: "#0a0b0f", borderColor: "rgba(255,255,255,0.07)" }}
    >
      {/* Branding */}
      <div className="flex items-center gap-2 shrink-0 w-[220px]">
        <span
          className="w-5 h-5 rounded-full shrink-0"
          style={{ background: "var(--c-purple)" }}
        />
        <span className="font-semibold text-sm text-white tracking-tight">Neurostack AI</span>
      </div>

      {/* Query input */}
      <div
        className="flex-1 flex items-center gap-2 rounded border px-3"
        style={{
          height: 32,
          background: "#161923",
          borderColor: "rgba(255,255,255,0.08)",
        }}
      >
        <input
          ref={inputRef}
          data-testid="input-query-topbar"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") handleSubmit(); }}
          placeholder="Ask anything..."
          className="flex-1 bg-transparent outline-none text-sm text-white placeholder:text-[#4a5168] font-sans"
        />
        <div className="flex items-center gap-1 shrink-0">
          <kbd className="text-[10px] font-mono px-1 rounded border text-[#4a5168]" style={{ borderColor: "rgba(255,255,255,0.1)", background: "#0a0b0f" }}>⌘</kbd>
          <kbd className="text-[10px] font-mono px-1 rounded border text-[#4a5168]" style={{ borderColor: "rgba(255,255,255,0.1)", background: "#0a0b0f" }}>K</kbd>
        </div>
      </div>

      {/* Pipeline status */}
      <button
        data-testid="button-send-topbar"
        onClick={handleSubmit}
        disabled={!draft.trim() || streaming}
        className="flex items-center gap-2 px-3 text-xs font-medium rounded border shrink-0 transition-opacity disabled:opacity-40"
        style={{
          height: 32,
          background: error && !streaming ? "rgba(239,68,68,0.12)" : "rgba(45,212,191,0.12)",
          borderColor: error && !streaming ? "rgba(239,68,68,0.5)" : "#2dd4bf",
          color: error && !streaming ? "#ef4444" : "#2dd4bf",
        }}
      >
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${streaming ? "pulse-dot" : ""}`}
          style={{ background: streaming ? "#2dd4bf" : error && jobId ? "#ef4444" : "#2dd4bf" }}
        />
        {streaming ? "Pipeline active" : jobId ? (error ? "Run failed" : "Run complete") : "Send"}
      </button>

      <button
        data-testid="button-more"
        className="w-8 h-8 flex items-center justify-center rounded border transition-colors hover:bg-white/5"
        style={{ borderColor: "rgba(255,255,255,0.08)", color: "#4a5168" }}
      >
        <MoreHorizontal size={16} />
      </button>
    </header>
  );
}
