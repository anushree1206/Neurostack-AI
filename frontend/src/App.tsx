import { useEffect } from "react";
import { Switch, Route, Router as WouterRouter } from "wouter";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppProvider } from "@/context/AppContext";
import NotFound from "@/pages/not-found";
import LiveRunPage from "@/pages/LiveRunPage";
import JobTracePage from "@/pages/JobTracePage";
import JobHistoryPage from "@/pages/JobHistoryPage";
import ExecutionTracesPage from "@/pages/ExecutionTracesPage";
import EvalPage from "@/pages/EvalPage";
import PromptsPage from "@/pages/PromptsPage";
import TestCasesPage from "@/pages/TestCasesPage";
import BudgetsPage from "@/pages/BudgetsPage";
import AgentTurnsPage from "@/pages/AgentTurnsPage";
import ToolCallsPage from "@/pages/ToolCallsPage";
import TopBar from "@/components/TopBar";
import Sidebar from "@/components/Sidebar";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

function Layout() {
  return (
    <div className="flex flex-col h-screen overflow-hidden" style={{ background: "#0a0b0f" }}>
      <TopBar />
      <div className="flex flex-1 min-h-0">
        <Sidebar />
        <main className="flex-1 min-w-0 overflow-auto">
          <Switch>
            <Route path="/" component={LiveRunPage} />
            <Route path="/jobs" component={JobHistoryPage} />
            <Route path="/jobs/:id" component={JobTracePage} />
            <Route path="/traces" component={ExecutionTracesPage} />
            <Route path="/eval" component={EvalPage} />
            <Route path="/prompts" component={PromptsPage} />
            <Route path="/test-cases" component={TestCasesPage} />
            <Route path="/budgets" component={BudgetsPage} />
            <Route path="/agent-turns" component={AgentTurnsPage} />
            <Route path="/tool-calls" component={ToolCallsPage} />
            <Route component={NotFound} />
          </Switch>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  useEffect(() => {
    document.documentElement.classList.add("dark");
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <AppProvider>
        <TooltipProvider>
          <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}>
            <Layout />
          </WouterRouter>
          <Toaster />
        </TooltipProvider>
      </AppProvider>
    </QueryClientProvider>
  );
}
