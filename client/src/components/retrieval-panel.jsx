/**
 * RetrievalPanel — expandable "How this answer was generated" panel.
 *
 * Shows a visual pipeline: chunks retrieved → reranked → confidence band.
 * Uses the `sources` and `confidence` already present on each assistant message.
 */
import { useState } from "react";
import { cn } from "@/lib/utils";

const CONFIDENCE_COLORS = {
  High:   { bg: "bg-emerald-50 border-emerald-200", dot: "bg-emerald-500", text: "text-emerald-700" },
  Medium: { bg: "bg-amber-50 border-amber-200",     dot: "bg-amber-400",   text: "text-amber-700"  },
  Low:    { bg: "bg-red-50 border-red-200",          dot: "bg-red-400",     text: "text-red-700"    },
  None:   { bg: "bg-muted/40 border-border/40",      dot: "bg-muted-foreground/40", text: "text-muted-foreground" },
};

function ScoreBar({ value, max = 1 }) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  return (
    <div className="flex items-center gap-1.5 min-w-0">
      <div className="h-1.5 flex-1 rounded-full bg-muted/50 overflow-hidden">
        <div
          className="h-full rounded-full bg-primary/60 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground">{value.toFixed(3)}</span>
    </div>
  );
}

export function RetrievalPanel({ sources = [], confidence = "None" }) {
  const [open, setOpen] = useState(false);

  if (!sources || sources.length === 0) return null;

  const col = CONFIDENCE_COLORS[confidence] || CONFIDENCE_COLORS.None;
  const maxScore = Math.max(...sources.map((s) => s.rerankScore ?? s.score ?? 0), 1);

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-[10px] text-muted-foreground/70 hover:text-primary/70 transition-colors"
        aria-expanded={open}
      >
        {/* Pipeline icon */}
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <circle cx="12" cy="12" r="3" /><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83" />
        </svg>
        How this was generated
        <svg
          width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
          strokeLinecap="round" strokeLinejoin="round" aria-hidden
          className={cn("transition-transform", open && "rotate-180")}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className="mt-2 rounded-xl border border-border/40 bg-background/70 backdrop-blur-sm p-3 text-[11px] space-y-3">

          {/* Pipeline stages */}
          <div className="flex items-center gap-1 flex-wrap">
            {[
              { label: "Embed", icon: "⚡" },
              { label: "FAISS", icon: "🔍" },
              { label: "BM25",  icon: "📝" },
              { label: "RRF Fusion", icon: "🔀" },
              { label: "Rerank", icon: "🏆" },
            ].map((stage, i, arr) => (
              <span key={stage.label} className="flex items-center gap-1">
                <span className="rounded-full px-2 py-0.5 bg-primary/10 text-primary/80 font-medium">
                  {stage.icon} {stage.label}
                </span>
                {i < arr.length - 1 && (
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                )}
              </span>
            ))}
          </div>

          {/* Confidence badge */}
          <div className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 border text-[10px] font-medium", col.bg, col.text)}>
            <span className={cn("h-1.5 w-1.5 rounded-full", col.dot)} />
            Confidence: {confidence}
          </div>

          {/* Retrieved chunks */}
          <div>
            <p className="text-[10px] font-semibold text-muted-foreground/80 uppercase tracking-wide mb-1.5">
              {sources.length} chunk{sources.length !== 1 ? "s" : ""} used
            </p>
            <div className="space-y-1.5">
              {sources.map((src, idx) => (
                <div key={src.id || idx} className="rounded-lg border border-border/30 bg-card/60 px-2.5 py-1.5">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <span className="font-medium text-foreground/80 leading-tight">{src.topic}</span>
                    <span className="shrink-0 rounded px-1 py-0.5 bg-muted/60 text-[9px] text-muted-foreground">
                      {src.domain}
                    </span>
                  </div>
                  <div className="space-y-0.5">
                    {src.rerankScore != null && (
                      <div className="flex items-center gap-2">
                        <span className="w-16 text-muted-foreground/60 shrink-0">Rerank</span>
                        <ScoreBar value={src.rerankScore} max={maxScore} />
                      </div>
                    )}
                    <div className="flex items-center gap-2">
                      <span className="w-16 text-muted-foreground/60 shrink-0">Score</span>
                      <ScoreBar value={src.score ?? 0} max={maxScore} />
                    </div>
                    {src.source && (
                      <p className="text-[9px] text-muted-foreground/50 truncate mt-0.5">
                        {src.sourceUrl ? (
                          <a href={src.sourceUrl} target="_blank" rel="noopener noreferrer" className="hover:underline hover:text-primary">
                            {src.source}
                          </a>
                        ) : src.source}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
