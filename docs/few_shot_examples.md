# Few-Shot Examples

Curated examples injected into Umang's composer system prompt to demonstrate
the expected response style. Defined in `server/ai/few_shot_examples.py`.

## Purpose

Few-shot examples:
1. Demonstrate the **exact response structure** the model should follow
2. Show **tone**: calm, direct, no overpromising, no clichés
3. Demonstrate **FIR guard** (salary disputes → Labour Commissioner, not police)
4. Show **language mirroring** (Hinglish query → Hinglish response)
5. Show **German-language** Indian law responses (not German law)

## Selection Logic (`get_few_shot_examples()`)

Examples are scored and selected by:
1. **Category + language match** (score: 2) — e.g., Employment + hi-roman
2. **Category match only** (score: 1) — same category, any language
3. **Language match only** (score: 0) — same language, any category
4. Unmatched examples are excluded

At most `max_examples=1` example is injected per Legal request to save tokens.

## Example Bank (10 examples)

| ID | Category | Language | Query topic |
|----|----------|----------|-------------|
| `ex_landlord_lockout_en` | Property | en | Landlord changed locks illegally |
| `ex_salary_withheld_en` | Employment | en | 3 months salary not paid (private employee) |
| `ex_wrongful_termination_hi_roman` | Employment | hi-roman | Fired without notice (Hinglish) |
| `ex_fir_refused_en` | Criminal | en | Police refusing to register FIR |
| `ex_upi_fraud_en` | Cyber | en | UPI/vishing fraud — ₹45,000 lost |
| `ex_consumer_complaint_en` | Consumer | en | Warranty refused on 8-month-old refrigerator |
| `ex_domestic_violence_en` | Family | en | Husband beating wife — 2 children |
| `ex_property_dispute_en` | Property | en | Brother sold inherited property without consent |
| `ex_pf_withdrawal_en` | Employment | en | EPFO PF withdrawal claim rejected |
| `ex_german_tenant_de` | Property | de | Landlord raising rent 50% (German speaker in India) |

## Key Patterns Demonstrated

### FIR Guard (Salary)
```
Example: ex_salary_withheld_en
Shows: "Step 5 — FIR only if criminal: An FIR is NOT appropriate for unpaid salary alone."
```

### Language Mirroring (Hinglish)
```
Example: ex_wrongful_termination_hi_roman
Shows: Full response in Roman-script Hindi, Indian laws only, legal terms in English
```

### German — Indian Law Only
```
Example: ex_german_tenant_de
Shows: Response in German, cites Indian Rent Control Act (not German Mietrecht)
```

### Emergency + Legal Structure
```
Example: ex_domestic_violence_en
Shows: Safety helplines FIRST (112, 181), then legal rights under PWDVA
```

## Adding New Examples

Add to the `EXAMPLES` list in `server/ai/few_shot_examples.py`:

```python
FewShotExample(
    id="ex_my_new_example",
    category="Consumer",   # or Employment, Property, Criminal, Family, Cyber, *
    lang="hi-roman",       # or en, hi, de, *
    user_query="...",
    ideal_response="""\
## Summary
...
## Issue Type
...
""",
)
```
