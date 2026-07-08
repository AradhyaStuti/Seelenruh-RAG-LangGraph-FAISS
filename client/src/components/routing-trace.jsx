import { useState } from "react";

const personaName = {
  "Mental Health": "Usha",
  Legal: "Umang",
  "Government Schemes": "Aarogya",
  Safety: "Raksha",
};

const langLabel = {
  auto: "Auto-detect",
  en: "English",
  hi: "Hindi / Hinglish",
  de: "German",
};

function Row({ label, value, accent }) {
  if (!value) return null;
  return (
    <div className="flex items-baseline gap-2">
      <span className="w-[68px] shrink-0 text-[10px] uppercase tracking-wide text-muted-foreground/80">
        {label}
      </span>
      <span className={`text-[12px] leading-snug ${accent || "text-foreground/85"}`}>{value}</span>
    </div>
  );
}

export function RoutingTrace({ routing }) {
  const [open, setOpen] = useState(false);
  if (!routing) return null;

  const persona = personaName[routing.routedDomain] || routing.routedDomain;
  const rerouted =
    routing.requestedDomain &&
    routing.routedDomain &&
    routing.requestedDomain !== routing.routedDomain;

  return (
    <div className="mt-1.5">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex items-center gap-1 rounded-full border border-border/50 bg-background/40 px-2 py-0.5 text-[10px] text-muted-foreground transition hover:border-primary/40 hover:text-foreground"
      >
        <span aria-hidden>✦</span>
        Why {persona || "this reply"}?
      </button>

      {open && (
        <div className="mt-1.5 rounded-xl border border-border/40 bg-background/40 px-3 py-2.5 text-[12px] space-y-1.5">
          <div className="text-[11px] font-medium text-muted-foreground/90">Detected</div>
          <Row label="Intent" value={routing.intent} />
          <Row label="Emotion" value={routing.emotion} />
          <Row
            label="Language"
            value={langLabel[routing.lang] || routing.lang || "Auto-detect"}
          />
          <Row
            label="Routed to"
            value={persona ? `${persona} (${routing.routedDomain})` : routing.routedDomain}
            accent="font-medium text-foreground/95"
          />
          {rerouted && (
            <div className="rounded-md bg-amber-500/10 px-2 py-1 text-[11px] text-amber-700 dark:text-amber-300 ring-1 ring-amber-500/20">
              You picked <span className="font-medium">{routing.requestedDomain}</span>, but
              the classifier escalated this to{" "}
              <span className="font-medium">{routing.routedDomain}</span>
              {routing.isEmergency ? " — emergency override." : "."}
            </div>
          )}
          {routing.reasoning && (
            <div className="pt-1 text-[11px] italic text-muted-foreground/90">
              "{routing.reasoning}"
            </div>
          )}
        </div>
      )}
    </div>
  );
}
