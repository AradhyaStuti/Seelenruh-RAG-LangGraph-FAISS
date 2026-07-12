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
Analyse the user's query deeply and output ONLY a valid JSON object — no markdown, no explanation.

{
  "category": "DomesticViolence|Divorce|Maintenance|FIR|Consumer|RTI|Tenant|Employment|Property|Cybercrime|POSH|ChequeBounce|Bail|POCSO|Constitutional|Criminal|General",
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
  "follow_up": null
}

Rules:
- category: single MOST SPECIFIC match for the primary legal issue
- urgency: "immediate" = danger/crisis right now; "recent" = happened in last few days/weeks;
           "informational" = asking about law / not in active crisis
- multi_domain: true if the situation spans multiple legal areas (e.g. domestic violence + child custody + maintenance)
- secondary_categories: list of up to 2 additional domains if multi_domain=true (e.g. ["Maintenance", "Divorce"])
- known_facts: list of specific facts explicitly mentioned by user (max 5 short strings)
  Examples: "cheque amount ₹50,000", "bounced 2 weeks ago", "in Maharashtra", "private company employer", "married under HMA"
- missing_facts: list of facts MISSING that would materially change the legal guidance (max 3)
  Examples for Tenant: ["state/city where property is located", "written rent agreement exists or not"]
  Examples for Divorce: ["personal law / religion", "whether contested or mutual consent"]
  Examples for Employment: ["government or private employer", "designation - workman or managerial"]
  Examples for ChequeBounce: ["days since bank return memo received", "legal notice sent yet"]
  Leave empty [] if query is purely informational or sufficient facts are present.
- limitation_concern: true if there is a time-critical legal deadline the user may be approaching or have missed
  (examples: ChequeBounce notice window, consumer court 2 years, POSH 3 months, default bail 60/90 days)
- needs_document: true ONLY if user explicitly asks to write/draft/generate a document
- doc_type (only when needs_document=true): RTI | ConsumerComplaint | PoliceComplaint | LegalNotice | Affidavit | null
- needs_evidence_guide: true if user appears to be gathering evidence or preparing to file — they need specific guidance
- needs_cost_estimate: true if user asks about fees, costs, or whether they can afford legal action
- state_hint: exact Indian state name if clearly mentioned, else null
- personal_law: for divorce/maintenance/inheritance — Hindu | Muslim | Christian | Parsi | Special | null (null if unclear)
- follow_up: ONE specific question whose answer would most change the legal guidance; null if sufficient info present
  ONLY set follow_up if missing_facts is non-empty. Make it a natural conversation question, not a form field.

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
            "Muslim Women (Protection of Rights on Divorce) Act, 1986 — for Muslim divorces",
            "PWDVA Section 20 — monetary relief including maintenance in DV cases",
            "Maintenance and Welfare of Parents and Senior Citizens Act, 2007 — parents/senior citizens can claim from children",
        ],
        "typical_remedies": [
            "Interim maintenance order pending hearing (typically within 60 days)",
            "Permanent maintenance monthly order",
            "Recovery of arrears (with potential imprisonment for wilful default)",
            "Attachment of salary or property for enforcement",
        ],
        "evidence_checklist": [
            "Marriage certificate",
            "Income evidence for both parties: salary slips, ITR, bank statements, business records",
            "Own expense documents: rent, utility bills, children's school fees, medical bills",
            "Children's birth certificates, school fee receipts",
            "Proof the other party has income / assets (if they claim no income)",
        ],
        "procedure_steps": [
            "File under BNSS Section 144 before Family Magistrate — fastest route, no divorce needed",
            "In divorce proceedings: simultaneously file HMA Section 24 application in Family Court",
            "After order: if payments are missed, file execution petition immediately",
            "Court can attach salary, bank account, or property to enforce payment",
        ],
        "limitation_period": "BNSS 144: no strict limitation. Courts may limit retrospective arrears — apply as soon as separation occurs.",
        "authorities": [
            "Family Magistrate Court (for BNSS 144)", "Family Court (for HMA 24/25)",
            "District Court where no Family Court exists",
        ],
        "typical_timeline": "Interim order: 1–3 months. Final order: 6 months–2 years.",
        "typical_costs": "Filing: ₹200–₹500. Lawyer: ₹10,000–₹50,000. NALSA legal aid for eligible persons.",
        "common_mistakes": [
            "Waiting too long — courts may limit retrospective arrears",
            "Not disclosing all of other party's income sources — request bank statements through court",
            "Not enforcing when payments lapse — file execution petition promptly",
            "Settling too low under financial pressure — revision requires significant change in circumstances",
        ],
        "free_legal_aid": "NALSA (nalsa.gov.in | 15100). State DLSA in every district. Women's helplines provide referrals.",
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
            "Industrial Disputes Act, 1947 (ID Act) — wrongful termination, retrenchment (applies to 'workmen' — non-supervisory)",
            "Shops and Establishments Acts — state-specific, applies to most commercial employees",
            "Payment of Gratuity Act, 1972 — gratuity = 15 days salary × years of service ÷ 26, after 5 years",
            "Payment of Wages Act, 1936 — timely wage payment",
            "EPF & Misc. Provisions Act, 1952 — provident fund rights",
            "POSH Act, 2013 — workplace sexual harassment",
            "Contract Labour (Regulation and Abolition) Act, 1970 — for contract/outsourced workers",
        ],
        "typical_remedies": [
            "Reinstatement (wrongful termination for 'workmen')",
            "Back wages from termination date",
            "Retrenchment compensation (1 month per year of service)",
            "Recovery of withheld salary, PF, gratuity, bonus",
            "Compensation for POSH violation",
        ],
        "evidence_checklist": [
            "Offer letter and appointment letter",
            "All employment contracts, increments, and promotion letters",
            "Last 12 months salary slips",
            "Bank statements showing salary credits",
            "Performance reviews and appraisals",
            "Termination letter (request one — employer must give it)",
            "All HR communications about the dispute (emails, letters)",
            "PF UAN number and EPF account statement",
        ],
        "procedure_steps": [
            "Send grievance in writing to HR/management — establish paper trail",
            "Approach Labour Commissioner / ALC for conciliation (free, fast)",
            "File complaint before Industrial Tribunal / Labour Court (for 'workmen')",
            "For PF: file with EPFO regional office or EPFO Grievance Portal (epfigms.gov.in)",
            "For gratuity: application to employer first, then Payment of Gratuity Authority",
            "For POSH: file with ICC within 3 months of last incident (critical deadline)",
        ],
        "limitation_period": "ID Act retrenchment: file within 3 years. POSH: 3 months from last incident (extendable to 6 months). Gratuity: 1 year from due date. PF: varies.",
        "authorities": [
            "Labour Commissioner / ALC (state level)", "Industrial Tribunal / Labour Court",
            "EPFO Regional Office / EPFO Grievance Portal", "Internal Complaints Committee (ICC) for POSH",
            "She-Box portal (shebox.wcd.gov.in) — government sector POSH",
        ],
        "typical_timeline": "Labour conciliation: 30–45 days. Labour Court: 1–3 years. POSH ICC: must complete in 90 days.",
        "typical_costs": "Conciliation: Free. Labour Court filing: ₹200–₹500. Lawyer: ₹15,000–₹75,000. NALSA for eligible.",
        "common_mistakes": [
            "Signing Full and Final Settlement without understanding what rights you waive",
            "Missing POSH 3-month deadline — it's absolute (extendable only for good cause to 6 months)",
            "Not getting a written termination letter — fight for one",
            "Confusing 'workman' (covered by ID Act) vs 'supervisor/manager' (different rights)",
            "Not following internal grievance mechanism first — courts and tribunals expect it",
        ],
        "free_legal_aid": "NALSA and state DLSA. Labour Commissioner conciliation is free.",
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
    "Maintenance":       ["maintenance", "alimony", "CrPC 125", "BNSS 144", "HMA 24", "Section 125", "monthly payment"],
    "FIR":               ["FIR", "first information report", "cognizable", "non-cognizable", "BNSS 173", "zero FIR", "police complaint"],
    "Consumer":          ["Consumer Protection", "COPRA", "deficiency", "unfair trade practice", "warranty", "consumer right", "refund"],
    "RTI":               ["Right to Information", "RTI Act", "public authority", "exemption", "Section 8", "CPIO", "information access"],
    "Tenant":            ["tenant", "landlord", "rent", "eviction", "Transfer of Property", "lease", "rent control", "security deposit"],
    "Employment":        ["employment", "labour", "termination", "retrenchment", "Industrial Disputes", "workman", "POSH", "gratuity", "PF"],
    "ChequeBounce":      ["cheque bounce", "NI Act", "Section 138", "dishonour", "criminal liability", "negotiable instrument"],
    "Bail":              ["bail", "bailable", "non-bailable", "BNSS 480", "BNSS 482", "anticipatory bail", "default bail", "custody"],
    "POCSO":             ["POCSO", "child protection", "sexual assault minor", "JJ Act", "child abuse"],
    "Constitutional":    ["Article", "fundamental rights", "directive principles", "writ", "constitutional remedy", "habeas corpus"],
    "Cybercrime":        ["IT Act", "Section 66", "cyber fraud", "data protection", "DPDP Act", "online fraud", "identity theft"],
    "Property":          ["Hindu Succession", "property rights", "inheritance", "will", "gift deed", "partition", "encumbrance"],
    "POSH":              ["POSH", "sexual harassment workplace", "ICC", "internal complaints committee"],
    "Maintenance":       ["maintenance", "alimony", "Section 125", "BNSS 144", "HMA 24", "alimony"],
}

_PROCEDURE_KW: dict[str, list[str]] = {
    "DomesticViolence":  ["protection officer", "magistrate", "shelter home", "One Stop Centre", "complaint DV", "domestic incident report"],
    "Divorce":           ["family court", "mediation", "mutual consent", "contested divorce", "cooling period", "petition"],
    "FIR":               ["file FIR", "police station", "Section 154", "SP", "Magistrate 156(3)", "BNSS 173", "zero FIR"],
    "Consumer":          ["District Commission", "State Commission", "NCDRC", "complaint filing", "forum procedure", "edaakhil"],
    "RTI":               ["RTI application", "30 days", "first appeal", "second appeal", "CIC", "SIC", "CPIO"],
    "Tenant":            ["rent controller", "eviction notice", "quit notice", "civil court", "15 day notice", "rent tribunal"],
    "Employment":        ["labour court", "grievance", "labour commissioner", "industrial tribunal", "conciliation", "EPFO"],
    "ChequeBounce":      ["legal notice", "30 days", "magistrate complaint", "criminal complaint NI Act", "return memo", "RPAD"],
    "Bail":              ["bail application", "sessions court", "bail bond", "personal bond", "BNSS 482 application", "default bail"],
    "POCSO":             ["special court", "child welfare committee", "SJPU", "mandatory reporting", "childline"],
    "Property":          ["partition suit", "injunction", "civil court", "RERA", "encumbrance certificate", "mutation"],
    "POSH":              ["ICC complaint", "LCC", "shebox", "90 days inquiry", "labour commissioner"],
    "Cybercrime":        ["cybercrime.gov.in", "1930", "FIR cybercrime", "complaint portal", "CERT-In"],
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
    cat       = case_analysis.get("category", "General")
    urgency   = case_analysis.get("urgency", "informational")
    follow_up = case_analysis.get("follow_up")
    pers_law  = case_analysis.get("personal_law")
    needs_r   = case_analysis.get("needs_rights", True)
    needs_p   = case_analysis.get("needs_procedure", True)
    needs_doc = case_analysis.get("needs_document", False)
    doc_type  = case_analysis.get("doc_type")
    multi_dom = case_analysis.get("multi_domain", False)
    lim_warn  = case_analysis.get("limitation_concern", False)

    focus = [x for x, flag in [
        ("legal rights / protections", needs_r),
        ("procedure / what to do",     needs_p),
        (f"draft {doc_type or 'document'}", needs_doc),
    ] if flag]

    analysis_lines = [
        f"Category: {cat}" + (" (multi-domain)" if multi_dom else ""),
        f"Urgency: {urgency}" + (" — ADDRESS SAFETY FIRST" if urgency == "immediate" else ""),
    ]
    if jurisdiction:
        analysis_lines.append(f"Jurisdiction: {jurisdiction} (note state-specific variations)")
    if pers_law:
        analysis_lines.append(f"Personal law: {pers_law}")
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
