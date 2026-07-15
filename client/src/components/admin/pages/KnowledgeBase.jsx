import { useState, useEffect, useCallback, useRef } from "react";
import {
  Search,
  Upload,
  Trash2,
  RotateCcw,
  Eye,
  X,
  FileText,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  CloudUpload,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  fetchDocuments,
  fetchDocument,
  deleteDocument,
  restoreDocument,
  uploadDocument,
} from "@/lib/adminApi";
import { useToast } from "@/hooks/use-toast";

const DOMAINS = ["Mental Health", "Legal", "Government Schemes", "Safety"];
const LANGUAGES = ["en", "hi", "mr", "ta", "te", "bn", "gu", "kn", "ml", "pa"];
const FILE_TYPES = ["pdf", "txt", "docx", "md", "csv"];

function Skeleton({ className }) {
  return <div className={cn("animate-pulse rounded-lg bg-muted/50", className)} />;
}

function StatusBadge({ status }) {
  const map = {
    active:   { label: "Active",   cls: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20" },
    deleted:  { label: "Deleted",  cls: "bg-red-500/10 text-red-500 border-red-500/20" },
    indexed:  { label: "Indexed",  cls: "bg-blue-500/10 text-blue-600 border-blue-500/20" },
    pending:  { label: "Pending",  cls: "bg-amber-500/10 text-amber-600 border-amber-500/20" },
  };
  const cfg = map[status?.toLowerCase()] || { label: status || "—", cls: "bg-muted text-muted-foreground border-border/40" };
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium border", cfg.cls)}>
      {cfg.label}
    </span>
  );
}

function Select({ value, onChange, options, placeholder, className }) {
  return (
    <div className={cn("relative", className)}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full appearance-none rounded-xl border border-border/40 bg-card/80 px-3 py-2 text-sm text-foreground pr-8 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all"
      >
        <option value="">{placeholder}</option>
        {options.map((o) => (
          <option key={typeof o === "string" ? o : o.value} value={typeof o === "string" ? o : o.value}>
            {typeof o === "string" ? o : o.label}
          </option>
        ))}
      </select>
      <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
    </div>
  );
}

function DocDetailModal({ docId, onClose }) {
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    if (!docId) return;
    setLoading(true);
    fetchDocument(docId)
      .then(setDoc)
      .catch((err) => toast({ title: "Failed to load document", description: err?.message, variant: "destructive" }))
      .finally(() => setLoading(false));
  }, [docId, toast]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="relative w-full max-w-2xl max-h-[85vh] flex flex-col rounded-2xl border border-border/40 bg-card shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border/30">
          <h2 className="text-base font-semibold text-foreground">Document Detail</h2>
          <button
            onClick={onClose}
            className="h-7 w-7 flex items-center justify-center rounded-lg hover:bg-muted/50 text-muted-foreground transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-5 w-full" />)}
            </div>
          ) : !doc ? (
            <div className="text-center text-sm text-muted-foreground py-8">Document not found</div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3 text-sm">
                {[
                  ["Filename",  doc.filename || doc.name],
                  ["Domain",    doc.domain],
                  ["Type",      doc.file_type || doc.type],
                  ["Status",    <StatusBadge key="s" status={doc.status} />],
                  ["Chunks",    doc.chunk_count ?? "—"],
                  ["Size",      doc.file_size ? `${(doc.file_size / 1024).toFixed(1)} KB` : "—"],
                  ["Language",  doc.language || "—"],
                  ["Source",    doc.source || "—"],
                  ["Topic",     doc.topic || "—"],
                  ["Indexed",   doc.indexed_at ? new Date(doc.indexed_at).toLocaleString() : "—"],
                ].map(([k, v]) => (
                  <div key={k} className="flex flex-col gap-0.5">
                    <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">{k}</span>
                    <span className="text-foreground">{v}</span>
                  </div>
                ))}
              </div>

              {/* Live chunks */}
              {doc.liveChunks?.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                    Live Chunks ({doc.liveChunks.length})
                  </h3>
                  <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                    {doc.liveChunks.map((chunk, i) => (
                      <div
                        key={chunk.id || i}
                        className="rounded-xl border border-border/30 bg-muted/20 px-3 py-2 text-xs text-muted-foreground"
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-foreground">Chunk {chunk.index ?? i + 1}</span>
                          {chunk.score != null && (
                            <span className="text-[10px] bg-primary/10 text-primary rounded-full px-1.5 py-0.5">
                              score: {typeof chunk.score === "number" ? chunk.score.toFixed(3) : chunk.score}
                            </span>
                          )}
                        </div>
                        <p className="line-clamp-3 leading-relaxed">{chunk.text || chunk.content || "—"}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function UploadSection({ onUploaded }) {
  const [file, setFile] = useState(null);
  const [domain, setDomain]     = useState("");
  const [topic, setTopic]       = useState("");
  const [source, setSource]     = useState("");
  const [language, setLanguage] = useState("en");
  const [progress, setProgress] = useState(null); // { stage, pct }
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);
  const { toast } = useToast();

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer?.files?.[0];
    if (f) setFile(f);
  };

  const handleUpload = async () => {
    if (!file || !domain) {
      toast({ title: "File and domain are required", variant: "destructive" });
      return;
    }
    setProgress({ stage: "Uploading", pct: 0 });
    try {
      await uploadDocument(file, { domain, topic, source, language }, (p) => {
        // Fake processing stages while uploading
        if (p.stage === "Uploading") {
          setProgress({ stage: "Uploading", pct: p.pct });
        } else if (p.stage === "Complete") {
          setProgress({ stage: "Processing", pct: 80 });
          setTimeout(() => setProgress({ stage: "Complete", pct: 100 }), 600);
        }
      });
      setTimeout(() => {
        setProgress(null);
        setFile(null);
        setTopic("");
        setSource("");
        toast({ title: "Document uploaded and indexed" });
        onUploaded?.();
      }, 800);
    } catch (err) {
      setProgress(null);
      toast({ title: "Upload failed", description: err?.message, variant: "destructive" });
    }
  };

  const stageColor = {
    Uploading:  "bg-blue-500",
    Processing: "bg-amber-500",
    Complete:   "bg-emerald-500",
  };

  return (
    <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm p-5 space-y-4">
      <div className="flex items-center gap-2">
        <CloudUpload className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold text-foreground">Upload Document</h3>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "relative flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed py-8 px-4 cursor-pointer transition-all duration-200",
          dragging
            ? "border-primary bg-primary/5 scale-[1.01]"
            : file
              ? "border-emerald-500/50 bg-emerald-500/5"
              : "border-border/40 hover:border-primary/40 hover:bg-primary/5"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.txt,.docx,.md,.csv"
          className="sr-only"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
        {file ? (
          <>
            <CheckCircle2 className="h-8 w-8 text-emerald-500" />
            <span className="text-sm font-medium text-foreground">{file.name}</span>
            <span className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(1)} KB</span>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); setFile(null); }}
              className="absolute top-2 right-2 h-6 w-6 flex items-center justify-center rounded-full hover:bg-muted/60 text-muted-foreground transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </>
        ) : (
          <>
            <Upload className="h-8 w-8 text-muted-foreground/50" />
            <span className="text-sm text-muted-foreground">
              {dragging ? "Drop file here" : "Drag & drop or click to select"}
            </span>
            <span className="text-xs text-muted-foreground/60">.pdf, .txt, .docx, .md, .csv</span>
          </>
        )}
      </div>

      {/* Fields */}
      <div className="grid sm:grid-cols-2 gap-3">
        <Select
          value={domain}
          onChange={setDomain}
          options={DOMAINS}
          placeholder="Select domain *"
        />
        <Select
          value={language}
          onChange={setLanguage}
          options={LANGUAGES.map((l) => ({ value: l, label: l.toUpperCase() }))}
          placeholder="Language"
        />
        <Input
          placeholder="Topic (optional)"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          className="rounded-xl border-border/40 bg-card/80 focus:border-primary/50"
        />
        <Input
          placeholder="Source URL (optional)"
          value={source}
          onChange={(e) => setSource(e.target.value)}
          className="rounded-xl border-border/40 bg-card/80 focus:border-primary/50"
        />
      </div>

      {/* Progress */}
      {progress && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium text-foreground">{progress.stage}</span>
            <span className="text-muted-foreground tabular-nums">{progress.pct}%</span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-muted/50 overflow-hidden">
            <div
              className={cn("h-full rounded-full transition-all duration-300", stageColor[progress.stage] || "bg-primary")}
              style={{ width: `${progress.pct}%` }}
            />
          </div>
        </div>
      )}

      <Button
        onClick={handleUpload}
        disabled={!file || !domain || !!progress}
        className="w-full rounded-xl gap-2"
      >
        <Upload className="h-4 w-4" />
        {progress ? `${progress.stage}…` : "Upload & Index"}
      </Button>
    </div>
  );
}

export default function KnowledgeBase({ adminKey }) {
  const [docs, setDocs]         = useState([]);
  const [loading, setLoading]   = useState(true);
  const [search, setSearch]     = useState("");
  const [domainFilter, setDomainFilter] = useState("");
  const [typeFilter, setTypeFilter]     = useState("");
  const [selectedDoc, setSelectedDoc]   = useState(null);
  const [deleting, setDeleting] = useState(null);
  const { toast } = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (domainFilter) params.domain = domainFilter;
      if (typeFilter)   params.file_type = typeFilter;
      const data = await fetchDocuments(params);
      setDocs(Array.isArray(data) ? data : (data?.documents || []));
    } catch (err) {
      toast({ title: "Failed to load documents", description: err?.message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [domainFilter, typeFilter, toast]);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async (docId, hard = false) => {
    const action = hard ? "permanently delete" : "soft delete";
    if (!window.confirm(`Are you sure you want to ${action} this document?`)) return;
    setDeleting(docId);
    try {
      await deleteDocument(docId, hard);
      toast({ title: `Document ${hard ? "deleted" : "removed"}` });
      load();
    } catch (err) {
      toast({ title: "Delete failed", description: err?.message, variant: "destructive" });
    } finally {
      setDeleting(null);
    }
  };

  const handleRestore = async (docId) => {
    try {
      await restoreDocument(docId);
      toast({ title: "Document restored" });
      load();
    } catch (err) {
      toast({ title: "Restore failed", description: err?.message, variant: "destructive" });
    }
  };

  const filtered = docs.filter((d) => {
    const name = (d.filename || d.name || "").toLowerCase();
    return !search || name.includes(search.toLowerCase());
  });

  const fmtSize = (bytes) => {
    if (!bytes) return "—";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const fmtDate = (ts) => {
    if (!ts) return "—";
    return new Date(ts).toLocaleDateString([], { dateStyle: "medium" });
  };

  return (
    <div className="space-y-5">
      <div className="grid lg:grid-cols-3 gap-5">
        {/* Document list — 2/3 */}
        <div className="lg:col-span-2 space-y-3">
          {/* Filters */}
          <div className="flex flex-wrap gap-2">
            <div className="relative flex-1 min-w-48">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Search documents…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8 rounded-xl border-border/40 bg-card/80 focus:border-primary/50"
              />
            </div>
            <Select
              value={domainFilter}
              onChange={setDomainFilter}
              options={DOMAINS}
              placeholder="All Domains"
              className="w-44"
            />
            <Select
              value={typeFilter}
              onChange={setTypeFilter}
              options={FILE_TYPES}
              placeholder="All Types"
              className="w-32"
            />
          </div>

          {/* Table */}
          <div className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead>
                  <tr className="border-b border-border/30 bg-muted/20">
                    {["Filename", "Domain", "Type", "Chunks", "Size", "Status", "Indexed", "Actions"].map((h) => (
                      <th key={h} className="px-3 py-2.5 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/20">
                  {loading
                    ? Array.from({ length: 5 }).map((_, i) => (
                        <tr key={i}>
                          {Array.from({ length: 8 }).map((_, j) => (
                            <td key={j} className="px-3 py-3">
                              <div className="h-4 rounded bg-muted/50 animate-pulse" style={{ width: `${40 + j * 10}%` }} />
                            </td>
                          ))}
                        </tr>
                      ))
                    : filtered.length === 0
                      ? (
                        <tr>
                          <td colSpan={8} className="px-3 py-10 text-center text-sm text-muted-foreground">
                            {search || domainFilter || typeFilter ? "No documents match your filters" : "No documents uploaded yet"}
                          </td>
                        </tr>
                      )
                      : filtered.map((doc, i) => {
                          const isDeleted = doc.status?.toLowerCase() === "deleted";
                          return (
                            <tr
                              key={doc.id || i}
                              className={cn(
                                "transition-colors cursor-pointer",
                                i % 2 === 1 ? "bg-muted/10" : "",
                                "hover:bg-primary/5"
                              )}
                              onClick={() => setSelectedDoc(doc.id)}
                            >
                              <td className="px-3 py-2.5 font-medium text-foreground max-w-[160px]">
                                <div className="flex items-center gap-1.5">
                                  <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                                  <span className="truncate text-xs">{doc.filename || doc.name || "—"}</span>
                                </div>
                              </td>
                              <td className="px-3 py-2.5 text-xs text-muted-foreground whitespace-nowrap">{doc.domain || "—"}</td>
                              <td className="px-3 py-2.5 text-xs text-muted-foreground uppercase">{doc.file_type || doc.type || "—"}</td>
                              <td className="px-3 py-2.5 text-xs text-muted-foreground tabular-nums">{doc.chunk_count ?? "—"}</td>
                              <td className="px-3 py-2.5 text-xs text-muted-foreground whitespace-nowrap">{fmtSize(doc.file_size)}</td>
                              <td className="px-3 py-2.5"><StatusBadge status={doc.status} /></td>
                              <td className="px-3 py-2.5 text-xs text-muted-foreground whitespace-nowrap">{fmtDate(doc.indexed_at || doc.created_at)}</td>
                              <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                                <div className="flex items-center gap-1">
                                  <button
                                    onClick={() => setSelectedDoc(doc.id)}
                                    className="h-7 w-7 flex items-center justify-center rounded-lg hover:bg-muted/60 text-muted-foreground hover:text-foreground transition-colors"
                                    title="View detail"
                                  >
                                    <Eye className="h-3.5 w-3.5" />
                                  </button>
                                  {isDeleted ? (
                                    <button
                                      onClick={() => handleRestore(doc.id)}
                                      className="h-7 w-7 flex items-center justify-center rounded-lg hover:bg-emerald-500/10 text-muted-foreground hover:text-emerald-600 transition-colors"
                                      title="Restore"
                                    >
                                      <RotateCcw className="h-3.5 w-3.5" />
                                    </button>
                                  ) : (
                                    <button
                                      onClick={() => handleDelete(doc.id, false)}
                                      disabled={deleting === doc.id}
                                      className="h-7 w-7 flex items-center justify-center rounded-lg hover:bg-red-500/10 text-muted-foreground hover:text-red-500 transition-colors disabled:opacity-40"
                                      title="Soft delete"
                                    >
                                      <Trash2 className={cn("h-3.5 w-3.5", deleting === doc.id && "animate-pulse")} />
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
            {!loading && filtered.length > 0 && (
              <div className="px-4 py-2 border-t border-border/20 text-xs text-muted-foreground">
                Showing {filtered.length} of {docs.length} documents
              </div>
            )}
          </div>
        </div>

        {/* Upload section — 1/3 */}
        <div className="lg:col-span-1">
          <UploadSection onUploaded={load} />
        </div>
      </div>

      {/* Document detail modal */}
      {selectedDoc && (
        <DocDetailModal docId={selectedDoc} onClose={() => setSelectedDoc(null)} />
      )}
    </div>
  );
}
