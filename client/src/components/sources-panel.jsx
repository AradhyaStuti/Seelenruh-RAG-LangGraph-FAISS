import { useState } from "react";

const confidenceClass = {
  High:   "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 ring-emerald-500/25",
  Medium: "bg-amber-500/15 text-amber-700 dark:text-amber-300 ring-amber-500/25",
  Low:    "bg-rose-500/15 text-rose-700 dark:text-rose-300 ring-rose-500/25",
  None:   "bg-muted text-muted-foreground ring-border",
};

function capitalize(s) {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// Try to extract a clean hostname for display (e.g. "legislative.gov.in")
function displayHost(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

// Identify official government / legal sources for badge
function isOfficial(url) {
  if (!url) return false;
  const u = url.toLowerCase();
  return (
    u.includes(".gov.in") || u.includes(".nic.in") ||
    u.includes("nalsa") || u.includes("ecourts") ||
    u.includes("legislative.gov") || u.includes("nrega.nic") ||
    u.includes("pmjay") || u.includes("myscheme") ||
    u.includes("cybercrime.gov") || u.includes("rtionline")
  );
}

const STALE_DAYS = 180;
function freshnessOf(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const ageDays = Math.floor((Date.now() - d.getTime()) / 86400000);
  return { iso, ageDays, stale: ageDays >= STALE_DAYS };
}

export function SourcesPanel({ sources, citedIndices = [], confidence }) {
  const [open, setOpen]       = useState(false);
  const [showAll, setShowAll] = useState(false);
  if (!sources || sources.length === 0) return null;

  const tone    = confidenceClass[confidence] || confidenceClass.None;
  const cited0  = new Set(citedIndices.map((i) => i - 1));
  const hasCitations = cited0.size > 0;
  const displayed    = !hasCitations || showAll ? sources : sources.filter((_, i) => cited0.has(i));
  const hiddenCount  = sources.length - displayed.length;

  return (
    <div className="mt-2 rounded-xl border border-border/40 bg-background/40 px-3 py-2 text-[12px]">
      {/* Header row */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 text-left text-muted-foreground transition hover:text-foreground"
      >
        <span className="flex min-w-0 items-center gap-2">
          <span className="font-medium">{hasCitations ? "Sources cited" : "Sources retrieved"}</span>
          <span className="text-muted-foreground/70">
            · {displayed.length}{hiddenCount > 0 ? ` of ${sources.length}` : ""}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ${tone}`}
            title="Confidence is derived from the top retrieval re-rank score."
          >
            {confidence}
          </span>
          <span aria-hidden className={`text-muted-foreground/60 transition-transform ${open ? "rotate-180" : ""}`}>▾</span>
        </span>
      </button>

      {/* Source cards */}
      {open && (
        <ul className="mt-2 space-y-2 border-t border-border/40 pt-2">
          {displayed.map((s) => {
            const fresh    = freshnessOf(s.lastVerifiedOn);
            const official = isOfficial(s.source);
            const hasUrl   = s.source && (s.source.startsWith("http://") || s.source.startsWith("https://"));

            return (
              <li
                key={s.id}
                className="rounded-lg border border-border/40 bg-card/60 px-3 py-2.5 flex flex-col gap-1.5"
              >
                {/* Title row */}
                <div className="flex items-start gap-2">
                  <span aria-hidden className="shrink-0 text-[13px] leading-none mt-0.5">
                    {hasUrl ? "🔗" : "📄"}
                  </span>
                  <div className="flex-1 min-w-0">
                    <span className="font-medium text-foreground/90 leading-snug block truncate">
                      {capitalize(s.topic) || (hasUrl ? displayHost(s.source) : s.id)}
                    </span>
                    <span className="text-[10px] text-muted-foreground/70 block mt-0.5">
                      {s.domain}
                      {hasUrl && <> · {displayHost(s.source)}</>}
                      {fresh && <> · verified {fresh.iso}</>}
                    </span>
                  </div>
                  <div className="flex shrink-0 items-center gap-1 ml-1">
                    {official && (
                      <span
                        className="rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-emerald-700 ring-1 ring-emerald-500/25"
                        title="Official government / legal source"
                      >
                        Official
                      </span>
                    )}
                    {fresh?.stale && (
                      <span
                        className="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-amber-700 ring-1 ring-amber-500/25"
                        title={`Last verified ${fresh.iso} (${fresh.ageDays} days ago) — may be out of date.`}
                      >
                        Stale
                      </span>
                    )}
                  </div>
                </div>

                {/* Text snippet if available */}
                {s.text && (
                  <p className="pl-5 text-[11px] text-muted-foreground/80 leading-relaxed line-clamp-2">
                    {s.text.replace(/\s+/g, " ").slice(0, 180)}{s.text.length > 180 ? "…" : ""}
                  </p>
                )}

                {/* Open link button */}
                {hasUrl && (
                  <div className="pl-5">
                    <a
                      href={s.source}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 rounded-full border border-border/50 bg-background/60 px-2.5 py-1 text-[10px] font-medium text-primary hover:bg-primary/10 transition-colors"
                    >
                      Open source ↗
                    </a>
                  </div>
                )}
              </li>
            );
          })}

          {hasCitations && hiddenCount > 0 && (
            <li>
              <button
                type="button"
                onClick={() => setShowAll((v) => !v)}
                className="w-full rounded-lg border border-dashed border-border/40 px-2.5 py-1.5 text-[11px] text-muted-foreground transition hover:bg-accent/30 hover:text-foreground"
              >
                {showAll
                  ? `Hide ${hiddenCount} uncited`
                  : `Show ${hiddenCount} more retrieved but not cited`}
              </button>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
