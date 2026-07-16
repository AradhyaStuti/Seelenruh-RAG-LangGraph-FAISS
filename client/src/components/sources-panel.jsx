import { useState } from "react";

const confidenceClass = {
  High:   "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 ring-emerald-500/25",
  Medium: "bg-amber-500/15 text-amber-700 dark:text-amber-300 ring-amber-500/25",
  Low:    "bg-amber-500/15 text-amber-700 dark:text-amber-300 ring-amber-500/25",
  None:   "bg-muted text-muted-foreground ring-border",
};

// Source authority badges
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

// Review status badges
const REVIEW_STATUS_BADGE = {
  NeedsReview: {
    label: "Needs Review",
    cls: "bg-amber-500/15 text-amber-700 dark:text-amber-300 ring-amber-500/25",
  },
  Deprecated: {
    label: "Deprecated",
    cls: "bg-slate-500/15 text-slate-700 dark:text-slate-300 ring-slate-500/25",
  },
  Superseded: {
    label: "Superseded",
    cls: "bg-slate-500/15 text-slate-700 dark:text-slate-300 ring-slate-500/25",
  },
};

// SVG icon component per document type — no emojis
function DocTypeIcon({ type, className = "" }) {
  const base = {
    width: 14, height: 14, viewBox: "0 0 24 24",
    fill: "none", stroke: "currentColor",
    strokeWidth: 1.75, strokeLinecap: "round", strokeLinejoin: "round",
    "aria-hidden": true, className,
  };

  switch (type) {
    case "Constitution":
    case "Judgment":
      // Scales of justice
      return (
        <svg {...base}>
          <path d="M12 3v19" />
          <path d="M5 12H2l3-7 3 7a3 3 0 0 1-6 0" />
          <path d="M19 12h-3l3-7 3 7a3 3 0 0 1-6 0" />
          <path d="M9 21h6" />
        </svg>
      );
    case "Helpline":
      // Phone
      return (
        <svg {...base}>
          <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.07 10a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3 .5h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 8a16 16 0 0 0 6.72 6.72l1.36-1.16a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
        </svg>
      );
    case "Scheme":
      // Building / government
      return (
        <svg {...base}>
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
          <polyline points="9 22 9 12 15 12 15 22"/>
        </svg>
      );
    case "Scholarship":
      // Graduation cap
      return (
        <svg {...base}>
          <path d="M22 10v6M2 10l10-5 10 5-10 5z"/>
          <path d="M6 12v5c3 3 9 3 12 0v-5"/>
        </svg>
      );
    case "Research":
      // Flask / beaker
      return (
        <svg {...base}>
          <path d="M9 3h6l1 5H8z"/>
          <path d="M8 8l-3 9a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1l-3-9"/>
          <line x1="10" y1="13" x2="14" y2="13"/>
        </svg>
      );
    case "FAQ":
      // Help circle
      return (
        <svg {...base}>
          <circle cx="12" cy="12" r="10"/>
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
          <line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
      );
    case "Portal":
      // Globe
      return (
        <svg {...base}>
          <circle cx="12" cy="12" r="10"/>
          <line x1="2" y1="12" x2="22" y2="12"/>
          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
        </svg>
      );
    case "Policy":
      // Scroll
      return (
        <svg {...base}>
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <line x1="10" y1="9" x2="8" y2="9"/>
        </svg>
      );
    // Act, Rule, Circular, Notification, Guideline, Manual — file-text
    default:
      return (
        <svg {...base}>
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
        </svg>
      );
  }
}

function ChevronDown({ className = "" }) {
  return (
    <svg
      aria-hidden
      width="14" height="14" viewBox="0 0 24 24"
      fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      className={className}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function ExternalLink({ className = "" }) {
  return (
    <svg
      aria-hidden
      width="10" height="10" viewBox="0 0 24 24"
      fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      className={className}
    >
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
      <polyline points="15 3 21 3 21 9"/>
      <line x1="10" y1="14" x2="21" y2="3"/>
    </svg>
  );
}

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
    <div className="mt-2 rounded-[1.15rem] border border-border/40 bg-gradient-to-br from-card/75 via-background/70 to-card/50 px-3 py-2.5 text-[12px] shadow-sm">
      {/* Header row */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 text-left text-muted-foreground transition-colors hover:text-foreground"
      >
        <span className="flex min-w-0 items-center gap-2">
          <span className="font-semibold text-foreground/85">{hasCitations ? "Sources cited" : "Sources retrieved"}</span>
          <span className="text-muted-foreground/60">
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
          <ChevronDown
            className={`text-muted-foreground/50 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          />
        </span>
      </button>

      {/* Source cards */}
      {open && (
        <ul className="mt-2.5 space-y-2 border-t border-border/35 pt-2.5">
          {displayed.map((s) => {
            const linkUrl        = s.sourceUrl || null;
            const hasLink        = Boolean(linkUrl);
            const authorityBadge = AUTHORITY_BADGE[s.sourceAuthority];
            const reviewBadge    = REVIEW_STATUS_BADGE[s.reviewStatus];
            const reviewNote     = s.reviewNote || null;

            return (
              <li
                key={s.id}
                className="rounded-[1rem] border border-border/40 bg-background/70 px-3 py-2.5 flex flex-col gap-1.5 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/25 hover:shadow-sm"
              >
                {/* Title row */}
                <div className="flex items-start gap-2">
                  <span className="shrink-0 text-muted-foreground/55 mt-0.5">
                    <DocTypeIcon type={s.documentType} />
                  </span>
                  <div className="flex-1 min-w-0">
                    <span className="font-semibold text-foreground/90 leading-snug block truncate">
                      {capitalize(s.topic) || (hasLink ? displayHost(linkUrl) : s.id)}
                    </span>
                    <span className="text-[10px] text-muted-foreground/65 block mt-0.5 leading-relaxed">
                      {s.domain}
                      {s.documentType && s.documentType !== "General" && <> · {s.documentType}</>}
                      {hasLink && <> · {displayHost(linkUrl)}</>}
                      {s.lastVerifiedOn && <> · verified {s.lastVerifiedOn}</>}
                    </span>
                    {s.source && (
                      <span className="text-[10px] text-muted-foreground/45 block mt-0.5 truncate">
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

                {/* Review note for problem statuses */}
                {reviewNote && (s.reviewStatus === "NeedsReview" || s.reviewStatus === "Deprecated" || s.reviewStatus === "Superseded") && (
                  <p className="pl-5 text-[10px] text-amber-700 dark:text-amber-400 leading-relaxed">
                    {reviewNote}
                  </p>
                )}

                {/* Text snippet */}
                {s.text && (
                  <p className="pl-5 text-[11px] text-muted-foreground/75 leading-relaxed line-clamp-2">
                    {s.text.replace(/\s+/g, " ").slice(0, 180)}{s.text.length > 180 ? "…" : ""}
                  </p>
                )}

                {/* Open official source */}
                {hasLink && (
                  <div className="pl-5">
                    <a
                      href={linkUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 rounded-full border border-border/50 bg-background/50 px-2.5 py-1 text-[10px] font-medium text-primary hover:bg-primary/10 hover:border-primary/30 transition-colors"
                    >
                      Open source
                      <ExternalLink />
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
                className="w-full rounded-xl border border-dashed border-border/40 px-2.5 py-1.5 text-[11px] text-muted-foreground transition-colors hover:bg-accent/20 hover:text-foreground hover:border-border/60"
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
