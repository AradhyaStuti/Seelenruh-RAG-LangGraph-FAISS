"""
bench_personas.py
-----------------
Keyword-based quality evaluation for all four Seelenruh personas using
the extended benchmark dataset (bench_data.py).

Operates without live LLM calls by scoring against the expected_keywords
and must_not_keywords defined in bench_data.py.

Dimensions scored per persona:
  Umang  — keyword coverage, law citation presence, must-not violations
  Aarogya — scheme coverage, eligibility mention, must-not violations
  Usha   — tone keyword presence, crisis resource presence, must-not violations
  Raksha — helpline/emergency action presence, must-not violations

Two ways to use:
  1. Self-score mode (default): Scores whether each test case's
     expected_keywords are representatively distinct from must_not_keywords
     (validates the dataset itself — no LLM needed).
  2. Response-file mode (--responses FILE.json): Score actual LLM responses
     against the benchmark criteria.
     FILE format: [{"id": "umang_emp_001", "response": "..."}, ...]

Run:
  cd server && .venv/Scripts/python -m bench.bench_personas
  cd server && .venv/Scripts/python -m bench.bench_personas --responses responses.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bench.bench_data import (  # noqa: E402
    UMANG_CASES, AAROGYA_CASES, USHA_SCENARIOS, RAKSHA_CASES,
    UMANG_CATEGORIES, AAROGYA_CATEGORIES, USHA_CATEGORIES, RAKSHA_CATEGORIES,
)

RESULTS_DIR = Path(__file__).parent / "reports"
RESULTS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

@dataclass
class CaseScore:
    case_id: str
    category: str
    lang: str
    query: str
    keyword_hits: int
    keyword_total: int
    must_not_violations: int
    passed: bool
    notes: list[str] = field(default_factory=list)

    @property
    def keyword_coverage(self) -> float:
        return self.keyword_hits / self.keyword_total if self.keyword_total else 0.0


def _score_case(case: dict, response: Optional[str] = None) -> CaseScore:
    """
    Score a single benchmark case.

    If *response* is provided, score it against expected/must_not keywords.
    Otherwise, score the dataset case itself for internal consistency
    (checks that expected_keywords are defined and non-trivially disjoint
    from must_not_keywords).
    """
    exp_kws: list[str] = case.get("expected_keywords", [])
    bad_kws: list[str] = case.get("must_not_keywords", [])
    notes: list[str] = []
    violations = 0

    if response is not None:
        resp_lower = response.lower()

        # Count keyword hits
        hits = sum(1 for kw in exp_kws if kw.lower() in resp_lower)

        # Count must-not violations
        for kw in bad_kws:
            if kw.lower() in resp_lower:
                violations += 1
                notes.append(f"Forbidden keyword found: {kw!r}")

        passed = hits >= max(1, len(exp_kws) // 2) and violations == 0
    else:
        # Self-score mode: validate the test case metadata itself
        hits = len(exp_kws)
        if len(exp_kws) == 0:
            notes.append("No expected_keywords defined")
            passed = False
        else:
            # Check that must_not_keywords don't overlap with expected_keywords
            overlap = set(kw.lower() for kw in exp_kws) & set(kw.lower() for kw in bad_kws)
            if overlap:
                notes.append(f"Overlap between expected and must_not: {overlap}")
                violations = len(overlap)
                passed = False
            else:
                passed = True

    return CaseScore(
        case_id=case["id"],
        category=case.get("category", "?"),
        lang=case.get("lang", "en"),
        query=case.get("q", "")[:100],
        keyword_hits=hits,
        keyword_total=len(exp_kws),
        must_not_violations=violations,
        passed=passed,
        notes=notes,
    )


def evaluate_persona(
    cases: list[dict],
    responses: Optional[dict[str, str]] = None,
) -> dict:
    """
    Evaluate a list of cases (from one persona).
    *responses* maps case_id -> response text (for response-file mode).
    """
    scores: list[CaseScore] = []
    by_category: dict[str, list[CaseScore]] = defaultdict(list)
    by_lang: dict[str, list[CaseScore]] = defaultdict(list)

    for case in cases:
        resp = responses.get(case["id"]) if responses else None
        score = _score_case(case, response=resp)
        scores.append(score)
        by_category[score.category].append(score)
        by_lang[score.lang].append(score)

    def _agg(ss: list[CaseScore]) -> dict:
        n = len(ss)
        n_pass = sum(1 for s in ss if s.passed)
        avg_cov = sum(s.keyword_coverage for s in ss) / n if n else 0.0
        total_viols = sum(s.must_not_violations for s in ss)
        return {
            "n": n,
            "pass_rate": n_pass / n if n else 0.0,
            "avg_keyword_coverage": avg_cov,
            "total_violations": total_viols,
        }

    failures = [s for s in scores if not s.passed]

    return {
        "overall": _agg(scores),
        "by_category": {cat: _agg(ss) for cat, ss in by_category.items()},
        "by_lang": {lang: _agg(ss) for lang, ss in by_lang.items()},
        "failures": [
            {"id": s.case_id, "category": s.category, "query": s.query, "notes": s.notes}
            for s in failures[:20]   # cap at 20 for report brevity
        ],
        "n_failures": len(failures),
    }


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _fmt_pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def write_benchmark_report(results: dict, mode: str, out_path: Path) -> None:
    lines: list[str] = []
    lines += [
        "# Benchmark Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  ",
        f"**Evaluation mode:** {mode}",
        "",
        "---",
        "",
    ]

    persona_meta = {
        "Umang (Legal)":             ("Legal",             UMANG_CASES,    UMANG_CATEGORIES),
        "Aarogya (Govt Schemes)":    ("Government Schemes",AAROGYA_CASES,  AAROGYA_CATEGORIES),
        "Usha (Mental Health)":      ("Mental Health",     USHA_SCENARIOS, USHA_CATEGORIES),
        "Raksha (Safety)":           ("Safety",            RAKSHA_CASES,   RAKSHA_CATEGORIES),
    }

    summary_rows: list[tuple[str, dict]] = []

    for persona_label, (domain, cases, categories) in persona_meta.items():
        data = results.get(domain, {})
        if not data:
            continue
        o = data.get("overall", {})
        summary_rows.append((persona_label, o))

        lines += [
            f"## {persona_label}",
            "",
            f"**Cases:** {o.get('n', 0)}  ",
            f"**Pass rate:** {_fmt_pct(o.get('pass_rate', 0))}  ",
            f"**Avg keyword coverage:** {_fmt_pct(o.get('avg_keyword_coverage', 0))}  ",
            f"**Must-not violations:** {o.get('total_violations', 0)}",
            "",
            "### By Category",
            "",
            "| Category | n | Pass Rate | Keyword Coverage | Violations |",
            "|---|---|---|---|---|",
        ]

        for cat, m in sorted(data.get("by_category", {}).items()):
            lines.append(
                f"| {cat} | {m['n']} "
                f"| {_fmt_pct(m['pass_rate'])} "
                f"| {_fmt_pct(m['avg_keyword_coverage'])} "
                f"| {m['total_violations']} |"
            )

        lines += [
            "",
            "### By Language",
            "",
            "| Language | n | Pass Rate |",
            "|---|---|---|",
        ]
        for lang, m in sorted(data.get("by_lang", {}).items()):
            lang_label = {"en": "English", "hi": "Hindi", "hi-roman": "Hinglish", "de": "German"}.get(lang, lang)
            lines.append(f"| {lang_label} | {m['n']} | {_fmt_pct(m['pass_rate'])} |")

        failures = data.get("failures", [])
        if failures:
            lines += [
                "",
                f"### Failing Cases ({data.get('n_failures', 0)} total, showing up to 5)",
                "",
            ]
            for f in failures[:5]:
                note_str = "; ".join(f.get("notes", [])) or "keyword coverage below 50%"
                lines.append(f"- **{f['id']}** [{f['category']}]: _{f['query']}_  ")
                lines.append(f"  -> {note_str}")
        lines += ["", "---", ""]

    # Summary table
    lines.insert(lines.index("---", 4) + 2, "## Executive Summary")
    lines.insert(lines.index("## Executive Summary") + 1, "")
    lines.insert(lines.index("## Executive Summary") + 2,
                 "| Persona | Cases | Pass Rate | Keyword Coverage | Violations |")
    lines.insert(lines.index("## Executive Summary") + 3, "|---|---|---|---|---|")
    for label, o in summary_rows:
        lines.insert(
            lines.index("## Executive Summary") + 4,
            f"| {label} | {o.get('n', 0)} | {_fmt_pct(o.get('pass_rate', 0))} "
            f"| {_fmt_pct(o.get('avg_keyword_coverage', 0))} | {o.get('total_violations', 0)} |"
        )

    lines += [
        "## Improvement Suggestions",
        "",
    ]

    for persona_label, (domain, _, _) in persona_meta.items():
        data = results.get(domain, {})
        o = data.get("overall", {})
        pass_rate = o.get("pass_rate", 1.0)
        violations = o.get("total_violations", 0)

        if pass_rate < 0.80:
            lines.append(f"- **{persona_label} pass rate < 80%**: Review the weakest "
                         f"category above and expand knowledge chunks or adjust prompts.")
        if violations > 0:
            lines.append(f"- **{persona_label} has {violations} must-not violation(s)**: "
                         f"Strengthen negative examples in the few-shot prompt to prevent "
                         f"forbidden phrases.")

    if not any(line.startswith("-") for line in lines[-6:]):
        lines.append("- All personas score above threshold. No immediate improvements required.")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Benchmark report -> {out_path.relative_to(Path(__file__).parent.parent)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]
    responses_file: Optional[Path] = None

    for i, arg in enumerate(args):
        if arg == "--responses" and i + 1 < len(args):
            responses_file = Path(args[i + 1])

    mode = "dataset-self-check" if responses_file is None else f"response-scoring ({responses_file.name})"
    print(f"\nPersona benchmark  |  mode={mode}")

    responses_by_id: Optional[dict[str, str]] = None
    if responses_file is not None:
        if not responses_file.exists():
            print(f"  ERROR: File not found: {responses_file}")
            sys.exit(1)
        raw = json.loads(responses_file.read_text(encoding="utf-8"))
        responses_by_id = {r["id"]: r["response"] for r in raw}

    domain_cases = {
        "Legal":             UMANG_CASES,
        "Government Schemes": AAROGYA_CASES,
        "Mental Health":     USHA_SCENARIOS,
        "Safety":            RAKSHA_CASES,
    }

    results: dict[str, dict] = {}
    for domain, cases in domain_cases.items():
        results[domain] = evaluate_persona(cases, responses=responses_by_id)
        o = results[domain]["overall"]
        print(f"  {domain:<22} pass={_fmt_pct(o['pass_rate'])} "
              f"coverage={_fmt_pct(o['avg_keyword_coverage'])} "
              f"violations={o['total_violations']}")

    report_path = RESULTS_DIR / "benchmark_report.md"
    write_benchmark_report(results, mode=mode, out_path=report_path)


def _fmt_pct(v: float) -> str:
    return f"{v * 100:.1f}%"


if __name__ == "__main__":
    main()
