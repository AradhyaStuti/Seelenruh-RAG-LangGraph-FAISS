import { useState, useEffect, useCallback } from "react";
import {
  Database,
  RotateCcw,
  ClipboardList,
  Shield,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  fetchAdminStatus,
  fetchAuditLog,
  fetchSnapshots,
  rollbackIndex,
} from "@/lib/adminApi";
import { useToast } from "@/hooks/use-toast";

function Skeleton({ className }) {
  return <div className={cn("animate-pulse rounded-lg bg-muted/50", className)} />;
}

function InfoRow({ label, value, loading }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-border/20 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      {loading
        ? <Skeleton className="h-4 w-24" />
        : <span className="text-sm font-medium text-foreground tabular-nums">{value ?? "—"}</span>
      }
    </div>
  );
}

function StatusDot({ ok }) {
  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
      ok
        ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
        : "bg-red-500/10 text-red-500 border border-red-500/20"
    )}>
      {ok ? <CheckCircle2 className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
      {ok ? "Healthy" : "Degraded"}
    </span>
  );
}

// Audit log drawer (inline, not a modal)
function AuditLogSection() {
  const [open, setOpen]     = useState(false);
  const [log, setLog]       = useState([]);
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const load = async () => {
    setLoading(true);
    try {
      const data = await fetchAuditLog(50);
      setLog(Array.isArray(data) ? data : (data?.logs || []));
    } catch (err) {
      toast({ title: "Failed to load audit log", description: err?.message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = () => {
    if (!open && log.length === 0) load();
    setOpen((v) => !v);
  };

  return (
    <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm overflow-hidden">
      <button
        onClick={handleToggle}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-muted/20 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-blue-500/10 text-blue-600">
            <ClipboardList className="h-4 w-4" />
          </div>
          <div className="text-left">
            <p className="text-sm font-semibold text-foreground">Audit Log</p>
            <p className="text-xs text-muted-foreground">Last 50 admin actions</p>
          </div>
        </div>
        <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform duration-200", open && "rotate-180")} />
      </button>

      {open && (
        <div className="border-t border-border/20">
          <div className="flex items-center justify-between px-5 py-2">
            <span className="text-xs text-muted-foreground">{log.length} events</span>
            <Button variant="ghost" size="sm" onClick={load} disabled={loading} className="h-7 gap-1.5 rounded-lg text-xs">
              <RefreshCw className={cn("h-3 w-3", loading && "animate-spin")} />
              Refresh
            </Button>
          </div>
          <div className="max-h-80 overflow-y-auto">
            {loading ? (
              <div className="p-4 space-y-2">
                {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-5 w-full" />)}
              </div>
            ) : log.length === 0 ? (
              <div className="py-8 text-center text-sm text-muted-foreground">No audit events yet</div>
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border/20 bg-muted/10">
                    <th className="px-4 py-2 text-left text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">Time</th>
                    <th className="px-4 py-2 text-left text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">Action</th>
                    <th className="px-4 py-2 text-left text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">Detail</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/20">
                  {log.map((entry, i) => {
                    const ts = entry.timestamp
                      ? new Date(entry.timestamp).toLocaleString([], { dateStyle: "short", timeStyle: "short" })
                      : "—";
                    return (
                      <tr key={entry.id || i} className={cn(i % 2 === 1 && "bg-muted/10")}>
                        <td className="px-4 py-2 text-muted-foreground whitespace-nowrap">{ts}</td>
                        <td className="px-4 py-2 font-medium text-foreground">{entry.action || entry.event || "—"}</td>
                        <td className="px-4 py-2 text-muted-foreground truncate max-w-xs">{entry.detail || entry.message || "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Settings({ adminKey }) {
  const [status, setStatus]       = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [loading, setLoading]     = useState(true);
  const [rollSteps, setRollSteps] = useState(1);
  const [rolling, setRolling]     = useState(false);
  const { toast } = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [sts, snaps] = await Promise.allSettled([
        fetchAdminStatus(),
        fetchSnapshots(),
      ]);
      if (sts.status   === "fulfilled") setStatus(sts.value);
      if (snaps.status === "fulfilled") setSnapshots(Array.isArray(snaps.value) ? snaps.value : (snaps.value?.snapshots || []));
    } catch {
      toast({ title: "Failed to load settings data", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const handleRollback = async () => {
    if (!window.confirm(`Roll back FAISS index by ${rollSteps} step${rollSteps > 1 ? "s" : ""}? This cannot be undone.`)) return;
    setRolling(true);
    try {
      await rollbackIndex(rollSteps);
      toast({ title: "Rollback successful", description: `Index rolled back ${rollSteps} step(s).` });
      load();
    } catch (err) {
      toast({ title: "Rollback failed", description: err?.message, variant: "destructive" });
    } finally {
      setRolling(false);
    }
  };

  const isHealthy = status?.status === "ok" || status?.status === "healthy";

  return (
    <div className="space-y-5 max-w-2xl">
      {/* FAISS Index Status */}
      <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm overflow-hidden">
        <div className="flex items-center gap-3 px-5 py-4 border-b border-border/20">
          <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-primary/10 text-primary">
            <Database className="h-4 w-4" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-foreground">FAISS Index Status</p>
            <p className="text-xs text-muted-foreground">Vector store health and statistics</p>
          </div>
          <div className="flex items-center gap-2">
            {!loading && <StatusDot ok={isHealthy} />}
            <Button variant="ghost" size="sm" onClick={load} disabled={loading} className="h-7 gap-1.5 rounded-lg text-xs">
              <RefreshCw className={cn("h-3 w-3", loading && "animate-spin")} />
            </Button>
          </div>
        </div>
        <div className="px-5 py-1 divide-y divide-border/10">
          <InfoRow label="Status"           value={status?.status}                                loading={loading} />
          <InfoRow label="Total Chunks"     value={status?.chunk_count ?? status?.faiss_size}     loading={loading} />
          <InfoRow label="Active Vectors"   value={status?.active_vectors ?? status?.chunk_count} loading={loading} />
          <InfoRow label="Deleted Vectors"  value={status?.deleted_vectors ?? status?.deleted_count ?? 0} loading={loading} />
          <InfoRow
            label="Compaction Status"
            value={
              loading ? undefined :
              status?.needs_compaction
                ? "Compaction recommended"
                : "Index is compact"
            }
            loading={loading}
          />
          <InfoRow label="BM25 Index Size"  value={status?.bm25_size ?? status?.bm25_doc_count}  loading={loading} />
          <InfoRow label="Total Documents"  value={status?.total_documents}                       loading={loading} />
          <InfoRow
            label="Last Updated"
            value={
              status?.last_updated
                ? new Date(status.last_updated).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })
                : undefined
            }
            loading={loading}
          />
        </div>
      </div>

      {/* Rollback control */}
      <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm p-5 space-y-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-amber-500/10 text-amber-600">
            <RotateCcw className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">Rollback Index</p>
            <p className="text-xs text-muted-foreground">Restore the FAISS index to a previous snapshot</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <select
              value={rollSteps}
              onChange={(e) => setRollSteps(Number(e.target.value))}
              className="appearance-none rounded-xl border border-border/40 bg-card/80 px-3 py-2 text-sm text-foreground pr-8 focus:outline-none focus:ring-2 focus:ring-primary/30"
            >
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>{n} step{n > 1 ? "s" : ""}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
          </div>
          {snapshots.length > 0 && rollSteps <= snapshots.length && (
            <span className="text-xs text-muted-foreground">
              → {snapshots[rollSteps - 1]?.label || snapshots[rollSteps - 1]?.name || `Snapshot ${rollSteps}`}
            </span>
          )}
        </div>

        <Button
          variant="outline"
          onClick={handleRollback}
          disabled={rolling || loading || snapshots.length === 0}
          className="gap-2 rounded-xl border-amber-500/30 text-amber-600 hover:bg-amber-500/10 hover:text-amber-600"
        >
          <RotateCcw className={cn("h-4 w-4", rolling && "animate-spin")} />
          {rolling ? "Rolling back…" : `Rollback ${rollSteps} step${rollSteps > 1 ? "s" : ""}`}
        </Button>

        {snapshots.length === 0 && !loading && (
          <p className="text-xs text-muted-foreground">No snapshots available to roll back to.</p>
        )}
      </div>

      {/* Audit log */}
      <AuditLogSection />

      {/* Danger zone */}
      <div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-5 space-y-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-red-500/10 text-red-500">
            <Shield className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-semibold text-red-600">Danger Zone</p>
            <p className="text-xs text-muted-foreground">Irreversible operations — use with caution</p>
          </div>
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between p-3 rounded-xl border border-red-500/15 bg-card/50">
            <div>
              <p className="text-sm font-medium text-foreground">Hard Delete All Deleted Documents</p>
              <p className="text-xs text-muted-foreground">Permanently removes soft-deleted documents from FAISS</p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              disabled
              className="gap-1.5 rounded-xl opacity-50 cursor-not-allowed"
              title="Coming soon"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Coming Soon
            </Button>
          </div>
          <div className="flex items-center justify-between p-3 rounded-xl border border-red-500/15 bg-card/50">
            <div>
              <p className="text-sm font-medium text-foreground">Compact FAISS Index</p>
              <p className="text-xs text-muted-foreground">Rebuild index to reclaim space from deleted vectors</p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              disabled
              className="gap-1.5 rounded-xl opacity-50 cursor-not-allowed"
              title="Coming soon"
            >
              <Database className="h-3.5 w-3.5" />
              Coming Soon
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
