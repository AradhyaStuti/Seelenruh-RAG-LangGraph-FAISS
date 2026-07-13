"""
response_template.py
--------------------
Defines the canonical response structure for Umang's legal assistant.
Injected into the composer system prompt as a format specification.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Section definitions (ordered)
# ---------------------------------------------------------------------------

RESPONSE_SECTIONS: list[dict] = [
    {
        "heading": "## Summary",
        "required": True,
        "description": "1–2 sentence plain-language summary of the situation and what Umang can offer.",
        "notes": "Never start with 'I am not a lawyer'. Lead with what IS possible, not what isn't.",
    },
    {
        "heading": "## Issue Type",
        "required": True,
        "description": "State the legal category: Civil | Criminal | Employment | Family | Property | Consumer | Cyber | Administrative | Constitutional | Mixed.",
        "notes": "Also note sub-type: e.g., 'Employment — wage dispute (labour matter)'.",
    },
    {
        "heading": "## Applicable Law",
        "required": True,
        "description": "Bullet list of relevant acts and sections. Cite only laws you are confident about.",
        "notes": (
            "Prefer BNS/BNSS/BSA 2023 over IPC/CrPC/Evidence Act for post-July-2024 matters. "
            "Cite IPC/CrPC when the matter predates July 2024 or for pending cases. "
            "Always verify section numbers — do not guess."
        ),
    },
    {
        "heading": "## Your Rights",
        "required": True,
        "description": "Numbered list of the user's specific rights in this situation.",
        "notes": "Be concrete. 'You have the right to X under Y Act' is better than vague statements.",
    },
    {
        "heading": "## What You Can Do",
        "required": True,
        "description": "Numbered step-by-step action plan. Start with the most accessible/free option.",
        "notes": (
            "Employment disputes: start with Labour Commissioner (free), not FIR. "
            "Property disputes: start with written notice, then Rent Court. "
            "Consumer disputes: start with company complaint, then e-Daakhil / consumer forum."
        ),
    },
    {
        "heading": "## Documents Needed",
        "required": True,
        "description": "Bullet list of documents the user should gather or preserve.",
        "notes": "Include documents they may not think to save (WhatsApp screenshots, bank statements, medical records).",
    },
    {
        "heading": "## When to Contact Police",
        "required": False,
        "description": "Specific conditions under which an FIR is appropriate.",
        "notes": (
            "REQUIRED for Criminal and Cyber categories. "
            "For Employment/Property/Consumer: only include if a cognizable criminal offence (fraud, forgery, assault) is present. "
            "Never recommend FIR for civil disputes (unpaid salary, rent, warranty)."
        ),
    },
    {
        "heading": "## When to Contact a Lawyer",
        "required": True,
        "description": "Specific trigger conditions for consulting a lawyer.",
        "notes": "Always mention free legal aid (DLSA, 15100) as the first option before paid lawyers.",
    },
    {
        "heading": "## Important Notes",
        "required": True,
        "description": "2–4 bullet points with caveats, limitations, and disclaimers.",
        "notes": (
            "Always include: (a) cannot guarantee outcome, (b) depends on facts/jurisdiction, "
            "(c) consult a lawyer for your specific situation. "
            "Never include fake helpline numbers."
        ),
    },
]

# ---------------------------------------------------------------------------
# Compact format description — injected into system prompt
# ---------------------------------------------------------------------------

RESPONSE_TEMPLATE_DESCRIPTION = """\
RESPONSE FORMAT — use these sections IN ORDER:

## Summary
1–2 sentences: what is the problem and what can Umang help with.

## Issue Type
Legal category (Civil | Criminal | Employment | Family | Property | Consumer | Cyber | Administrative | Mixed) + sub-type.

## Applicable Law
Bullet list of relevant Indian acts and sections. Only cite laws you are confident about. Prefer BNS/BNSS/BSA 2023 for post-July-2024 matters.

## Your Rights
Numbered list of the user's concrete rights in this situation.

## What You Can Do
Numbered step-by-step action plan, most accessible/free option first.
- Employment wage disputes: Labour Commissioner first, FIR ONLY if fraud/criminal.
- Consumer disputes: company complaint first, then e-Daakhil / Consumer Forum.
- Property/tenant disputes: written notice, then Rent Court / Magistrate.

## Documents Needed
Bullet list of documents to gather or preserve (include non-obvious ones like WhatsApp screenshots).

## When to Contact Police  [include only if criminal element present]
Specific conditions for FIR. Never recommend FIR for civil salary/rent/warranty disputes.

## When to Contact a Lawyer
Trigger conditions. Always mention free legal aid (DLSA / 15100) before paid lawyers.

## Important Notes
2–4 bullets: (a) cannot guarantee outcome, (b) state-specific laws may vary, (c) consult a lawyer for specific advice. Do NOT include unverified helpline numbers.\
"""

# ---------------------------------------------------------------------------
# Disclaimer (appended to every response)
# ---------------------------------------------------------------------------

DISCLAIMER = (
    "\n\n---\n"
    "*Umang provides general legal information, not legal advice. "
    "Outcomes depend on specific facts, jurisdiction, and applicable state law. "
    "For your specific situation, consult a qualified lawyer — "
    "free legal aid is available through the District Legal Services Authority (DLSA) at 15100.*"
)
