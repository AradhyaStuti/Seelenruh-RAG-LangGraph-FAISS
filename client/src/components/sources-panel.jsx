import { useState } from "react";

const confidenceClass = {
  High:   "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 ring-emerald-500/25",
  Medium: "bg-amber-500/15 text-amber-700 dark:text-amber-300 ring-amber-500/25",
  Low:    "bg-rose-500/15 text-rose-700 dark:text-rose-300 ring-rose-500/25",
  None:   "bg-muted text-muted-foreground ring-border",
};

// Source authority badges — shown instead of the old "OFFICIAL" flag
const AUTHORITY_BADGE = {
  Authoritative: {
    label: "Authoritative",
    cls: "bg-purple-500/15 text-purple-700 dark:text-purple-300 ring-purple-500/25",
    title: "Primary law source — gazette, apex court, or India Code",
  },
  Official: {
    label: "Official",
    cls: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 ring-emerald-500/25",
    title: "Official government or ministry portal",
  },
  Institutional: {
    label: "Institutional",
    cls: "bg-blue-500/15 text-blue-700 dark:text-blue-300 ring-blue-500/25",
    title: "University, statutory body, or international organisation",
  },
};

// Review status badges — replaces the old age-based "STALE" badge
const REVIEW_STATUS_BADGE = {
  NeedsReview: {
    label: "Needs Review",
    cls: "bg-amber-500/15 text-amber-700 dark:text-amber-300 ring-amber-500/25",
  },
  Deprecated: {
    label: "Deprecated",
    cls: "bg-rose-500/15 text-rose-700 dark:text-rose-300 ring-rose-500/25",
  },
  Superseded: {
    label: "Superseded",
    cls: "bg-rose-500/15 text-rose-700 dark:text-rose-300 ring-rose-500/25",
  },
};

// Document type icons for the leading icon slot
const DOC_TYPE_ICON = {
  Constitution: "⚖️",
  Act:          "📋",
  Rule:         "📋",
  Helpline:     "📞",
  Scheme:       "🏛️",
  Scholarship:  "🎓",
  Judgment:     "⚖️",
  Research:     "🔬",
  FAQ:          "❓",
  Portal:       "🌐",
  Notification: "📢",
  Circular:     "📢",
  Policy:       "📜",
  Manual:       "📖",
  Guideline:    "📖",
};

function capitalize(s) {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function displayHost(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function SourcesPanel({ sources, citedIndices = [], confidence }) {
  const [open, setOpen]       = useState(false);
  const [showAll, setShowAll] = useState(false);
  if (!sources || sources.length === 0) return null;

  const tone        = confidenceClass[confidence] || confidenceClass.None;
  const cited0      = new Set(citedIndices.map((i) => i - 1));
  const hasCitations = cited0.size > 0;
  const displayed   = !hasCitations || showAll ? sources : sources.filter((_, i) => cited0.has(i));
  const hiddenCount = sources.length - displayed.length;

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
            title="Confidence is derived from source authority, retrieval score, and review status."
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
            // sourceUrl = resolved official URL (from knowledge_meta resolver)
            // source    = human-readable citation string (e.g. "PWDVA · NALSA")
            const linkUrl        = s.sourceUrl || null;
            const hasLink        = Boolean(linkUrl);
            const authorityBadge = AUTHORITY_BADGE[s.sourceAuthority];
            const reviewBadge    = REVIEW_STATUS_BADGE[s.reviewStatus];
            const docIcon        = DOC_TYPE_ICON[s.documentType] ?? (hasLink ? "🔗" : "📄");
            const reviewNote     = s.reviewNote || null;

            return (
              <li
                key={s.id}
                className="rounded-lg border border-border/40 bg-card/60 px-3 py-2.5 flex flex-col gap-1.5"
              >
                {/* Title row */}
                <div className="flex items-start gap-2">
                  <span aria-hidden className="shrink-0 text-[13px] leading-none mt-0.5">
                    {docIcon}
                  </span>
                  <div className="flex-1 min-w-0">
                    <span className="font-medium text-foreground/90 leading-snug block truncate">
                      {capitalize(s.topic) || (hasLink ? displayHost(linkUrl) : s.id)}
                    </span>
                    <span className="text-[10px] text-muted-foreground/70 block mt-0.5">
                      {s.domain}
                      {s.documentType && s.documentType !== "General" && <> · {s.documentType}</>}
                      {hasLink && <> · {displayHost(linkUrl)}</>}
                      {s.lastVerifiedOn && <> · verified {s.lastVerifiedOn}</>}
                    </span>
                    {/* Citation authority string (e.g. "PWDVA · NALSA · NCW") */}
                    {s.source && (
                      <span className="text-[10px] text-muted-foreground/50 block mt-0.5 truncate">
                        {s.source}
                      </span>
                    )}
                  </div>

                  {/* Authority + review status badges */}
                  <div className="flex shrink-0 items-center gap-1 ml-1">
                    {authorityBadge && (
                      <span
                        className={`rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide ring-1 ${authorityBadge.cls}`}
                        title={authorityBadge.title}
                      >
                        {authorityBadge.label}
                      </span>
                    )}
                    {reviewBadge && (
                      <span
                        className={`rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide ring-1 ${reviewBadge.cls}`}
                        title={reviewNote || reviewBadge.label}
                      >
                        {reviewBadge.label}
                      </span>
                    )}
                  </div>
                </div>

                {/* Human-readable review note (only for problem statuses) */}
                {reviewNote && (s.reviewStatus === "NeedsReview" || s.reviewStatus === "Deprecated" || s.reviewStatus === "Superseded") && (
                  <p className="pl-5 text-[10px] text-amber-700 dark:text-amber-400 leading-relaxed">
                    ℹ {reviewNote}
                  </p>
                )}

                {/* Text snippet if available */}
                {s.text && (
                  <p className="pl-5 text-[11px] text-muted-foreground/80 leading-relaxed line-clamp-2">
                    {s.text.replace(/\s+/g, " ").slice(0, 180)}{s.text.length > 180 ? "…" : ""}
                  </p>
                )}

                {/* Open official source button — uses resolved sourceUrl */}
                {hasLink && (
                  <div className="pl-5">
                    <a
                      href={linkUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 rounded-full border border-border/50 bg-background/60 px-2.5 py-1 text-[10px] font-medium text-primary hover:bg-primary/10 transition-colors"
                    >
                      Open official source ↗
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
