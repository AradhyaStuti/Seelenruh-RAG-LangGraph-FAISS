"""Few-shot examples injected into Umang's composer prompt to show the ideal response style."""

from __future__ import annotations

from dataclasses import dataclass

@dataclass
class FewShotExample:
    id: str
    category: str          # Legal category tag
    lang: str              # "en", "hi", "hi-roman", "de", "*" (any)
    user_query: str
    ideal_response: str


EXAMPLES: list[FewShotExample] = [

    # ── 1. Landlord lockout (Property / Tenant Rights) ──────────────────────
    FewShotExample(
        id="ex_landlord_lockout_en",
        category="Property",
        lang="en",
        user_query="My landlord changed the locks while I was at work and threw my belongings outside. I pay rent on time. What can I do?",
        ideal_response="""\
## Summary
Your landlord has illegally evicted you — this is called "forcible dispossession" and is not permitted under Indian law even if you owe rent.

## Issue Type
Tenant rights — unlawful eviction / criminal intimidation

## Applicable Law
- Transfer of Property Act, 1882 — a landlord cannot repossess without a court order
- Bharatiya Nyaya Sanhita (BNS), 2023, Section 351 — criminal intimidation
- Your state's Rent Control Act may provide additional protection

## Your Rights
1. You have the right to re-entry — your landlord cannot lock you out without a court decree.
2. You may claim compensation for damage to your belongings.

## What You Can Do
1. **Immediately:** Call the local police station and report forcible eviction (this is a cognizable offence).
2. **Get an FIR:** Police are generally required to register an FIR if a cognizable offence is disclosed — insist politely if they hesitate.
3. **File in Rent Court / Civil Court:** Apply for an injunction to restore possession.
4. **Collect evidence:** Photographs of the locked door, your belongings outside, and your rent receipts.

## Documents Needed
- Rent agreement / receipts
- Photos/video of the lockout
- Any written communication from the landlord

## When to Contact Police
Now — if the landlord refuses to give access, this may amount to criminal trespass and intimidation.

## When to Contact a Lawyer
As soon as possible for an urgent injunction application; free legal aid is available at your District Legal Services Authority (DLSA).

## Important Notes
- I cannot predict how a court will rule — outcomes depend on your specific agreement and local rent laws.
- Free legal aid: call 15100 (National Legal Services Authority helpline).""",
    ),

    # ── 2. Salary withheld (Employment) ─────────────────────────────────────
    FewShotExample(
        id="ex_salary_withheld_en",
        category="Employment",
        lang="en",
        user_query="My employer has not paid my salary for 3 months. I am a software developer in a private company. What should I do?",
        ideal_response="""\
## Summary
Withholding salary for 3 months is a violation of the Code on Wages, 2019. You have several remedies — starting with a free complaint to the Labour Commissioner.

## Issue Type
Employment — wage dispute (labour / civil matter, NOT criminal unless fraud is involved)

## Applicable Law
- Code on Wages, 2019 (consolidates Payment of Wages Act 1936, Minimum Wages Act 1948)
- Industrial Relations Code, 2020 — if you qualify as a "worker"
- Note: Software developers are usually "employees" under the Shops & Establishments Act of your state

## Your Rights
1. You are entitled to full salary within the payment cycle defined in your offer letter.
2. Delayed wages attract compensation under the Code on Wages.

## What You Can Do
**Step 1 — Preserve evidence now:**
- Save all salary slips, bank statements showing missing credits, offer letter, and any written communication about the delay.

**Step 2 — Send a written demand:**
- Email HR/management stating the exact unpaid months and requesting payment within 7 days. Keep a copy.

**Step 3 — File with the Labour Commissioner (free):**
- Go to your state's Labour Commissioner office and file a wage claim. This is free and typically faster than court.

**Step 4 — If company refuses or is unresponsive:**
- File a complaint with the Labour Court under the Industrial Relations Code.

**Step 5 — FIR only if criminal:**
- An FIR is NOT appropriate for unpaid salary alone. Police cannot recover civil wages.
- An FIR is appropriate ONLY if the employer committed fraud, forged documents, or misappropriated your PF.

## Documents Needed
- Offer letter / appointment letter
- Last 6 months' salary slips (if available)
- Bank statements showing salary credits (and the 3-month gap)
- Written demand email and employer's response (or silence)

## When to Contact Police
Only if fraud, cheating, or PF misappropriation is involved — not for simple unpaid salary.

## When to Contact a Lawyer
If the Labour Commissioner process stalls or the amount is significant; free legal aid is available at your DLSA (call 15100).

## Important Notes
- I cannot guarantee recovery — outcomes depend on your employment contract and company's financial situation.
- If the company has shut down or the employer has absconded, wages have priority under the Insolvency & Bankruptcy Code, 2016.""",
    ),

    # ── 3. Wrongful termination (Employment / Hinglish) ──────────────────────
    FewShotExample(
        id="ex_wrongful_termination_hi_roman",
        category="Employment",
        lang="hi-roman",
        user_query="Mujhe bina kisi reason ke notice period bhi nahi deke fire kar diya. Kya main kuch kar sakta hoon?",
        ideal_response="""\
## Summary
Bina valid reason aur notice period ke termination — yeh wrongful termination ho sakta hai. Aapke paas Industrial Relations Code 2020 ke tahat rights hain.

## Issue Type
Employment — wrongful termination / unfair dismissal

## Applicable Law
- Industrial Relations Code, 2020 — unfair labour practices aur termination procedures
- Shops & Establishments Act (aapke state ka) — notice period aur dues ke baare mein
- Code on Wages, 2019 — F&F (Full & Final settlement) ke liye

## Aapke Rights
1. Agar aap "workman" category mein aate hain — employer ko valid reason dena hoga (misconduct, redundancy, etc.).
2. Notice period ya notice pay (lieu of notice) dena zaroori hai jo aapke offer letter mein likha ho.
3. F&F settlement — last salary, pending leaves ka encashment, aur relieving letter aapka haq hai.

## Kya Karein
**Abhi:**
- Appointment letter, termination letter (agar diya gaya ho), aur last salary slip sambhal ke rakhein.
- HR ko email karein aur F&F + relieving letter ki maang karein.

**Agar company ignore kare:**
- Labour Commissioner ke office mein complaint file karein — yeh free hai.
- Industrial Disputes Act / Industrial Relations Code ke tahat Labour Court mein bhi ja sakte hain.

## Documents Chahiye
- Appointment / offer letter
- Termination letter (agar diya gaya)
- Salary slips aur bank statements
- HR ke saath koi bhi email / WhatsApp communication

## Police Kab Jaayein
Aam taur par police ki zaroorat nahi hai wrongful termination mein — yeh civil/labour matter hai. Police tabhi involved karein jab employer ne documents forge kiye hoon ya fraud kiya ho.

## Vakeel Kab Karein
Agar Labour Commissioner process mein problem aaye ya bahut bada amount involved ho — DLSA (District Legal Services Authority) se free legal aid le sakte hain. Helpline: 15100.

## Important
- Main guarantee nahi de sakta — outcome aapke employment contract aur category par depend karta hai.
- Agar aap manager/executive hain (workman nahi), toh rights thodi alag ho sakti hain.""",
    ),

    # ── 4. Police refusing to file FIR ──────────────────────────────────────
    FewShotExample(
        id="ex_fir_refused_en",
        category="Criminal",
        lang="en",
        user_query="The police are refusing to register my FIR about a theft. What are my options?",
        ideal_response="""\
## Summary
If a cognizable offence (like theft) is reported, police are legally required to register an FIR. Refusal to register is itself an offence under BNSS 2023.

## Issue Type
Criminal — FIR refusal

## Applicable Law
- Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023, Section 173 — mandatory FIR registration for cognizable offences
- Lalita Kumari v. Govt. of UP (2013) — Supreme Court ruling: FIR is mandatory if a cognizable offence is disclosed

## What You Can Do
1. **Written complaint to SHO:** Submit a written complaint to the Station House Officer (SHO) in person. Get a receipt/acknowledgment.
2. **SP / DCP complaint:** If SHO refuses, file a written complaint with the Superintendent of Police (SP) or DCP of your district.
3. **Magistrate application (Section 175 BNSS):** You can directly approach a Judicial Magistrate who can direct police to register an FIR.
4. **Online FIR / e-FIR:** Many states allow online FIR filing — check your state police website.
5. **State Human Rights Commission / Police Complaints Authority:** For systematic refusal.

## Documents Needed
- Written record of your complaint (keep a copy of everything you submitted)
- Any evidence of the theft (photos, CCTV, witnesses)
- Acknowledgment receipt from police (if any)

## When to Contact a Lawyer
If the Magistrate route is needed — a lawyer can draft the Section 175 BNSS application quickly. Free aid: 15100.

## Important Notes
- Refusal to register FIR for a cognizable offence is a dereliction of duty — you have multiple escalation options.
- I cannot predict how quickly the police will act.""",
    ),

    # ── 5. Cyber / UPI fraud ─────────────────────────────────────────────────
    FewShotExample(
        id="ex_upi_fraud_en",
        category="Cyber",
        lang="en",
        user_query="Someone called me pretending to be a bank and got me to share an OTP. Rs. 45,000 was debited from my account. What do I do?",
        ideal_response="""\
## Summary
You are a victim of vishing (voice phishing) — a cyber financial fraud. Act immediately; the first 24 hours are critical for recovery.

## Issue Type
Cyber crime — financial fraud / phishing

## Applicable Law
- Bharatiya Nyaya Sanhita (BNS), 2023, Section 318 — cheating
- Information Technology Act, 2000, Section 66C (identity theft), Section 66D (cheating by impersonation using computer)

## What You Can Do — IN ORDER

**1. Call 1930 NOW (Cyber Crime Helpline)**
This is the National Cyber Crime Helpline. Report immediately — they can freeze the fraudulent account before the money is transferred further.

**2. File complaint at cybercrime.gov.in**
Go to the National Cyber Crime Reporting Portal and file a complaint. Preserve your complaint number.

**3. Contact your bank immediately**
- Call your bank's fraud hotline and report the unauthorized debit.
- Ask them to mark the transaction for reversal / chargeback.
- Banks are required under RBI guidelines to respond within 10 working days.

**4. File an FIR**
Visit your nearest police station and file an FIR under BNS Section 318 and IT Act Section 66D. Bring your bank statement showing the debit.

## Documents Needed
- Bank statement / transaction SMS / screenshot
- Call record (date, time, caller number if available)
- Complaint number from cybercrime.gov.in

## Important Notes
- Do NOT share this incident publicly (social media) until you have filed the complaint.
- Recovery is NOT guaranteed — success depends on how quickly the fraudulent account is frozen.
- You do not need to pay anyone to "help recover" funds — that is a secondary scam.""",
    ),

    # ── 6. Consumer complaint (Consumer) ────────────────────────────────────
    FewShotExample(
        id="ex_consumer_complaint_en",
        category="Consumer",
        lang="en",
        user_query="I bought a refrigerator 8 months ago and it broke down. The company is refusing to honour the warranty. What are my options?",
        ideal_response="""\
## Summary
A manufacturer refusing to honour a valid warranty is a "deficiency in service" under the Consumer Protection Act, 2019. You can file a free complaint.

## Issue Type
Consumer — warranty / deficiency in service

## Applicable Law
- Consumer Protection Act, 2019
- Consumer Protection (E-Commerce) Rules, 2020 (if purchased online)

## What You Can Do
1. **Written complaint to company:** Send an email/letter to the brand's customer grievance cell giving them 15 days to respond.
2. **Online consumer forum (edaakhil.nic.in):** File your complaint online at the e-Daakhil portal (no physical visit needed). Claims up to ₹50 lakh go to District Consumer Commission.
3. **Physical filing:** Visit your District Consumer Disputes Redressal Commission (DCDRC) and file a complaint. The fee is minimal (₹100–₹500 for small claims).

## What You Can Claim
- Repair or replacement of the refrigerator
- Refund if repair is not possible
- Compensation for mental agony and cost of complaint

## Documents Needed
- Purchase invoice / bill
- Warranty card
- Written service requests / complaint numbers
- Company's refusal (email, SMS, or written)
- Photos of the defect

## When to Contact a Lawyer
Consumer cases are simple enough to file yourself. A lawyer is optional but may help for large claims (above ₹20 lakh).

## Important Notes
- Consumer courts are free for claims under ₹5 lakh (no lawyer required).
- I cannot predict the timeline — District Consumer Commissions aim for 90-day resolution but often take longer.""",
    ),

    # ── 7. Domestic violence ─────────────────────────────────────────────────
    FewShotExample(
        id="ex_domestic_violence_en",
        category="Family",
        lang="en",
        user_query="My husband hits me and threatens to throw me out. I have two children. I am scared to go to the police.",
        ideal_response="""\
## Summary
What you are experiencing is domestic violence — it is a crime under Indian law. You have the right to stay in your home and get police/court protection, even if it is your husband's property.

## Immediate Safety — Do This First
If you are in immediate danger, call **112** (Police Emergency) or **181** (Women's Helpline — free, 24×7).

## Issue Type
Family / Criminal — domestic violence

## Applicable Law
- Protection of Women from Domestic Violence Act (PWDVA), 2005 — physical, verbal, economic, sexual abuse by family member
- Bharatiya Nyaya Sanhita (BNS), 2023, Section 115 — voluntarily causing hurt

## Your Rights
1. **Right to residence** — You cannot be thrown out of the shared household even if it is your husband's.
2. **Protection Order** — A Magistrate can immediately prohibit your husband from contacting or harming you.
3. **Custody of children** — You can seek temporary custody.
4. **Maintenance** — You can claim financial support for yourself and children.

## What You Can Do
1. **Contact a Protection Officer:** Every district has a Protection Officer under PWDVA — they file the Domestic Incident Report (DIR) for free.
2. **Call iCall / Vandrevala helpline (9999 666 555)** — confidential counselling if you need to talk first.
3. **File an application in Magistrate's Court** — for Protection Order, Residence Order, and Maintenance. This can be done without a lawyer (the Protection Officer can assist).
4. **Go to the nearest police station** — domestic violence is cognizable; police must assist.

## Documents Needed (collect when safe)
- Photos of injuries
- Medical records if you have sought treatment
- Children's documents (birth certificates)
- Any written threats

## When to Contact a Lawyer
If your husband contests the case or you want to file for divorce/custody — free legal aid is available at DLSA (15100). Many NGOs also provide free representation.

## Important Notes
- Your safety comes first — there is no shame in seeking help.
- Protection orders can be obtained urgently (within 3 days in emergencies).
- I cannot predict legal outcomes, but the law gives you strong protections.""",
    ),

    # ── 8. Property dispute / possession ────────────────────────────────────
    FewShotExample(
        id="ex_property_dispute_en",
        category="Property",
        lang="en",
        user_query="My brother and I inherited a house from our father. He sold the house without my consent. Can he do this?",
        ideal_response="""\
## Summary
A co-owner (including a brother) generally cannot sell jointly owned inherited property without the consent of all co-owners. The sale may be voidable.

## Issue Type
Property / Civil — co-ownership dispute, alienation without consent

## Applicable Law
- Hindu Succession Act, 1956 (if Hindu family) — both siblings inherit equally; neither can sell without the other's consent
- Transfer of Property Act, 1882, Section 44 — a co-sharer can only transfer their own undivided share, not the whole property
- Specific Relief Act, 1963 — you may seek cancellation of the sale deed

## Your Rights
1. Your brother could only sell his own undivided share — not yours.
2. If he sold the entire property misrepresenting ownership, the sale can be challenged.
3. You can seek cancellation of the sale deed and damages.

## What You Can Do
1. **Get a copy of the sale deed:** Visit the Sub-Registrar's office and obtain a copy of the registered sale deed.
2. **Send a legal notice:** A lawyer can send a notice to your brother and the buyer putting them on notice of your ownership claim.
3. **File a civil suit:** For declaration of your share, injunction to stop construction/possession change, and cancellation of the sale deed.
4. **Partition suit:** If you want to formally divide the property, file a partition suit in civil court.

## Documents Needed
- Your father's death certificate
- Will (if any) or succession certificate
- Property documents (khata, patta, previous sale/gift deeds)
- Copy of the disputed sale deed

## When to Contact a Lawyer
Immediately — property matters have strict limitation periods (usually 12 years for possession; 3 years for cancellation of deed from discovery).

## Important Notes
- Property disputes can be complex and fact-specific. This is general guidance only.
- I cannot predict outcomes — courts look at the specific ownership records and documents.""",
    ),

    # ── 9. Government scheme / PF withdrawal ────────────────────────────────
    FewShotExample(
        id="ex_pf_withdrawal_en",
        category="Employment",
        lang="en",
        user_query="My PF withdrawal claim has been rejected by EPFO. What can I do?",
        ideal_response="""\
## Summary
EPFO rejections are common and most can be resolved by correcting KYC details or providing additional documents. You also have a formal grievance mechanism.

## Issue Type
Employment / Administrative — PF withdrawal dispute

## Applicable Law
- Employees' Provident Funds & Miscellaneous Provisions Act, 1952
- EPF Scheme, 1952 — withdrawal eligibility rules

## Common Rejection Reasons (check your rejection notice)
1. KYC mismatch (name, DOB, Aadhaar/PAN mismatch)
2. Missing bank account verification
3. Service period requirements not met for the type of withdrawal
4. Joint declaration not submitted (if employer verification needed)

## What You Can Do
1. **Check rejection reason:** Log in to the EPFO Member Portal (unifiedportal-mem.epfindia.gov.in) and check the rejection reason.
2. **Correct KYC:** Update Aadhaar/PAN/bank details on the portal and re-submit.
3. **Employer assistance:** For joint declaration issues, contact your HR — they need to approve the claim on the employer portal.
4. **File a grievance:** Use the EPFiGMS portal (epfigms.gov.in) — EPFO must respond within 30 days.
5. **Escalate to Regional PF Commissioner** if grievance is not resolved.
6. **Employees' Provident Fund Appellate Tribunal:** For formal appeals.

## Documents Needed
- UAN (Universal Account Number)
- Aadhaar linked and verified with UAN
- Bank account linked and verified
- Rejection notice from EPFO

## When to Contact a Lawyer
Usually not needed for PF issues — the grievance and appeal process is sufficient. A lawyer may help if the Appellate Tribunal route becomes necessary.

## Important Notes
- EPFO grievances typically resolve in 15–30 days if documentation is complete.
- Free guidance: EPFO toll-free 1800-118-005 (Mon–Sat, 9am–6pm).""",
    ),

    # ── 10. German-speaking tenant in India ─────────────────────────────────
    FewShotExample(
        id="ex_german_tenant_de",
        category="Property",
        lang="de",
        user_query="Mein Vermieter möchte die Miete um 50% erhöhen. Ist das legal in Indien?",
        ideal_response="""\
## Zusammenfassung
Eine Mieterhöhung von 50% auf einmal ist in den meisten indischen Bundesstaaten durch das jeweilige Mietrecht (Rent Control Act) begrenzt. Ich beantworte diese Frage nach **indischem Recht**.

## Art des Problems
Mietrecht — unzulässige Mieterhöhung (Property / Tenant Rights)

## Anwendbares Recht (Indisches Recht)
- **Rent Control Act Ihres Bundesstaates** (z. B. Delhi Rent Control Act, Maharashtra Rent Control Act) — begrenzt Mieterhöhungen in der Regel auf bestimmte Prozentsätze pro Jahr
- **Transfer of Property Act, 1882** — regelt allgemeine Mieterrechte
- **Model Tenancy Act, 2021** — neueres Rahmengesetz (gilt nur, wenn Ihr Bundesstaat es übernommen hat)

## Ihre Rechte (in Indien)
1. Der Vermieter kann die Miete nicht willkürlich erhöhen — die Erhöhung muss im Mietvertrag vereinbart oder gesetzlich zulässig sein.
2. Eine 50%-Erhöhung in einem Schritt ist in den meisten Bundesstaaten unzulässig.
3. Sie können eine unverhältnismäßige Erhöhung vor dem Rent Controller / Rent Tribunal anfechten.

## Was Sie tun können
1. **Mietvertrag prüfen:** Steht eine Klausel zur Mieterhöhung im Vertrag?
2. **Schriftliche Ablehnung:** Antworten Sie schriftlich und bestreiten Sie die Rechtmäßigkeit der Erhöhung.
3. **Rent Controller (Mietgericht):** Stellen Sie einen Antrag beim zuständigen Rent Controller Ihres Bezirks.

## Benötigte Dokumente
- Mietvertrag (Rent Agreement)
- Schriftliche Mitteilung des Vermieters über die Erhöhung
- Zahlungsnachweise der bisherigen Miete

## Wichtige Hinweise
- Ich kann keine Garantie für das Ergebnis geben — dies hängt von Ihrem Bundesstaat und Ihrem Vertrag ab.
- Kostenlose Rechtsberatung: Indischer Rechtshilfedienst NALSA — Telefon 15100.""",
    ),
]

def get_few_shot_examples(
    category: str = "*",
    lang: str = "*",
    max_examples: int = 2,
) -> str:
    """Return formatted few-shot examples for the given category/language, or '' if none match."""
    # Priority: category + lang match → category match → lang match → any
    def score(ex: FewShotExample) -> int:
        cat_match = category == "*" or ex.category.lower() == category.lower() or ex.lang == "*"
        lang_match = lang == "*" or ex.lang == lang or ex.lang == "*"
        if cat_match and lang_match:
            return 2
        if cat_match:
            return 1
        if lang_match:
            return 0
        return -1

    scored = sorted(EXAMPLES, key=score, reverse=True)
    selected = [ex for ex in scored if score(ex) >= 0][:max_examples]

    if not selected:
        return ""

    parts = ["### Examples of ideal responses (follow this style):\n"]
    for i, ex in enumerate(selected, 1):
        parts.append(f"**Example {i}**")
        parts.append(f"User: {ex.user_query}")
        parts.append(f"Umang:\n{ex.ideal_response}")
        parts.append("")  # blank line between examples

    return "\n".join(parts)
