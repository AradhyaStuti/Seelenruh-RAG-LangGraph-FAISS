import { useState } from "react";

const confidenceClass = {
  High: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 ring-emerald-500/25",
  Medium: "bg-amber-500/15 text-amber-700 dark:text-amber-300 ring-amber-500/25",
  Low: "bg-rose-500/15 text-rose-700 dark:text-rose-300 ring-rose-500/25",
  None: "bg-muted text-muted-foreground ring-border",
};

function capitalize(s) {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
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
  const [open, setOpen] = useState(false);
  const [showAll, setShowAll] = useState(false);
  if (!sources || sources.length === 0) return null;

  const tone = confidenceClass[confidence] || confidenceClass.None;

  const cited0 = new Set(citedIndices.map((i) => i - 1));
  const hasCitations = cited0.size > 0;
  const displayed = !hasCitations || showAll ? sources : sources.filter((_, i) => cited0.has(i));
  const hiddenCount = sources.length - displayed.length;

  return (
    <div className="mt-2 rounded-xl border border-border/40 bg-background/40 px-3 py-2 text-[12px]">
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
          <span
            aria-hidden
            className={`text-muted-foreground/60 transition-transform ${open ? "rotate-180" : ""}`}
          >
            ▾
          </span>
        </span>
      </button>

      {open && (
        <ul className="mt-2 space-y-2 border-t border-border/40 pt-2">
          {displayed.map((s) => {
            const fresh = freshnessOf(s.lastVerifiedOn);
            return (
              <li
                key={s.id}
                className="rounded-lg border border-border/40 bg-card/60 px-2.5 py-2"
              >
                {s.source ? (
                  <>
                    <div className="flex items-start gap-1.5 text-foreground/90">
                      <span aria-hidden className="shrink-0 text-[13px] leading-none">📄</span>
                      <span className="font-medium leading-snug">{s.source}</span>
                      <span className="ml-auto flex shrink-0 items-center gap-1">
                        {fresh?.stale && (
                          <span
                            className="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300 ring-1 ring-amber-500/25"
                            title={`Last verified ${fresh.iso} (${fresh.ageDays} days ago) — may be out of date.`}
                          >
                            Stale
                          </span>
                        )}
                      </span>
                    </div>
                    <div className="mt-1 pl-5 text-[10px] text-muted-foreground/80">
                      {capitalize(s.topic)} · {s.domain} · {s.id}
                      {fresh && (
                        <> · verified {fresh.iso}</>
                      )}
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex items-start gap-1.5 text-foreground/85">
                      <span
                        aria-hidden
                        className="mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-primary/60"
                      />
                      <span className="leading-snug">{capitalize(s.topic)}</span>
                    </div>
                    <div className="mt-0.5 pl-5 text-[10px] text-muted-foreground/80">
                      {s.domain} · {s.id}
                    </div>
                  </>
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
