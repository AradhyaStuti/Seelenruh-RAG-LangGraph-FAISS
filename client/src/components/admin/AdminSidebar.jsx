import { useState } from "react";
import {
  LayoutDashboard,
  BookOpen,
  AlertCircle,
  BarChart2,
  MessageSquare,
  Settings,
  LogOut,
  Menu,
  X,
  Shield,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const NAV_ITEMS = [
  { id: "dashboard",      label: "Dashboard",       icon: LayoutDashboard },
  { id: "knowledge-base", label: "Knowledge Base",  icon: BookOpen },
  { id: "knowledge-gaps", label: "Knowledge Gaps",  icon: AlertCircle },
  { id: "analytics",      label: "Analytics",       icon: BarChart2 },
  { id: "feedback",       label: "Feedback",        icon: MessageSquare },
  { id: "settings",       label: "Settings",        icon: Settings },
];

export default function AdminSidebar({ activePage, onNavigate, onExit }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleNav = (id) => {
    onNavigate(id);
    setMobileOpen(false);
  };

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-white/10">
        <div className="flex items-center justify-center h-9 w-9 rounded-xl bg-primary/20 border border-primary/30">
          <Shield className="h-5 w-5 text-primary" />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-bold text-foreground leading-tight">Seelenruh</span>
          <span className="text-[10px] text-muted-foreground/70 uppercase tracking-widest">Admin</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
          const isActive = activePage === id;
          return (
            <button
              key={id}
              onClick={() => handleNav(id)}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200",
                "focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/50",
                isActive
                  ? "bg-primary/15 text-primary border border-primary/25 shadow-sm"
                  : "text-muted-foreground hover:bg-white/5 hover:text-foreground border border-transparent"
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0 transition-colors duration-200",
                  isActive ? "text-primary" : "text-muted-foreground/70"
                )}
              />
              <span>{label}</span>
              {isActive && (
                <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary" />
              )}
            </button>
          );
        })}
      </nav>

      {/* Exit button */}
      <div className="px-3 py-4 border-t border-white/10">
        <button
          onClick={onExit}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-muted-foreground hover:text-destructive hover:bg-destructive/10 border border-transparent hover:border-destructive/20 transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-destructive/40"
        >
          <LogOut className="h-4 w-4 shrink-0" />
          <span>Exit Admin</span>
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile toggle button */}
      <button
        className="fixed top-4 left-4 z-50 lg:hidden flex items-center justify-center h-9 w-9 rounded-xl bg-card/90 border border-border/40 backdrop-blur-sm shadow-md transition-all duration-200 hover:bg-card"
        onClick={() => setMobileOpen((v) => !v)}
        aria-label="Toggle sidebar"
      >
        {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-64 lg:hidden",
          "bg-card/95 backdrop-blur-xl border-r border-white/10 shadow-2xl",
          "transition-transform duration-300",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <SidebarContent />
      </aside>

      {/* Desktop sidebar */}
      <aside className="hidden lg:flex flex-col w-60 shrink-0 bg-card/60 backdrop-blur-xl border-r border-border/30 shadow-lg">
        <SidebarContent />
      </aside>
    </>
  );
}
