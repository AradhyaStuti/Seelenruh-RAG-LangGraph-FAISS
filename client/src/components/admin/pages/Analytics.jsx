import { useState, useEffect, useCallback } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  PieChart, Pie, Cell, Legend, ResponsiveContainer,
} from "recharts";
import { RefreshCw, TrendingUp, MessageSquare, FileText, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { fetchAdminAnalytics, fetchFeedbackStats } from "@/lib/adminApi";
import { useToast } from "@/hooks/use-toast";

const CHART_COLORS = ["#a78bfa", "#34d399", "#f59e0b", "#60a5fa", "#f87171", "#c084fc"];
const CONFIDENCE_COLORS = { High: "#34d399", Medium: "#f59e0b", Low: "#f87171", None: "#94a3b8" };

function Skeleton({ className }) {
  return <div className={cn("animate-pulse rounded-lg bg-muted/50", className)} />;
}

function StatCard({ icon: Icon, label, value, sub, loading }) {
  if (loading) {
    return (
      <div className="rounded-2xl border border-border/40 bg-card/80 p-4 space-y-3">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-16" />
      </div>
    );
  }
  return (
    <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-muted-foreground font-medium uppercase tracking-wide">{label}</span>
        <span className="flex items-center justify-center h-7 w-7 rounded-lg bg-primary/10 text-primary">
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <div className="text-2xl font-bold text-foreground tabular-nums">{value ?? "—"}</div>
      {sub && <div className="text-xs text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  );
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-border/40 bg-card/95 backdrop-blur-md px-3 py-2 shadow-lg text-xs">
      <p className="font-semibold text-foreground mb-1">{label}</p>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ background: p.fill || p.stroke }} />
          <span className="text-muted-foreground">{p.name}:</span>
          <span className="font-medium text-foreground">{p.value}</span>
        </div>
      ))}
    </div>
  );
};

const PieTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const entry = payload[0];
  return (
    <div className="rounded-xl border border-border/40 bg-card/95 backdrop-blur-md px-3 py-2 shadow-lg text-xs">
      <div className="flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full" style={{ background: entry.payload.fill }} />
        <span className="font-medium text-foreground">{entry.name}:</span>
        <span className="text-muted-foreground">{entry.value}</span>
      </div>
    </div>
  );
};

export default function Analytics({ adminKey }) {
  const [analytics, setAnalytics]   = useState(null);
  const [feedback, setFeedback]     = useState(null);
  const [loading, setLoading]       = useState(true);
  const { toast } = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ana, fb] = await Promise.allSettled([
        fetchAdminAnalytics(),
        fetchFeedbackStats(),
      ]);
      if (ana.status === "fulfilled") setAnalytics(ana.value);
      if (fb.status  === "fulfilled") setFeedback(fb.value);
    } catch {
      toast({ title: "Failed to load analytics", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  // ── Data derivation ──────────────────────────────────────────────────────────
  // Feedback by domain — for BarChart
  const feedbackByDomain = (() => {
    const raw = feedback?.by_domain || analytics?.feedback_by_domain || [];
    if (Array.isArray(raw)) {
      return raw.map((d) => ({
        name: d.domain || d.name || "Unknown",
        upvotes:   d.upvotes   || d.up   || 0,
        downvotes: d.downvotes || d.down || 0,
      }));
    }
    // Object shape
    return Object.entries(raw).map(([domain, vals]) => ({
      name: domain,
      upvotes:   vals.upvotes   || vals.up   || 0,
      downvotes: vals.downvotes || vals.down || 0,
    }));
  })();

  // Confidence distribution — for PieChart
  const confidenceDist = (() => {
    const raw = analytics?.confidence_distribution || {};
    if (Array.isArray(raw)) {
      return raw.map((d, i) => ({
        name:  d.label || d.name || d.confidence || `Level ${i}`,
        value: d.count || d.value || 0,
        fill:  CONFIDENCE_COLORS[d.label || d.name] || CHART_COLORS[i % CHART_COLORS.length],
      }));
    }
    return Object.entries(raw).map(([k, v]) => ({
      name:  k,
      value: typeof v === "number" ? v : (v?.count || 0),
      fill:  CONFIDENCE_COLORS[k] || CHART_COLORS[0],
    }));
  })();

  // Knowledge gaps by domain — for BarChart
  const gapsByDomain = (() => {
    const raw = analytics?.gaps_by_domain || [];
    if (Array.isArray(raw)) {
      return raw.map((d) => ({
        name:  d.domain || d.name || "Unknown",
        open:    d.open    || 0,
        solved:  d.solved  || 0,
        ignored: d.ignored || 0,
      }));
    }
    return Object.entries(raw).map(([domain, vals]) => ({
      name:    domain,
      open:    vals.open    || 0,
      solved:  vals.solved  || 0,
      ignored: vals.ignored || 0,
    }));
  })();

  // Recent uploads
  const recentUploads = analytics?.recent_uploads || analytics?.recent_documents || [];

  const totalQueries  = analytics?.total_queries  ?? "—";
  const totalFeedback = (feedback?.total_votes)   ?? (analytics?.total_feedback) ?? "—";
  const openGaps      = analytics?.open_gaps      ?? "—";
  const totalDocs     = analytics?.total_documents ?? "—";

  const axisStyle  = { fontSize: 11, fill: "hsl(var(--muted-foreground))" };
  const gridStyle  = { stroke: "hsl(var(--border))", strokeOpacity: 0.4 };

  return (
    <div className="space-y-5">
      {/* Top cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard loading={loading} icon={MessageSquare} label="Total Queries"  value={totalQueries}  />
        <StatCard loading={loading} icon={TrendingUp}    label="Total Feedback" value={totalFeedback} />
        <StatCard loading={loading} icon={AlertCircle}   label="Open Gaps"      value={openGaps}      />
        <StatCard loading={loading} icon={FileText}      label="Documents"      value={totalDocs}     />
      </div>

      {/* Refresh */}
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={load} disabled={loading} className="gap-1.5 rounded-xl">
          <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {/* Charts row 1 */}
      <div className="grid lg:grid-cols-2 gap-5">
        {/* Feedback by domain */}
        <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm p-4">
          <h3 className="text-sm font-semibold text-foreground mb-4">Feedback by Domain</h3>
          {loading ? (
            <div className="h-52 flex items-center justify-center">
              <Skeleton className="h-48 w-full" />
            </div>
          ) : feedbackByDomain.length === 0 ? (
            <div className="h-52 flex items-center justify-center text-sm text-muted-foreground">
              No feedback data yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={feedbackByDomain} margin={{ top: 4, right: 8, bottom: 4, left: -16 }}>
                <CartesianGrid strokeDasharray="3 3" {...gridStyle} />
                <XAxis dataKey="name" tick={axisStyle} tickLine={false} axisLine={false} />
                <YAxis tick={axisStyle} tickLine={false} axisLine={false} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: "hsl(var(--muted)/0.2)" }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="upvotes"   name="Upvotes"   fill="#34d399" radius={[4, 4, 0, 0]} />
                <Bar dataKey="downvotes" name="Downvotes" fill="#f87171" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Confidence distribution */}
        <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm p-4">
          <h3 className="text-sm font-semibold text-foreground mb-4">Confidence Distribution</h3>
          {loading ? (
            <div className="h-52 flex items-center justify-center">
              <Skeleton className="h-48 w-full" />
            </div>
          ) : confidenceDist.length === 0 ? (
            <div className="h-52 flex items-center justify-center text-sm text-muted-foreground">
              No confidence data yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={confidenceDist}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {confidenceDist.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} stroke="transparent" />
                  ))}
                </Pie>
                <Tooltip content={<PieTooltip />} />
                <Legend
                  iconType="circle"
                  iconSize={8}
                  wrapperStyle={{ fontSize: 11 }}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Charts row 2 */}
      <div className="grid lg:grid-cols-2 gap-5">
        {/* Gaps by domain */}
        <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm p-4">
          <h3 className="text-sm font-semibold text-foreground mb-4">Knowledge Gaps by Domain</h3>
          {loading ? (
            <Skeleton className="h-52 w-full" />
          ) : gapsByDomain.length === 0 ? (
            <div className="h-52 flex items-center justify-center text-sm text-muted-foreground">
              No gap data yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={gapsByDomain} margin={{ top: 4, right: 8, bottom: 4, left: -16 }}>
                <CartesianGrid strokeDasharray="3 3" {...gridStyle} />
                <XAxis dataKey="name" tick={axisStyle} tickLine={false} axisLine={false} />
                <YAxis tick={axisStyle} tickLine={false} axisLine={false} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: "hsl(var(--muted)/0.2)" }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="open"    name="Open"    fill="#f59e0b" radius={[4, 4, 0, 0]} />
                <Bar dataKey="solved"  name="Solved"  fill="#34d399" radius={[4, 4, 0, 0]} />
                <Bar dataKey="ignored" name="Ignored" fill="#94a3b8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Recent uploads table */}
        <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-border/30">
            <h3 className="text-sm font-semibold text-foreground">Recent Uploads</h3>
          </div>
          {loading ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-6 w-full" />)}
            </div>
          ) : recentUploads.length === 0 ? (
            <div className="py-10 text-center text-sm text-muted-foreground">No recent uploads</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-border/20 bg-muted/10">
                    {["Filename", "Domain", "Chunks", "Date"].map((h) => (
                      <th key={h} className="px-3 py-2 text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/20">
                  {recentUploads.slice(0, 8).map((doc, i) => (
                    <tr key={doc.id || i} className={cn("transition-colors", i % 2 === 1 && "bg-muted/10")}>
                      <td className="px-3 py-2 font-medium text-foreground max-w-[140px]">
                        <span className="truncate block">{doc.filename || doc.name || "—"}</span>
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">{doc.domain || "—"}</td>
                      <td className="px-3 py-2 text-muted-foreground tabular-nums">{doc.chunk_count ?? "—"}</td>
                      <td className="px-3 py-2 text-muted-foreground whitespace-nowrap">
                        {doc.indexed_at || doc.created_at
                          ? new Date(doc.indexed_at || doc.created_at).toLocaleDateString()
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
