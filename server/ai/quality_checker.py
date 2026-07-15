"""Pattern-based validation for Umang's legal responses.

Catches overpromising, German law bleed-in, FIR misuse for salary disputes,
and hallucinated helpline numbers. Errors append a disclaimer; warnings are logged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# error-level — these cause a disclaimer to be appended
_FAIL_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Overpromising outcomes
    (
        re.compile(
            r"\b(you (will|shall|are going to) (definitely|certainly|surely|100%) "
            r"(win|succeed|get|receive|recover))\b",
            re.IGNORECASE,
        ),
        "Overpromise: guaranteed outcome language detected",
    ),
    (
        re.compile(r"\b(guaranteed|guarantee|garaunteed)\b", re.IGNORECASE),
        "Overpromise: 'guaranteed' used — legal outcomes are never guaranteed",
    ),
    (
        re.compile(r"\byou (will|shall) win\b", re.IGNORECASE),
        "Overpromise: 'you will win' — remove; use 'you may have a strong case'",
    ),
    # German / foreign law bleed-in
    (
        re.compile(
            r"\b(deutsches recht|german law|BGB|StGB|ZPO|arbeitsrecht|mietrecht"
            r"|bürgerliches gesetzbuch|strafgesetzbuch)\b",
            re.IGNORECASE,
        ),
        "Foreign law: German law reference in Indian legal response",
    ),
    # Fabricated / banned helpline numbers
    (
        re.compile(r"\b(1800[-\s]?\d{6,9}|1860[-\s]?\d{6,9})\b"),
        "Unverified toll-free number: do not cite unless from FALLBACK_LINKS",
    ),
    # Citing IPC sections that don't exist (> 511)
    (
        re.compile(r"\b(?:section|sec|s\.)\s*(5[2-9]\d|[6-9]\d{2,})\s+(?:ipc|indian penal code)\b", re.IGNORECASE),
        "Possible hallucination: IPC section > 511 cited",
    ),
    # Citing BNS sections > 358
    (
        re.compile(r"\b(?:section|sec|s\.)\s*(3[6-9]\d|[4-9]\d{2,})\s+(?:bns|bharatiya nyaya sanhita)\b", re.IGNORECASE),
        "Possible hallucination: BNS section > 358 cited",
    ),
]

# warning-level — logged but not shown to users
_WARN_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # FIR misuse for employment salary disputes
    (
        re.compile(
            r"\b(file|lodge|register).{0,30}FIR.{0,60}(salary|wages|unpaid|dues|arrears)\b",
            re.IGNORECASE,
        ),
        "FIR guard: FIR recommended for salary dispute — prefer Labour Commissioner unless fraud involved",
        "Employment",
    ),
    # Missing disclaimer for property/contract advice
    (
        re.compile(
            r"\b(sign|execute|register).{0,20}(agreement|deed|contract)\b",
            re.IGNORECASE,
        ),
        "Missing disclaimer: advising on document signing without recommending legal review",
        "*",
    ),
    # Citing Model Tenancy Act as enforceable without a caveat
    (
        re.compile(r"\bModel Tenancy Act\b", re.IGNORECASE),
        "Model Tenancy Act guard: confirm state has adopted MTA before citing it as enforceable",
        "Property",
    ),
    # Specific article/section numbers without act context
    (
        re.compile(
            r"\bSection\s+\d+\b(?!.{0,80}(?:act|code|rules|regulations|ordinance|order))",
            re.IGNORECASE,
        ),
        "Floating section: section number cited without accompanying act name",
        "*",
    ),
    # No next-step mentioned in response
    (
        re.compile(
            r"^(?!.*(?:you (can|should|may|must)|next step|contact|visit|file|lodge|apply|submit|speak to|consult))",
            re.IGNORECASE | re.DOTALL,
        ),
        "No actionable next step detected — ensure response includes at least one concrete action",
        "*",
    ),
]

@dataclass
class QualityIssue:
    pattern_desc: str
    severity: str    # "error" | "warning"
    category: str    # category filter this check belongs to, or "*" for all


@dataclass
class QualityResult:
    passed: bool
    issues: list[QualityIssue] = field(default_factory=list)

    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    def has_warnings(self) -> bool:
        return any(i.severity == "warning" for i in self.issues)

    def summary(self) -> str:
        if self.passed and not self.issues:
            return "OK"
        parts = [f"[{i.severity.upper()}] {i.pattern_desc}" for i in self.issues]
        return " | ".join(parts)


def check_response(text: str, category: str = "*") -> QualityResult:
    """Run all quality checks. .passed is False only on error-level hits; warnings are advisory."""
    issues: list[QualityIssue] = []

    for pattern, description in _FAIL_PATTERNS:
        if pattern.search(text):
            issues.append(QualityIssue(
                pattern_desc=description,
                severity="error",
                category="*",
            ))

    for pattern, description, pat_category in _WARN_PATTERNS:
        if pat_category != "*" and pat_category.lower() != category.lower():
            continue
        if pattern.search(text):
            issues.append(QualityIssue(
                pattern_desc=description,
                severity="warning",
                category=pat_category,
            ))

    passed = not any(i.severity == "error" for i in issues)
    return QualityResult(passed=passed, issues=issues)


def append_quality_note(text: str, result: QualityResult) -> str:
    """
    Append a brief quality note to *text* when issues were found.
    Only appends if there are errors (warnings are logged but not shown to users).

    Returns the (possibly modified) response string.
    """
    if result.passed:
        return text

    # Only surface error-level issues to users; warnings are for logging
    error_issues = [i for i in result.issues if i.severity == "error"]
    if not error_issues:
        return text

    note = (
        "\n\n---\n"
        "> **Disclaimer:** Some details in this response are general guidance only. "
        "Legal outcomes depend on specific facts and jurisdiction. "
        "Please verify any cited laws or section numbers with a qualified lawyer "
        "before taking action."
    )
    return text + note
