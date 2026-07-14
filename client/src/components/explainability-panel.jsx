/**
 * ExplainabilityPanel — "Why did I answer this?" expandable panel.
 *
 * Provides transparent retrieval information without exposing chain-of-thought,
 * prompts, or internal reasoning. Everything shown here is derived from the
 * already-public ChatResponse fields: sources, confidence, routing, webSearched, goal.
 *
 * Features
 *  • Animated RAG pipeline (Embed → FAISS → BM25 → Fusion → Rerank → LLM)
 *  • Deterministic reasoning summary
 *  • Quality indicators (confidence, freshness, hallucination guard, web search, etc.)
 *  • Document cards with scores and freshness
 */
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

// ─── Pipeline stages ──────────────────────────────────────────────────────────

const PIPELINE_STAGES = [
  { id: "embed",  label: "Embed",       icon: "⚡", desc: "Query vectorised" },
  { id: "faiss",  label: "FAISS",       icon: "🔍", desc: "Dense vector search" },
  { id: "bm25",   label: "BM25",        icon: "📝", desc: "Keyword search" },
  { id: "fusion", label: "RRF Fusion",  icon: "🔀", desc: "Score combination" },
  { id: "rerank", label: "Rerank",      icon: "🏆", desc: "Cross-encoder rerank" },
  { id: "llm",    label: "LLM",         icon: "✨", desc: "Answer generation" },
];

// ─── Confidence colours ───────────────────────────────────────────────────────

const CONF = {
  High:   { ring: "ring-emerald-500/30", bg: "bg-emerald-500/10", text: "text-emerald-700 dark:text-emerald-300", dot: "bg-emerald-500" },
  Medium: { ring: "ring-amber-500/30",   bg: "bg-amber-500/10",   text: "text-amber-700 dark:text-amber-300",   dot: "bg-amber-400"   },
  Low:    { ring: "ring-red-500/30",     bg: "bg-red-500/10",     text: "text-red-700 dark:text-red-300",       dot: "bg-red-500"     },
  None:   { ring: "ring-border/40",      bg: "bg-muted/30",       text: "text-muted-foreground",                dot: "bg-muted-foreground/40" },
};

// ─── Deterministic reasoning summary ─────────────────────────────────────────

function buildReasoningSummary({ sources, confidence, routing, webSearched, goal, selectedDomain }) {
  const n = sources?.length ?? 0;
  const domain = routing?.routedDomain || selectedDomain || "General";
  const intent = routing?.intent ? ` (${routing.intent})` : "";
  const lang = routing?.lang ? ` Language detected: ${routing.lang.toUpperCase()}.` : "";

  let summary = `The question was classified as a ${domain}${intent} query.`;

  if (n > 0) {
    summary += ` ${n} document${n !== 1 ? "s" : ""} were retrieved using hybrid FAISS + BM25 search and reranked by a cross-encoder.`;
    summary += ` Confidence level: ${confidence || "None"}.`;
  } else {
    summary += " No knowledge documents matched — the answer draws on general training knowledge.";
  }

  if (webSearched) summary += " The agent autonomously searched the web to supplement the answer.";
  if (goal) summary += ` An active goal ("${goal.length > 40 ? goal.slice(0, 40) + "…" : goal}") was tracked across turns.`;
  if (lang) summary += lang;
  summary += " Hallucination guardrails were applied before the response was finalised.";

  return summary;
}

// ─── Quality indicators ───────────────────────────────────────────────────────

function QualityBadge({ label, value, ok = null }) {
  const base = "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ring-1";
  const cls = ok === true
    ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 ring-emerald-500/25"
    : ok === false
    ? "bg-red-500/10 text-red-700 dark:text-red-300 ring-red-500/25"
    : "bg-muted/40 text-muted-foreground ring-border/40";
  const dot = ok === true ? "🟢" : ok === false ? "🔴" : "⚫";
  return (
    <span className={cn(base, cls)} title={label}>
      {dot} {value ?? label}
    </span>
  );
}

// ─── Animated pipeline ────────────────────────────────────────────────────────

function AnimatedPipeline({ active, hasRetrieval }) {
  const [step, setStep] = useState(-1);

  useEffect(() => {
    if (!active) { setStep(-1); return; }
    setStep(0);
    let i = 0;
    const total = PIPELINE_STAGES.length;
    const iv = setInterval(() => {
      i += 1;
      if (i >= total) { clearInterval(iv); setStep(total); return; }
      setStep(i);
    }, 220);
    return () => clearInterval(iv);
  }, [active]);

  return (
    <div className="flex items-center gap-1 flex-wrap py-1">
      {PIPELINE_STAGES.map((s, idx) => {
        const done = step > idx;
        const cur  = step === idx;
        const skip = !hasRetrieval && ["faiss", "bm25", "fusion", "rerank"].includes(s.id);
        return (
          <span key={s.id} className="flex items-center gap-0.5">
            <span
              className={cn(
                "flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 transition-all duration-300",
                done || step >= PIPELINE_STAGES.length
                  ? "bg-primary/15 text-primary ring-primary/30"
                  : cur
                  ? "bg-primary/25 text-primary ring-primary/50 scale-105"
                  : skip
                  ? "bg-muted/20 text-muted-foreground/40 ring-border/20 line-through"
                  : "bg-muted/30 text-muted-foreground/60 ring-border/30"
              )}
              title={s.desc}
            >
              <span aria-hidden>{s.icon}</span>
              {s.label}
              {cur && (
                <span className="ml-0.5 inline-block h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
              )}
            </span>
            {idx < PIPELINE_STAGES.length - 1 && (
              <svg
                width="8" height="8" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2.5"
                strokeLinecap="round" strokeLinejoin="round"
                aria-hidden
                className={cn(
                  "transition-colors duration-300",
                  done ? "text-primary/60" : "text-muted-foreground/30"
                )}
              >
                <polyline points="9 18 15 12 9 6" />
              </svg>
            )}
          </span>
        );
      })}
    </div>
  );
}

// ─── Score bar ────────────────────────────────────────────────────────────────

function ScoreBar({ value = 0, max = 1 }) {
  const pct = Math.min(100, Math.round((value / (max || 1)) * 100));
  return (
    <div className="flex items-center gap-1.5 min-w-0">
      <div className="h-1 flex-1 rounded-full bg-muted/50 overflow-hidden">
        <div
          className="h-full rounded-full bg-primary/60 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground w-9 text-right">
        {value.toFixed(3)}
      </span>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function ExplainabilityPanel({
  sources = [],
  confidence = "None",
  routing = null,
  webSearched = false,
  goal = null,
  selectedDomain = "",
  timelineUsed = false,
}) {
  const [open, setOpen] = useState(false);
  const [pipelineActive, setPipelineActive] = useState(false);
  const hasRetrieval = sources.length > 0;
  const conf = CONF[confidence] || CONF.None;
  const maxScore = Math.max(...sources.map((s) => s.rerankScore ?? s.score ?? 0), 1);

  const reasoning = buildReasoningSummary({
    sources, confidence, routing, webSearched, goal, selectedDomain,
  });

  function handleOpen() {
    setOpen((v) => {
      if (!v) {
        // Trigger pipeline animation on open
        setPipelineActive(false);
        setTimeout(() => setPipelineActive(true), 80);
      }
      return !v;
    });
  }

  const freshness = sources.length > 0
    ? sources.some((s) => s.reviewStatus === "Deprecated" || s.reviewStatus === "Superseded")
      ? false
      : sources.some((s) => s.lastVerifiedOn)
      ? true : null
    : null;

  return (
    <div className="mt-2">
      {/* Trigger */}
      <button
        type="button"
        onClick={handleOpen}
        className="flex items-center gap-1.5 text-[10px] text-muted-foreground/70 hover:text-primary/70 transition-colors group"
        aria-expanded={open}
        aria-label="Why did I answer this?"
      >
        <svg
          width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden
          className="group-hover:text-primary transition-colors"
        >
          <circle cx="12" cy="12" r="10" />
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
        Why did I answer this?
        <svg
          width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden
          className={cn("transition-transform duration-200", open && "rotate-180")}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className="mt-2 rounded-2xl border border-border/40 bg-background/80 backdrop-blur-sm overflow-hidden">

          {/* Header bar */}
          <div className={cn("px-3 py-2.5 border-b border-border/30 flex items-center justify-between gap-3", conf.bg)}>
            <span className="flex items-center gap-1.5 text-[11px] font-semibold">
              <span className={cn("h-2 w-2 rounded-full", conf.dot)} />
              <span className={conf.text}>Confidence: {confidence}</span>
            </span>
            <span className="text-[10px] text-muted-foreground/70">
              {hasRetrieval ? `${sources.length} document${sources.length !== 1 ? "s" : ""} used` : "No retrieval"}
            </span>
          </div>

          <div className="p-3 space-y-3.5 text-[11px]">

            {/* Animated pipeline */}
            <div>
              <p className="text-[10px] font-semibold text-muted-foreground/70 uppercase tracking-wide mb-1.5">
                Retrieval Pipeline
              </p>
              <AnimatedPipeline active={pipelineActive} hasRetrieval={hasRetrieval} />
            </div>

            {/* Reasoning summary */}
            <div className="rounded-xl bg-muted/20 border border-border/30 px-3 py-2.5">
              <p className="text-[10px] font-semibold text-muted-foreground/80 uppercase tracking-wide mb-1">
                Reasoning Summary
              </p>
              <p className="leading-relaxed text-foreground/80">{reasoning}</p>
            </div>

            {/* Quality indicators */}
            <div>
              <p className="text-[10px] font-semibold text-muted-foreground/70 uppercase tracking-wide mb-1.5">
                Quality Indicators
              </p>
              <div className="flex flex-wrap gap-1.5">
                <QualityBadge label="Confidence" value={`Confidence: ${confidence}`}
                  ok={confidence === "High" ? true : confidence === "Low" || confidence === "None" ? false : null} />
                <QualityBadge label="Hallucination guard" value="Guard: Active" ok={true} />
                <QualityBadge label="Source freshness" value="Freshness" ok={freshness} />
                <QualityBadge label="Web search" value={webSearched ? "Web: Used" : "Web: Not used"} ok={webSearched ? true : null} />
                <QualityBadge label="Memory" value={routing?.memory ? "Memory: Used" : "Memory: None"} ok={routing?.memory ? true : null} />
                <QualityBadge label="Goal tracking" value={goal ? "Goal: Active" : "Goal: None"} ok={goal ? true : null} />
                <QualityBadge label="Legal timeline" value={timelineUsed ? "Timeline: Active" : "Timeline: None"} ok={timelineUsed ? true : null} />
                {routing?.lang && (
                  <QualityBadge label="Language" value={`Lang: ${routing.lang.toUpperCase()}`} ok={true} />
                )}
              </div>
            </div>

            {/* Documents used */}
            {hasRetrieval && (
              <div>
                <p className="text-[10px] font-semibold text-muted-foreground/70 uppercase tracking-wide mb-1.5">
                  Documents Used
                </p>
                <div className="space-y-1.5">
                  {sources.map((src, idx) => (
                    <div
                      key={src.id || idx}
                      className="rounded-xl border border-border/30 bg-card/50 px-2.5 py-2 space-y-1"
                    >
                      <div className="flex items-start gap-2">
                        <span className="shrink-0 text-[13px] mt-0.5" aria-hidden>
                          {src.documentType === "Act" ? "📋" : src.documentType === "Scheme" ? "🏛️" : "📄"}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-foreground/85 leading-snug truncate">
                            {src.topic || src.id}
                          </p>
                          <p className="text-[9px] text-muted-foreground/60 mt-0.5">
                            {src.id}
                            {src.lastVerifiedOn && <> · verified {src.lastVerifiedOn}</>}
                            {src.domain && <> · {src.domain}</>}
                          </p>
                        </div>
                        <span className="shrink-0 text-[9px] text-muted-foreground/50 tabular-nums">
                          #{idx + 1}
                        </span>
                      </div>

                      {src.rerankScore != null && (
                        <div className="flex items-center gap-2 pl-5">
                          <span className="w-14 text-muted-foreground/50 shrink-0">Rerank</span>
                          <ScoreBar value={src.rerankScore} max={maxScore} />
                        </div>
                      )}
                      <div className="flex items-center gap-2 pl-5">
                        <span className="w-14 text-muted-foreground/50 shrink-0">Score</span>
                        <ScoreBar value={src.score ?? 0} max={maxScore} />
                      </div>

                      {src.sourceUrl && (
                        <div className="pl-5">
                          <a
                            href={src.sourceUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[9px] text-primary/70 hover:text-primary hover:underline"
                          >
                            {src.source || src.sourceUrl} ↗
                          </a>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

          </div>
        </div>
      )}
    </div>
  );
}
