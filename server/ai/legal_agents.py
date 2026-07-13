"""
Umang's specialized legal reasoning agents — internal only, invisible to the user.

The user sees ONE assistant (Umang). Internally, specialized agents collaborate:

  Agent 1 — Case Analyzer        (8B LLM, ~150 ms):  classify, extract known facts,
                                                        detect missing facts, identify
                                                        domains, flag limitation concerns
  Agent 2 — Rights Organizer     (Python):             filter RAG chunks for rights
  Agent 3 — Procedure Organizer  (Python):             filter RAG chunks for procedure
  Agent 4 — Document Assistant   (Python):             load template if draft requested
  Agent 5 — Legal Reasoner       (Python):             build deterministic reasoning
                                                        context from _LEGAL_KNOWLEDGE
  Agent 6 — Jurisdiction Detector(Python):             extract state / court from text
  Agent 7 — Response Composer    (70B LLM):            synthesise the final response

Total LLM calls: 2 (8B analyze + 70B compose).
"""
import json
from typing import Optional

from ai.context import trim_history
from ai.provider import chat
from config import GROQ_MODEL_FAST
from logger import get_logger

log = get_logger("legal_agents")


# ──────────────────────────────────────────────────────────────
# AGENT 1 — CASE ANALYZER (8B)
# ──────────────────────────────────────────────────────────────

_CASE_ANALYZER_SYSTEM = """\
You are a senior Indian legal case analyst for Umang, a legal information assistant.
Analyse the user's query using this reasoning chain:
  1. Identify the legal issue and its type (civil / criminal / family / consumer / employment / property / cyber / administrative / constitutional)
  2. Identify the jurisdiction (which state, central law, or personal law)
  3. Identify applicable law framework (Labour Code / Consumer Act / IPC-BNS / personal law / etc.)
  4. Identify what evidence would matter
  5. Identify the correct remedy and authority
  6. Extract or flag missing facts that would materially change the guidance

Output ONLY a valid JSON object — no markdown, no explanation.

{
  "category": "DomesticViolence|Divorce|Maintenance|FIR|Consumer|RTI|Tenant|Employment|Property|Cybercrime|POSH|ChequeBounce|Bail|POCSO|Constitutional|Criminal|Contract|Inheritance|MedicalNegligence|LabourCodes|DPDP|MotorVehicles|ChildCustody|RTE|General",
  "issue_type": "Civil|Criminal|Family|Consumer|Employment|Property|Cyber|Administrative|Constitutional|Mixed",
  "urgency": "immediate|recent|informational",
  "multi_domain": false,
  "secondary_categories": [],
  "known_facts": [],
  "missing_facts": [],
  "limitation_concern": false,
  "needs_rights": true,
  "needs_procedure": true,
  "needs_document": false,
  "doc_type": null,
  "needs_evidence_guide": false,
  "needs_cost_estimate": false,
  "state_hint": null,
  "personal_law": null,
  "employment_type": null,
  "property_type": null,
  "follow_up": null
}

Rules:
- issue_type: the LEGAL NATURE of the dispute — determines which court / authority handles it:
  Civil = contracts, property, money recovery, injunctions
  Criminal = FIR, arrest, prosecution (BNS/IPC offences)
  Family = divorce, maintenance, custody, inheritance under personal law
  Consumer = deficiency of service, product defect, unfair trade practice
  Employment = unpaid wages, wrongful termination, F&F, POSH, PF disputes
  Property = rent/eviction, land rights, RERA, succession
  Cyber = IT Act offences, data breach, online fraud
  Administrative = RTI, government officer misconduct, scheme denial
  Constitutional = fundamental rights, writ jurisdiction
  Mixed = genuinely straddles 2+ types (e.g. domestic violence is Family + Criminal)
- category: single MOST SPECIFIC match for the primary legal issue
  Use "Contract" for breach of contract, service agreements, freelancer disputes, builder defaults
  Use "Inheritance" for will disputes, succession, ancestral property, intestate succession
  Use "MedicalNegligence" for hospital errors, wrong surgery, delayed diagnosis, doctor misconduct
  Use "Employment" for unpaid salary, salary withheld, F&F not settled, experience letter withheld, wrongful termination, notice period pay — these are LABOUR/CIVIL matters; only add "Criminal" as secondary_category if facts clearly indicate fraud or criminal breach of trust
  Use "LabourCodes" for PF/EPF disputes, gratuity denial, maternity benefit, gig worker rights, Labour Code compliance
  Use "DPDP" for data privacy, data breach, personal data misuse, consent withdrawal, Data Protection Board
  Use "MotorVehicles" for road accidents, MACT claims, third-party insurance, hit-and-run, traffic offences
  Use "ChildCustody" for custody of minor children, guardianship, visitation rights, parental disputes over children
  Use "RTE" for school admission (EWS/25% quota), free education, physical punishment in school, child education rights
  Use "Criminal" for general criminal matters (assault, theft, cheating) not covered by more specific categories
  Use "General" ONLY when no specific category fits
- urgency (be precise):
  "immediate" = danger or crisis happening RIGHT NOW (ongoing violence, active arrest, medical emergency)
  "recent" = incident occurred within last 1–7 days AND evidence/deadlines exist (fresh cheque bounce, recent termination, just filed FIR)
  "informational" = asking about law in general, or incident is old (>1 week) with no active deadline
- multi_domain: true only if situation genuinely spans 2+ independent legal areas
  Example TRUE: domestic violence + child custody + maintenance (3 areas)
  Example FALSE: employment termination + unpaid salary (same area — Employment)
- secondary_categories: up to 2 additional categories IF multi_domain=true; else []
- known_facts: specific facts the user explicitly stated (max 5 short strings)
  Examples: "cheque amount ₹50,000", "bounced 2 weeks ago", "in Maharashtra", "private company employer", "married under HMA", "no written contract"
- missing_facts: facts NOT provided that would materially change the guidance (max 3)
  For Tenant: ["state/city of property", "written rent agreement or oral only", "occupancy type: rented flat / PG / hostel / commercial / agricultural"]
  For Divorce: ["personal law / religion", "contested or mutual consent"]
  For Employment: ["government or private employer", "workman or managerial role", "still employed or terminated", "how many months salary unpaid", "appointment/offer letter available"]
  For ChequeBounce: ["days since return memo received", "legal notice already sent?"]
  For Contract: ["written contract or verbal", "amount involved", "nature of breach"]
  For Inheritance: ["deceased's religion / applicable personal law", "will exists or intestate"]
  Leave [] if query is purely informational OR sufficient facts already present.
- limitation_concern: true if a time-critical legal deadline may be APPROACHING or already MISSED
  Approaching: "cheque bounced yesterday" → 30-day notice window starts
  Missed: "my case was dismissed 70 days ago but no chargesheet" → default bail right may have been missed
  Key windows: ChequeBounce notice 30 days | Consumer court 2 years | POSH complaint 3 months |
               Default bail 60/90 days from FIR | RTI first appeal 30 days | POCSO no limit
- needs_document: true ONLY if user explicitly says "write", "draft", "generate", "make a letter/notice/affidavit"
- doc_type (only when needs_document=true): RTI | ConsumerComplaint | PoliceComplaint | LegalNotice | Affidavit | null
- needs_evidence_guide: true if user is gathering evidence, preparing to file, or asking "what proof do I need"
- needs_cost_estimate: true if user asks about fees, court costs, lawyer charges, or "can I afford"
- state_hint: exact Indian state name if clearly mentioned (e.g. "Maharashtra", "Delhi", "Tamil Nadu"), else null
- personal_law: for Divorce / Maintenance / Inheritance — Hindu | Muslim | Christian | Parsi | Special | null
- employment_type: for Employment / LabourCodes — extract from user message if stated:
  "private_employee" | "government_employee" | "contract_worker" | "gig_worker" | "domestic_worker" | "intern" | "apprentice" | "factory_worker" | null
  Different legal frameworks apply: ID Act (private workmen) | Service Rules (government) | Contract Labour Act | Code on Social Security (gig/domestic) | Apprentices Act (apprentice)
- property_type: for Tenant / Property disputes — extract from user message if stated:
  "rented_residential" | "pg_hostel" | "commercial_lease" | "agricultural" | "owned_property" | "inherited_property" | null
  Determines whether Rent Control Act / Transfer of Property Act / agricultural tenancy law / personal law applies
- follow_up: ONE natural conversation question whose answer would most change the guidance
  CRITICAL: set follow_up to null if missing_facts is empty []
  Make it conversational ("Which state are you in?") NOT form-like ("State: ___")

Output ONLY the JSON object. No markdown. No commentary."""


async def analyze_case(query: str, history: list[dict], lang: str) -> dict:
    """
    Agent 1: Case Analyzer — fast 8B model.
    Returns structured case facts; falls back to safe defaults on any failure.
    """
    default: dict = {
        "category": "General",
        "urgency": "informational",
        "multi_domain": False,
        "secondary_categories": [],
        "known_facts": [],
        "missing_facts": [],
        "limitation_concern": False,
        "needs_rights": True,
        "needs_procedure": True,
        "needs_document": False,
        "doc_type": None,
        "needs_evidence_guide": False,
        "needs_cost_estimate": False,
        "state_hint": None,
        "personal_law": None,
        "issue_type": None,
        "employment_type": None,
        "property_type": None,
        "follow_up": None,
    }

    recent_text = ""
    if history:
        snippets = [f"{m['role'].upper()}: {m['content'][:200]}" for m in history[-4:]]
        recent_text = "\nRecent conversation:\n" + "\n".join(snippets)

    messages = [
        {"role": "system", "content": _CASE_ANALYZER_SYSTEM},
        {"role": "user", "content": f"User query: {query}{recent_text}"},
    ]

    try:
        result = await chat(model=GROQ_MODEL_FAST, temperature=0.0, max_tokens=350, messages=messages)
        raw = result["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            raw = raw[4:] if raw.startswith("json") else raw
        parsed = json.loads(raw)
        merged = {**default, **{k: v for k, v in parsed.items() if k in default}}
        # Sanitise list fields
        for field in ("secondary_categories", "known_facts", "missing_facts"):
            if not isinstance(merged.get(field), list):
                merged[field] = []
        # Enforce consistency: follow_up must be null when no missing_facts
        if not merged.get("missing_facts"):
            merged["follow_up"] = None
        # Enforce: secondary_categories only when multi_domain=True
        if not merged.get("multi_domain"):
            merged["secondary_categories"] = []
        return merged
    except Exception as err:
        log.warning("case_analyzer failed — using defaults", error=str(err))
        return default


# ──────────────────────────────────────────────────────────────
# AGENT 5 — LEGAL KNOWLEDGE BASE (Python, deterministic)
# Maps every category to: laws, remedies, evidence, procedure,
# limitation periods, costs, timelines, common mistakes, aid.
# Never changes without a human review — not LLM-generated.
# ──────────────────────────────────────────────────────────────

_LEGAL_KNOWLEDGE: dict[str, dict] = {
    "DomesticViolence": {
        "applicable_laws": [
            "Protection of Women from Domestic Violence Act, 2005 (PWDVA) — civil remedies: protection orders, residence orders, maintenance",
            "BNS Section 85-86 (formerly IPC 498A) — cruelty by husband/relatives; cognizable, non-bailable",
            "Dowry Prohibition Act 1961 + BNS Section 80 — dowry-related cruelty and death",
            "BNSS Section 173 — mandatory FIR for cognizable offences",
        ],
        "typical_remedies": [
            "Protection Order — court prevents abuser from committing further violence",
            "Residence Order — right to stay in shared household even if not owner",
            "Monetary relief / maintenance under PWDVA Section 20",
            "Criminal FIR under BNS 85/86 — criminal liability for abuser",
            "Custody order for children if applicable",
        ],
        "evidence_checklist": [
            "Medical reports and doctor's certificates of injuries (go to government hospital)",
            "Date-stamped photographs of injuries",
            "Screenshots of threatening or abusive messages (WhatsApp, SMS, email)",
            "Names and contact details of witnesses (neighbours, family, colleagues)",
            "Any previous police complaints, NCR copies, or court orders",
            "Marriage certificate",
            "Children's documents if custody is involved",
        ],
        "procedure_steps": [
            "Immediate safety: call 112 (emergency) or 1091 (women's helpline) if in danger",
            "Contact Protection Officer (PO) in your district — file Domestic Incident Report (DIR) — free",
            "Alternatively: approach Magistrate's court directly with DV complaint",
            "File FIR at police station under BNS 85/86 for criminal liability",
            "Apply simultaneously for Protection Order + Residence Order from Magistrate",
            "Approach nearest One Stop Centre (at district hospitals) — free shelter, medical, legal, police",
        ],
        "limitation_period": "No strict limitation for PWDVA. FIR: file immediately. Protection Orders can be applied anytime while danger exists.",
        "authorities": [
            "Protection Officer (every district, free)", "Judicial Magistrate / Metropolitan Magistrate",
            "Police SHO (for BNS 85/86 FIR)", "One Stop Centre (district hospitals, free)",
            "NCW: 7827170170", "Women's Helpline: 1091", "Emergency: 112",
        ],
        "typical_timeline": "Interim Protection Order: 3–7 working days. FIR → chargesheet: 60–90 days. Trial: 1–3 years.",
        "typical_costs": "PWDVA complaint: Free. FIR: Free. Legal aid through NALSA: Free for eligible persons.",
        "common_mistakes": [
            "Leaving the shared household immediately — may weaken Residence Order claim",
            "Not getting medical reports — these are critical evidence",
            "Accepting private settlement without a court record",
            "Delaying FIR — early filing is far stronger",
        ],
        "free_legal_aid": "NALSA (nalsa.gov.in | 15100). One Stop Centres provide free legal counselling. State DLSA free helpline.",
    },

    "Divorce": {
        "applicable_laws": [
            "Hindu Marriage Act, 1955 (HMA) Sec 13 — grounds: cruelty, adultery, desertion (2 yrs), conversion, mental disorder",
            "HMA Section 13B — mutual consent divorce (two motions, 6-18 month cooling period, waivable to 6 months)",
            "Special Marriage Act, 1954 — for civil/inter-religious marriages",
            "Muslim Women (Protection of Rights on Divorce) Act, 1986",
            "Indian Divorce Act, 1869 — Christians; Parsi Marriage and Divorce Act, 1936 — Parsis",
            "HMA Section 24 — interim maintenance during proceedings; Section 25 — permanent alimony",
            "HMA Section 26 — child custody; Section 27 — matrimonial property",
        ],
        "typical_remedies": [
            "Decree of divorce dissolving the marriage",
            "Interim maintenance during pendency (HMA Sec 24)",
            "Permanent alimony after divorce (HMA Sec 25)",
            "Child custody and visitation order (HMA Sec 26)",
            "Division of matrimonial property",
        ],
        "evidence_checklist": [
            "Marriage certificate / Nikahnama / registration document",
            "Evidence of grounds (for cruelty: medical reports, messages, witness statements; for desertion: date of departure proof)",
            "Financial documents of both parties: salary slips, ITR, bank statements (for maintenance)",
            "Property documents if division sought",
            "Children's birth certificates if custody involved",
            "Any existing court orders or injunctions",
        ],
        "procedure_steps": [
            "Mutual consent (HMA 13B): joint petition → first motion → 6-18 month gap (waivable to 6 months on application) → second motion → decree",
            "Contested: petition in Family Court → serve notice → evidence stage → arguments → decree",
            "File simultaneously for interim maintenance (HMA Sec 24) — do not wait for final decree",
            "Mandatory mediation referral by most family courts — attend, even if you expect it to fail",
        ],
        "limitation_period": "Marriage must be at least 1 year old before filing petition (exceptions for exceptional hardship). No upper limitation.",
        "authorities": [
            "Family Court (cities with Family Courts Act 1984 courts)",
            "District Court or Principal Civil Court of Original Jurisdiction (elsewhere)",
            "Mediation Centre (attached to most courts)",
        ],
        "typical_timeline": "Mutual consent: 6–18 months. Contested: 2–5 years depending on grounds and cooperation.",
        "typical_costs": "Filing fee: ₹200–₹500. Lawyer: ₹15,000–₹1,00,000+ (contested). NALSA legal aid for eligible persons.",
        "common_mistakes": [
            "Not filing for interim maintenance immediately — do it separately, it takes months",
            "Agreeing on asset/custody terms verbally without court record",
            "Missing the 6-month waiver window — courts have discretion, apply early",
            "Not addressing children's custody and maintenance in the same petition",
        ],
        "free_legal_aid": "NALSA for women and economically weaker sections. Family court legal services committees have duty lawyers.",
    },

    "Maintenance": {
        "applicable_laws": [
            "BNSS Section 144 (formerly CrPC 125) — interim maintenance for wife, children, parents; Magistrate court; fastest route",
            "HMA Section 24 — interim maintenance during divorce proceedings (both spouses can apply)",
            "HMA Section 25 — permanent alimony after divorce decree",
            "Muslim Women (Protection of Rights on Divorce) Act, 1986 — for Muslim divorces; Danial Latifi (2001) SC mandates reasonable provision for entire life",
            "PWDVA Section 20 — monetary relief including maintenance in DV cases; can overlap with BNSS 144",
            "Maintenance and Welfare of Parents and Senior Citizens Act, 2007 — Section 4: parents/grandparents can claim maintenance from children/grandchildren (Max ₹10,000/month before 2019 amendment; states may raise cap)",
            "Senior Citizens Act 2007, Section 23 — CRITICAL: any property transfer (gift, will, sale) by a senior citizen to children/relatives is VOIDABLE if the transferee fails to provide basic amenities and physical needs; Tribunal can set aside the transfer",
            "Senior Citizens Act 2007, Section 7 — Maintenance Tribunal: District Magistrate/SDM is the adjudicating authority; fast-track (disposal within 90 days)",
            "Special Marriage Act Section 36/37 — maintenance for inter-faith / civil marriages",
        ],
        "typical_remedies": [
            "Interim maintenance order pending hearing (typically within 60 days under BNSS 144)",
            "Permanent maintenance / alimony monthly order",
            "Recovery of arrears (with potential imprisonment for wilful default — BNSS 144(3))",
            "Attachment of salary, bank account, or property for enforcement",
            "For senior citizens: Tribunal order for monthly maintenance up to ₹10,000 (or state cap)",
            "Property transfer revocation under Senior Citizens Act Section 23 — can recover gifted/sold property if children neglect them",
            "Eviction of neglectful children from senior citizen's own residence (Section 23(1))",
        ],
        "evidence_checklist": [
            "Marriage certificate (for spousal maintenance)",
            "Income evidence for both parties: salary slips, ITR, Form 16, bank statements, business records",
            "Own expense documents: rent, utility bills, children's school fees, medical bills",
            "Children's birth certificates, school fee receipts (for child support)",
            "Proof the other party has income/assets (if they claim no income) — request via court discovery",
            "For Senior Citizens Act: property transfer deed/gift deed, proof of neglect (witness statements, medical bills showing non-payment, police complaint if abandoned), age proof of senior citizen",
            "Medical expenses of senior citizen or ailing applicant",
        ],
        "procedure_steps": [
            "Spouse/child maintenance: File under BNSS Section 144 before Family Magistrate — fastest route, no divorce needed",
            "In ongoing divorce proceedings: simultaneously file HMA Section 24 application in Family Court",
            "Senior citizens claiming maintenance from children: File before Maintenance Tribunal (SDM/DM office) under Senior Citizens Act Section 4 — free, no lawyer required",
            "Senior citizen property reversal: File application before Maintenance Tribunal under Section 23 — Tribunal can set aside the gift/transfer deed within 90 days",
            "After maintenance order: if payments are missed, file execution petition immediately",
            "Court can attach salary, bank account, or property to enforce payment",
        ],
        "limitation_period": "BNSS 144: no strict limitation (but courts may limit retrospective arrears — apply promptly). Senior Citizens Act: no specific limitation stated; file as soon as neglect begins. HMA 25: apply within proceedings.",
        "authorities": [
            "Family Magistrate Court (for BNSS 144)",
            "Family Court (for HMA 24/25, SMA 36/37)",
            "Maintenance Tribunal — SDM / DM office (for Senior Citizens Act Sections 4 & 23)",
            "District Court where no Family Court exists",
            "Appellate Tribunal: Sessions Court (Senior Citizens Act appeals)",
        ],
        "typical_timeline": "Interim order under BNSS 144: 1–3 months. Senior Citizens Act Tribunal: 90 days (mandated). Final maintenance order: 6 months–2 years.",
        "typical_costs": "Filing: ₹200–₹500. Senior Citizens Act Tribunal: FREE (no court fee). Lawyer: ₹10,000–₹50,000. NALSA legal aid for eligible persons.",
        "common_mistakes": [
            "Waiting too long — courts may limit retrospective arrears to the date of application",
            "Senior citizens not knowing Section 23 exists — they CAN get back transferred property",
            "Not disclosing all of other party's income sources — request bank statements through court",
            "Not enforcing when payments lapse — file execution petition promptly, don't wait",
            "Settling too low under financial pressure — revision petition requires significant change in circumstances",
            "Confusing BNSS 144 (Magistrate, faster) with HMA 24 (Family Court, during divorce only)",
        ],
        "free_legal_aid": "NALSA (nalsa.gov.in | 15100). State DLSA in every district. Senior Citizens Act Tribunal is FREE — no lawyer or court fee required. Women's helplines provide referrals. Dignity Foundation and HelpAge India assist senior citizens.",
    },

    "FIR": {
        "applicable_laws": [
            "BNSS Section 173 (formerly CrPC 154) — mandatory FIR for cognizable offences; police cannot refuse",
            "BNSS Section 173(4) — accused/informant gets free copy of FIR on request",
            "BNSS Section 175(3) — Magistrate can direct FIR if police refuse",
            "Supreme Court: Lalita Kumari v. UP (2014) — FIR is mandatory for cognizable offences, no prior inquiry",
            "Zero FIR — valid at ANY police station regardless of jurisdiction; must be transferred to correct station",
        ],
        "typical_remedies": [
            "Immediate FIR registration (legally mandated for cognizable offences)",
            "Written complaint to SP/DCP if SHO refuses",
            "Magistrate order directing FIR under BNSS 175(3)",
            "High Court writ if Magistrate also fails",
        ],
        "evidence_checklist": [
            "Your written complaint (signed, keep a copy stamped by police)",
            "Any documentary evidence of offence (photos, screenshots, receipts)",
            "Witness names and contact details",
            "Medical reports if physical injury",
            "Bank statements / transaction records if financial fraud",
        ],
        "procedure_steps": [
            "Visit police station, approach SHO/duty officer, give complaint (oral or written)",
            "For cognizable offence: FIR must be registered immediately — police cannot refuse",
            "Demand free copy of FIR — this is a legal right under BNSS 173(4)",
            "If SHO refuses: send written complaint via Speed Post/registered post to SP/DCP of district",
            "If SP also refuses: file before Judicial Magistrate under BNSS 175(3)",
            "Zero FIR: if crime was in a different jurisdiction, file at nearest station; police must transfer it",
        ],
        "limitation_period": "No fixed limitation for serious cognizable offences. Report as soon as possible — delay weakens evidence.",
        "authorities": [
            "SHO of nearest police station", "SP / DCP of district (if police inaction)",
            "Judicial Magistrate (can direct FIR)", "High Court (writ if all else fails)",
        ],
        "typical_timeline": "FIR must be registered immediately. Investigation: 60–90 days for minor offences. Charge sheet: 60–90 days under BNSS.",
        "typical_costs": "Filing FIR: Free. Magistrate complaint: ₹100–₹500.",
        "common_mistakes": [
            "Accepting NCR instead of FIR for cognizable offences — insist on FIR",
            "Not demanding your free copy of the FIR",
            "Providing vague information — be specific about date, time, place, accused",
            "Assuming FIR only at crime-scene jurisdiction — Zero FIR is valid everywhere",
        ],
        "free_legal_aid": "NALSA. DLSA if police are unresponsive.",
    },

    "Consumer": {
        "applicable_laws": [
            "Consumer Protection Act, 2019 (CPA 2019) — primary law for consumer rights",
            "Section 2(7) — consumer definition (excludes commercial purchases for resale)",
            "Section 35 — complaint to District Consumer Commission (up to ₹50 lakh)",
            "Section 47 — State Commission (₹50 lakh – ₹2 crore)",
            "Section 58 — National Commission / NCDRC (above ₹2 crore)",
            "Consumer Protection (E-Commerce) Rules, 2020 — for online purchases",
            "Section 18 — CCPA for misleading advertisements and product recalls",
        ],
        "typical_remedies": [
            "Replacement of defective product",
            "Full refund of purchase price",
            "Repair at seller's cost",
            "Compensation for mental agony and inconvenience",
            "Litigation costs awarded",
            "Cancellation of unfair contract terms",
        ],
        "evidence_checklist": [
            "Invoice / receipt / purchase proof",
            "Warranty card or service agreement",
            "Screenshots of online order and product description as shown at purchase",
            "All complaint emails and chat transcripts with company (with dates)",
            "Company's written rejection or silence proof",
            "Photographs of defective product",
            "Bank / payment statements showing transaction",
            "Delivery receipt with date",
        ],
        "procedure_steps": [
            "Step 1: File formal complaint with company's grievance team — get a complaint number in writing",
            "Step 2: If unresolved in 15 days: send formal demand letter / legal notice with 15-day deadline",
            "Step 3: File Consumer Complaint at DCDRC — online: edaakhil.nic.in or visit commission office",
            "Pay nominal court fee (₹200–₹5000 based on claim amount)",
            "Mandatory mediation attempt under 2019 Act before adjudication",
            "If mediation fails: hearing and final order — no lawyer strictly required",
        ],
        "limitation_period": "⚠ 2 YEARS from date of defect/deficiency. If company keeps promising resolution, limitation may be extended. Do not wait too long.",
        "authorities": [
            "District Consumer Disputes Redressal Commission (DCDRC) — claims ≤ ₹50 lakh",
            "State Consumer Disputes Redressal Commission (SCDRC) — ₹50 lakh–₹2 crore",
            "National Consumer Disputes Redressal Commission (NCDRC) — > ₹2 crore; ncdrc.nic.in",
            "Online filing: edaakhil.nic.in | Helpline: 1800-11-4000 / 1915",
        ],
        "typical_timeline": "District Commission: 3–18 months. State Commission: 6–18 months more on appeal. NCDRC: 1–3 years.",
        "typical_costs": "Filing fee: ₹200–₹5000 (claim-based). Lawyer: optional (consumer court is informal). NALSA for eligible.",
        "common_mistakes": [
            "Filing without a written prior complaint to the company — shows no prior effort",
            "Wrong forum based on claim value — total claim including compensation determines forum",
            "Missing 2-year limitation period",
            "Claiming unrealistically high compensation — courts award actual loss + reasonable damages",
            "Not attaching all supporting documents at filing",
        ],
        "free_legal_aid": "No lawyer needed for District Commission. NALSA provides aid. Consumer Helpline 1915 guides procedure.",
    },

    "RTI": {
        "applicable_laws": [
            "Right to Information Act, 2005",
            "Section 6 — application to CPIO; fee ₹10 (BPL exempt); 30 working days to respond",
            "Section 7(1) — 30-day response period; 48 hours for life/liberty matters",
            "Section 8 — exemptions: national security, personal privacy, cabinet proceedings, commercially sensitive",
            "Section 19 — First Appeal to FAA within 30 days; Second Appeal to CIC/SIC within 90 days of FAA order",
            "Section 20 — penalty on PIO for unjustified delay: ₹250/day, max ₹25,000",
        ],
        "typical_remedies": [
            "Information provided within 30 days",
            "Transfer to correct authority if filed with wrong body",
            "Penalty on PIO for delay or unjustified refusal",
            "First and second appeals if information withheld",
        ],
        "evidence_checklist": [
            "Copy of RTI application (signed and dated — keep copy stamped by authority)",
            "Proof of ₹10 fee payment (IPO / DD / online payment receipt)",
            "Acknowledgment receipt from CPIO",
            "CPIO's response (for First Appeal)",
            "FAA order (for Second Appeal to CIC/SIC)",
        ],
        "procedure_steps": [
            "Identify the correct Public Authority holding the information (Central Ministry or State?)",
            "Write application to CPIO: be specific — list 3–5 clear, distinct information points",
            "Pay ₹10 fee (BPL applicants exempt — attach BPL card copy)",
            "Central govt: file online at rtionline.gov.in; State: state RTI portal or post to CPIO",
            "If no response in 30 days or unsatisfactory response: First Appeal to FAA within 30 days",
            "If FAA unsatisfactory: Second Appeal to CIC (central) or SIC (state) within 90 days of FAA order",
        ],
        "limitation_period": "First Appeal: within 30 days of response / expiry of 30-day period. Second Appeal: within 90 days of FAA order. Miss these and the case weakens significantly.",
        "authorities": [
            "CPIO (Central Public Information Officer) of relevant department",
            "First Appellate Authority (FAA) — one level above CPIO in same department",
            "Central Information Commission (CIC) — cic.gov.in (for central bodies)",
            "State Information Commission (SIC) — for state/local government bodies",
        ],
        "typical_timeline": "CPIO response: 30 days. FAA: 30–45 days. CIC hearing: 6 months–2 years (backlog).",
        "typical_costs": "Application fee: ₹10. Additional copies: ₹2/page. Online filing: free. No court fee for appeals.",
        "common_mistakes": [
            "Vague questions ('give all information about X') — be specific and targeted",
            "Filing with wrong authority — research which department holds the data",
            "Missing the 30-day first appeal deadline — calendar it on the day you file RTI",
            "Asking for 'opinions' or 'reasons why' — RTI gives you documents and data, not explanations",
            "Not keeping copies of everything sent and received",
        ],
        "free_legal_aid": "RTI does not require a lawyer. NALSA can help with complex appeals. RTI helplines in most states.",
    },

    "Tenant": {
        "applicable_laws": [
            "Transfer of Property Act, 1882 — general tenant-landlord relationship and quiet enjoyment",
            "State Rent Control Acts — MOST IMPORTANT; override general law; vary by state",
            "Model Tenancy Act, 2021 — adopted by some states (e.g. UP, Tamil Nadu)",
            "Registration Act, 1908 — lease agreements > 12 months must be registered",
            "BNS Section 329 — criminal trespass (for landlord entering without permission)",
        ],
        "typical_remedies": [
            "Injunction preventing illegal eviction or unauthorized entry",
            "Recovery of wrongfully withheld security deposit",
            "Damages for illegal eviction",
            "Protection from eviction except on legal grounds",
            "Reduced rent if accommodation is uninhabitable",
        ],
        "evidence_checklist": [
            "Rent agreement (registered copy if lease > 12 months)",
            "All rent payment receipts / bank transfer records",
            "WhatsApp / email communications with landlord (screenshots)",
            "Photographs of property condition (move-in and current state)",
            "Utility bills in your name (proof of occupancy)",
            "Any eviction or demand notice received from landlord",
        ],
        "procedure_steps": [
            "For any dispute: first send written notice to landlord (WhatsApp + email + written letter)",
            "For security deposit recovery: legal notice with 15-day deadline → civil suit or consumer court if builder/company",
            "For illegal eviction: approach Rent Controller / Rent Tribunal of your district",
            "For unauthorized entry: file police complaint under BNS Section 329",
            "Check if your property falls under State Rent Control Act — older properties and lower rents usually qualify",
        ],
        "limitation_period": "Security deposit recovery: 3 years from demand. Eviction appeal: depends on state notice period. Always respond to eviction notices within stated timeframe.",
        "authorities": [
            "Rent Controller / Rent Tribunal (state-specific)",
            "Civil Court (for matters outside Rent Control Act)",
            "Police / Magistrate (criminal trespass)",
            "Consumer Forum (for commercial landlords / builders)",
        ],
        "typical_timeline": "Rent Controller proceedings: 3 months–2 years. Civil court: 2–5 years.",
        "typical_costs": "Filing: ₹200–₹2000. Lawyer: ₹10,000–₹50,000.",
        "common_mistakes": [
            "Vacating before recovering security deposit — leverage drops significantly after leaving",
            "No written rent agreement — oral agreements are very hard to prove",
            "Paying rent in cash without receipts — always pay by transfer or get signed receipts",
            "Ignoring eviction notices — always respond within the stated period",
            "Assuming all properties are under Rent Control Act — check your area and rent level",
        ],
        "free_legal_aid": "NALSA assists with eviction matters. State legal services committees.",
    },

    "Employment": {
        "applicable_laws": [
            # ── Labour Codes 2020 (consolidating older standalone acts; implementation varies by state) ──
            "Code on Wages, 2019 — consolidates Payment of Wages Act 1936, Minimum Wages Act, Payment of Bonus Act; ensures timely payment of wages to all employees including gig workers",
            "Industrial Relations Code, 2020 — consolidates Industrial Disputes Act 1947 (ID Act), Trade Unions Act, Industrial Employment (Standing Orders) Act; governs wrongful termination and retrenchment",
            "Code on Social Security, 2020 — consolidates EPF Act 1952, Payment of Gratuity Act 1972, Maternity Benefit Act; extends coverage to gig/platform workers",
            "Occupational Safety, Health and Working Conditions Code, 2020 — consolidates Factories Act, Contract Labour Act; governs working conditions",
            # ── Standalone acts still widely applicable ──
            "Industrial Disputes Act, 1947 (ID Act) — still operative in most states; applies to 'workmen' (non-supervisory employees); governs wrongful termination, retrenchment, lay-off",
            "Payment of Gratuity Act, 1972 — gratuity = 15 days × years of service ÷ 26; payable after 5 years continuous service; maximum ₹20 lakh",
            "Shops and Establishments Acts — state-specific; covers most commercial employees not governed by Factories Act",
            "EPF & Miscellaneous Provisions Act, 1952 — provident fund rights; 12% employer + 12% employee contribution",
            "POSH Act, 2013 — workplace sexual harassment; Internal Complaints Committee (ICC) mandatory for employers with 10+ employees",
            "Contract Labour (Regulation and Abolition) Act, 1970 — for contract/outsourced workers",
        ],
        "dispute_classification": {
            "labour_dispute": "Unpaid salary, wrongful termination, retrenchment, PF deduction issues, gratuity denial — FILE WITH LABOUR COMMISSIONER or labour court",
            "civil_dispute": "Breach of employment contract, F&F settlement not paid, experience letter withheld — SEND LEGAL NOTICE, then civil suit",
            "administrative_complaint": "PF not deposited by employer — FILE WITH EPFO Regional Office or Grievance Portal",
            "criminal_offence_only_if": "Employer fraudulently induced employment (cheating), criminally misappropriated PF deductions already cut from salary, forged documents — ONLY then may FIR under BNS be appropriate",
            "WARNING": "DO NOT recommend FIR merely because salary is unpaid. Unpaid wages are a labour/civil matter. Explicitly state this when advising users.",
        },
        "typical_remedies": [
            "Reinstatement with back wages (wrongful termination of 'workmen' — ID Act)",
            "Retrenchment compensation (1 month per year of service for workmen)",
            "Recovery of withheld salary, PF, gratuity, earned-leave encashment, notice-period pay",
            "Full and final settlement (F&F) — includes all dues payable on exit",
            "Experience / relieving letter (employer cannot lawfully withhold this)",
            "Compensation for POSH violation (decided by ICC/LCC)",
        ],
        "evidence_checklist": [
            "Appointment letter / offer letter (proof of employment terms)",
            "All employment contracts, increment and promotion letters",
            "Last 6–12 months salary slips",
            "Bank statements showing salary credits (and any months where credit is missing)",
            "Attendance records (if employer disputes work done)",
            "Performance reviews and appraisals",
            "Termination letter or email (request one in writing — employer should provide)",
            "WhatsApp/email communication about salary, termination, or HR disputes",
            "Any written salary demand or grievance already sent",
            "PF UAN number and EPF passbook / account statement",
            "Full and final settlement statement (if partially paid)",
            "Experience letter / relieving letter (or evidence of withholding)",
            "Notice period agreement from contract",
        ],
        "procedure_steps": [
            "Step 1 — PRESERVE EVIDENCE: Save appointment letter, salary slips, bank statements, all emails and WhatsApp chats about pay/termination.",
            "Step 2 — CHECK YOUR CONTRACT: Confirm what notice period, salary, F&F terms, and dispute resolution clause apply.",
            "Step 3 — WRITTEN DEMAND: Send a written salary demand / grievance to HR and management by email (creates paper trail). WhatsApp also works but email is cleaner evidence.",
            "Step 4 — INTERNAL ESCALATION: If HR ignores for 1–2 weeks, escalate to the MD/CEO in writing. State exact months unpaid and amount.",
            "Step 5 — LABOUR AUTHORITY (primary remedy): File complaint with the Labour Commissioner / Assistant Labour Commissioner (ALC) in your district. Free, no lawyer needed. They call both parties for conciliation within 30–45 days.",
            "Step 6 — LEGAL NOTICE (if employer is unresponsive): Have a lawyer send a formal legal notice under the relevant labour statute. Often triggers settlement without court.",
            "Step 7 — LABOUR COURT / TRIBUNAL: For 'workmen' (non-supervisory) — file before the Industrial Tribunal or Labour Court. For others — civil court suit for money recovery.",
            "Step 8 — PF ISSUES SEPARATELY: If PF was deducted but not deposited → file directly with EPFO Regional Office and the EPFO Grievance Portal (epfigms.gov.in). This is a separate process from salary recovery.",
            "Step 9 — FIR ONLY IF CRIMINAL: Only consider FIR if there is evidence of a cognizable criminal offence — e.g., employer collected PF deductions from salary and misappropriated them (criminal breach of trust), or employer used fraudulent documents. Unpaid salary alone does NOT justify an FIR.",
        ],
        "limitation_period": "ID Act retrenchment: 3 years. POSH complaint: 3 months from last incident (extendable to 6 months for good cause). Gratuity: application within 30 days of becoming due (employer) / 1 year (employee). PF: EPFO accepts complaints anytime during employment + 3 years. Civil suit for wages: 3 years.",
        "authorities": [
            "Labour Commissioner / ALC (state level) — primary free authority for labour disputes",
            "Industrial Tribunal / Labour Court — for 'workmen' wrongful termination, retrenchment",
            "EPFO Regional Office / Grievance Portal (epfigms.gov.in) — PF non-deposit, withdrawal issues",
            "Payment of Gratuity Authority (Labour Commissioner acts as authority) — gratuity denial",
            "Internal Complaints Committee (ICC) — POSH complaints (employer's ICC)",
            "Local Complaints Committee (LCC) — POSH, if employer has no ICC or has fewer than 10 employees",
            "She-Box portal (shebox.wcd.gov.in) — government sector POSH",
            "Civil Court — for non-workman salary/F&F recovery",
        ],
        "typical_timeline": "Labour conciliation: 30–45 days. Labour Court: 1–3 years. EPFO grievance: 30–60 days. POSH ICC: must complete in 90 days.",
        "typical_costs": "Labour Commissioner complaint: Free. Labour Court filing: ₹200–₹500. Civil suit: ₹500–₹2,000 + ad valorem. Lawyer: ₹15,000–₹75,000. NALSA for eligible.",
        "common_mistakes": [
            "Filing an FIR for unpaid salary — unpaid wages are a LABOUR dispute, not a criminal matter unless there is evidence of fraud, criminal breach of trust, or forgery; police often cannot help and may dismiss you",
            "Signing Full and Final Settlement without reviewing what dues you are releasing — once signed it is very difficult to challenge",
            "Missing POSH 3-month deadline — courts treat it as absolute; act promptly",
            "Not getting a written termination letter — request it in writing; employer's silence is itself evidence",
            "Confusing 'workman' (ID Act protection) vs 'supervisor/manager' (different rights) — depends on salary, role, and nature of work",
            "Not filing a written grievance first — Labour Courts and tribunals expect you to exhaust internal remedies",
            "Forgetting to claim earned-leave encashment in F&F — it is a statutory right, not a favour",
            "PF deducted but not deposited — this is employer fraud on the PF fund; report directly to EPFO, not police",
        ],
        "important_note": "The 4 Labour Codes 2020 (Wages, Industrial Relations, Social Security, OHS) consolidate 29+ older labour laws. Full implementation and state rules vary — always verify which specific laws and rules are currently operative in your state before filing.",
        "free_legal_aid": "NALSA (nalsa.gov.in | 15100) and state DLSA. Labour Commissioner conciliation is free. EPFO grievance is free. Labour Court filing fee is nominal.",
    },

    "ChequeBounce": {
        "applicable_laws": [
            "Section 138, Negotiable Instruments Act, 1881 — dishonoured cheque is a criminal offence",
            "Section 142 — strict procedure with time limits (notice within 30 days of return memo; complaint within 30 days of notice expiry)",
            "Section 147 — compoundable offence (can settle outside court)",
            "Punishment: up to 2 years imprisonment AND/OR fine up to twice the cheque amount",
            "Section 138 is summary trial — typically faster than regular criminal matters",
        ],
        "typical_remedies": [
            "Recovery of cheque amount + interest",
            "Fine up to twice the cheque amount",
            "Criminal conviction (up to 2 years imprisonment) as leverage for settlement",
            "Civil suit for money recovery (parallel option)",
        ],
        "evidence_checklist": [
            "ORIGINAL dishonoured cheque (most critical — do not lose it)",
            "Bank return memo / dishonour slip (must state specific reason for return)",
            "Copy of legal notice sent (with text as received by drawer)",
            "Postal receipt + acknowledgment / tracking proof of notice delivery",
            "Underlying transaction proof: loan agreement, invoice, contract, acknowledgment of debt",
        ],
        "procedure_steps": [
            "Step 1: Get bank return memo with reason (usually 'funds insufficient' or 'account closed')",
            "Step 2: Within 30 days of return memo — send legal notice to drawer via Registered Post with AD (RPAD)",
            "Step 3: Wait 15 days — this is the drawer's chance to pay in full",
            "Step 4: If no full payment within 15 days — file complaint with Magistrate within next 30 days",
            "File at Magistrate in area where PAYEE'S bank is located (jurisdiction changed in 2015)",
            "Attach: original cheque, return memo, notice copy, postal receipts",
        ],
        "limitation_period": "⚠ CRITICALLY TIME-BOUND: Notice MUST be within 30 days of return memo. Complaint MUST be within 30 days of 15-day notice expiry. Missing either deadline destroys the case entirely.",
        "authorities": [
            "Judicial Magistrate First Class (JMFC) — at payee's bank jurisdiction",
            "Civil Court — for parallel money recovery suit",
        ],
        "typical_timeline": "Complaint to first hearing: 2–6 weeks. Summary trial: 6 months–2 years. Most matters settle after complaint is registered.",
        "typical_costs": "Magistrate complaint fee: ₹200–₹500. RPAD notice: ₹50–₹100. Lawyer: ₹10,000–₹30,000.",
        "common_mistakes": [
            "Delaying legal notice beyond 30 days of return memo — case collapses entirely",
            "Sending notice by regular courier / WhatsApp instead of RPAD — not legally valid",
            "Accepting partial payment without written acknowledgment and balance undertaking",
            "Losing the original cheque or return memo",
            "Not specifying the exact amount due and demand for full payment in the legal notice",
        ],
        "free_legal_aid": "NALSA. Magistrate complaints under NI Act are relatively straightforward.",
    },

    "Bail": {
        "applicable_laws": [
            "BNSS Section 478 — bailable offences: bail as of right at police station or court",
            "BNSS Section 480 — non-bailable offences: bail at Sessions Court / High Court discretion",
            "BNSS Section 482 — anticipatory bail: Sessions Court or High Court before arrest",
            "BNSS Section 479 — undertrial entitled to bail after serving half maximum sentence",
            "BNSS Section 187 — custody limits: police custody max 15 days; then judicial custody",
            "Default bail (Section 187(3)): if chargesheet not filed within 60 days (minor) or 90 days (serious offences) — absolute right",
        ],
        "typical_remedies": [
            "Bail at police station (bailable offences — right, not discretion)",
            "Regular bail from Sessions Court / High Court",
            "Anticipatory bail before arrest",
            "Default bail if chargesheet not filed within statutory period",
            "Bail on medical/humanitarian grounds",
        ],
        "evidence_checklist": [
            "Copy of FIR (to understand charges and assess bailable/non-bailable nature)",
            "Arrest memo",
            "Identity and address proof for accused",
            "Proof of community ties, family, employment (for bail discretion factors)",
            "Surety documents (property papers, bank guarantee)",
            "Medical documents if bail on health grounds",
            "Chargesheet (if filed) — check filing date for default bail",
        ],
        "procedure_steps": [
            "Bailable offence: apply directly to SHO — bail is a right, cannot be refused without order",
            "Non-bailable offence: file bail application in Sessions Court first",
            "If Sessions Court refuses: appeal to High Court",
            "Anticipatory bail (before arrest): application to Sessions Court or High Court",
            "Default bail: file application on EXACTLY Day 61/90 (whichever applies) — right lapses if chargesheet filed even one day later",
        ],
        "limitation_period": "Default bail must be applied on Day 61/91 exactly. If chargesheet is filed even that day before application, right is lost.",
        "authorities": [
            "Police SHO (bailable offences)", "Sessions Court (most bail applications start here)",
            "High Court (for serious offences or if Sessions rejects)",
            "Supreme Court (SLP in extreme cases only)",
        ],
        "typical_timeline": "Regular bail: hearing 3–15 days. Anticipatory bail: 3–7 days (courts treat as urgent). Default bail: same day.",
        "typical_costs": "Application: ₹500–₹2000. Lawyer: ₹10,000–₹50,000+. NALSA free legal aid (mandatory at arrest).",
        "common_mistakes": [
            "Missing the default bail window by even one day",
            "Not having surety ready before the bail hearing",
            "Not challenging unreasonable bail conditions (can be done separately)",
            "Assuming anticipatory bail continues automatically post-arrest — specific order needed",
        ],
        "free_legal_aid": "Under BNSS, all arrested persons have right to free legal aid. NALSA 24x7. Duty lawyers at Sessions Court.",
    },

    "Property": {
        "applicable_laws": [
            "Hindu Succession Act, 1956 (amended 2005) — daughters have equal rights in ancestral property; applies even if father died before 2005 (Vineeta Sharma SC 2020)",
            "Indian Succession Act, 1925 — for Christians, Parsis, and intestate succession of others",
            "Transfer of Property Act, 1882 — sale, mortgage, lease, gift",
            "Registration Act, 1908 — compulsory registration of sale deeds (unregistered not recognised as title)",
            "RERA 2016 — for builder-buyer disputes: delayed possession, defects, refunds",
            "Specific Relief Act, 1963 — specific performance of sale agreements",
        ],
        "typical_remedies": [
            "Partition suit — court-ordered division of property between co-owners",
            "Injunction — prevent unlawful transfer, encroachment, or dispossession",
            "Specific performance of sale agreement",
            "Declaration of title",
            "RERA compensation for delayed possession or defects",
        ],
        "evidence_checklist": [
            "Sale deed / original title document",
            "Encumbrance certificate (EC) from Sub-Registrar's office — establish ownership history",
            "Mutation / Khata certificate (revenue records showing ownership)",
            "Property tax receipts in owner's name",
            "Previous sale deeds establishing chain of title (going back 30+ years ideal)",
            "For inheritance: Will / probate / family tree documents",
            "For builder disputes: allotment letter, sale agreement, payment receipts, builder's RERA registration",
        ],
        "procedure_steps": [
            "Get encumbrance certificate from Sub-Registrar's office to verify ownership",
            "Send legal notice to co-owners / builder specifying claim and 30-day response deadline",
            "For partition: file partition suit in Civil Court (District Court)",
            "For builder disputes: file at State RERA Authority (quick and specialised)",
            "For property fraud: file FIR under BNS + civil suit for title",
        ],
        "limitation_period": "Partition suit: 12 years from ouster. Sale agreement specific performance: 3 years. RERA: 5 years from cause. Title dispute: 12 years (adverse possession after 12 years).",
        "authorities": [
            "Civil Court (District Court) — title disputes, partition, injunction",
            "State RERA Authority — builder-buyer disputes",
            "Revenue Court (Collector/SDO) — agricultural land",
            "Sub-Registrar's Office — document registration, encumbrance certificates",
        ],
        "typical_timeline": "Civil property suits: 3–10 years. RERA: order in 60–90 days, recovery longer. Title search: 1–4 weeks.",
        "typical_costs": "Civil court fee: 1–5% of property value. RERA: ₹1000–₹5000 (state-specific). Lawyer: ₹30,000–₹2,00,000+.",
        "common_mistakes": [
            "Buying without encumbrance certificate — always get EC for 30 years minimum",
            "Not registering sale deed — courts do not recognise unregistered sale as title",
            "Forgetting 2005 HSA amendment daughters' rights — daughters have equal rights even if father died before 2020 SC judgment",
            "Missing RERA's 5-year limitation for builder delays",
            "Not updating mutation after inheritance — revenue records must be updated",
        ],
        "free_legal_aid": "NALSA assists. Revenue court matters sometimes handled without lawyer.",
    },

    "Cybercrime": {
        "applicable_laws": [
            "IT Act, 2000 — Sec 66 (hacking), 66C (identity theft), 66D (impersonation/cheating), 66E (privacy violation), 67/67A/67B (obscene/adult/CSAM content)",
            "Digital Personal Data Protection Act, 2023 (DPDP) — data rights",
            "BNS Sec 318 (cheating), 316 (criminal breach of trust) — for online fraud",
            "BNS Sec 351 (criminal intimidation) — for cyber threats",
            "BNS Sec 77 (voyeurism via device) — for non-consensual recording",
            "RBI guidelines on liability for unauthorised digital transactions",
        ],
        "typical_remedies": [
            "Transaction freeze / reversal via 1930 helpline (time-critical — first 60 minutes)",
            "FIR at cybercrime police station",
            "Online complaint at cybercrime.gov.in",
            "Platform content takedown",
            "Account recovery (for hacked social media / email)",
        ],
        "evidence_checklist": [
            "Screenshots of all communications with timestamps visible",
            "Bank transaction IDs / UTR numbers",
            "Fraudster's UPI ID, phone number, or bank account number",
            "URLs of offending pages / profiles",
            "Bank statements showing fraudulent transactions",
            "Email headers if email-based fraud",
        ],
        "procedure_steps": [
            "Financial fraud: IMMEDIATELY call 1930 — golden hour for fund recovery",
            "File online complaint at cybercrime.gov.in (get complaint ID)",
            "File FIR at nearest Cybercrime Police Station (every district has one)",
            "Inform your bank immediately to flag / freeze fraudulent transactions",
            "For harassment / blackmail: report to platform AND police simultaneously",
            "Preserve all evidence — do NOT delete anything even if offensive",
        ],
        "limitation_period": "Report financial fraud within hours — every hour reduces recovery chance. FIR: file within days. Complaint limitation: 3 years, but act immediately.",
        "authorities": [
            "Cybercrime Reporting Portal: cybercrime.gov.in", "National Cyber Crime Helpline: 1930",
            "Cybercrime Police Station (every district)", "CERT-In: cert-in.org.in",
        ],
        "typical_timeline": "1930 freeze: within minutes. Investigation: 3–6 months. Criminal trial: 1–3 years.",
        "typical_costs": "Reporting: Free. FIR: Free.",
        "common_mistakes": [
            "Delaying report — every hour reduces chance of fund recovery",
            "Paying blackmailer — escalates demands, does not stop threat",
            "Deleting messages / evidence out of embarrassment",
            "Clicking links in follow-up 'police' or 'bank' messages — secondary fraud",
        ],
        "free_legal_aid": "Police filing free. NALSA for complex cases.",
    },

    "POSH": {
        "applicable_laws": [
            "Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) Act, 2013",
            "Internal Complaints Committee (ICC) — mandatory for organisations with 10+ employees; employer must set one up",
            "Local Complaints Committee (LCC) — district level, for unorganised sector or companies < 10 employees",
            "BNS Sections 74–79 — criminal sexual offences (parallel criminal remedy)",
        ],
        "typical_remedies": [
            "Written apology from harasser",
            "Warning, suspension, or termination of harasser",
            "Transfer of harasser (complainant should not be transferred against their will)",
            "Compensation up to 3 months salary + counselling costs",
            "Criminal complaint under BNS as parallel option",
        ],
        "evidence_checklist": [
            "Written complaint to ICC/LCC with specific dates and detailed description of each incident",
            "Screenshots of messages, emails, any digital evidence",
            "Names of witnesses who observed incidents",
            "Medical or psychological treatment records",
            "Any prior HR complaints about the same person",
            "Request CCTV footage preservation immediately through proper channels",
        ],
        "procedure_steps": [
            "File written complaint to ICC within 3 months of last incident (extendable to 6 months for good cause)",
            "ICC must complete inquiry within 90 days",
            "If no ICC or < 10 employees: file with Local Complaints Committee (LCC) at district level",
            "Parallel option: file criminal complaint under BNS",
            "For government employees: She-Box portal (shebox.wcd.gov.in)",
            "If employer has no ICC: file complaint with Labour Commissioner (employer is in violation)",
        ],
        "limitation_period": "⚠ ICC complaint: strictly within 3 months of last incident (extendable to 6 months only for good cause). Criminal complaint: no hard limit but file promptly.",
        "authorities": [
            "Internal Complaints Committee (ICC) of employer",
            "Local Complaints Committee (LCC) — district level",
            "She-Box portal: shebox.wcd.gov.in (government sector)",
            "Labour Commissioner (if employer violates POSH by not having ICC)",
            "Police (for criminal complaint under BNS)",
        ],
        "typical_timeline": "ICC inquiry: 90 days mandatory. LCC: 90 days. Criminal case: 1–3 years.",
        "typical_costs": "ICC/LCC complaint: Free. Criminal complaint: Free.",
        "common_mistakes": [
            "Missing the 3-month deadline — act without delay",
            "Accepting informal resolution without ICC documentation",
            "Not knowing ICC must include an external member and be gender-neutral",
            "Retaliation by employer — itself an offence under POSH; document and report",
        ],
        "free_legal_aid": "NALSA. NCW Helpline: 7827170170. She-Box: shebox.wcd.gov.in.",
    },

    "Constitutional": {
        "applicable_laws": [
            "Article 14 — equality before law and equal protection",
            "Article 19 — freedoms: speech, assembly, movement, profession, residence",
            "Article 21 — right to life and personal liberty (includes privacy: Puttaswamy 2017, dignity, health, education, environment)",
            "Article 22 — protection against arbitrary arrest: right to be informed of grounds, right to lawyer, max 24 hours before Magistrate",
            "Article 32 — Supreme Court jurisdiction for fundamental rights (cannot be suspended except Emergency)",
            "Article 226 — High Court writ jurisdiction (broader than Article 32, covers any legal right)",
        ],
        "typical_remedies": [
            "Habeas Corpus — challenge illegal detention or disappearance",
            "Mandamus — compel a public authority to perform a legal duty",
            "Certiorari — quash an inferior court/tribunal order",
            "Prohibition — prevent inferior court from exceeding jurisdiction",
            "Quo Warranto — challenge right to hold a public office",
        ],
        "evidence_checklist": [
            "Government order / action being challenged (certified copy)",
            "Evidence of direct violation of a fundamental right",
            "Proof of standing (petitioner is directly and substantially affected)",
            "Correspondence with the authority showing prior representation",
            "Timeline of events leading to the constitutional violation",
        ],
        "procedure_steps": [
            "For fundamental rights violation: file writ petition under Article 226 in High Court first (more accessible, broader jurisdiction)",
            "For nationwide issues or Supreme Court jurisdiction: file under Article 32",
            "For Public Interest Litigation (PIL): may be filed on behalf of a class by any citizen",
            "Urgent matters: can seek ex-parte ad-interim relief on day of filing",
        ],
        "limitation_period": "No fixed limitation but courts insist on promptness — laches doctrine applies. File as soon as violation occurs.",
        "authorities": [
            "High Court of the State (Article 226 — broader, more accessible)",
            "Supreme Court of India (Article 32 — for fundamental rights; after High Court)",
        ],
        "typical_timeline": "Urgent writs (habeas corpus): heard within days. PIL / regular petitions: 1–5+ years.",
        "typical_costs": "High Court filing: ₹1000–₹5000 + stamp duty. Lawyer: ₹20,000–₹5,00,000+.",
        "common_mistakes": [
            "Going to Supreme Court before High Court — exhaust High Court remedy first",
            "Not showing direct violation of a fundamental right — must be unconstitutional, not just unfair",
            "Delay in filing (laches) — courts can dismiss on grounds of unexplained delay",
        ],
        "free_legal_aid": "Supreme Court Legal Services Committee: sclsc.gov.in. NALSA. High Court Legal Services Committees.",
    },

    "POCSO": {
        "applicable_laws": [
            "Protection of Children from Sexual Offences Act, 2012 (amended 2019) — comprehensive child protection law",
            "Sec 3: Penetrative sexual assault; Sec 7: Non-penetrative assault; Sec 11: Sexual harassment of child",
            "BNSS mandatory FIR — POCSO offences are cognizable and non-bailable",
            "BNSS Section 19 — ANY person who knows of POCSO offence MUST report it; failure is itself an offence",
            "JJ Act, 2015 — care and protection, Child Welfare Committee",
        ],
        "typical_remedies": [
            "Immediate police action and FIR registration",
            "Child's removal from unsafe environment",
            "Criminal prosecution — POCSO Special Court; expedited trials",
            "Victim compensation (POCSO Section 33(8))",
            "Rehabilitation and trauma counselling",
        ],
        "evidence_checklist": [
            "Medical examination — by government hospital doctor (female doctor for female children)",
            "Child's statement — recorded by Magistrate only once, in camera (never repeat questioning)",
            "Any digital evidence: messages from accused to child",
        ],
        "procedure_steps": [
            "Call Childline 1098 immediately for guidance and support",
            "File FIR at any police station — POCSO FIR is mandatory for all",
            "Police must notify Child Welfare Committee within 24 hours",
            "Medical exam arranged by police (not family — to preserve evidence validity)",
            "Child's statement recorded by Magistrate only once in closed proceedings",
            "POCSO Special Court — designated for each district, expedited trial",
        ],
        "limitation_period": "No limitation period for POCSO offences. Report immediately. Every hour delays evidence and may affect the child's safety.",
        "authorities": [
            "Police (any station — POCSO FIR mandatory)", "Childline: 1098 (24x7, free)",
            "Child Welfare Committee (CWC)", "POCSO Special Court", "One Stop Centre",
        ],
        "typical_timeline": "Trial target: within 1 year (often delayed in practice). Fast-track courts for heinous offences. Compensation: ordered at trial stage.",
        "typical_costs": "Free legal aid mandatory for child victims. NALSA. DLSA in every district.",
        "common_mistakes": [
            "Not reporting because of family pressure or shame — reporting is mandatory for all",
            "Taking child to private doctor instead of government hospital — affects evidence",
            "Repeatedly questioning child about the incident — only one in-camera statement is legal",
            "Delaying police report while seeking private resolution",
        ],
        "free_legal_aid": "Mandatory free legal aid for POCSO victims. NALSA. DLSA in every district.",
    },

    "Contract": {
        "applicable_laws": [
            "Indian Contract Act, 1872 — foundational law; all agreements for consideration between competent parties",
            "Sec 10 — valid contract requires free consent, lawful object, consideration, competent parties",
            "Sec 73 — compensation for breach: actual loss directly resulting from breach (not remote)",
            "Sec 74 — liquidated damages / penalty clause: court awards reasonable compensation",
            "Specific Relief Act, 1963 — Sec 10: specific performance of contract (where money is inadequate)",
            "Specific Relief Act Sec 38 — perpetual injunction to prevent breach",
            "Information Technology Act, 2000 Sec 10A — electronic contracts are valid and enforceable",
            "Consumer Protection Act, 2019 — for consumer service contracts (builder, online service, etc.)",
            "RERA 2016 — builder-buyer agreements for real estate projects",
        ],
        "typical_remedies": [
            "Damages for breach — actual financial loss caused by breach (Sec 73)",
            "Specific performance — court orders the other party to do what was promised",
            "Injunction — court prevents the other party from doing something",
            "Rescission — contract cancelled and parties restored to original position",
            "Quantum meruit — payment for work already done even if contract fails",
            "Liquidated damages / penalty as agreed in contract (Sec 74)",
        ],
        "evidence_checklist": [
            "Original signed contract / agreement (both parties must have signed)",
            "All WhatsApp / email communications about the contract and performance",
            "Payment receipts, bank transfer records, invoices",
            "Evidence of what was delivered / not delivered (photos, delivery notes)",
            "Any variation or amendment to the contract (in writing)",
            "Communication showing breach (demand emails, rejection letters)",
            "Evidence of your actual loss caused by the breach (bills, bank statements)",
        ],
        "procedure_steps": [
            "Step 1: Document everything — gather all evidence of contract and breach NOW",
            "Step 2: Send formal legal notice (Registered Post AD) with 15–30 day deadline to remedy breach",
            "Step 3: If unresolved: file civil suit in Civil Court or Consumer Forum (for consumer contracts)",
            "For amounts ≤ ₹1 crore: District Civil Court; > ₹1 crore: High Court original jurisdiction",
            "For builder/real estate: file at State RERA Authority (faster and cheaper than civil court)",
            "For consumer service contracts (e-commerce, app subscriptions): Consumer Court at edaakhil.nic.in",
            "For employment contracts: Labour Court if it involves employment terms",
        ],
        "limitation_period": "3 years from date of breach (Limitation Act 1963, Article 55). RERA: 5 years. Consumer: 2 years. Do not wait — limitation runs from the date breach became known.",
        "authorities": [
            "Civil Court (District Court) — for general contract disputes",
            "High Court (Original Jurisdiction) — for large commercial disputes",
            "RERA Authority (state-level) — for real estate / builder disputes",
            "Consumer District Commission — for consumer service contracts (edaakhil.nic.in)",
            "Arbitration (if contract has arbitration clause) — faster and private",
        ],
        "typical_timeline": "Civil Court: 3–7 years. RERA: 3–6 months. Consumer Court: 3–18 months. Arbitration: 6–18 months.",
        "typical_costs": "Civil Court filing: 1–2% of claim value. Consumer Court: ₹200–₹5000. RERA: ₹1000–₹5000. Legal aid from NALSA if eligible.",
        "common_mistakes": [
            "Not sending a formal legal notice before filing — courts expect prior notice",
            "Missing the 3-year limitation period for civil suits",
            "Relying on verbal contracts without any written evidence — very difficult to prove",
            "Accepting partial performance without expressly reserving rights against balance",
            "Signing a settlement/receipt without understanding it waives further claims",
        ],
        "free_legal_aid": "NALSA for economically weaker sections. Lok Adalat for pre-litigation settlements (fast and free). Mediation Centre attached to most courts.",
    },

    "Inheritance": {
        "applicable_laws": [
            "Hindu Succession Act, 1956 (amended 2005) — for Hindus, Buddhists, Jains, Sikhs",
            "HSA Section 6 (post-2005 amendment) — daughters have EQUAL rights in ancestral/coparcenary property",
            "Supreme Court: Vineeta Sharma v. Rakesh Sharma (2020) — daughters' equal rights apply even if father died before 2005",
            "Indian Succession Act, 1925 — for Christians, Parsis, Jews, and persons without religion",
            "Muslim Personal Law (Shariat) Application Act, 1937 — for Muslims (Hanafi, Shia rules differ)",
            "Special Marriage Act, 1954 — civil marriage succession follows Indian Succession Act",
            "Transfer of Property Act, 1882 — gift deeds, transfer during lifetime",
            "Registration Act, 1908 — Will must be registered for easy probate (unregistered Wills are valid but harder to act on)",
        ],
        "typical_remedies": [
            "Partition suit — court-ordered division of inherited property among legal heirs",
            "Probate — court validates the Will and grants executor authority",
            "Letter of Administration — where there is no Will, court grants this to heir",
            "Succession Certificate — for movable assets (bank accounts, FDs, shares, insurance)",
            "Injunction — prevent illegal sale or transfer of estate property pending dispute",
            "Declaration of heirship / title",
        ],
        "evidence_checklist": [
            "Death certificate of the deceased",
            "Will (if any) — both original and registration certificate",
            "Proof of relationship: birth certificate, marriage certificate, family tree affidavit",
            "Property documents: sale deed, title documents, mutation records, encumbrance certificate",
            "Bank account details and FD certificates of deceased",
            "Revenue records (Khata, mutation) in deceased's name",
            "Any earlier partition deed or family settlement",
            "Legal Heir Certificate from local tehsildar / MRO (required for most claims)",
        ],
        "procedure_steps": [
            "Step 1: Obtain Death Certificate and Legal Heir Certificate from local authority",
            "Step 2: If Will exists — apply for Probate in High Court (mandatory in Mumbai, Chennai, Kolkata; advisable elsewhere)",
            "Step 3: If no Will — apply for Letter of Administration (High Court) or Succession Certificate (District Court for movables)",
            "Step 4: Update mutation / Khata in revenue records to transfer property in heirs' names",
            "Step 5: For disputed partition — file partition suit in Civil Court (District Court)",
            "Step 6: For bank accounts / shares — present Succession Certificate + death certificate to institution",
        ],
        "limitation_period": "Partition suit: 12 years from when partition was first refused. Probate: no strict limit but courts dislike delay. Succession Certificate: no strict limit. Act promptly — long delays weaken claims.",
        "authorities": [
            "High Court (Probate and Letters of Administration)",
            "District Civil Court (Partition suits, Succession Certificates)",
            "Revenue Court / Tehsildar (mutation of property records)",
            "Sub-Registrar (Will registration)",
        ],
        "typical_timeline": "Legal Heir Certificate: 1–4 weeks. Succession Certificate: 3–6 months. Probate: 6 months–2 years. Partition suit: 3–7 years.",
        "typical_costs": "Legal Heir Certificate: ₹100–₹500. Succession Certificate: 2% of assets (court fee). Probate: 2–4% of estate value. Partition: 1–3% of property value. NALSA for eligible.",
        "common_mistakes": [
            "Believing daughters have no rights in ancestral property — they do, after the 2005 HSA amendment",
            "Not updating mutation / Khata after death — creates complications in later sale",
            "Accepting verbal family settlement without written partition deed (registered)",
            "Not getting Probate when required — title becomes clouded",
            "Missing the 12-year limitation for partition after a refusal",
        ],
        "free_legal_aid": "NALSA for eligible heirs. Revenue court matters sometimes handled without lawyer. Lok Adalat for family settlements.",
    },

    "MedicalNegligence": {
        "applicable_laws": [
            "Consumer Protection Act, 2019 — medical services fall under 'services'; doctor/hospital is a 'service provider'",
            "Indian Medical Council Act, 1956 — professional misconduct complaints to State Medical Council",
            "Clinical Establishments (Registration and Regulation) Act, 2010 — hospital regulation",
            "BNS Section 106 — causing death by negligent act (criminal negligence)",
            "BNS Section 125A — endangering life or personal safety of others",
            "Supreme Court: Jacob Mathew v. State of Punjab (2005) — 3-element test for medical negligence: duty, breach, causation",
            "Supreme Court: V. Krishnakumar v. State of Tamil Nadu (2015) — hospital negligence standard",
        ],
        "typical_remedies": [
            "Compensation through Consumer Court (District/State/National Commission)",
            "Criminal complaint for gross negligence under BNS Section 106",
            "Professional misconduct complaint to State Medical Council (can suspend/cancel licence)",
            "Complaint to National Medical Commission (NMC) — appeals body",
            "Civil suit for damages in Civil Court",
        ],
        "evidence_checklist": [
            "ALL original medical records, test reports, prescriptions, discharge summary",
            "Consent forms signed by patient / family (check what was consented to)",
            "Billing records / payment receipts",
            "Photographs of injuries or condition before/after",
            "Second medical opinion in writing from an independent expert",
            "Death certificate + post-mortem report (if death occurred)",
            "All communications with hospital (written / WhatsApp / email)",
            "Hospital registration certificate (to verify it's a registered establishment)",
        ],
        "procedure_steps": [
            "Step 1: Collect ALL medical records from hospital immediately — hospital must provide (file RTI if refused)",
            "Step 2: Get independent second opinion from a specialist to establish standard of care breach",
            "Step 3: Send legal notice to hospital / doctor with demand and 30-day deadline",
            "Step 4: File Consumer complaint at District Commission (up to ₹50 lakh) — edaakhil.nic.in",
            "Step 5: File misconduct complaint with State Medical Council (no fee, separate process)",
            "Step 6: For criminal negligence (death): file FIR under BNS Section 106 at police station",
        ],
        "limitation_period": "Consumer Court: 2 years from date of negligence. Criminal: no strict limit for serious offences. Medical Council complaint: as soon as possible — no statutory limit but councils prefer prompt complaints.",
        "authorities": [
            "District Consumer Disputes Redressal Commission (edaakhil.nic.in)",
            "State Medical Council of the concerned state",
            "National Medical Commission (NMC): nmc.org.in",
            "Police station (for criminal negligence / death)",
            "National Human Rights Commission (NHRC) for government hospital failures",
        ],
        "typical_timeline": "Consumer Court: 6 months–2 years. Medical Council: 3–12 months. Criminal: 1–3 years.",
        "typical_costs": "Consumer Court fee: ₹200–₹5000 (claim-based). Medical Council: free. NALSA for eligible patients.",
        "common_mistakes": [
            "Not collecting all medical records immediately — hospitals sometimes 'lose' records later",
            "Missing the 2-year consumer court limitation period",
            "Filing criminal complaint without securing a second medical opinion first",
            "Assuming the hospital's internal complaint mechanism is adequate — always escalate externally",
            "Not getting written second opinion before filing — courts require expert evidence",
        ],
        "free_legal_aid": "NALSA for eligible patients. Consumer Court does not require a lawyer. National Human Rights Commission accepts pro se complaints.",
    },

    "LabourCodes": {
        "applicable_laws": [
            "Code on Wages, 2019 — consolidates Payment of Wages Act, Minimum Wages Act, Payment of Bonus Act, Equal Remuneration Act; applies to all employees",
            "Industrial Relations Code, 2020 — consolidates Trade Unions Act, Industrial Employment (Standing Orders) Act, Industrial Disputes Act; rationalises retrenchment rules",
            "Code on Social Security, 2020 — consolidates EPF, ESI, Gratuity, Maternity Benefit, Building & Construction Workers Acts; extends to gig & platform workers",
            "Occupational Safety, Health and Working Conditions Code, 2020 — consolidates Factories Act and 12 other laws; sets safety standards across industries",
            "Payment of Gratuity Act, 1972 (absorbed into Social Security Code) — 5 years continuous service triggers gratuity; max ₹20 lakh",
            "Employees' Provident Funds & Miscellaneous Provisions Act, 1952 (absorbed) — 12% employer + 12% employee PF contribution; EPFO enforcement",
            "Maternity Benefit Act, 1961 (absorbed) — 26 weeks paid maternity leave (for first two children); crèche facilities mandatory for 50+ employees",
        ],
        "typical_remedies": [
            "Back wages and interest for unpaid salary (Code on Wages)",
            "Reinstatement or compensation for unlawful retrenchment (Industrial Relations Code)",
            "Recovery of PF dues with interest and damages (EPFO)",
            "Gratuity with 10% interest per annum if withheld",
            "Maternity benefit recovery through labour commissioner",
            "Social security benefits for gig/platform workers (Social Security Code — notified portions)",
        ],
        "evidence_checklist": [
            "Appointment/offer letter and job description",
            "Salary slips for last 6 months (or payroll records)",
            "Bank statements showing salary credits / gaps",
            "PF account statement (UAN portal: unifiedportal-mem.epfindia.gov.in)",
            "Form 16 or Form 12B from employer",
            "Any written communication about termination, retrenchment, or wage dispute",
            "Attendance records / leave records if disputed",
        ],
        "procedure_steps": [
            "For unpaid wages: file complaint with Labour Commissioner / Payment of Wages Authority in your district",
            "For PF non-deposit: file complaint at EPFO regional office OR online at epfindia.gov.in",
            "For gratuity: apply in writing to employer first; if rejected, file before Controlling Authority (Labour Commissioner) within 60 days",
            "For wrongful termination: file complaint before Labour Court / Industrial Tribunal (under Industrial Relations Code)",
            "For maternity benefit: complaint to Inspector under Maternity Benefit Act / Controlling Authority",
            "Shram Suvidha portal (shramsuvidha.gov.in) for centralised grievances — all 4 Labour Codes covered",
        ],
        "limitation_period": "Wages: 1 year from due date. Gratuity: 60 days to apply to employer after retirement/resignation; 90 days to Controlling Authority if rejected. PF: no strict limitation but file within 3 years for best results.",
        "authorities": [
            "Labour Commissioner / Asst Labour Commissioner (district)",
            "EPFO Regional/Sub-Regional Office",
            "Controlling Authority (Gratuity Act)",
            "Labour Court / Industrial Tribunal",
            "Shram Suvidha Portal (central grievance)",
        ],
        "typical_timeline": "Labour Commissioner: 1–3 months. Labour Court: 6 months–2 years.",
        "typical_costs": "Filing fees: nominal (₹50–₹500). Lawyer optional for most labour complaints. NALSA provides free aid.",
        "common_mistakes": [
            "Not activating UAN or checking PF balance — employer may be deducting but not depositing",
            "Missing limitation period for gratuity (60 days after entitlement to apply to employer)",
            "Accepting Full & Final settlement verbally — always insist on written F&F statement",
            "Not preserving salary slips — most disputes turn on proof of salary",
            "Assuming 'contract workers' have no rights — all workers covered under Labour Codes",
        ],
        "free_legal_aid": "NALSA (15100). Labour Commissioner provides grievance mechanism free of charge. EPFO complaints require no lawyer.",
    },

    "DPDP": {
        "applicable_laws": [
            "Digital Personal Data Protection Act, 2023 (DPDP Act) — India's first comprehensive data privacy law; governs collection, storage, and use of digital personal data",
            "DPDP Act Section 4 — lawful basis for processing: consent OR legitimate use",
            "DPDP Act Section 6 — consent must be free, specific, informed, unconditional, and unambiguous; may be withdrawn at any time",
            "DPDP Act Section 11 — Data Principal rights: right to access information, right to correction, right to erasure, right to grievance redressal, right to nominate",
            "DPDP Act Section 16 — Data Fiduciary duties: purpose limitation, storage limitation, accuracy, security safeguards",
            "DPDP Act Section 40 — Data Protection Board of India (DPBI) adjudicates complaints; penalties up to ₹250 crore",
            "IT Act, 2000 Section 43A — compensation for failure to protect sensitive personal data (still applicable alongside DPDP Act)",
        ],
        "typical_remedies": [
            "Complaint to Data Protection Board of India (DPBI) for data breaches or refusal of rights",
            "Withdrawal of consent — Data Fiduciary must stop processing within reasonable time",
            "Right to erasure — personal data deleted unless retention is legally mandated",
            "Right to correction of inaccurate data held by a company",
            "Compensation under IT Act Section 43A for data breach causing loss",
            "Financial penalty on Data Fiduciary up to ₹250 crore (imposed by DPBI)",
        ],
        "evidence_checklist": [
            "Screenshot/copy of consent given (or privacy policy at time of sign-up)",
            "Written request to company for access/correction/erasure with date",
            "Company's response (or proof of non-response after 30 days)",
            "Evidence of the data breach or misuse (email, SMS, bank statement, news report)",
            "Communications with the company's Grievance Officer",
        ],
        "procedure_steps": [
            "Step 1: Contact the company's Grievance Officer (every company must publish one under DPDP Act / IT Rules)",
            "Step 2: If no response in 30 days, escalate to Data Protection Board of India (DPBI) — rules still being notified",
            "Step 3: For existing breaches under IT Act, file complaint at cybercrime.gov.in (Section 43A claim)",
            "Step 4: For financial fraud resulting from data breach, also file at 1930 cyber helpline",
        ],
        "limitation_period": "DPDP Act limitation not yet fully notified. IT Act Section 43A: general civil limitation of 3 years.",
        "authorities": [
            "Data Protection Board of India (DPBI) — central authority under DPDP Act",
            "Company's Grievance Officer (mandatory contact first)",
            "CERT-In (cert-in.org.in) for data breach reporting",
            "Cybercrime portal (cybercrime.gov.in) for fraud resulting from breach",
        ],
        "typical_timeline": "DPBI: rules still being notified (as of 2025). IT Act complaints: 6–18 months.",
        "typical_costs": "DPBI complaint: expected to be low-fee. Cybercrime portal: free. IT Act civil suit: standard court fees.",
        "common_mistakes": [
            "Not contacting the company's Grievance Officer first — mandatory prerequisite for DPBI complaint",
            "Thinking DPDP Act is fully operational — secondary legislation (rules) still being notified as of mid-2025",
            "Confusing DPDP Act with IT Act Section 43A — both may apply for existing breaches",
            "Not preserving proof of consent given and withdrawal requested",
        ],
        "free_legal_aid": "NALSA (15100). Cybercrime portal complaints are self-service and free. CERT-In reports require no lawyer.",
    },

    "MotorVehicles": {
        "applicable_laws": [
            "Motor Vehicles Act, 1988 (amended 2019) — governs registration, licensing, insurance, traffic offences, accident claims",
            "MV Act Section 140 — no-fault liability: ₹50,000 for permanent disability, ₹25,000 for death — payable without proving negligence",
            "MV Act Section 163A — structured formula compensation for hit-and-run or uninsured vehicle deaths (Second Schedule)",
            "MV Act Section 166 — compensation claim before Motor Accident Claims Tribunal (MACT); claimant need not prove negligence separately",
            "MV Act Section 147 — compulsory third-party insurance mandatory for all vehicles; insurer must compensate victims",
            "MV Act Section 185 — drunk driving (>30mg/100ml blood alcohol): Rs.10,000 fine + 6 months imprisonment for first offence",
            "Insurance Regulatory and Development Authority of India (IRDAI) — regulates motor insurance; complaints via Bima Bharosa portal",
        ],
        "typical_remedies": [
            "Compensation from MACT for death or injury (no-fault or negligence-based — whichever higher)",
            "Third-party insurer liable even if owner/driver uninsured (within limits)",
            "Hit-and-run fund: Solatium Fund Scheme (Central Motor Vehicles Rules) — ₹2 lakh (death), ₹50,000 (grievous injury)",
            "Insurance claim for own vehicle damage (comprehensive policy)",
            "Damages for pain and suffering, loss of earnings, medical expenses, loss of consortium",
            "Interim compensation under Section 140 within 30 days of claim",
        ],
        "evidence_checklist": [
            "FIR copy from police station (essential for insurance and MACT claim)",
            "Medical records, bills, and discharge summary",
            "Vehicle registration certificate (RC) and insurance documents",
            "DL of the vehicle owner/driver",
            "Panchnama (spot inspection by police)",
            "Witness names and contact",
            "Photographs of accident scene, vehicle damage, injuries",
            "Post-mortem report if death occurred",
            "Loss of income proof (salary slips, business records) for compensation calculation",
        ],
        "procedure_steps": [
            "Step 1: Call 112 / 1033 (highway helpline); ensure injured receive medical care",
            "Step 2: Inform police immediately — FIR is essential for all claims",
            "Step 3: Notify insurance company within 24–48 hours (as required by policy)",
            "Step 4: File claim petition before Motor Accident Claims Tribunal (MACT) at the district where accident occurred OR where claimant resides",
            "Step 5: For hit-and-run: apply to Claims Inspector / Police for Solatium Fund disbursement",
            "Step 6: MACT adjudicates and awards compensation (no court fee for MACT claim)",
        ],
        "limitation_period": "MACT claim: 6 months from accident date (Section 166, though courts often condone delay with good reason). File as early as possible.",
        "authorities": [
            "Motor Accident Claims Tribunal (MACT) — at district level",
            "Insurance company (Third-party claims)",
            "IRDAI (insurance regulator): irdai.gov.in | Bima Bharosa portal",
            "National Highway Authority / 1033 (highway accidents)",
            "Parivahan portal: parivahan.gov.in (RC/DL verification)",
        ],
        "typical_timeline": "Interim Section 140 order: 30 days. Full MACT award: 6 months–2 years.",
        "typical_costs": "MACT filing: no court fee. Lawyer: ₹5,000–₹30,000 (often on contingency). Insurance surveyor: appointed by insurer.",
        "common_mistakes": [
            "Not filing FIR — insurance companies use absence of FIR to deny claims",
            "Missing 6-month limitation for MACT (file immediately, don't wait for treatment to finish)",
            "Accepting insurer's first settlement offer without MACT — typically far lower than tribunal award",
            "Not claiming under Section 140 (no-fault) for immediate interim relief",
            "Forgetting to add ALL liable parties: owner + driver + insurer as respondents in MACT",
        ],
        "free_legal_aid": "MACT requires no court fee. NALSA (15100) provides free lawyers for road accident victims. Many lawyers take motor accident cases on contingency.",
    },

    "ChildCustody": {
        "applicable_laws": [
            "Guardians and Wards Act, 1890 — governs custody for all religions; court's paramount consideration is 'welfare of the child'",
            "Hindu Minority and Guardianship Act, 1956 — father is natural guardian of minor Hindu child, but mother is preferred for children under 5",
            "Special Marriage Act, 1954 Section 38 — custody provisions for civil marriages",
            "Muslim Personal Law — mother (mother's custody/hizanat) preferred for young children (boys till 7, girls till puberty in Hanafi law); father is natural guardian",
            "BNS Section 95 — wrongful confinement / taking child away in violation of court order is a criminal offence",
            "Supreme Court: Gaurav Nagpal v. Sumedha Nagpal (2009) — child's welfare is the supreme and paramount consideration overriding all else",
        ],
        "typical_remedies": [
            "Custody order (physical custody — who the child lives with)",
            "Visitation / access rights for the non-custodial parent",
            "Interim custody order (obtained quickly while main case is pending)",
            "Modification of custody order if circumstances change significantly",
            "Habeas corpus in High Court for immediate recovery of child taken wrongfully",
        ],
        "evidence_checklist": [
            "Child's birth certificate",
            "Marriage certificate (for parental status)",
            "Proof of stable home environment (photos, rent agreement, employment proof)",
            "School records and child's academic performance",
            "Medical records / health status of child",
            "Evidence of other parent's conduct if relevant (screenshots, FIR, medical reports)",
            "Financial capability evidence (income proof, bank statements)",
        ],
        "procedure_steps": [
            "File custody petition before Family Court (or District Court where no Family Court exists)",
            "Apply for interim custody order simultaneously — court can grant within days",
            "Court will typically interview the child if old enough to express preference",
            "Mediation may be ordered (Family Courts Act — attempt mediation before trial)",
            "For child taken to another state: file writ of habeas corpus in relevant High Court",
            "Violation of custody order: file contempt of court petition",
        ],
        "limitation_period": "No strict limitation for initial custody petition. For modification: significant change in circumstances must be shown.",
        "authorities": [
            "Family Court (primary forum)",
            "District Court (where no Family Court exists)",
            "High Court (habeas corpus for immediate recovery, or appeals)",
            "Child Welfare Committee (if child welfare concerns exist)",
        ],
        "typical_timeline": "Interim custody: 1–4 weeks. Final order: 6 months–2 years.",
        "typical_costs": "Filing: ₹200–₹1,000. Lawyer: ₹15,000–₹1,00,000. NALSA provides free legal aid for eligible persons.",
        "common_mistakes": [
            "Taking the child away from the other parent without court order — contempt risk + criminal exposure",
            "Not applying for interim custody immediately — delays allow status quo to entrench",
            "Thinking religion determines everything — courts apply 'welfare of child' test above personal law",
            "Not including child support / maintenance in the same petition",
            "Alienating the child against the other parent — courts penalise parental alienation",
        ],
        "free_legal_aid": "NALSA (15100). Women seeking custody can approach NCW (ncw.nic.in) for referrals. Child welfare matters — Child Welfare Committee can be involved at no cost.",
    },

    "RTE": {
        "applicable_laws": [
            "Right to Education Act, 2009 (RTE Act) — free and compulsory education for all children aged 6–14 (Classes 1–8) is a Fundamental Right under Article 21A",
            "RTE Act Section 12(1)(c) — every private unaided school must reserve 25% seats for children from economically weaker sections (EWS) and disadvantaged groups (DG); government reimburses",
            "RTE Act Section 16 — no child shall be held back (detained) in any class until completion of elementary education (Classes 1–8)",
            "RTE Act Section 17 — physical punishment and mental harassment of children is prohibited; teacher is liable",
            "RTE Act Section 28 — private tutoring by teachers of the students they teach is prohibited",
            "RTE Act Section 32 — complaint to Local Authority first; if unresolved, to State Commission for Protection of Child Rights (SCPCR)",
            "POCSO Act 2012 — if school abuse is sexual in nature, POCSO applies alongside RTE",
        ],
        "typical_remedies": [
            "Admission under 25% EWS/DG quota in any private school near your home",
            "Complaint to District Education Officer (DEO) for school violations",
            "Complaint to SCPCR (State Commission for Protection of Child Rights) for persistent non-compliance",
            "Action against teacher for physical punishment (school administration + DEO)",
            "No-detention policy: child cannot be expelled or failed before Class 8",
        ],
        "evidence_checklist": [
            "Child's birth certificate",
            "Proof of residence (Aadhaar, ration card, electricity bill)",
            "Income certificate (for EWS/DG admission — issued by Tehsildar/SDM)",
            "Caste certificate if applicable (SC/ST/OBC)",
            "Photographs of any injury if physical punishment occurred",
            "Written complaints previously made to school",
        ],
        "procedure_steps": [
            "EWS/DG admission: apply online at your state's education portal or visit the school during admission season (typically January–March)",
            "School refusing admission: complain to Block Education Officer (BEO) or District Education Officer (DEO)",
            "Physical punishment: complain in writing to school principal, then DEO, then SCPCR",
            "SCPCR complaint: state-specific portals — e.g. Delhi (dcpcr.gov.in), Maharashtra (wcd.maharashtra.gov.in), etc.",
            "National Commission for Protection of Child Rights (NCPCR): ncpcr.gov.in | 1800-11-9176",
        ],
        "limitation_period": "No strict limitation for most RTE complaints. EWS admissions: state-specific annual deadlines.",
        "authorities": [
            "Block Education Officer (BEO) — first contact",
            "District Education Officer (DEO)",
            "State Commission for Protection of Child Rights (SCPCR)",
            "National Commission for Protection of Child Rights (NCPCR): ncpcr.gov.in | 1800-11-9176",
        ],
        "typical_timeline": "EWS admission order: 2–4 weeks. SCPCR complaint: 30–90 days.",
        "typical_costs": "RTE admission: completely FREE (government reimburses school). Complaints to DEO/SCPCR/NCPCR: free.",
        "common_mistakes": [
            "Not knowing the 25% EWS quota exists — many parents miss it due to lack of awareness",
            "Missing state-specific EWS admission windows (usually January–March)",
            "Assuming private schools can legally expel or detain children before Class 8 — they cannot",
            "Not reporting physical punishment formally — informal complaints to teachers rarely result in change",
        ],
        "free_legal_aid": "NALSA (15100). NCPCR (1800-11-9176) provides guidance free of charge. Complaints to DEO and SCPCR are free and require no lawyer.",
    },

    "General": {
        "applicable_laws": [
            "Indian Constitution — fundamental rights under Part III (Articles 14, 19, 21, 22, 32)",
            "Bharatiya Nyaya Sanhita (BNS) 2023 — replaced Indian Penal Code (IPC)",
            "Bharatiya Nagarik Suraksha Sanhita (BNSS) 2023 — replaced CrPC",
            "Bharatiya Sakshya Adhiniyam (BSA) 2023 — replaced Indian Evidence Act",
        ],
        "typical_remedies": ["Varies by specific issue — please ask about your specific situation"],
        "evidence_checklist": [
            "Preserve all documents related to the dispute",
            "Photograph or screenshot any evidence (with timestamps visible)",
            "Record the timeline of events in writing",
            "Note witness names and contact details",
        ],
        "procedure_steps": [
            "Identify the specific legal issue accurately",
            "Gather all relevant documents",
            "Consult NALSA (nalsa.gov.in | 15100) for free legal aid guidance",
        ],
        "limitation_period": "Varies significantly by case type — ask about your specific situation to get accurate limitation period.",
        "authorities": ["NALSA: nalsa.gov.in | 15100", "District Court / High Court", "Relevant regulatory authority"],
        "typical_timeline": "Varies widely by case type and court",
        "typical_costs": "Varies. NALSA provides free assistance for eligible persons.",
        "common_mistakes": [
            "Not consulting a lawyer for complex matters",
            "Missing limitation periods — ask specifically about your case",
        ],
        "free_legal_aid": "NALSA: nalsa.gov.in | 15100. State DLSA in every district. Lok Adalat for settlements.",
    },
}


def build_legal_reasoning_context(
    category: str,
    case_analysis: dict,
    jurisdiction: Optional[str],
) -> str:
    """
    Agent 5 — Legal Reasoner: Build a structured, deterministic reasoning context
    from the static _LEGAL_KNOWLEDGE lookup.

    This gives the 70B composer a pre-built legal analysis framework
    so it reasons like a lawyer rather than just summarising RAG chunks.

    Injects:
    - Applicable laws (relevant to this category)
    - Possible remedies
    - Evidence checklist
    - Typical procedure
    - Limitation period warning (flagged prominently if limitation_concern=True)
    - Relevant authorities
    - Typical timeline and cost guidance
    - Common mistakes to warn against
    - Multi-domain secondary analysis
    - Known and missing facts extracted by Agent 1
    """
    knowledge = _LEGAL_KNOWLEDGE.get(category, _LEGAL_KNOWLEDGE["General"])
    lines: list[str] = [
        "[LEGAL REASONING CONTEXT — internal guidance for response composition; never expose this block to user]"
    ]

    # Applicable laws
    if knowledge.get("applicable_laws"):
        lines.append(
            "Potentially applicable laws:\n"
            + "\n".join(f"• {law}" for law in knowledge["applicable_laws"])
        )

    # Possible remedies
    if knowledge.get("typical_remedies"):
        lines.append(
            "Possible remedies available:\n"
            + "\n".join(f"• {r}" for r in knowledge["typical_remedies"])
        )

    # Evidence the user should preserve
    needs_ev = case_analysis.get("needs_evidence_guide", False)
    urgency = case_analysis.get("urgency", "informational")
    if needs_ev or urgency in ("immediate", "recent"):
        checklist = knowledge.get("evidence_checklist", [])
        if checklist:
            lines.append(
                "Evidence user should preserve RIGHT NOW:\n"
                + "\n".join(f"• {e}" for e in checklist)
            )

    # Procedure steps
    if knowledge.get("procedure_steps"):
        lines.append(
            "Typical procedure (adapt to user's specific situation):\n"
            + "\n".join(f"{i+1}. {s}" for i, s in enumerate(knowledge["procedure_steps"]))
        )

    # Limitation period — flag prominently if there is a concern
    if knowledge.get("limitation_period"):
        lp = knowledge["limitation_period"]
        prefix = "⚠ CRITICAL DEADLINE — " if case_analysis.get("limitation_concern") else "Limitation period: "
        lines.append(f"{prefix}{lp}")
        if case_analysis.get("limitation_concern"):
            lines.append(
                "The user may be approaching or have already passed a legal deadline. "
                "Mention this clearly and advise them to act immediately."
            )

    # Relevant authorities
    if knowledge.get("authorities"):
        lines.append(
            "Relevant authorities:\n"
            + "\n".join(f"• {a}" for a in knowledge["authorities"])
        )

    # Timeline and costs
    if knowledge.get("typical_timeline"):
        lines.append(f"Typical timeline: {knowledge['typical_timeline']}")

    if case_analysis.get("needs_cost_estimate") and knowledge.get("typical_costs"):
        lines.append(f"Approximate costs: {knowledge['typical_costs']}")

    # Common mistakes to warn against
    if knowledge.get("common_mistakes"):
        lines.append(
            "Common mistakes to warn against (weave in naturally, do not list mechanically):\n"
            + "\n".join(f"• {m}" for m in knowledge["common_mistakes"])
        )

    # Free legal aid
    if knowledge.get("free_legal_aid"):
        lines.append(f"Free legal aid: {knowledge['free_legal_aid']}")

    # Multi-domain analysis
    secondary = [c for c in case_analysis.get("secondary_categories", []) if c]
    if secondary:
        lines.append(f"Multi-domain issue — also involves: {', '.join(secondary)}")
        for sec_cat in secondary[:2]:
            sec_k = _LEGAL_KNOWLEDGE.get(sec_cat, {})
            if sec_k.get("applicable_laws"):
                lines.append(
                    f"Also relevant ({sec_cat}):\n"
                    + "\n".join(f"  • {law}" for law in sec_k["applicable_laws"][:3])
                )

    # Known facts extracted by Agent 1
    known = [f for f in case_analysis.get("known_facts", []) if f]
    if known:
        lines.append("Facts already established:\n" + "\n".join(f"• {f}" for f in known))

    # Missing facts
    missing = [f for f in case_analysis.get("missing_facts", []) if f]
    if missing:
        lines.append(
            "Facts still unknown that would change analysis:\n"
            + "\n".join(f"• {f}" for f in missing)
        )

    if jurisdiction:
        lines.append(
            f"Jurisdiction detected: {jurisdiction}. "
            "Note any state-specific variations in rent control, personal law, or court procedure."
        )

    return "\n\n".join(lines)


# ──────────────────────────────────────────────────────────────
# AGENTS 2 & 3 — RIGHTS ORGANIZER + PROCEDURE ORGANIZER (Python)
# ──────────────────────────────────────────────────────────────

_RIGHTS_KW: dict[str, list[str]] = {
    "DomesticViolence":  ["domestic violence", "PWDVA", "protection order", "residence order", "498A", "BNS 85", "BNS 86", "maintenance", "shelter"],
    "Divorce":           ["divorce", "judicial separation", "HMA", "talaq", "khula", "restitution of conjugal rights", "marriage dissolution"],
    "Maintenance":       ["maintenance", "alimony", "CrPC 125", "BNSS 144", "HMA 24", "Section 125", "monthly payment", "senior citizen", "parents welfare", "Senior Citizens Act", "Section 23", "property revocation", "Maintenance Tribunal"],
    "FIR":               ["FIR", "first information report", "cognizable", "non-cognizable", "BNSS 173", "zero FIR", "police complaint"],
    "Consumer":          ["Consumer Protection", "COPRA", "deficiency", "unfair trade practice", "warranty", "consumer right", "refund"],
    "RTI":               ["Right to Information", "RTI Act", "public authority", "exemption", "Section 8", "CPIO", "information access"],
    "Tenant":            ["tenant", "landlord", "rent", "eviction", "Transfer of Property", "lease", "rent control", "security deposit"],
    "Employment":        ["employment", "labour", "termination", "retrenchment", "Industrial Disputes", "workman", "POSH", "gratuity", "PF", "unpaid salary", "wages withheld", "full and final", "F&F settlement", "experience letter", "relieving letter", "notice period pay", "Code on Wages", "Shops and Establishments"],
    "ChequeBounce":      ["cheque bounce", "NI Act", "Section 138", "dishonour", "criminal liability", "negotiable instrument"],
    "Bail":              ["bail", "bailable", "non-bailable", "BNSS 480", "BNSS 482", "anticipatory bail", "default bail", "custody"],
    "POCSO":             ["POCSO", "child protection", "sexual assault minor", "JJ Act", "child abuse"],
    "Constitutional":    ["Article", "fundamental rights", "directive principles", "writ", "constitutional remedy", "habeas corpus"],
    "Cybercrime":        ["IT Act", "Section 66", "cyber fraud", "data protection", "DPDP Act", "online fraud", "identity theft"],
    "Property":          ["Hindu Succession", "property rights", "inheritance", "will", "gift deed", "partition", "encumbrance"],
    "POSH":              ["POSH", "sexual harassment workplace", "ICC", "internal complaints committee"],
    "Contract":         ["contract", "agreement", "breach", "specific performance", "damages", "Indian Contract Act", "consideration", "void", "voidable", "rescind"],
    "Inheritance":      ["inheritance", "succession", "Hindu Succession Act", "intestate", "will", "probate", "legal heir", "coparcener", "ancestral property"],
    "MedicalNegligence": ["medical negligence", "doctor negligence", "hospital negligence", "Consumer Protection medical", "IMC Act", "Jacob Mathew", "standard of care", "iatrogenic"],
    "LabourCodes":      ["Code on Wages", "Social Security Code", "Industrial Relations Code", "gig worker", "platform worker", "EPFO", "PF provident fund", "gratuity", "maternity benefit", "ESI"],
    "DPDP":             ["data protection", "DPDP Act", "personal data", "data breach", "Data Protection Board", "consent withdrawal", "right to erasure", "data fiduciary", "digital privacy"],
    "MotorVehicles":    ["motor accident", "MACT", "third party insurance", "Motor Vehicles Act", "hit and run", "solatium", "vehicle compensation", "traffic offence", "road accident"],
    "ChildCustody":     ["child custody", "guardianship", "Guardians and Wards Act", "visitation rights", "welfare of child", "parental rights", "custody order"],
    "RTE":              ["right to education", "RTE Act", "EWS admission", "free education", "school admission", "Article 21A", "NCPCR", "no detention", "physical punishment school"],
}

_PROCEDURE_KW: dict[str, list[str]] = {
    "DomesticViolence":  ["protection officer", "magistrate", "shelter home", "One Stop Centre", "complaint DV", "domestic incident report"],
    "Divorce":           ["family court", "mediation", "mutual consent", "contested divorce", "cooling period", "petition"],
    "FIR":               ["file FIR", "police station", "Section 154", "SP", "Magistrate 156(3)", "BNSS 173", "zero FIR"],
    "Consumer":          ["District Commission", "State Commission", "NCDRC", "complaint filing", "forum procedure", "edaakhil"],
    "RTI":               ["RTI application", "30 days", "first appeal", "second appeal", "CIC", "SIC", "CPIO"],
    "Tenant":            ["rent controller", "eviction notice", "quit notice", "civil court", "15 day notice", "rent tribunal"],
    "Employment":        ["labour court", "grievance", "labour commissioner", "industrial tribunal", "conciliation", "EPFO", "written demand", "salary demand letter", "legal notice employer", "EPFO grievance", "Shops Establishments complaint", "F&F full and final", "experience letter demand"],
    "ChequeBounce":      ["legal notice", "30 days", "magistrate complaint", "criminal complaint NI Act", "return memo", "RPAD"],
    "Bail":              ["bail application", "sessions court", "bail bond", "personal bond", "BNSS 482 application", "default bail"],
    "POCSO":             ["special court", "child welfare committee", "SJPU", "mandatory reporting", "childline"],
    "Property":          ["partition suit", "injunction", "civil court", "RERA", "encumbrance certificate", "mutation"],
    "POSH":              ["ICC complaint", "LCC", "shebox", "90 days inquiry", "labour commissioner"],
    "Cybercrime":        ["cybercrime.gov.in", "1930", "FIR cybercrime", "complaint portal", "CERT-In"],
    "Contract":         ["send legal notice", "civil suit", "commercial court", "specific performance suit", "civil court plaint", "arbitration", "Lok Adalat settlement"],
    "Inheritance":      ["succession certificate", "probate court", "letters of administration", "partition suit", "family settlement deed", "mutation of revenue records"],
    "MedicalNegligence": ["consumer forum medical", "District Commission", "state medical council", "IMC complaint", "hospital notice", "evidence preservation medical"],
    "Maintenance":      ["family court", "family magistrate", "execution petition", "Maintenance Tribunal", "SDM office", "Section 23 application", "NALSA", "legal aid"],
    "LabourCodes":      ["labour commissioner", "EPFO regional office", "shramsuvidha.gov.in", "labour court", "Industrial Tribunal", "Controlling Authority", "PF complaint", "gratuity application"],
    "DPDP":             ["Data Protection Board", "Grievance Officer company", "cybercrime.gov.in", "CERT-In", "meity.gov.in", "consent withdrawal notice"],
    "MotorVehicles":    ["Motor Accident Claims Tribunal", "MACT petition", "insurance claim", "IRDAI complaint", "Solatium Fund", "parivahan.gov.in", "1033 highway helpline"],
    "ChildCustody":     ["family court petition", "interim custody", "habeas corpus High Court", "mediation", "Child Welfare Committee", "visitation order"],
    "RTE":              ["Block Education Officer", "District Education Officer", "SCPCR complaint", "NCPCR", "ncpcr.gov.in", "EWS lottery", "school admission portal"],
}


def _kw_score(chunk: dict, keywords: list[str]) -> float:
    text = (chunk.get("topic", "") + " " + chunk.get("text", "")).lower()
    hits = sum(1 for kw in keywords if kw.lower() in text)
    return hits / max(len(keywords), 1)


def organize_chunks(retrieved: list[dict], category: str) -> dict:
    """
    Agents 2, 3 — Pure-Python chunk classifiers.
    Categorise retrieved RAG chunks into rights, procedure, and general buckets.
    Returns {"rights": [...], "procedure": [...], "general": [...]}.
    """
    rights_kws  = _RIGHTS_KW.get(category, [])
    proc_kws    = _PROCEDURE_KW.get(category, [])

    rights: list[dict] = []
    procedure: list[dict] = []
    general: list[dict] = []

    for chunk in retrieved:
        r = _kw_score(chunk, rights_kws)  if rights_kws  else 0.0
        p = _kw_score(chunk, proc_kws) if proc_kws else 0.0

        if r > 0.05 or p > 0.05:
            (rights if r >= p else procedure).append(chunk)
        else:
            general.append(chunk)

    return {"rights": rights, "procedure": procedure, "general": general}


# ──────────────────────────────────────────────────────────────
# AGENT 6 — JURISDICTION DETECTOR (Python, no LLM)
# ──────────────────────────────────────────────────────────────

def detect_jurisdiction(query: str, history: list[dict]) -> Optional[str]:
    """
    Agent 6: Keyword-based jurisdiction detection — no LLM.
    Returns detected Indian state or major city name, or None.
    """
    _KNOWN = [
        "delhi", "maharashtra", "mumbai", "karnataka", "bengaluru", "bangalore",
        "tamil nadu", "chennai", "gujarat", "ahmedabad", "surat", "rajasthan",
        "jaipur", "uttar pradesh", "lucknow", "agra", "varanasi", "noida",
        "west bengal", "kolkata", "andhra pradesh", "telangana", "hyderabad",
        "punjab", "chandigarh", "haryana", "gurugram", "gurgaon", "faridabad",
        "kerala", "kochi", "trivandrum", "thiruvananthapuram",
        "madhya pradesh", "bhopal", "indore", "bihar", "patna", "jharkhand",
        "ranchi", "odisha", "bhubaneswar", "assam", "guwahati", "himachal",
        "uttarakhand", "dehradun", "goa", "panaji", "chhattisgarh", "raipur",
        "nagpur", "pune", "lucknow", "nagaland", "manipur", "meghalaya",
        "tripura", "mizoram", "arunachal", "sikkim", "jammu", "kashmir",
        "ladakh", "puducherry", "andaman", "lakshadweep",
    ]
    haystack = query.lower()
    for msg in (history or [])[-4:]:
        haystack += " " + msg.get("content", "").lower()
    for name in _KNOWN:
        if name in haystack:
            return name.title()
    return None


# ──────────────────────────────────────────────────────────────
# AGENT 4 — DOCUMENT ASSISTANT (templates, no LLM)
# ──────────────────────────────────────────────────────────────

_TEMPLATES: dict[str, str] = {
    "RTI": """\
RTI APPLICATION

To,
The Public Information Officer (CPIO),
[Name of Ministry / Department / Public Authority]
[Address]

Date: [DATE]

Subject: Application under Section 6(1) of the Right to Information Act, 2005

Sir/Madam,

I, [YOUR FULL NAME], resident of [YOUR ADDRESS], hereby request the following information under the RTI Act, 2005:

1. [SPECIFIC INFORMATION POINT 1]
2. [SPECIFIC INFORMATION POINT 2 — add or remove points as needed]

I am willing to pay the prescribed application fee of ₹10 (BPL card holders are exempt — enclose copy).

Please furnish the information within 30 days as mandated under Section 7(1) of the RTI Act. If the information is not available with your office, please transfer this application to the concerned Public Authority under Section 6(3).

Yours faithfully,

[YOUR FULL NAME]
[COMPLETE ADDRESS]
[MOBILE NUMBER]
[EMAIL ID (optional)]

─────────────────────────────────────
How to submit:
• Online: rtionline.gov.in (Central Govt. only)
• By hand / post: to the CPIO of the concerned office
• Keep a copy + acknowledgment receipt

If no reply in 30 days → First Appeal to First Appellate Authority (within 30 days of deadline).
If unsatisfied → Second Appeal to CIC / SIC (within 90 days of FAA order).""",

    "PoliceComplaint": """\
POLICE COMPLAINT

To,
The Station House Officer (SHO),
[POLICE STATION NAME] Police Station,
[POLICE STATION ADDRESS]

Date: [DATE]

Subject: Complaint regarding [BRIEFLY STATE THE SUBJECT — e.g., theft, harassment, fraud]

Sir,

I, [YOUR FULL NAME], resident of [YOUR COMPLETE ADDRESS], wish to bring the following incident to your notice and request registration of an FIR / NCR:

DATE OF INCIDENT: [DATE AND TIME]
PLACE OF INCIDENT: [FULL ADDRESS / LOCATION]
ACCUSED / RESPONDENT: [NAME, ADDRESS, DESCRIPTION IF KNOWN — write "Unknown" if not known]

FACTS OF THE INCIDENT:
[Describe what happened in clear, chronological order. Include: what happened, how it happened, what was said or done, any injuries or losses.]

WITNESSES (if any):
1. [NAME — CONTACT]
2. [NAME — CONTACT]

EVIDENCE AVAILABLE:
• [Photos / screenshots / documents / CCTV footage / WhatsApp messages / bank statements]
• [Other evidence]

I respectfully request you to:
1. Register an FIR under applicable provisions of the Bharatiya Nyaya Sanhita / [OTHER ACT] and take necessary action.
2. Issue me a copy of the FIR as required under BNSS Section 173.

Yours faithfully,

[YOUR FULL NAME]
[ADDRESS]
[MOBILE]
[DATE]

─────────────────────────────────────
If SHO refuses to register FIR:
→ Send written complaint by Speed Post to SP / DCP of the district.
→ If still no action, file complaint before the Judicial Magistrate under BNSS 175(3).""",

    "LegalNotice": """\
LEGAL NOTICE

Date: [DATE]

To,
[RECIPIENT FULL NAME]
[RECIPIENT COMPLETE ADDRESS]

From:
[YOUR FULL NAME / ADVOCATE'S NAME]
[YOUR ADDRESS / ADVOCATE'S OFFICE ADDRESS]

Subject: Legal Notice for [SUBJECT — e.g., Recovery of Dues / Vacation of Premises / Cheque Bounce]

Madam / Sir,

Under instructions from my client, [CLIENT NAME], resident of [CLIENT ADDRESS], I hereby serve you with this Legal Notice.

BACKGROUND:
[Describe the relationship — e.g., tenant-landlord, buyer-seller, borrower-lender.]

FACTS:
1. On [DATE], [DESCRIBE WHAT HAPPENED — FACT 1].
2. On [DATE], [DESCRIBE WHAT HAPPENED — FACT 2].
3. Despite repeated requests/reminders on [DATES], you have failed to [SPECIFY].

LEGAL BASIS:
[Mention applicable law — e.g., Section 138 NI Act / Consumer Protection Act 2019 / Transfer of Property Act 1882 / Contract Act 1872]

DEMAND:
My client hereby calls upon you to [SPECIFIC DEMAND — pay ₹[AMOUNT] / vacate premises by [DATE] / replace / restore] within [15/30] days of receipt of this notice.

In default, my client shall be constrained to initiate appropriate legal proceedings before the competent court / forum / authority at your risk and cost.

This notice is served without prejudice to all other rights and remedies available to my client.

[ADVOCATE NAME]
[BAR COUNCIL ENROLMENT NUMBER]
[ADDRESS]
[CONTACT]

─────────────────────────────────────
Send via: Registered Post with Acknowledgment Due (RPAD).
Keep: copy of notice + postal receipt + delivery acknowledgment.
These are essential if you proceed to court.""",

    "ConsumerComplaint": """\
CONSUMER COMPLAINT

Before the District Consumer Disputes Redressal Commission,
[DISTRICT NAME]

Complaint No.: [TO BE ASSIGNED]
Date: [DATE]

COMPLAINANT:
Name:    [YOUR FULL NAME]
Address: [COMPLETE ADDRESS]
Phone:   [MOBILE NUMBER]
Email:   [EMAIL ID]

OPPOSITE PARTY (OP):
Name:    [COMPANY / SELLER / SERVICE PROVIDER NAME]
Address: [REGISTERED / BRANCH OFFICE ADDRESS]
Website: [IF APPLICABLE]

Subject: Complaint under Section 35 of the Consumer Protection Act, 2019
         for [DEFECTIVE PRODUCT / DEFICIENCY IN SERVICE / UNFAIR TRADE PRACTICE]

FACTS:
1. On [DATE], the Complainant purchased [PRODUCT / SERVICE] from the OP for ₹[AMOUNT]. [Attach invoice.]
2. The OP represented / promised: [WHAT WAS PROMISED].
3. On [DATE], the Complainant discovered: [WHAT WENT WRONG — defect, non-delivery, fraud, etc.].
4. The Complainant reported this to the OP on [DATE] via [email / phone / letter / consumer helpline].
5. The OP responded on [DATE] with: [WHAT THEY SAID / OR DID NOT RESPOND].
6. Despite [NUMBER] follow-ups over [DAYS/MONTHS], the grievance remains unresolved.

DOCUMENTS ATTACHED:
☐ Invoice / Receipt
☐ Warranty Card / Service Agreement
☐ All Complaint Emails / Chat Screenshots
☐ Company's Written Response (if any)
☐ Photos of Defective Product (if applicable)
☐ Bank Statement (for financial fraud)

PRAYER:
The Complainant prays that this Commission may:
(a) Direct the OP to [refund ₹[AMOUNT] / replace the product / complete the service as promised].
(b) Award ₹[AMOUNT] as compensation for mental agony and inconvenience.
(c) Award ₹[AMOUNT] as litigation costs.

Place: [CITY]                    Complainant's Signature: _______________
Date:  [DATE]                    [YOUR FULL NAME]

─────────────────────────────────────
Jurisdiction by claim value:
• ≤ ₹50 lakh    → District Consumer Commission (DCDRC)
• ₹50 L–₹2 Cr  → State Consumer Commission (SCDRC)
• > ₹2 Cr       → National Commission (NCDRC, ncdrc.nic.in)

File online: edaakhil.nic.in  |  Helpline: 1800-11-4000 / 1915""",

    "Affidavit": """\
AFFIDAVIT

I, [YOUR FULL NAME], son/daughter/wife of [FATHER'S / HUSBAND'S NAME], aged [AGE] years, resident of [COMPLETE ADDRESS], do hereby solemnly affirm and declare as under:

1. That I am the deponent and am fully competent to swear this affidavit.
2. That [STATE THE SPECIFIC FACT OR DECLARATION — e.g., "I am the sole legal heir of the deceased [NAME]"].
3. That [SECOND FACT IF NEEDED — add or remove numbered paragraphs as required].
4. That the above facts stated are true and correct to the best of my knowledge and belief, and nothing material has been concealed therefrom.

VERIFICATION

Verified at [CITY] on [DATE] that the contents of paras 1 to [LAST PARA NUMBER] of this affidavit are true and correct to my knowledge and no part of it is false and nothing material has been concealed therein.

DEPONENT

[YOUR FULL NAME]
[DATE]

─────────────────────────────────────
Sworn before me on [DATE]
at [PLACE]

NOTARY PUBLIC / OATH COMMISSIONER / MAGISTRATE
[NAME]
[SEAL & REGISTRATION NUMBER]

─────────────────────────────────────
How to execute:
• Type or write legibly; do NOT leave blanks.
• Sign every page; full signature on the last page.
• Appear before a Notary Public (Notary Fees: ₹20–₹200).
• Alternatively, swear before a First Class Judicial Magistrate or Executive Magistrate.
• Stamp duty: required in some states — check local rules (commonly ₹10–₹100 stamp paper).
• False affidavit is an offence under BNS Section 229 (perjury) — punishable with up to 7 years imprisonment.""",
}


def get_document_template(doc_type: Optional[str]) -> Optional[str]:
    """Agent 4: Return a structured template for the requested document type, or None."""
    return _TEMPLATES.get(doc_type or "") if doc_type else None


# ──────────────────────────────────────────────────────────────
# AGENT 7 — RESPONSE COMPOSER (message builder for 70B call)
# ──────────────────────────────────────────────────────────────

def build_composer_messages(
    *,
    query: str,
    history: list[dict],
    case_analysis: dict,
    organized_chunks: dict,
    jurisdiction: Optional[str],
    reasoning_context: str,
    emotion: str,
    lang: str,
    outer_context: str,
    confidence: str = "None",
    template: Optional[str] = None,
) -> list[dict]:
    """
    Agent 7: Build the final message list for the 70B Response Composer.

    Now passes a deterministic legal reasoning context (from _LEGAL_KNOWLEDGE)
    alongside RAG chunks, so the 70B model has:
      • Pre-identified applicable laws (not just RAG-retrieved ones)
      • Evidence checklists tailored to the category
      • Procedure steps
      • Limitation period warnings
      • Common mistakes to warn against
      • Multi-domain analysis
    """
    from ai.responder import PERSONA, LANG_INSTRUCTIONS, FALLBACK_LINKS, SOURCES_SECTION_PROMPT

    history = trim_history(history)
    persona = PERSONA["Legal"]
    lang_instr = LANG_INSTRUCTIONS.get(lang, LANG_INSTRUCTIONS["auto"])

    # Organise RAG chunks by category
    rights_chunks  = organized_chunks.get("rights", [])
    proc_chunks    = organized_chunks.get("procedure", [])
    general_chunks = organized_chunks.get("general", [])
    all_chunks     = rights_chunks + proc_chunks + general_chunks

    # Stable citation index [1], [2], …
    chunk_to_idx: dict[int, int] = {id(c): i + 1 for i, c in enumerate(all_chunks)}

    def _fmt_section(chunks: list[dict], title: str) -> str:
        if not chunks:
            return ""
        parts = [f"[{title}]"]
        for c in chunks:
            url_line  = f"\n  URL: {c['sourceUrl']}" if c.get("sourceUrl") else ""
            auth_line = f"\n  Authority: {c['source']}" if c.get("source") else ""
            parts.append(
                f"[Source {chunk_to_idx[id(c)]} — {c['topic']}]{url_line}{auth_line}\n{c['text'].strip()}"
            )
        return "\n\n".join(parts)

    sections = [
        _fmt_section(rights_chunks,  "Rights & Protections"),
        _fmt_section(proc_chunks,    "Procedure & Steps"),
        _fmt_section(general_chunks, "Additional Context"),
    ]
    knowledge_block = "\n\n".join(s for s in sections if s) or \
        "(No specific RAG knowledge retrieved — rely on your legal reasoning context above)"

    # Case analysis summary for the composer
    cat             = case_analysis.get("category", "General")
    issue_type      = case_analysis.get("issue_type")
    urgency         = case_analysis.get("urgency", "informational")
    follow_up       = case_analysis.get("follow_up")
    pers_law        = case_analysis.get("personal_law")
    employment_type = case_analysis.get("employment_type")
    property_type   = case_analysis.get("property_type")
    needs_r         = case_analysis.get("needs_rights", True)
    needs_p         = case_analysis.get("needs_procedure", True)
    needs_doc       = case_analysis.get("needs_document", False)
    doc_type        = case_analysis.get("doc_type")
    multi_dom       = case_analysis.get("multi_domain", False)
    lim_warn        = case_analysis.get("limitation_concern", False)

    focus = [x for x, flag in [
        ("legal rights / protections", needs_r),
        ("procedure / what to do",     needs_p),
        (f"draft {doc_type or 'document'}", needs_doc),
    ] if flag]

    analysis_lines = [
        f"Category: {cat}" + (" (multi-domain)" if multi_dom else ""),
        f"Urgency: {urgency}" + (" — ADDRESS SAFETY FIRST" if urgency == "immediate" else ""),
    ]
    if issue_type:
        analysis_lines.append(
            f"Issue type: {issue_type} — include '## Issue Type' in response using this classification."
        )
    if jurisdiction:
        analysis_lines.append(f"Jurisdiction: {jurisdiction} (note state-specific variations)")
    if pers_law:
        analysis_lines.append(f"Personal law: {pers_law}")
    if employment_type:
        analysis_lines.append(
            f"Employment type: {employment_type} — tailor applicable law accordingly "
            "(private_employee → ID Act / Code on Wages; government_employee → service rules; "
            "gig_worker/domestic_worker → Code on Social Security; intern/apprentice → limited protection)."
        )
    if property_type:
        analysis_lines.append(
            f"Property/occupancy type: {property_type} — affects which law applies "
            "(rented_residential → Rent Control Act; pg_hostel → limited statutory protection; "
            "commercial_lease → Transfer of Property Act; agricultural → state land tenancy law)."
        )
    if focus:
        analysis_lines.append(f"Response focus: {', '.join(focus)}")
    if lim_warn:
        analysis_lines.append(
            "⚠ LIMITATION PERIOD CONCERN — This matter may have a time-critical deadline. "
            "Mention it clearly and advise immediate action."
        )
    if follow_up:
        analysis_lines.append(
            f"Key question still missing — if not already answered in conversation, ask this ONE question: {follow_up}"
        )

    # Confidence — guide caution level
    if confidence in ("Low", "None") and not all_chunks:
        analysis_lines.append(
            "RAG confidence: LOW — No strong RAG hits. Rely on legal reasoning context. "
            "State uncertainty explicitly. Never invent section numbers or Act names."
        )
    elif confidence == "Low":
        analysis_lines.append(
            "RAG confidence: LOW — Use retrieved sources carefully. Acknowledge uncertainty where present."
        )

    analysis_block = (
        "[INTERNAL CASE ANALYSIS — guide your response; do not expose this block]\n"
        + "\n".join(analysis_lines)
    )

    # Template block
    template_block = ""
    if template and needs_doc:
        template_block = (
            "\n[DOCUMENT TEMPLATE — fill bracketed fields with details the user provided]\n"
            f"{template}\n"
        )

    context_section = f"\nCONVERSATION CONTEXT: {outer_context}\n" if outer_context else ""
    fallback = FALLBACK_LINKS.get("Legal", "")

    system_prompt = f"""{persona}

LANGUAGE: {lang_instr}
{context_section}
{analysis_block}

{reasoning_context}

Retrieved knowledge (cite inline with [1] [2] etc. — place bracket after the sentence it supports):
{knowledge_block}
{template_block}
LEGAL-SPECIFIC RULES — follow these precisely:

1. CONTRADICTING SOURCES: If two retrieved sources give different answers (e.g., different limitation periods or different section numbers), explicitly flag the conflict — "Sources differ on this point. One says X; another says Y. A lawyer can clarify for your specific facts." Never silently pick one.

2. STATE-SPECIFIC CAVEATS: Rent control laws, personal law applicability, consumer forum fees, and land record procedures vary significantly by state. If jurisdiction is known, add state-specific notes. If not known and it matters, say so and ask.

3. NEW CRIMINAL CODES: Always use BNS / BNSS / BSA (2023) as the primary reference. Mention the old IPC/CrPC equivalent in parentheses ONLY if it helps the user (e.g., "BNS Section 85 (formerly IPC 498A)").

4. FREE LEGAL AID: When a matter involves criminal charges, family law, labour disputes, or the user appears to have limited resources — always mention NALSA (15100 / nalsa.gov.in) and the nearest District Legal Services Authority (DLSA). Free legal aid is a constitutional right under Article 39A.

5. PERSONAL LAW COMPLEXITY: For divorce, inheritance, and maintenance — the applicable law depends on religion (Hindu/Muslim/Christian/Parsi/Special Marriage Act). Never assume Hindu law. State which law you are applying and why, based on facts provided.

6. AVOID FLATTENING COMPLEXITY: Do NOT oversimplify multi-step processes. If the answer genuinely requires multiple filings in different forums (e.g., consumer forum + police + civil court), say so clearly. A complete answer that is longer is better than a simple answer that omits critical steps.

7. MEDICAL NEGLIGENCE CAUTION: Consumer forums handle medical negligence but the standard is "gross negligence" (Jacob Mathew 2005 SC). Do not overstate the ease of winning. Always recommend evidence preservation (records, prescriptions, referral letters) as the first step.

8. LIMITATION PERIODS: Mention the limitation period for the claim type. If concern was flagged, lead with it — missed deadlines extinguish legal rights.

9. HALLUCINATION GUARD: Do not cite any case name, section number, or judgment you are not certain of. If a number seems uncertain, say "approximately" or omit it and tell the user to verify.

UNCERTAINTY RULE — if unsure of a fact, say so explicitly. Never guess section numbers or Act names. If unsure: "I'd recommend verifying this at legislative.gov.in or with a lawyer."

CITATION FORMAT — [1] [2] inline after the sentence; do not cite sources you did not use.

GOAL FOLLOW-UP RULE — if context mentions a user goal, check in naturally once at the end.

Authoritative links:
{fallback}

{SOURCES_SECTION_PROMPT}"""

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    messages.extend({"role": m["role"], "content": m["content"]} for m in history)
    messages.append({"role": "user", "content": query})
    return messages
