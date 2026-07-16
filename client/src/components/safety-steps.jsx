// "Safety action mode" — when Raksha returns an emergency reply, we surface
// the numbered action steps as standalone cards above the prose. Parses the
// model's response without any server-side contract, so it degrades safely:
// if no steps are detected, nothing renders.

import { SoftSiren, SoftPhone, GentleShield } from "@/components/icons";

const STEP_PATTERNS = [
  // **Step 1:** ... / Step 1 — ... / Step 1. ...
  /(?:^|\n)\s*\*{0,2}step\s*(\d+)\*{0,2}\s*[:.\-—–]\s*([^\n]+)/gi,
  // 1. ... / 1) ... / 1 — ...
  /(?:^|\n)\s*(\d+)[.\)\-—–]\s+([^\n]+)/g,
];

const PHONE_RE = /\b(?:\+?\d{2,3}[\s-]?)?\d{2,4}[-\s]?\d{3,4}[-\s]?\d{2,5}\b|\b1\d{2,3}\b/;

export function parseSafetySteps(text) {
  if (!text) return [];
  for (const re of STEP_PATTERNS) {
    re.lastIndex = 0;
    const found = [];
    let m;
    while ((m = re.exec(text)) !== null) {
      const n = parseInt(m[1], 10);
      const body = (m[2] || "").trim().replace(/\*+/g, "").trim();
      if (body) found.push({ n, body });
      if (found.length >= 5) break;
    }
    if (found.length >= 2) {
      const seen = new Set();
      const dedup = found.filter((s) => {
        if (seen.has(s.n)) return false;
        seen.add(s.n);
        return true;
      });
      dedup.sort((a, b) => a.n - b.n);
      return dedup.slice(0, 5);
    }
  }
  return [];
}

function iconFor(body) {
  const lc = body.toLowerCase();
  if (PHONE_RE.test(body) || /(call|dial|helpline|1930|112|100|101|102|108|911)/i.test(lc)) {
    return <SoftPhone className="h-4 w-4" />;
  }
  if (/(safe|lock|move|leave|exit|hide|shelter|location)/i.test(lc)) {
    return <GentleShield className="h-4 w-4" />;
  }
  return <SoftSiren className="h-4 w-4" />;
}

export function SafetySteps({ text }) {
  const steps = parseSafetySteps(text);
  if (steps.length === 0) return null;

  return (
    <div className="mb-3 space-y-1.5">
      <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-primary/80 dark:text-primary/70">
        <SoftSiren className="h-3.5 w-3.5" />
        Action steps
      </div>
      <ol className="space-y-1.5">
        {steps.map((s, i) => (
          <li
            key={`${s.n}-${i}`}
            className="flex items-start gap-2.5 rounded-xl border border-primary/20 bg-primary/10 px-3 py-2"
          >
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary/90 ring-1 ring-primary/25">
              <span className="text-[12px] font-semibold">{i + 1}</span>
            </div>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-primary/80">
                {iconFor(s.body)}
                Step {i + 1}
              </div>
              <div className="mt-0.5 text-[13px] leading-snug text-foreground/90">{s.body}</div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
