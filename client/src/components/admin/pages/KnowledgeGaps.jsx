import { useState, useEffect, useCallback } from "react";
import {
  AlertCircle,
  CheckCircle2,
  EyeOff,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { fetchKnowledgeGaps, updateKnowledgeGap } from "@/lib/adminApi";
import { useToast } from "@/hooks/use-toast";

const STATUS_OPTS = [
  { value: "",        label: "All Statuses" },
  { value: "open",    label: "Open" },
  { value: "solved",  label: "Solved" },
  { value: "ignored", label: "Ignored" },
];

const PAGE_SIZE = 20;

function Skeleton({ className }) {
  return <div className={cn("animate-pulse rounded-lg bg-muted/50", className)} />;
}

function StatusBadge({ status }) {
  const cfg = {
    open:    { cls: "bg-amber-500/10 text-amber-600 border-amber-500/20",   icon: AlertCircle },
    solved:  { cls: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20", icon: CheckCircle2 },
    ignored: { cls: "bg-muted/50 text-muted-foreground border-border/30",   icon: EyeOff },
  }[status?.toLowerCase()] || { cls: "bg-muted/50 text-muted-foreground border-border/30", icon: AlertCircle };
  const Icon = cfg.icon;
  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border", cfg.cls)}>
      <Icon className="h-3 w-3" />
      {status || "—"}
    </span>
  );
}

function ConfidencePill({ value }) {
  const cls =
    value === "High"   ? "bg-emerald-500/10 text-emerald-600" :
    value === "Medium" ? "bg-amber-500/10 text-amber-600" :
    value === "Low"    ? "bg-red-500/10 text-red-500" :
    "bg-muted/50 text-muted-foreground";
  return (
    <span className={cn("inline-block px-2 py-0.5 rounded-md text-[11px] font-medium", cls)}>
      {value || "—"}
    </span>
  );
}

function Select({ value, onChange, options, className }) {
  return (
    <div className={cn("relative", className)}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full appearance-none rounded-xl border border-border/40 bg-card/80 px-3 py-2 text-sm text-foreground pr-8 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
    </div>
  );
}

export default function KnowledgeGaps({ adminKey }) {
  const [gaps, setGaps]         = useState([]);
  const [loading, setLoading]   = useState(true);
  const [statusFilter, setStatusFilter] = useState("open");
  const [page, setPage]         = useState(1);
  const [updating, setUpdating] = useState(null);
  const { toast } = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchKnowledgeGaps(statusFilter || undefined);
      setGaps(Array.isArray(data) ? data : (data?.gaps || []));
      setPage(1);
    } catch (err) {
      toast({ title: "Failed to load knowledge gaps", description: err?.message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [statusFilter, toast]);

  useEffect(() => { load(); }, [load]);

  const handleUpdate = async (id, newStatus) => {
    setUpdating(id);
    try {
      await updateKnowledgeGap(id, newStatus);
      toast({ title: `Gap marked as ${newStatus}` });
      // Optimistic update
      setGaps((prev) => prev.map((g) => g.id === id ? { ...g, status: newStatus } : g));
    } catch (err) {
      toast({ title: "Update failed", description: err?.message, variant: "destructive" });
    } finally {
      setUpdating(null);
    }
  };

  const totalPages = Math.max(1, Math.ceil(gaps.length / PAGE_SIZE));
  const paginated  = gaps.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const fmtDate = (ts) => {
    if (!ts) return "—";
    return new Date(ts).toLocaleDateString([], { dateStyle: "medium" });
  };

  return (
    <div className="space-y-4">
      {/* Header controls */}
      <div className="flex flex-wrap items-center gap-3">
        <Select
          value={statusFilter}
          onChange={setStatusFilter}
          options={STATUS_OPTS}
          className="w-44"
        />
        <span className="text-xs text-muted-foreground ml-auto">
          {loading ? "Loading…" : `${gaps.length} gap${gaps.length !== 1 ? "s" : ""}`}
        </span>
        <Button variant="outline" size="sm" onClick={load} disabled={loading} className="gap-1.5 rounded-xl">
          <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {/* Table */}
      <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="border-b border-border/30 bg-muted/20">
                {["Query", "Domain", "Confidence", "Created", "Status", "Actions"].map((h) => (
                  <th key={h} className="px-3 py-2.5 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border/20">
              {loading
                ? Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: 6 }).map((_, j) => (
                        <td key={j} className="px-3 py-3">
                          <Skeleton className="h-4" style={{ width: `${50 + j * 8}%` }} />
                        </td>
                      ))}
                    </tr>
                  ))
                : paginated.length === 0
                  ? (
                    <tr>
                      <td colSpan={6} className="px-3 py-12 text-center text-sm text-muted-foreground">
                        No {statusFilter || ""} knowledge gaps found
                      </td>
                    </tr>
                  )
                  : paginated.map((gap, i) => {
                      const isUpdating = updating === gap.id;
                      const status = gap.status?.toLowerCase();
                      return (
                        <tr
                          key={gap.id || i}
                          className={cn(
                            "transition-colors",
                            i % 2 === 1 ? "bg-muted/10" : "",
                            "hover:bg-primary/5"
                          )}
                        >
                          <td className="px-3 py-2.5 max-w-xs">
                            <p className="text-xs text-foreground line-clamp-2 leading-relaxed">
                              {gap.query || gap.question || "—"}
                            </p>
                          </td>
                          <td className="px-3 py-2.5 text-xs text-muted-foreground whitespace-nowrap">
                            {gap.domain || "—"}
                          </td>
                          <td className="px-3 py-2.5">
                            <ConfidencePill value={gap.confidence} />
                          </td>
                          <td className="px-3 py-2.5 text-xs text-muted-foreground whitespace-nowrap">
                            {fmtDate(gap.created_at || gap.timestamp)}
                          </td>
                          <td className="px-3 py-2.5">
                            <StatusBadge status={gap.status} />
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="flex items-center gap-1">
                              {status !== "solved" && (
                                <button
                                  onClick={() => handleUpdate(gap.id, "solved")}
                                  disabled={isUpdating}
                                  className="h-7 px-2 flex items-center gap-1 rounded-lg text-[11px] font-medium bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20 border border-emerald-500/20 transition-colors disabled:opacity-40"
                                  title="Mark solved"
                                >
                                  <CheckCircle2 className="h-3 w-3" />
                                  Solve
                                </button>
                              )}
                              {status !== "ignored" && (
                                <button
                                  onClick={() => handleUpdate(gap.id, "ignored")}
                                  disabled={isUpdating}
                                  className="h-7 px-2 flex items-center gap-1 rounded-lg text-[11px] font-medium bg-muted/40 text-muted-foreground hover:bg-muted/70 border border-border/30 transition-colors disabled:opacity-40"
                                  title="Mark ignored"
                                >
                                  <EyeOff className="h-3 w-3" />
                                  Ignore
                                </button>
                              )}
                              {status !== "open" && (
                                <button
                                  onClick={() => handleUpdate(gap.id, "open")}
                                  disabled={isUpdating}
                                  className="h-7 px-2 flex items-center gap-1 rounded-lg text-[11px] font-medium bg-amber-500/10 text-amber-600 hover:bg-amber-500/20 border border-amber-500/20 transition-colors disabled:opacity-40"
                                  title="Reopen"
                                >
                                  <AlertCircle className="h-3 w-3" />
                                  Reopen
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })
              }
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {!loading && gaps.length > PAGE_SIZE && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-border/20">
            <span className="text-xs text-muted-foreground">
              Page {page} of {totalPages}
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="h-7 w-7 p-0 rounded-lg"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </Button>
              {Array.from({ length: Math.min(5, totalPages) }).map((_, i) => {
                const pg = i + 1;
                return (
                  <button
                    key={pg}
                    onClick={() => setPage(pg)}
                    className={cn(
                      "h-7 w-7 flex items-center justify-center rounded-lg text-xs font-medium transition-colors",
                      pg === page
                        ? "bg-primary text-primary-foreground"
                        : "hover:bg-muted/60 text-muted-foreground"
                    )}
                  >
                    {pg}
                  </button>
                );
              })}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="h-7 w-7 p-0 rounded-lg"
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
