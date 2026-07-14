import { useState } from "react";
import {
  LayoutDashboard,
  BookOpen,
  AlertCircle,
  BarChart2,
  MessageSquare,
  Settings as SettingsIcon,
  LogOut,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getAdminKey, clearAdminKey } from "@/lib/adminApi";
import AdminSidebar from "./AdminSidebar";
import Dashboard       from "./pages/Dashboard";
import KnowledgeBase   from "./pages/KnowledgeBase";
import KnowledgeGaps   from "./pages/KnowledgeGaps";
import Analytics       from "./pages/Analytics";
import FeedbackPage    from "./pages/FeedbackPage";
import Settings        from "./pages/Settings";

const PAGE_META = {
  "dashboard":       { label: "Dashboard",       icon: LayoutDashboard },
  "knowledge-base":  { label: "Knowledge Base",  icon: BookOpen },
  "knowledge-gaps":  { label: "Knowledge Gaps",  icon: AlertCircle },
  "analytics":       { label: "Analytics",       icon: BarChart2 },
  "feedback":        { label: "Feedback",        icon: MessageSquare },
  "settings":        { label: "Settings",        icon: SettingsIcon },
};

export default function AdminPanel({ onExit }) {
  const [activePage, setActivePage] = useState("dashboard");
  const adminKey = getAdminKey();

  const handleExit = () => {
    clearAdminKey();
    onExit?.();
  };

  const meta = PAGE_META[activePage] || PAGE_META["dashboard"];
  const PageIcon = meta.icon;

  const renderPage = () => {
    const props = { adminKey };
    switch (activePage) {
      case "dashboard":       return <Dashboard     {...props} />;
      case "knowledge-base":  return <KnowledgeBase {...props} />;
      case "knowledge-gaps":  return <KnowledgeGaps {...props} />;
      case "analytics":       return <Analytics     {...props} />;
      case "feedback":        return <FeedbackPage  {...props} />;
      case "settings":        return <Settings      {...props} />;
      default:                return <Dashboard     {...props} />;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex bg-background overflow-hidden">
      {/* Sidebar */}
      <AdminSidebar
        activePage={activePage}
        onNavigate={setActivePage}
        onExit={handleExit}
      />

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar */}
        <header className="shrink-0 flex items-center gap-3 px-5 py-3.5 border-b border-border/30 bg-card/60 backdrop-blur-sm">
          {/* Mobile spacer for hamburger button */}
          <div className="w-10 lg:hidden shrink-0" />

          <div className="flex items-center gap-2.5 flex-1 min-w-0">
            <div className="flex items-center justify-center h-7 w-7 rounded-lg bg-primary/10 text-primary shrink-0">
              <PageIcon className="h-4 w-4" />
            </div>
            <h1 className="text-base font-semibold text-foreground truncate">{meta.label}</h1>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* Admin key indicator */}
            <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              Admin authenticated
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleExit}
              className="gap-1.5 rounded-xl text-muted-foreground hover:text-destructive hover:bg-destructive/10 hidden lg:flex"
            >
              <LogOut className="h-3.5 w-3.5" />
              Exit
            </Button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <div className="p-5 lg:p-6 max-w-7xl mx-auto">
            {renderPage()}
          </div>
        </main>
      </div>
    </div>
  );
}
