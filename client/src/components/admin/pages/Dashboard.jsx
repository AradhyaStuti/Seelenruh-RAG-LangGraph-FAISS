import { useState, useEffect, useCallback } from "react";
import {
  FileText,
  Layers,
  AlertCircle,
  ThumbsUp,
  ThumbsDown,
  Activity,
  RefreshCw,
  RotateCcw,
  Clock,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  fetchAdminAnalytics,
  fetchAdminStatus,
  fetchAuditLog,
  fetchSnapshots,
  rollbackIndex,
} from "@/lib/adminApi";
import { useToast } from "@/hooks/use-toast";
import {
  DEMO_ANALYTICS,
  DEMO_STATUS,
  DEMO_AUDIT_LOG,
  DEMO_SNAPSHOTS,
} from "@/lib/adminDemoData";

function Skeleton({ className }) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-lg bg-muted/50",
        className
      )}
    />
  );
}

function StatCardSkeleton() {
  return (
    <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm p-4 space-y-3">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-16" />
      <Skeleton className="h-3 w-32" />
    </div>
  );
}

function StatCard({ icon: Icon, label, value, sub, color = "primary", loading }) {
  if (loading) return <StatCardSkeleton />;
  return (
    <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm p-4 flex flex-col gap-1 hover:border-primary/30 transition-all duration-200">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground font-medium uppercase tracking-wide">{label}</span>
        <span className={cn(
          "flex items-center justify-center h-7 w-7 rounded-lg",
          color === "primary" && "bg-primary/10 text-primary",
          color === "green"   && "bg-emerald-500/10 text-emerald-500",
          color === "red"     && "bg-red-500/10 text-red-500",
          color === "amber"   && "bg-amber-500/10 text-amber-500",
          color === "blue"    && "bg-blue-500/10 text-blue-500",
        )}>
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <div className="text-2xl font-bold text-foreground tabular-nums">{value ?? "—"}</div>
      {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

function StatusBadge({ status }) {
  const ok = status === "ok" || status === "healthy";
  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
      ok
        ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
        : "bg-red-500/10 text-red-500 border border-red-500/20"
    )}>
      {ok ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
      {status || "unknown"}
    </span>
  );
}

function AuditRow({ entry, idx }) {
  const ts = entry.timestamp
    ? new Date(entry.timestamp).toLocaleString([], { dateStyle: "short", timeStyle: "short" })
    : "—";
  return (
    <tr className={cn(
      "text-xs transition-colors",
      idx % 2 === 0 ? "bg-transparent" : "bg-muted/20"
    )}>
      <td className="px-3 py-2 text-muted-foreground whitespace-nowrap">{ts}</td>
      <td className="px-3 py-2 font-medium text-foreground">{entry.action || entry.event || "—"}</td>
      <td className="px-3 py-2 text-muted-foreground truncate max-w-xs">{entry.detail || entry.message || "—"}</td>
      <td className="px-3 py-2 text-muted-foreground">{entry.user || "admin"}</td>
    </tr>
  );
}

export default function Dashboard({ adminKey }) {
  const [analytics, setAnalytics] = useState(null);
  const [status, setStatus]       = useState(null);
  const [auditLog, setAuditLog]   = useState([]);
  const [snapshots, setSnapshots] = useState([]);
  const [loading, setLoading]     = useState(true);
  const [rolling, setRolling]     = useState(false);
  const { toast } = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ana, sts, audit, snaps] = await Promise.allSettled([
        fetchAdminAnalytics(),
        fetchAdminStatus(),
        fetchAuditLog(10),
        fetchSnapshots(),
      ]);
      const anaVal  = ana.status  === "fulfilled" ? ana.value  : null;
      const stsVal  = sts.status  === "fulfilled" ? sts.value  : null;
      const auditVal = audit.status === "fulfilled" ? audit.value : null;
      const snapsVal = snaps.status === "fulfilled" ? snaps.value : null;

      setAnalytics(anaVal ?? DEMO_ANALYTICS);
      setStatus(stsVal ?? DEMO_STATUS);
      const auditArr = Array.isArray(auditVal) ? auditVal : (auditVal?.logs || []);
      setAuditLog(auditArr.length > 0 ? auditArr : DEMO_AUDIT_LOG);
      const snapsArr = Array.isArray(snapsVal) ? snapsVal : (snapsVal?.snapshots || []);
      setSnapshots(snapsArr.length > 0 ? snapsArr : DEMO_SNAPSHOTS);
    } catch {
      toast({ title: "Failed to load dashboard", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const handleRollback = async (steps = 1) => {
    if (!window.confirm(`Roll back index by ${steps} step${steps > 1 ? "s" : ""}?`)) return;
    setRolling(true);
    try {
      await rollbackIndex(steps);
      toast({ title: "Rollback successful", description: `Index rolled back ${steps} step(s).` });
      load();
    } catch (err) {
      toast({ title: "Rollback failed", description: err?.message, variant: "destructive" });
    } finally {
      setRolling(false);
    }
  };

  const ups   = analytics?.feedback_summary?.upvotes   ?? analytics?.upvotes   ?? "—";
  const downs = analytics?.feedback_summary?.downvotes ?? analytics?.downvotes ?? "—";
  const ragStatus = status?.status ?? status?.rag_status ?? "—";

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <StatCard
          loading={loading}
          icon={FileText}
          label="Documents"
          value={analytics?.total_documents ?? status?.total_documents ?? "—"}
          sub="indexed"
          color="primary"
        />
        <StatCard
          loading={loading}
          icon={Layers}
          label="Active Chunks"
          value={analytics?.active_chunks ?? status?.chunk_count ?? "—"}
          sub="in FAISS"
          color="blue"
        />
        <StatCard
          loading={loading}
          icon={AlertCircle}
          label="Open Gaps"
          value={analytics?.open_gaps ?? "—"}
          sub="knowledge gaps"
          color="amber"
        />
        <StatCard
          loading={loading}
          icon={ThumbsUp}
          label="Upvotes"
          value={ups}
          color="green"
        />
        <StatCard
          loading={loading}
          icon={ThumbsDown}
          label="Downvotes"
          value={downs}
          color="red"
        />
      </div>

      {/* RAG Status + Refresh */}
      <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm p-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Activity className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium text-foreground">RAG System Status</span>
          {loading
            ? <Skeleton className="h-6 w-20" />
            : <StatusBadge status={ragStatus} />
          }
          {!loading && status && (
            <span className="text-xs text-muted-foreground hidden sm:inline">
              FAISS vectors: {status.faiss_size ?? status.index_size ?? "?"}
            </span>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading} className="gap-1.5 rounded-xl">
          <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        {/* Audit log */}
        <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-border/30">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold text-foreground">Recent Activity</h3>
            <span className="ml-auto text-xs text-muted-foreground">Last 10 events</span>
          </div>
          {loading ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-6 w-full" />
              ))}
            </div>
          ) : auditLog.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">No audit events yet</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-border/20">
                    <th className="px-3 py-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Time</th>
                    <th className="px-3 py-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Action</th>
                    <th className="px-3 py-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Detail</th>
                    <th className="px-3 py-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">User</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/20">
                  {auditLog.slice(0, 10).map((entry, i) => (
                    <AuditRow key={entry.id || i} entry={entry} idx={i} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Snapshots */}
        <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-border/30">
            <RotateCcw className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold text-foreground">Index Snapshots</h3>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => handleRollback(1)}
              disabled={rolling || loading || snapshots.length === 0}
              className="ml-auto gap-1.5 rounded-xl text-xs"
            >
              <RotateCcw className={cn("h-3 w-3", rolling && "animate-spin")} />
              Rollback 1 Step
            </Button>
          </div>
          {loading ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : snapshots.length === 0 ? (
            <div className="p-8 text-center text-sm text-muted-foreground">No snapshots available</div>
          ) : (
            <div className="divide-y divide-border/20">
              {snapshots.slice(0, 8).map((snap, i) => {
                const ts = snap.timestamp || snap.created_at
                  ? new Date(snap.timestamp || snap.created_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" })
                  : "—";
                return (
                  <div key={snap.id || i} className={cn(
                    "flex items-center justify-between px-4 py-2.5 text-xs",
                    i % 2 === 1 && "bg-muted/20"
                  )}>
                    <div className="flex flex-col gap-0.5">
                      <span className="font-medium text-foreground">
                        {snap.label || snap.name || `Snapshot #${i + 1}`}
                      </span>
                      <span className="text-muted-foreground">{ts}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {snap.chunk_count != null && (
                        <span className="text-muted-foreground">{snap.chunk_count} chunks</span>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleRollback(i + 1)}
                        disabled={rolling}
                        className="h-7 px-2 rounded-lg text-[11px]"
                      >
                        Restore
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
