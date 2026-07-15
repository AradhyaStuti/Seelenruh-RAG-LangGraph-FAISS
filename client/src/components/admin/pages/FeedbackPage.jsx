import { useState, useEffect, useCallback } from "react";
import {
  ThumbsUp,
  ThumbsDown,
  Download,
  RefreshCw,
  BarChart2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { fetchFeedbackStats, exportFeedbackUrl } from "@/lib/adminApi";
import { useToast } from "@/hooks/use-toast";

function Skeleton({ className }) {
  return <div className={cn("animate-pulse rounded-lg bg-muted/50", className)} />;
}

function StatCard({ icon: Icon, label, value, sub, color = "primary", loading }) {
  if (loading) {
    return (
      <div className="rounded-2xl border border-border/40 bg-card/80 p-4 space-y-3">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-8 w-14" />
      </div>
    );
  }
  return (
    <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-muted-foreground font-medium uppercase tracking-wide">{label}</span>
        <span className={cn(
          "flex items-center justify-center h-7 w-7 rounded-lg",
          color === "primary" && "bg-primary/10 text-primary",
          color === "green"   && "bg-emerald-500/10 text-emerald-500",
          color === "red"     && "bg-red-500/10 text-red-500",
          color === "blue"    && "bg-blue-500/10 text-blue-500",
        )}>
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <div className="text-2xl font-bold text-foreground tabular-nums">{value ?? "—"}</div>
      {sub && <div className="text-xs text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  );
}

function PositiveBar({ pct }) {
  const width = isNaN(pct) ? 0 : Math.max(0, Math.min(100, pct));
  const color = width >= 70 ? "bg-emerald-500" : width >= 40 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-muted/50 overflow-hidden">
        <div className={cn("h-full rounded-full transition-all duration-500", color)} style={{ width: `${width}%` }} />
      </div>
      <span className="text-[11px] font-medium tabular-nums text-muted-foreground w-9 text-right">
        {isNaN(pct) ? "—" : `${pct.toFixed(0)}%`}
      </span>
    </div>
  );
}

export default function FeedbackPage({ adminKey }) {
  const [stats, setStats]   = useState(null);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchFeedbackStats();
      setStats(data);
    } catch (err) {
      toast({ title: "Failed to load feedback stats", description: err?.message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const handleExport = () => {
    const url = exportFeedbackUrl();
    const a = document.createElement("a");
    a.href = url;
    a.download = `seelenruh-feedback-${Date.now()}.csv`;
    a.click();
    toast({ title: "Downloading feedback CSV…" });
  };

  const total    = stats?.total_votes    ?? stats?.total    ?? 0;
  const upvotes  = stats?.upvotes        ?? stats?.up       ?? 0;
  const downvotes = stats?.downvotes     ?? stats?.down     ?? 0;
  const pctPos   = total > 0 ? (upvotes / total) * 100 : 0;

  const byDomain = (() => {
    const raw = stats?.by_domain || {};
    if (Array.isArray(raw)) {
      return raw.map((d) => ({
        domain:    d.domain || d.name || "Unknown",
        count:     d.total  || d.count || (d.up || 0) + (d.down || 0),
        upvotes:   d.upvotes  || d.up   || 0,
        downvotes: d.downvotes || d.down || 0,
      }));
    }
    return Object.entries(raw).map(([domain, v]) => ({
      domain,
      count:     (v.upvotes || v.up || 0) + (v.downvotes || v.down || 0),
      upvotes:   v.upvotes  || v.up   || 0,
      downvotes: v.downvotes || v.down || 0,
    }));
  })();

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-muted-foreground">
          <BarChart2 className="h-4 w-4" />
          <span className="text-sm">User feedback across all domains</span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={load} disabled={loading} className="gap-1.5 rounded-xl">
            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
            Refresh
          </Button>
          <Button size="sm" onClick={handleExport} className="gap-1.5 rounded-xl">
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard loading={loading} icon={BarChart2}  label="Total Votes"  value={total}    color="blue"    />
        <StatCard loading={loading} icon={ThumbsUp}   label="Upvotes"      value={upvotes}  color="green"   />
        <StatCard loading={loading} icon={ThumbsDown} label="Downvotes"    value={downvotes} color="red"    />
        <StatCard
          loading={loading}
          icon={ThumbsUp}
          label="% Positive"
          value={total > 0 ? `${pctPos.toFixed(1)}%` : "—"}
          sub={total > 0 ? `${upvotes} of ${total}` : undefined}
          color="primary"
        />
      </div>

      {/* Overall positive bar */}
      {!loading && total > 0 && (
        <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-foreground">Overall Sentiment</span>
            <span className="text-xs text-muted-foreground">{upvotes} up · {downvotes} down</span>
          </div>
          <PositiveBar pct={pctPos} />
        </div>
      )}

      {/* By domain table */}
      <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-border/30 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">Feedback by Domain</h3>
          {!loading && (
            <span className="text-xs text-muted-foreground">{byDomain.length} domain{byDomain.length !== 1 ? "s" : ""}</span>
          )}
        </div>

        {loading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex gap-3">
                <Skeleton className="h-5 flex-1" />
                <Skeleton className="h-5 w-12" />
                <Skeleton className="h-5 w-12" />
                <Skeleton className="h-5 w-12" />
                <Skeleton className="h-5 w-24" />
              </div>
            ))}
          </div>
        ) : byDomain.length === 0 ? (
          <div className="py-12 text-center text-sm text-muted-foreground">
            No feedback data available yet
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="border-b border-border/20 bg-muted/10">
                  {["Domain", "Total", "Upvotes", "Downvotes", "% Positive"].map((h) => (
                    <th key={h} className="px-4 py-2.5 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                {byDomain.map((row, i) => {
                  const rowPct = row.count > 0 ? (row.upvotes / row.count) * 100 : 0;
                  return (
                    <tr
                      key={row.domain}
                      className={cn(
                        "transition-colors hover:bg-primary/5",
                        i % 2 === 1 && "bg-muted/10"
                      )}
                    >
                      <td className="px-4 py-3 font-medium text-foreground">{row.domain}</td>
                      <td className="px-4 py-3 text-muted-foreground tabular-nums">{row.count}</td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1 text-emerald-600 font-medium tabular-nums">
                          <ThumbsUp className="h-3 w-3" />
                          {row.upvotes}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1 text-red-500 font-medium tabular-nums">
                          <ThumbsDown className="h-3 w-3" />
                          {row.downvotes}
                        </span>
                      </td>
                      <td className="px-4 py-3 min-w-[140px]">
                        <PositiveBar pct={rowPct} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
