/**
 * AdminDashboard — full-screen knowledge management panel.
 * Tabs: Overview · Chunks · Documents · Gaps · Crawler · Index · Audit
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  verifyAdminKey, setAdminKey, getAdminKey, clearAdminKey,
  fetchAdminAnalytics, fetchAdminStatus,
  fetchChunks, ingestChunks, deleteChunks,
  fetchDocuments, uploadDocument, deleteDocument, restoreDocument,
  fetchKnowledgeGaps, updateKnowledgeGap,
  fetchSnapshots, rollbackIndex,
  fetchCrawlerSources, triggerCrawler,
  fetchAuditLog, testEmail,
} from "@/lib/admin-api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DOMAINS = ["Mental Health", "Legal", "Government Schemes", "Safety"];
const GAP_STATUSES = ["open", "solved", "ignored"];

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  } catch { return iso; }
}

function fmtBytes(n) {
  if (!n) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function Badge({ children, color = "default" }) {
  const cls = {
    default: "bg-muted text-muted-foreground",
    green:   "bg-emerald-100 text-emerald-800",
    amber:   "bg-amber-100 text-amber-800",
    red:     "bg-red-100 text-red-800",
    blue:    "bg-blue-100 text-blue-800",
    purple:  "bg-purple-100 text-purple-800",
  }[color] ?? "bg-muted text-muted-foreground";
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide", cls)}>
      {children}
    </span>
  );
}

function StatusBadge({ status }) {
  const map = { active: "green", deleted: "red", open: "amber", solved: "green", ignored: "default", ok: "green", error: "red", pending: "amber" };
  return <Badge color={map[status] ?? "default"}>{status}</Badge>;
}

function SectionTitle({ children }) {
  return <h3 className="text-sm font-semibold text-foreground/80 mb-3">{children}</h3>;
}

function ErrMsg({ msg }) {
  if (!msg) return null;
  return <p className="mt-2 text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2">{msg}</p>;
}

function OkMsg({ msg }) {
  if (!msg) return null;
  return <p className="mt-2 text-xs text-emerald-700 bg-emerald-50 rounded-lg px-3 py-2">{msg}</p>;
}

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4 text-primary" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}

function StatCard({ label, value, sub, color = "default" }) {
  const colors = {
    default: "border-border/40",
    blue: "border-blue-200 bg-blue-50/50",
    green: "border-emerald-200 bg-emerald-50/50",
    amber: "border-amber-200 bg-amber-50/50",
    red: "border-red-200 bg-red-50/50",
  };
  return (
    <div className={cn("rounded-2xl border p-4", colors[color])}>
      <p className="text-[11px] text-muted-foreground uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-bold text-foreground">{value ?? "—"}</p>
      {sub && <p className="text-[11px] text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  );
}

function useLoad(fn, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fn();
      setData(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => { load(); }, [load]);

  return { data, loading, error, reload: load };
}

// ---------------------------------------------------------------------------
// Tab: Overview
// ---------------------------------------------------------------------------
function OverviewTab() {
  const { data, loading, error, reload } = useLoad(fetchAdminAnalytics);
  const { data: status } = useLoad(fetchAdminStatus);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <SectionTitle>System Overview</SectionTitle>
        <Button variant="ghost" size="sm" onClick={reload} disabled={loading}>
          {loading ? <Spinner /> : "Refresh"}
        </Button>
      </div>
      <ErrMsg msg={error} />
      {data && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <StatCard
            label="Chunks in Index"
            value={status?.chunksInIndex ?? data.rag?.chunksInIndex}
            sub={status?.ragReady ? "RAG ready" : "RAG not ready"}
            color={status?.ragReady ? "green" : "red"}
          />
          <StatCard
            label="Open Gaps"
            value={data.knowledgeGaps?.open}
            sub="unanswered queries"
            color={data.knowledgeGaps?.open > 0 ? "amber" : "green"}
          />
          <StatCard
            label="Documents"
            value={data.documents?.total}
            sub={`${data.documents?.active ?? 0} active`}
            color="blue"
          />
          <StatCard
            label="Feedback"
            value={data.feedback?.total ?? "—"}
            sub={`👍 ${data.feedback?.up ?? 0} · 👎 ${data.feedback?.down ?? 0}`}
            color="default"
          />
        </div>
      )}
      {status && (
        <div className="rounded-2xl border border-border/40 p-4">
          <p className="text-[11px] text-muted-foreground uppercase tracking-wider mb-3">Index Health</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div>
              <span className="text-muted-foreground text-[11px]">Total Vectors</span>
              <p className="font-semibold">{status.totalVectors}</p>
            </div>
            <div>
              <span className="text-muted-foreground text-[11px]">Live Chunks</span>
              <p className="font-semibold">{status.chunksInIndex}</p>
            </div>
            <div>
              <span className="text-muted-foreground text-[11px]">Deleted (waste)</span>
              <p className="font-semibold">{status.deletedVectors}</p>
            </div>
            <div>
              <span className="text-muted-foreground text-[11px]">Compaction</span>
              <p className={cn("font-semibold", status.compactionNeeded ? "text-amber-600" : "text-emerald-600")}>
                {status.compactionNeeded ? "Needed" : "OK"}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Knowledge Chunks
// ---------------------------------------------------------------------------
function ChunksTab() {
  const [domain, setDomain] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [selected, setSelected] = useState(new Set());
  const [deleting, setDeleting] = useState(false);

  // Add chunk form
  const [showAdd, setShowAdd] = useState(false);
  const [newChunk, setNewChunk] = useState({ topic: "", domain: "Mental Health", text: "", source: "" });
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchChunks(domain || undefined, page);
      setData(res);
      setSelected(new Set());
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [domain, page]);

  useEffect(() => { load(); }, [load]);

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleDelete = async () => {
    if (!selected.size) return;
    if (!confirm(`Delete ${selected.size} chunk(s)? This is reversible via rollback.`)) return;
    setDeleting(true);
    setError("");
    try {
      const res = await deleteChunks([...selected]);
      setOk(`Deleted ${res.removed} chunk(s). Index now has ${res.totalInIndex} chunks.`);
      await load();
    } catch (e) { setError(e.message); }
    finally { setDeleting(false); }
  };

  const handleAdd = async () => {
    if (!newChunk.topic.trim() || !newChunk.text.trim()) {
      setError("Topic and text are required.");
      return;
    }
    setAdding(true);
    setError("");
    setOk("");
    try {
      const res = await ingestChunks([newChunk]);
      setOk(`Added ${res.added} chunk(s). Index now has ${res.totalInIndex} chunks.`);
      setNewChunk({ topic: "", domain: "Mental Health", text: "", source: "" });
      setShowAdd(false);
      await load();
    } catch (e) { setError(e.message); }
    finally { setAdding(false); }
  };

  const totalPages = data ? Math.ceil(data.total / (data.pageSize || 50)) : 1;

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <SectionTitle>Knowledge Chunks</SectionTitle>
        <div className="flex gap-2 flex-wrap">
          <select
            value={domain}
            onChange={(e) => { setDomain(e.target.value); setPage(1); }}
            className="text-xs rounded-lg border border-border/50 bg-card px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="">All domains</option>
            {DOMAINS.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            {loading ? <Spinner /> : "Refresh"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setShowAdd((v) => !v)}>
            {showAdd ? "Cancel" : "+ Add Chunk"}
          </Button>
          {selected.size > 0 && (
            <Button variant="destructive" size="sm" onClick={handleDelete} disabled={deleting}>
              {deleting ? <Spinner /> : `Delete ${selected.size}`}
            </Button>
          )}
        </div>
      </div>

      <ErrMsg msg={error} />
      <OkMsg msg={ok} />

      {showAdd && (
        <div className="mb-4 rounded-2xl border border-border/50 p-4 space-y-3">
          <p className="text-sm font-semibold">Add Knowledge Chunk</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] text-muted-foreground mb-1 block">Topic *</label>
              <Input
                value={newChunk.topic}
                onChange={(e) => setNewChunk((p) => ({ ...p, topic: e.target.value }))}
                placeholder="e.g. POCSO Act overview"
                maxLength={200}
              />
            </div>
            <div>
              <label className="text-[11px] text-muted-foreground mb-1 block">Domain *</label>
              <select
                value={newChunk.domain}
                onChange={(e) => setNewChunk((p) => ({ ...p, domain: e.target.value }))}
                className="w-full text-sm rounded-lg border border-border/50 bg-card px-3 py-2 focus:outline-none focus:ring-1 focus:ring-primary"
              >
                {DOMAINS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="text-[11px] text-muted-foreground mb-1 block">Text * (10–4000 chars)</label>
            <textarea
              value={newChunk.text}
              onChange={(e) => setNewChunk((p) => ({ ...p, text: e.target.value }))}
              placeholder="Knowledge text that will be embedded and indexed…"
              rows={4}
              maxLength={4000}
              className="w-full text-sm rounded-lg border border-border/50 bg-card px-3 py-2 resize-y focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          <div>
            <label className="text-[11px] text-muted-foreground mb-1 block">Source URL (optional)</label>
            <Input
              value={newChunk.source}
              onChange={(e) => setNewChunk((p) => ({ ...p, source: e.target.value }))}
              placeholder="https://…"
              maxLength={500}
            />
          </div>
          <Button onClick={handleAdd} disabled={adding} size="sm">
            {adding ? <Spinner /> : "Add to Index"}
          </Button>
        </div>
      )}

      {data && (
        <>
          <p className="text-[11px] text-muted-foreground mb-3">
            {data.total} chunk{data.total !== 1 ? "s" : ""} total
            {selected.size > 0 && ` · ${selected.size} selected`}
          </p>

          <div className="space-y-2">
            {data.chunks.map((chunk) => (
              <div
                key={chunk.id}
                className={cn(
                  "rounded-xl border p-3 cursor-pointer transition-colors text-left",
                  selected.has(chunk.id)
                    ? "border-primary bg-primary/5"
                    : "border-border/40 hover:border-border/70 hover:bg-muted/30"
                )}
                onClick={() => toggleSelect(chunk.id)}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{chunk.topic || chunk.id}</p>
                    <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">{chunk.text}</p>
                  </div>
                  <div className="shrink-0 flex flex-col items-end gap-1">
                    <Badge color="blue">{chunk.domain}</Badge>
                    <span className="text-[10px] text-muted-foreground/60">{chunk.id}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-4">
              <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>
                Prev
              </Button>
              <span className="text-xs text-muted-foreground">Page {page} of {totalPages}</span>
              <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
                Next
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Documents
// ---------------------------------------------------------------------------
function DocumentsTab() {
  const [domainFilter, setDomainFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [docs, setDocs] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  // Upload state
  const [file, setFile] = useState(null);
  const [uploadDomain, setUploadDomain] = useState("Mental Health");
  const [uploadTopic, setUploadTopic] = useState("");
  const [uploadSource, setUploadSource] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchDocuments(domainFilter || undefined, statusFilter || undefined);
      setDocs(res.documents);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [domainFilter, statusFilter]);

  useEffect(() => { load(); }, [load]);

  const handleUpload = async () => {
    if (!file) { setError("Please select a file."); return; }
    setUploading(true);
    setError("");
    setOk("");
    try {
      const res = await uploadDocument(file, uploadDomain, uploadTopic, uploadSource);
      setOk(`Uploaded "${res.filename}" → ${res.chunksAdded} chunks added (ID: ${res.docId}).`);
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      await load();
    } catch (e) { setError(e.message); }
    finally { setUploading(false); }
  };

  const handleDelete = async (docId, filename, hard) => {
    const action = hard ? "permanently delete" : "soft-delete";
    if (!confirm(`${action} "${filename}"?`)) return;
    setError("");
    setOk("");
    try {
      const res = await deleteDocument(docId, hard);
      setOk(`Deleted "${filename}" — ${res.chunksRemoved} chunks removed.`);
      await load();
    } catch (e) { setError(e.message); }
  };

  const handleRestore = async (docId, filename) => {
    setError("");
    setOk("");
    try {
      await restoreDocument(docId);
      setOk(`Restored "${filename}".`);
      await load();
    } catch (e) { setError(e.message); }
  };

  return (
    <div>
      {/* Upload section */}
      <div className="mb-5 rounded-2xl border border-border/50 p-4 space-y-3">
        <p className="text-sm font-semibold">Upload Document</p>
        <p className="text-[11px] text-muted-foreground">Accepted: .pdf, .docx, .md, .txt, .json — max 10 MB</p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-[11px] text-muted-foreground mb-1 block">Domain *</label>
            <select
              value={uploadDomain}
              onChange={(e) => setUploadDomain(e.target.value)}
              className="w-full text-sm rounded-lg border border-border/50 bg-card px-3 py-2 focus:outline-none focus:ring-1 focus:ring-primary"
            >
              {DOMAINS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[11px] text-muted-foreground mb-1 block">Topic (optional)</label>
            <Input
              value={uploadTopic}
              onChange={(e) => setUploadTopic(e.target.value)}
              placeholder="Inferred from filename if blank"
              maxLength={200}
            />
          </div>
          <div>
            <label className="text-[11px] text-muted-foreground mb-1 block">Source URL (optional)</label>
            <Input
              value={uploadSource}
              onChange={(e) => setUploadSource(e.target.value)}
              placeholder="https://…"
              maxLength={500}
            />
          </div>
        </div>
        <div className="flex items-center gap-3">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.md,.txt,.json"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-xs text-muted-foreground file:mr-3 file:text-xs file:rounded-lg file:border-0 file:bg-primary/10 file:text-primary file:px-3 file:py-1.5 file:font-medium file:cursor-pointer hover:file:bg-primary/20"
          />
          <Button onClick={handleUpload} disabled={uploading || !file} size="sm">
            {uploading ? <Spinner /> : "Upload & Ingest"}
          </Button>
        </div>
      </div>

      <ErrMsg msg={error} />
      <OkMsg msg={ok} />

      {/* Filter row */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <SectionTitle>Uploaded Documents</SectionTitle>
        <div className="flex gap-2">
          <select
            value={domainFilter}
            onChange={(e) => setDomainFilter(e.target.value)}
            className="text-xs rounded-lg border border-border/50 bg-card px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="">All domains</option>
            {DOMAINS.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs rounded-lg border border-border/50 bg-card px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="deleted">Deleted</option>
          </select>
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            {loading ? <Spinner /> : "Refresh"}
          </Button>
        </div>
      </div>

      {docs && (
        <div className="space-y-2">
          {docs.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">No documents found.</p>
          )}
          {docs.map((doc) => (
            <div key={doc.docId || doc._id} className="rounded-xl border border-border/40 p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{doc.filename}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {doc.domain} · {doc.chunkIds?.length ?? 0} chunks · {fmtBytes(doc.sizeBytes)} · {fmtDate(doc.uploadedAt)}
                  </p>
                  {doc.topic && <p className="text-[11px] text-muted-foreground/70 mt-0.5">Topic: {doc.topic}</p>}
                </div>
                <div className="shrink-0 flex flex-col items-end gap-2">
                  <StatusBadge status={doc.status} />
                  <div className="flex gap-1.5">
                    {doc.status !== "deleted" && (
                      <button
                        type="button"
                        onClick={() => handleDelete(doc.docId, doc.filename, false)}
                        className="text-[11px] text-red-600 hover:text-red-700 hover:underline"
                      >
                        Delete
                      </button>
                    )}
                    {doc.status !== "deleted" && (
                      <button
                        type="button"
                        onClick={() => handleDelete(doc.docId, doc.filename, true)}
                        className="text-[11px] text-red-800 hover:underline"
                      >
                        Hard delete
                      </button>
                    )}
                    {doc.status === "deleted" && (
                      <button
                        type="button"
                        onClick={() => handleRestore(doc.docId, doc.filename)}
                        className="text-[11px] text-emerald-600 hover:underline"
                      >
                        Restore
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Knowledge Gaps
// ---------------------------------------------------------------------------
function GapsTab() {
  const [statusFilter, setStatusFilter] = useState("open");
  const [gaps, setGaps] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [updating, setUpdating] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchKnowledgeGaps(statusFilter || undefined);
      setGaps(res.gaps);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  const handleUpdate = async (gapId, newStatus) => {
    setUpdating((p) => ({ ...p, [gapId]: true }));
    setError("");
    setOk("");
    try {
      await updateKnowledgeGap(gapId, newStatus);
      setOk(`Gap marked as "${newStatus}".`);
      await load();
    } catch (e) { setError(e.message); }
    finally { setUpdating((p) => ({ ...p, [gapId]: false })); }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <SectionTitle>Knowledge Gaps</SectionTitle>
        <div className="flex gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs rounded-lg border border-border/50 bg-card px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="">All</option>
            {GAP_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            {loading ? <Spinner /> : "Refresh"}
          </Button>
        </div>
      </div>
      <ErrMsg msg={error} />
      <OkMsg msg={ok} />
      {gaps && (
        <div className="space-y-2">
          {gaps.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">No knowledge gaps found.</p>
          )}
          {gaps.map((gap) => (
            <div key={gap._id || gap.id} className="rounded-xl border border-border/40 p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium line-clamp-2">{gap.query || gap.question}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {gap.domain && <span className="mr-2">{gap.domain}</span>}
                    {gap.confidence && <span className="mr-2">conf: {gap.confidence}</span>}
                    {gap.createdAt && <span>{fmtDate(gap.createdAt)}</span>}
                  </p>
                </div>
                <div className="shrink-0 flex flex-col items-end gap-2">
                  <StatusBadge status={gap.status || "open"} />
                  <div className="flex gap-1.5">
                    {gap.status !== "solved" && (
                      <button
                        type="button"
                        disabled={updating[gap._id || gap.id]}
                        onClick={() => handleUpdate(gap._id || gap.id, "solved")}
                        className="text-[11px] text-emerald-600 hover:underline disabled:opacity-50"
                      >
                        Mark solved
                      </button>
                    )}
                    {gap.status !== "ignored" && (
                      <button
                        type="button"
                        disabled={updating[gap._id || gap.id]}
                        onClick={() => handleUpdate(gap._id || gap.id, "ignored")}
                        className="text-[11px] text-muted-foreground hover:underline disabled:opacity-50"
                      >
                        Ignore
                      </button>
                    )}
                    {gap.status !== "open" && (
                      <button
                        type="button"
                        disabled={updating[gap._id || gap.id]}
                        onClick={() => handleUpdate(gap._id || gap.id, "open")}
                        className="text-[11px] text-amber-600 hover:underline disabled:opacity-50"
                      >
                        Reopen
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Crawler
// ---------------------------------------------------------------------------
function CrawlerTab() {
  const { data, loading, error, reload } = useLoad(fetchCrawlerSources);
  const [triggering, setTriggering] = useState(false);
  const [triggerOk, setTriggerOk] = useState("");
  const [triggerErr, setTriggerErr] = useState("");

  const handleTrigger = async () => {
    if (!confirm("Trigger a full knowledge crawl? This runs in the background and may take several minutes.")) return;
    setTriggering(true);
    setTriggerOk("");
    setTriggerErr("");
    try {
      const res = await triggerCrawler();
      setTriggerOk(res.message || "Crawler triggered.");
    } catch (e) { setTriggerErr(e.message); }
    finally { setTriggering(false); }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <SectionTitle>Crawler Sources</SectionTitle>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={reload} disabled={loading}>
            {loading ? <Spinner /> : "Refresh"}
          </Button>
          <Button size="sm" onClick={handleTrigger} disabled={triggering}>
            {triggering ? <Spinner /> : "Trigger Crawl"}
          </Button>
        </div>
      </div>
      <ErrMsg msg={error} />
      <ErrMsg msg={triggerErr} />
      <OkMsg msg={triggerOk} />
      {data?.sources?.length === 0 && (
        <p className="text-sm text-muted-foreground text-center py-8">
          No sources recorded yet — they appear after the first crawl cycle runs.
        </p>
      )}
      {data?.sources && data.sources.length > 0 && (
        <div className="space-y-2">
          {data.sources.map((src) => (
            <div key={src.sourceId} className="rounded-xl border border-border/40 p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{src.sourceId}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5 truncate">{src.url}</p>
                  <p className="text-[11px] text-muted-foreground/70 mt-0.5">
                    Checked: {fmtDate(src.lastChecked)} · Updated: {fmtDate(src.lastUpdated)}
                    {src.version && ` · v${src.version}`}
                  </p>
                  {src.lastError && (
                    <p className="text-[11px] text-red-600 mt-0.5">Error: {src.lastError}</p>
                  )}
                </div>
                <StatusBadge status={src.status || "pending"} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Index Management
// ---------------------------------------------------------------------------
function IndexTab() {
  const { data: statusData, loading: statusLoading, reload: reloadStatus } = useLoad(fetchAdminStatus);
  const { data: snapsData, loading: snapsLoading, reload: reloadSnaps } = useLoad(fetchSnapshots);
  const [rolling, setRolling] = useState(false);
  const [steps, setSteps] = useState(1);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const handleRollback = async () => {
    if (!confirm(`Roll back the index by ${steps} snapshot(s)? This affects the live index immediately.`)) return;
    setRolling(true);
    setError("");
    setOk("");
    try {
      const res = await rollbackIndex(steps);
      setOk(`Rolled back ${res.steps} step(s). Index now has ${res.totalInIndex} chunks.`);
      await Promise.all([reloadStatus(), reloadSnaps()]);
    } catch (e) { setError(e.message); }
    finally { setRolling(false); }
  };

  const loading = statusLoading || snapsLoading;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <SectionTitle>Index Management</SectionTitle>
        <Button variant="outline" size="sm" onClick={() => { reloadStatus(); reloadSnaps(); }} disabled={loading}>
          {loading ? <Spinner /> : "Refresh"}
        </Button>
      </div>
      <ErrMsg msg={error} />
      <OkMsg msg={ok} />

      {statusData && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
          <StatCard label="Live Chunks" value={statusData.chunksInIndex} color="green" />
          <StatCard label="Total Vectors" value={statusData.totalVectors} color="blue" />
          <StatCard label="Deleted (waste)" value={statusData.deletedVectors} color={statusData.deletedVectors > 0 ? "amber" : "default"} />
          <StatCard
            label="Compaction"
            value={statusData.compactionNeeded ? "Needed" : "OK"}
            color={statusData.compactionNeeded ? "amber" : "green"}
          />
        </div>
      )}

      <div className="rounded-2xl border border-border/50 p-4 mb-4">
        <p className="text-sm font-semibold mb-3">Rollback Index</p>
        <p className="text-[12px] text-muted-foreground mb-3">
          Restore the FAISS index to a previous snapshot. The index is auto-snapshotted after each ingest.
        </p>
        <div className="flex items-center gap-3">
          <label className="text-xs text-muted-foreground whitespace-nowrap">Steps back:</label>
          <Input
            type="number"
            min={1}
            max={5}
            value={steps}
            onChange={(e) => setSteps(Math.max(1, Math.min(5, parseInt(e.target.value) || 1)))}
            className="w-20"
          />
          <Button variant="destructive" size="sm" onClick={handleRollback} disabled={rolling}>
            {rolling ? <Spinner /> : "Rollback"}
          </Button>
        </div>
      </div>

      {snapsData && (
        <div>
          <p className="text-[11px] text-muted-foreground uppercase tracking-wider mb-2">Available Snapshots ({snapsData.count})</p>
          {snapsData.snapshots.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-6">No snapshots yet.</p>
          )}
          <div className="space-y-2">
            {snapsData.snapshots.map((snap, i) => (
              <div key={snap.name || i} className="rounded-xl border border-border/40 p-3 flex items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-medium">{snap.name || `Snapshot ${i + 1}`}</p>
                  {snap.created && <p className="text-[11px] text-muted-foreground">{fmtDate(snap.created)}</p>}
                  {snap.size && <p className="text-[11px] text-muted-foreground">{fmtBytes(snap.size)}</p>}
                </div>
                <span className="text-[11px] text-muted-foreground/60">step {i + 1}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Audit Log
// ---------------------------------------------------------------------------
function AuditTab() {
  const [limit, setLimit] = useState(100);
  const { data, loading, error, reload } = useLoad(() => fetchAuditLog(limit), [limit]);

  const ACTION_COLORS = {
    ingest: "green",
    delete: "red",
    rollback: "amber",
    trigger_crawler: "blue",
    ingest_document: "green",
    soft_delete_document: "red",
    hard_delete_document: "red",
    restore_document: "green",
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <SectionTitle>Audit Log</SectionTitle>
        <div className="flex gap-2 items-center">
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="text-xs rounded-lg border border-border/50 bg-card px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
          >
            {[50, 100, 200, 500].map((n) => <option key={n} value={n}>Last {n}</option>)}
          </select>
          <Button variant="outline" size="sm" onClick={reload} disabled={loading}>
            {loading ? <Spinner /> : "Refresh"}
          </Button>
        </div>
      </div>
      <ErrMsg msg={error} />
      {data && (
        <div className="space-y-2">
          {data.entries.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">No audit log entries yet.</p>
          )}
          {data.entries.map((entry, i) => (
            <div key={entry._id || i} className="rounded-xl border border-border/40 p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge color={ACTION_COLORS[entry.action] ?? "default"}>{entry.action}</Badge>
                    <span className="text-[11px] text-muted-foreground">{fmtDate(entry.ts || entry.createdAt)}</span>
                  </div>
                  {entry.detail && (
                    <pre className="text-[10px] text-muted-foreground bg-muted/40 rounded-lg px-2 py-1 overflow-x-auto whitespace-pre-wrap">
                      {JSON.stringify(entry.detail, null, 2)}
                    </pre>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Email
// ---------------------------------------------------------------------------
function EmailTab() {
  const [to, setTo] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const handleTest = async () => {
    if (!to.trim()) { setError("Enter a recipient email address."); return; }
    setSending(true);
    setError("");
    setResult(null);
    try {
      const res = await testEmail(to.trim());
      setResult(res);
    } catch (e) { setError(e.message); }
    finally { setSending(false); }
  };

  return (
    <div>
      <SectionTitle>Email Delivery</SectionTitle>

      {/* Config status */}
      <div className="rounded-2xl border border-border/50 p-4 mb-5 space-y-2 text-sm">
        <p className="font-medium text-foreground/80 mb-2">Current configuration</p>
        <p className="text-[12px] text-muted-foreground">
          Email is sent via <strong>Resend API</strong> (if <code className="text-xs bg-muted px-1 rounded">RESEND_API_KEY</code> is set)
          or <strong>SMTP</strong> (if <code className="text-xs bg-muted px-1 rounded">SMTP_HOST + SMTP_USER + SMTP_PASSWORD</code> are set).
          If neither is configured, emails are only printed to the server console.
        </p>
        <div className="mt-3 rounded-xl bg-muted/40 px-4 py-3 text-[11px] text-muted-foreground space-y-1 font-mono">
          <p><strong>Gmail setup (recommended):</strong></p>
          <p>SMTP_HOST=smtp.gmail.com</p>
          <p>SMTP_PORT=587</p>
          <p>SMTP_USER=your-gmail@gmail.com</p>
          <p>SMTP_PASSWORD={"<16-char App Password>"}</p>
          <p>SMTP_FROM=your-gmail@gmail.com</p>
          <p>APP_BASE_URL=https://your-app.hf.space</p>
          <p className="text-amber-600 mt-1 font-sans not-italic">
            ⚠ Use an App Password, NOT your regular Gmail password.<br />
            Enable at: myaccount.google.com/apppasswords (needs 2FA turned on)
          </p>
        </div>
      </div>

      {/* Test send */}
      <div className="rounded-2xl border border-border/50 p-4 space-y-3">
        <p className="text-sm font-semibold">Send a test email</p>
        <div className="flex gap-2">
          <Input
            type="email"
            placeholder="recipient@example.com"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleTest()}
          />
          <Button onClick={handleTest} disabled={sending || !to.trim()} size="sm">
            {sending ? <Spinner /> : "Send test"}
          </Button>
        </div>
        <ErrMsg msg={error} />
        {result && (
          <div className={cn(
            "rounded-xl px-4 py-3 text-sm",
            result.ok ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"
          )}>
            {result.ok ? (
              <p>✓ Test email delivered via <strong>{result.provider}</strong> to <strong>{result.to}</strong>. Check your inbox.</p>
            ) : (
              <div>
                <p className="font-medium mb-1">Delivery failed</p>
                <p className="text-[12px]">{result.error}</p>
                <p className="text-[11px] mt-2 opacity-70">Check SMTP/Resend credentials in server/.env and restart the server.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Admin Key Gate
// ---------------------------------------------------------------------------
function AdminKeyGate({ onSuccess }) {
  const [key, setKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!key.trim()) return;
    setLoading(true);
    setError("");
    const valid = await verifyAdminKey(key.trim());
    setLoading(false);
    if (valid) {
      setAdminKey(key.trim());
      onSuccess();
    } else {
      setError("Invalid admin key. Check your ADMIN_KEY env var.");
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[300px] max-w-sm mx-auto">
      <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary">
          <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
        </svg>
      </div>
      <h2 className="font-headline text-lg font-semibold mb-1">Admin Access</h2>
      <p className="text-sm text-muted-foreground text-center mb-5">Enter your ADMIN_KEY to continue.</p>
      <form onSubmit={handleSubmit} className="w-full space-y-3">
        <Input
          type="password"
          placeholder="Admin key…"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          autoFocus
          className="text-center"
        />
        <Button type="submit" className="w-full" disabled={loading || !key.trim()}>
          {loading ? <Spinner /> : "Unlock Dashboard"}
        </Button>
      </form>
      <ErrMsg msg={error} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main AdminDashboard component
// ---------------------------------------------------------------------------

const TABS = [
  { id: "overview",   label: "Overview" },
  { id: "chunks",     label: "Chunks" },
  { id: "documents",  label: "Documents" },
  { id: "gaps",       label: "Gaps" },
  { id: "crawler",    label: "Crawler" },
  { id: "index",      label: "Index" },
  { id: "email",      label: "Email" },
  { id: "audit",      label: "Audit Log" },
];

export function AdminDashboard({ onClose }) {
  const [authed, setAuthed] = useState(() => !!getAdminKey());
  const [activeTab, setActiveTab] = useState("overview");

  // Trap focus inside the modal
  const panelRef = useRef(null);
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-background/80 backdrop-blur-sm overflow-y-auto"
      onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}
    >
      <div
        ref={panelRef}
        className="relative w-full max-w-5xl mx-4 my-6 rounded-3xl border border-border/50 bg-card shadow-2xl animate-in fade-in-0 zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border/40">
          <div>
            <h2 className="font-headline text-lg font-semibold">Knowledge Dashboard</h2>
            <p className="text-[11px] text-muted-foreground">Admin · knowledge management</p>
          </div>
          <div className="flex items-center gap-2">
            {authed && (
              <button
                type="button"
                onClick={() => { clearAdminKey(); setAuthed(false); }}
                className="text-[11px] text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded-lg hover:bg-muted"
              >
                Lock
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close admin dashboard"
              className="rounded-full p-1.5 hover:bg-muted transition-colors"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>

        {!authed ? (
          <div className="p-6">
            <AdminKeyGate onSuccess={() => setAuthed(true)} />
          </div>
        ) : (
          <div className="flex flex-col sm:flex-row min-h-[600px]">
            {/* Sidebar navigation */}
            <nav className="sm:w-40 shrink-0 border-b sm:border-b-0 sm:border-r border-border/40 flex sm:flex-col gap-1 overflow-x-auto sm:overflow-x-visible px-3 py-3">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "whitespace-nowrap sm:whitespace-normal text-left px-3 py-2 rounded-xl text-sm transition-colors shrink-0 sm:shrink",
                    activeTab === tab.id
                      ? "bg-primary/10 text-primary font-medium"
                      : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </nav>

            {/* Tab content */}
            <div className="flex-1 min-w-0 p-5 sm:p-6 overflow-y-auto max-h-[80vh]">
              {activeTab === "overview"  && <OverviewTab />}
              {activeTab === "chunks"    && <ChunksTab />}
              {activeTab === "documents" && <DocumentsTab />}
              {activeTab === "gaps"      && <GapsTab />}
              {activeTab === "crawler"   && <CrawlerTab />}
              {activeTab === "index"     && <IndexTab />}
              {activeTab === "email"     && <EmailTab />}
              {activeTab === "audit"     && <AuditTab />}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
