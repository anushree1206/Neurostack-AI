import { useLocation, Link } from "wouter";
import { useApp } from "@/context/AppContext";

interface NavItem {
  label: string;
  path: string;
  dot?: string;
  badge?: number | string;
}

interface Section {
  title: string;
  items: NavItem[];
}

const SECTIONS: Section[] = [
  {
    title: "PIPELINE",
    items: [
      { label: "Live run", path: "/", badge: 1 },
      { label: "Job history", path: "/jobs" },
      { label: "Execution traces", path: "/traces" },
    ],
  },
  {
    title: "EVALUATION",
    items: [
      { label: "Eval runs", path: "/eval", dot: "#2dd4bf", badge: 3 },
      { label: "Prompt rewrites", path: "/prompts", dot: "#f59e0b", badge: 2 },
      { label: "Test cases", path: "/test-cases" },
    ],
  },
  {
    title: "OBSERVABILITY",
    items: [
      { label: "Agent turns", path: "/agent-turns" },
      { label: "Tool calls", path: "/tool-calls" },
      { label: "Context budgets", path: "/budgets" },
    ],
  },
];

export default function Sidebar() {
  const [location] = useLocation();
  const { streaming } = useApp();

  const isActive = (path: string) => {
    if (path === "/") return location === "/";
    return location.startsWith(path);
  };

  return (
    <aside
      className="flex flex-col shrink-0 border-r"
      style={{
        width: 220,
        background: "#0a0b0f",
        borderColor: "rgba(255,255,255,0.07)",
      }}
    >
      {/* System status */}
      <div
        className="flex items-center gap-2 px-4 py-2 border-b"
        style={{ borderColor: "rgba(255,255,255,0.07)" }}
      >
        <span
          className={`w-1.5 h-1.5 rounded-full ${streaming ? "pulse-dot" : ""}`}
          style={{ background: streaming ? "#2dd4bf" : "#2dd4bf" }}
        />
        <span className="text-[11px]" style={{ color: "#4a5168" }}>
          {streaming ? "processing..." : "system ready"}
        </span>
      </div>

      <nav className="flex-1 py-3 overflow-auto">
        {SECTIONS.map(section => (
          <div key={section.title} className="mb-4">
            <div
              className="px-4 pb-1.5 text-[10px] font-semibold tracking-widest"
              style={{ color: "#4a5168" }}
            >
              {section.title}
            </div>
            {section.items.map(item => {
              const active = isActive(item.path);
              return (
                <Link key={item.path} href={item.path}>
                  <div
                    data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, "-")}`}
                    className="flex items-center gap-2.5 px-4 py-1.5 cursor-pointer relative transition-colors"
                    style={{
                      borderRight: active ? "2px solid var(--c-purple)" : "2px solid transparent",
                      background: active ? "rgba(124,106,247,0.08)" : "transparent",
                      color: active ? "#e2e0ff" : "#6b7280",
                    }}
                    onMouseEnter={e => { if (!active) (e.currentTarget as HTMLDivElement).style.color = "#9ca3af"; }}
                    onMouseLeave={e => { if (!active) (e.currentTarget as HTMLDivElement).style.color = "#6b7280"; }}
                  >
                    {item.dot && (
                      <span
                        className="w-1.5 h-1.5 rounded-full shrink-0"
                        style={{ background: item.dot }}
                      />
                    )}
                    <span className="text-[13px] font-medium flex-1">{item.label}</span>
                    {item.badge !== undefined && (
                      <span
                        className="text-[10px] font-mono px-1.5 rounded"
                        style={{
                          background: active ? "rgba(124,106,247,0.2)" : "rgba(255,255,255,0.05)",
                          color: active ? "var(--c-purple)" : "#4a5168",
                        }}
                      >
                        {item.badge}
                      </span>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
    </aside>
  );
}
