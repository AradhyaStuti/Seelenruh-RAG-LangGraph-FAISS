"""Check LLM responses for hallucinated section numbers.

Maintains a whitelist of Indian statutes with their valid section ranges.
If a cited section exceeds the known max, we append a verification note.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# act name / alias → max valid section number
KNOWN_ACTS: dict[str, dict] = {
    # Constitution & criminal codes
    "constitution of india": {"max_section": 395, "aliases": ["article", "constitution"]},
    "bharatiya nyaya sanhita": {"max_section": 358, "aliases": ["bns", "bns 2023"]},
    "bharatiya nagarik suraksha sanhita": {"max_section": 531, "aliases": ["bnss", "bnss 2023"]},
    "bharatiya sakshya adhiniyam": {"max_section": 170, "aliases": ["bsa", "bsa 2023", "bharatiya sakshya"]},
    # Legacy criminal codes (still cited in pending cases)
    "indian penal code": {"max_section": 511, "aliases": ["ipc", "i.p.c"]},
    "code of criminal procedure": {"max_section": 484, "aliases": ["crpc", "cr.p.c", "cr pc"]},
    "indian evidence act": {"max_section": 167, "aliases": ["evidence act 1872"]},
    # Civil & family
    "code of civil procedure": {"max_section": 158, "aliases": ["cpc", "c.p.c"]},
    "hindu marriage act": {"max_section": 30, "aliases": ["hma", "hindu marriage act 1955"]},
    "hindu succession act": {"max_section": 30, "aliases": ["hsa", "hindu succession act 1956"]},
    "protection of women from domestic violence act": {"max_section": 37, "aliases": ["pwdva", "domestic violence act", "dv act"]},
    "muslim personal law": {"max_section": 0, "aliases": ["shariat act", "muslim personal law application act"]},
    "special marriage act": {"max_section": 50, "aliases": ["special marriage act 1954"]},
    "guardian and wards act": {"max_section": 43, "aliases": []},
    # Employment
    "code on wages": {"max_section": 69, "aliases": ["code on wages 2019", "wages code"]},
    "industrial relations code": {"max_section": 105, "aliases": ["industrial relations code 2020", "ir code"]},
    "social security code": {"max_section": 164, "aliases": ["social security code 2020", "ss code"]},
    "occupational safety health and working conditions code": {"max_section": 143, "aliases": ["osh code", "ohs code 2020"]},
    "payment of wages act": {"max_section": 26, "aliases": ["payment of wages act 1936"]},
    "minimum wages act": {"max_section": 31, "aliases": ["minimum wages act 1948"]},
    "employees provident funds act": {"max_section": 20, "aliases": ["epf act", "epf act 1952", "provident fund act"]},
    "maternity benefit act": {"max_section": 29, "aliases": ["maternity benefit act 1961"]},
    "sexual harassment of women at workplace act": {"max_section": 30, "aliases": ["posh act", "posh act 2013", "shww act"]},
    "factories act": {"max_section": 120, "aliases": ["factories act 1948"]},
    "shops and establishments act": {"max_section": 0, "aliases": ["shops act", "shops & establishments", "s&e act"]},
    # Consumer & property
    "consumer protection act": {"max_section": 107, "aliases": ["consumer protection act 2019", "copa"]},
    "transfer of property act": {"max_section": 137, "aliases": ["tpa", "transfer of property act 1882"]},
    "registration act": {"max_section": 107, "aliases": ["registration act 1908"]},
    "rent control act": {"max_section": 0, "aliases": ["rent act", "rent control"]},
    "model tenancy act": {"max_section": 45, "aliases": ["model tenancy act 2021", "mta"]},
    # Cyber & data
    "information technology act": {"max_section": 90, "aliases": ["it act", "it act 2000", "cyber law"]},
    "digital personal data protection act": {"max_section": 44, "aliases": ["dpdp act", "dpdp act 2023", "data protection act"]},
    # Other important acts
    "right to information act": {"max_section": 31, "aliases": ["rti act", "rti act 2005"]},
    "legal services authorities act": {"max_section": 28, "aliases": ["legal aid act", "nalsa act"]},
    "national commission for protection of child rights act": {"max_section": 32, "aliases": ["ncpcr act", "pocso act", "protection of children from sexual offences act"]},
    "narcotic drugs and psychotropic substances act": {"max_section": 82, "aliases": ["ndps act", "ndps act 1985"]},
    "arbitration and conciliation act": {"max_section": 87, "aliases": ["arbitration act", "arbitration act 1996"]},
    "insolvency and bankruptcy code": {"max_section": 358, "aliases": ["ibc", "ibc 2016", "bankruptcy code"]},
    "goods and services tax act": {"max_section": 174, "aliases": ["gst act", "cgst act", "igst act"]},
}

_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _canonical, _info in KNOWN_ACTS.items():
    _ALIAS_TO_CANONICAL[_canonical] = _canonical
    for _alias in _info.get("aliases", []):
        _ALIAS_TO_CANONICAL[_alias.lower()] = _canonical


# catches "Section 42", "S. 420", "Art. 21" etc.
_SECTION_PATTERN = re.compile(
    r"\b(?:section|sec|s\.|article|art\.)\s*(\d{1,4})[A-Z]?\b",
    re.IGNORECASE,
)

# look this far around a section ref to find the act name
_ACT_WINDOW = 120

@dataclass
class CitationIssue:
    text: str          # The problematic text snippet
    reason: str        # Human-readable reason
    severity: str      # "error" | "warning"


@dataclass
class GuardrailResult:
    passed: bool
    issues: list[CitationIssue] = field(default_factory=list)
    flagged_sections: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.passed:
            return "OK"
        parts = [f"[{i.severity.upper()}] {i.reason}" for i in self.issues]
        return "; ".join(parts)


def is_known_act(act_name: str) -> bool:
    """Return True if act_name (or a known alias) is in the whitelist."""
    return act_name.strip().lower() in _ALIAS_TO_CANONICAL


def get_act_info(act_name: str) -> Optional[dict]:
    """Return the act metadata dict, or None if not found."""
    canonical = _ALIAS_TO_CANONICAL.get(act_name.strip().lower())
    if canonical:
        return {"canonical_name": canonical, **KNOWN_ACTS[canonical]}
    return None


def validate_citations(text: str, strict: bool = False) -> GuardrailResult:
    """Scan text for section references and flag any that exceed the known max for their act."""
    issues: list[CitationIssue] = []
    flagged: list[str] = []

    text_lower = text.lower()

    for m in _SECTION_PATTERN.finditer(text):
        section_num = int(m.group(1))
        start = max(0, m.start() - _ACT_WINDOW)
        end = min(len(text), m.end() + _ACT_WINDOW)
        window = text_lower[start:end]

        matched_canonical: Optional[str] = None
        for alias, canonical in _ALIAS_TO_CANONICAL.items():
            if alias and alias in window:
                matched_canonical = canonical
                break

        if matched_canonical is None:
            if strict:
                snippet = text[m.start() : m.end() + 40].strip()
                issues.append(CitationIssue(
                    text=snippet,
                    reason=f"Section {section_num} cited without a recognisable act name nearby",
                    severity="warning",
                ))
                flagged.append(f"Section {section_num} (no act context)")
            continue

        max_sec = KNOWN_ACTS[matched_canonical]["max_section"]
        if max_sec and section_num > max_sec:
            snippet = text[m.start() : m.end() + 60].strip()
            issues.append(CitationIssue(
                text=snippet,
                reason=(
                    f"Section {section_num} exceeds known max ({max_sec}) "
                    f"for '{matched_canonical}' — possible hallucination"
                ),
                severity="error",
            ))
            flagged.append(f"Section {section_num} of {matched_canonical}")

    passed = not any(i.severity == "error" for i in issues)
    return GuardrailResult(passed=passed, issues=issues, flagged_sections=flagged)


def build_guardrail_note(result: GuardrailResult) -> str:
    """Returns a disclaimer to append when citations look suspect. Empty string if all good."""
    if result.passed:
        return ""
    return (
        "\n\n> **Note:** One or more legal references in this response could "
        "not be fully verified. Please confirm section numbers with an "
        "authoritative source or a qualified lawyer before acting on them."
    )
