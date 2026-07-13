# Response Template

Umang structures every substantive legal response using the following sections.
The template is defined in `server/ai/response_template.py` and injected into
the composer system prompt at request time.

## Section Order

### `## Summary` *(required)*
1–2 sentences: what the problem is and what Umang can offer.
- Lead with what IS possible, not disclaimers.
- "you may have the right to..." not "you are guaranteed..."

### `## Issue Type` *(required)*
Legal category + sub-type.

**Categories**: Civil | Criminal | Employment | Family | Property | Consumer | Cyber | Administrative | Constitutional | Mixed

**Examples**:
- `Employment — wage dispute (labour matter)`
- `Property — tenant rights / illegal eviction`
- `Criminal — FIR refusal (cognizable offence)`

### `## Applicable Law` *(required)*
Bullet list of relevant Indian acts and sections.
- Only cite laws you are confident about
- Prefer BNS/BNSS/BSA 2023 for post-July-2024 matters
- If uncertain of section: name the Act + describe what it provides + "verify at legislative.gov.in"
- Max 3–4 provisions per response (depth > breadth)

### `## Your Rights` *(required)*
Numbered list of concrete rights in this situation.
- "You have the right to X under Y Act" is better than vague statements

### `## What You Can Do` *(required)*
Numbered step-by-step action plan, most accessible/free option first.

**Domain-specific escalation order**:
- Employment wage disputes: written demand → Labour Commissioner (free) → Labour Court → FIR ONLY if criminal
- Consumer disputes: company complaint → e-Daakhil (edaakhil.nic.in) → Consumer Forum
- Property/tenant: written notice → Rent Controller / Magistrate → civil court
- Family/DV: Protection Officer → Magistrate order → police if immediate danger

### `## Documents Needed` *(required)*
Bullet list — include non-obvious items:
- WhatsApp/email screenshots (employment)
- Bank statements showing missing credits (salary)
- Medical records (DV, negligence)
- Photos of locked door / eviction

### `## When to Contact Police` *(conditional — criminal element only)*
- Include for Criminal, Cyber categories
- For Employment/Property/Consumer: only if cognizable criminal offence present (fraud, forgery, assault)
- Never recommend FIR for unpaid salary, civil rent disputes, or warranty claims
- Use language: "police are generally required to register an FIR if a cognizable offence is disclosed"

### `## When to Contact a Lawyer` *(required)*
- State trigger conditions specifically
- Always mention free legal aid first: DLSA / NALSA (15100)

### `## Important Notes` *(required)*
2–4 bullets:
- Cannot guarantee outcome
- State-specific laws may vary
- Consult a lawyer for specific advice
- Do NOT include unverified helpline numbers

## Short / Follow-up Responses

For clarification questions, follow-ups, or very short queries: write 1–3 natural paragraphs without headers.

## Emergency Responses

Lead with immediate action (helpline + what to do NOW), then the structured sections.
