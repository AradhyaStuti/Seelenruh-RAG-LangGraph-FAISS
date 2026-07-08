"""Retrieval corpus. Each chunk has a domain and language hint, gets embedded
once at startup, and is matched against user queries via FAISS + cross-encoder
rerank. Core chunks below are appended with EXPANSION_CHUNKS for ~800 total."""

from rag.knowledge_expansion import EXPANSION_CHUNKS

CORE_CHUNKS = [
    # ═════════════════════════════════════════════════════════════════════
    # MENTAL HEALTH (English)
    # ═════════════════════════════════════════════════════════════════════
    {
        "id": "mh-1", "domain": "Mental Health", "lang": "en",
        "topic": "anxiety — what it is and when to seek help",
        "source": "DSM-5 / NIMHANS guidance · iCall, Vandrevala, Tele-MANAS helplines",
        "lastVerifiedOn": "2025-10-15",
        "text": """Anxiety is the body's natural response to stress, but it becomes a clinical concern when it persists and interferes with daily life. Common signs of an anxiety disorder include persistent racing thoughts, restlessness, muscle tension, difficulty concentrating, sleep disturbance, rapid heartbeat, and avoidance behaviour.
Types worth knowing: Generalised Anxiety Disorder (chronic worry across domains), Social Anxiety (fear of judgement), specific phobias, and Panic Disorder (sudden surges).
Seek professional help when anxiety lasts more than two weeks, affects work or relationships, includes recurrent panic attacks, or comes with thoughts of self-harm. In India: iCall +91 9152987821 (Mon-Sat 8am-10pm), Vandrevala 1860-2662-345 (24×7), Tele-MANAS 14416 (24×7, free). For an in-person therapist see "finding a therapist in India".""",
    },
    {
        "id": "mh-20", "domain": "Mental Health", "lang": "en",
        "topic": "anxiety coping techniques — grounding and breathing",
        "source": "CBT / DBT-derived skills · NHS UK and NIMHANS self-help guides",
        "lastVerifiedOn": "2025-10-15",
        "text": """Quick techniques to calm down when anxiety spikes:
- Box breathing (4-4-4-4): inhale 4 seconds, hold 4, exhale 4, hold 4. Repeat 4 cycles. Slows the sympathetic nervous system within ~90 seconds.
- 5-4-3-2-1 grounding: name 5 things you can see, 4 you can touch, 3 you can hear, 2 you can smell, 1 you can taste. Pulls attention out of catastrophic loops.
- Cognitive reframing: write down the anxious thought ("I'll fail the interview"). Beside it write "What's the evidence FOR this?" and "What's the evidence AGAINST?". Then a balanced alternative ("I've prepared; outcomes are uncertain but not catastrophic").
- 10-minute brisk walk: short bursts of movement are as effective as ~50% of a low-dose SSRI for situational anxiety, per Harvard 2023 review.
- Reduce caffeine and alcohol; both amplify the physiological signature of anxiety.
These are first-aid skills, not substitutes for therapy. If anxiety recurs daily for more than two weeks, see "anxiety — what it is and when to seek help".""",
    },
    {
        "id": "mh-2", "domain": "Mental Health", "lang": "en",
        "topic": "depression",
        "source": "DSM-5 · NIMHANS / iCall guidance",
        "lastVerifiedOn": "2025-10-15",
        "text": """Depression is more than feeling sad — persistent low mood for two weeks or more with loss of interest, fatigue, sleep/appetite changes, worthlessness, and concentration problems.
First steps: (1) basic daily structure, (2) connect with one trusted person daily, (3) 10-20 minutes gentle activity, (4) limit alcohol and late screens, (5) track mood daily.
Therapy: CBT, IPT, behavioural activation. Medication via psychiatrist may be needed for moderate-to-severe. NIMHANS Bengaluru offers free/subsidised consultations.
Self-harm or suicide thoughts → iCall +91 9152987821, Vandrevala 1860-2662-345, AASRA +91 9820466726 immediately.""",
    },
    {
        "id": "mh-3", "domain": "Mental Health", "lang": "en",
        "topic": "sleep hygiene",
        "source": "NHS UK · AASM CBT-I clinical guidelines",
        "lastVerifiedOn": "2025-10-15",
        "text": """Poor sleep amplifies anxiety and low mood. Research-supported practices:
- Fixed wake-up time every day, even weekends.
- No screens 30-60 minutes before bed; blue light suppresses melatonin.
- Bedroom cool, dark, quiet.
- No caffeine after 2 PM.
- Don't lie in bed awake more than 20 minutes — get up, do something boring with dim light, return when sleepy.
- "Worry dump" notebook beside the bed.
If insomnia persists more than three weeks, CBT-I (Cognitive Behavioural Therapy for Insomnia) is first-line, more effective long-term than sleeping pills.""",
    },
    {
        "id": "mh-4", "domain": "Mental Health", "lang": "en",
        "topic": "finding a therapist in India",
        "source": "NIMHANS Bengaluru · The Live Love Laugh Foundation directory",
        "lastVerifiedOn": "2025-10-15",
        "text": """Ways to find a qualified mental-health professional:
- NIMHANS Bengaluru (nimhans.ac.in) — government, affordable, long waitlist.
- TISS iCall (icallhelpline.org) — free email and phone counselling.
- Vandrevala Foundation — free 24x7 helpline 1860-2662-345, online chat.
- Manastha, YourDOST, Amaha, BetterLYF — paid platforms with verified therapists.
- District Mental Health Programme (DMHP) — every district.
Credentials: RCI-registered clinical psychologist (MPhil Clinical Psychology) for therapy; MD Psychiatry doctor for medication. First sessions ₹500-₹2500.""",
    },
    {
        "id": "mh-5", "domain": "Mental Health", "lang": "en",
        "topic": "stress and burnout",
        "source": "WHO ICD-11 occupational burnout definition · APA",
        "lastVerifiedOn": "2025-10-15",
        "text": """Burnout = exhaustion + cynicism + reduced productivity, usually from prolonged work or caregiving. Distinguish from depression: burnout lifts when the stressor lifts, depression does not.
Recovery: (1) take real time off, (2) reduce decision-fatigue, (3) one boundary at a time (e.g. no Slack after 8 PM), (4) restorative activities (walks, music, hobbies), (5) talk to your manager about workload.
If burnout persists > a month or comes with insomnia/panic/loss of interest, treat as a mental-health issue and consult a therapist.""",
    },
    {
        "id": "mh-6", "domain": "Mental Health", "lang": "en",
        "topic": "relationship conflict",
        "source": "Gottman Institute · NIMHANS couples-counselling guidance",
        "lastVerifiedOn": "2025-10-15",
        "text": """Healthy conflict resolution:
- "I" statements ("I felt hurt when…") not "you always" attacks.
- Right time: not when hungry, tired, or in public.
- One issue at a time. No old grievances.
- Repair attempts: humour, a touch, a pause to reset (Gottman research).
- Distinguish solvable problems (logistics) from perpetual problems (values, personality).
Couples therapy: EFT (Emotionally Focused), Gottman Method.""",
    },
    {
        "id": "mh-7", "domain": "Mental Health", "lang": "en",
        "topic": "grief and loss",
        "source": "Kübler-Ross stages · NIMHANS bereavement guidance",
        "lastVerifiedOn": "2025-10-15",
        "text": """Grief is not linear; "5 stages" come in waves. No fixed timeline — intense grief softens over 6-18 months but the relationship to the loss stays.
Helpful: (1) name the loss aloud or in writing, (2) keep a small daily ritual, (3) accept help with practical tasks, (4) avoid major decisions for the first 6 months if possible, (5) anniversaries trigger waves — plan softer days.
Complicated grief lasting > 1 year with major impairment benefits from CGT (Complicated Grief Treatment).""",
    },
    {
        "id": "mh-8", "domain": "Mental Health", "lang": "en",
        "topic": "self-care basics",
        "source": "WHO mental-health self-help resources",
        "lastVerifiedOn": "2025-10-15",
        "text": """Sustainable self-care, research-supported:
- Sleep 7-9 hours.
- Move daily, even briefly.
- One real social contact per day.
- Morning sunlight for 10 minutes — anchors circadian rhythm.
- Regular meals, water, less ultra-processed food.
- One unstructured pleasure per day (hobby, music, reading — not scrolling).
- Say no to one thing you don't want to do.
80/20 rule: doing 80% of these 80% of the time is enough.""",
    },
    {
        "id": "mh-9", "domain": "Mental Health", "lang": "en",
        "topic": "panic attack first aid",
        "source": "ADAA · NHS panic-attack first-response guide",
        "lastVerifiedOn": "2025-10-15",
        "text": """A panic attack feels like a heart attack — rapid heartbeat, chest tightness, dizziness, shortness of breath, fear of dying. Not dangerous, peaks within 10 minutes.
In the moment: (1) name it — "this is a panic attack, it will pass". (2) Slow exhale (4 in, 6 out) for 2 minutes. (3) 5-4-3-2-1 senses grounding. (4) Cold water on face or ice cube activates dive reflex, slows heart rate. (5) Don't fight it — let the wave rise and fall.
Recurring panic = Panic Disorder. CBT and sometimes medication help; see a psychiatrist.""",
    },
    {
        "id": "mh-10", "domain": "Mental Health", "lang": "en",
        "topic": "student mental health",
        "source": "UGC Mental Health guidelines · YourDOST campus surveys",
        "lastVerifiedOn": "2025-10-15",
        "text": """Common student issues: exam anxiety, peer comparison, sleep loss, homesickness, fear of failure, family pressure about career.
What helps: (1) 25-50 minute focused study blocks (Pomodoro), (2) sleep is part of studying — memory consolidates during sleep, (3) move ≥ 20 min daily, (4) one trusted friend, (5) reduce social media.
College counselling cells — confidential and free. Helplines: Tele-MANAS 14416, iCall 9152987821, Vandrevala 1860-2662-345. Exam pressure feeling life-threatening — talk to someone TODAY.""",
    },
    {
        "id": "mh-11", "domain": "Mental Health", "lang": "en",
        "topic": "social anxiety",
        "source": "DSM-5 social anxiety disorder · CBT clinical protocols",
        "lastVerifiedOn": "2025-10-15",
        "text": """Social anxiety = intense fear of being judged, with physical symptoms (blushing, sweating, racing heart, mind going blank).
Coping: (1) gradual exposure — start low-stakes (cashier, neighbour), build up. (2) focus outward, not inward — pay attention to the other person. (3) accept some discomfort as normal. (4) avoid alcohol as a crutch — worsens anxiety over time.
CBT with exposure has the strongest evidence. SSRIs help moderate-to-severe cases (consult a psychiatrist).""",
    },
    {
        "id": "mh-19", "domain": "Mental Health", "lang": "en",
        "topic": "loneliness in seniors and adults",
        "source": "HelpAge India research · UK loneliness commission findings",
        "lastVerifiedOn": "2025-10-15",
        "text": """Chronic loneliness is now classified as a major public-health risk — equivalent to smoking 15 cigarettes a day for mortality. Especially affects seniors after retirement / loss of spouse, students moving cities, new parents, remote workers.
What helps (evidence-based): (1) one weekly recurring social ritual (call a sibling, neighbourhood walk, faith group). (2) Join a structured activity, not just a chat group — book club, gardening, volunteering. (3) Reach out FIRST — most people are also lonely and grateful. (4) Reduce passive social media (scrolling deepens loneliness); use it actively (message friends). (5) Get a pet if circumstances allow.
For seniors specifically: HelpAge India runs Daughters of HelpAge groups, free senior care helpline 1800-180-1253, Elderline 14567. Khushiyaan (khushiyaan.in) and Anwesha senior centres for community.
For young adults: Meetup, Internations, local club-house apps. Studies on "weak ties" (acquaintances) show they significantly raise wellbeing alongside close friends.""",
    },
    {
        "id": "mh-14", "domain": "Mental Health", "lang": "en",
        "topic": "OCD basics",
        "source": "DSM-5 OCD criteria · IOCDF.org guidance",
        "lastVerifiedOn": "2025-10-15",
        "text": """Obsessive-Compulsive Disorder = unwanted intrusive thoughts (obsessions) + repetitive behaviours or mental acts to neutralise the anxiety (compulsions). Common themes: contamination, harm, symmetry, religious / sexual taboo.
Key point: OCD is treatable. ERP (Exposure and Response Prevention), a specific form of CBT, has the strongest evidence — typically 60-80% see significant improvement. SSRIs at higher doses (than for depression) also work.
Self-help: do NOT engage with reassurance-seeking (asking the same question repeatedly). Practise sitting with uncertainty. Reduce caffeine and alcohol.
India: NIMHANS OCD clinic, IBHAS Delhi. International Foundation for OCD (iocdf.org) has resources.""",
    },
    {
        "id": "mh-15", "domain": "Mental Health", "lang": "en",
        "topic": "postpartum / women's mental health",
        "source": "ICMR postpartum depression guidelines · WHO maternal MH",
        "lastVerifiedOn": "2025-10-15",
        "text": """Postpartum blues affect 50-80% of new mothers (mood swings, weepiness) — usually resolves in 2 weeks. Postpartum depression affects 10-15% — persistent low mood, anhedonia, anxiety, sleep + appetite issues lasting > 2 weeks, sometimes intrusive thoughts about the baby. Postpartum psychosis is rarer (~0.1-0.2%) but a psychiatric emergency.
What helps: practical support (sleep in shifts, help with feeding), connect with other new parents, screen with the EPDS (Edinburgh Postnatal Depression Scale).
Get help: gynaecologist, postpartum support groups, NIMHANS Perinatal Psychiatry clinic, Mpower (mpowerminds.com).
Premenstrual Dysphoric Disorder (PMDD) — severe mood symptoms 1-2 weeks before periods, distinct from PMS. SSRIs + lifestyle help. Track symptoms for 2 cycles for diagnosis.""",
    },
    {
        "id": "mh-16", "domain": "Mental Health", "lang": "en",
        "topic": "substance use disorder",
        "source": "AIIMS NDDTC · Alcoholics Anonymous India · WHO ASSIST",
        "lastVerifiedOn": "2025-10-15",
        "text": """Substance use becomes a disorder when it causes harm and you can't stop despite consequences. Includes alcohol, tobacco, cannabis, opioids, prescription drug misuse.
Steps: (1) recognise it's a medical condition, not a moral failure. (2) Don't quit alcohol or benzodiazepines abruptly — withdrawal can be dangerous; do it under medical supervision. (3) Treatment combines medication (e.g. naltrexone, acamprosate, buprenorphine) + therapy (CBT, motivational interviewing) + peer support (AA, NA, SMART Recovery).
India: NIMHANS Centre for Addiction Medicine, AIIMS National Drug Dependence Treatment Centre. Free helpline: 1800-11-0031 (NDDTC). Asha Family Foundation, T.T. Ranganathan Clinical Research Foundation (Chennai).""",
    },

    # MENTAL HEALTH — German
    {
        "id": "mh-12", "domain": "Mental Health", "lang": "de",
        "topic": "Angst-Grundlagen (German)",
        "source": "Deutsche Angst-Hilfe e.V. · ICD-11",
        "lastVerifiedOn": "2025-10-15",
        "text": """Angst ist die natürliche Reaktion des Körpers auf Stress, wird aber zum Problem, wenn sie anhält und den Alltag beeinträchtigt. Häufige Anzeichen: Gedankenkreisen, Unruhe, Muskelverspannung, Konzentrationsprobleme, Schlafstörungen, Herzrasen.
Bewährte Strategien: (1) Box-Atmung (4-4-4-4), (2) 5-4-3-2-1-Sinnesübung zur Erdung, (3) kognitive Umstrukturierung — den ängstlichen Gedanken aufschreiben und fragen "was spricht dafür / dagegen?", (4) sanfte Bewegung wie ein 10-minütiger Spaziergang, (5) Koffein reduzieren.
Professionelle Hilfe suchen, wenn Angst länger als zwei Wochen anhält. In Deutschland: Telefonseelsorge 0800 111 0 111 (24/7), Nummer gegen Kummer 116 111. In Indien: iCall +91 9152987821.""",
    },
    {
        "id": "mh-13", "domain": "Mental Health", "lang": "de",
        "topic": "Schlafhygiene (German)",
        "source": "Deutsche Gesellschaft für Schlafforschung (DGSM)",
        "lastVerifiedOn": "2025-10-15",
        "text": """Schlechter Schlaf verstärkt Angst und gedrückte Stimmung. Forschungsgestützte Praktiken:
- Feste Aufwachzeit jeden Tag, auch am Wochenende.
- Keine Bildschirme 30-60 Minuten vor dem Schlafengehen.
- Schlafzimmer kühl, dunkel, ruhig.
- Kein Koffein nach 14 Uhr.
- Nicht länger als 20 Minuten wach im Bett liegen — aufstehen, etwas Langweiliges bei gedämpftem Licht tun, zurückkehren wenn müde.
- "Sorgen-Notizbuch" neben dem Bett.
Bei mehr als dreiwöchiger Schlaflosigkeit ist KVT-I (Kognitive Verhaltenstherapie für Insomnie) die First-Line-Therapie.""",
    },
    {
        "id": "mh-17", "domain": "Mental Health", "lang": "de",
        "topic": "Burnout-Erkennung (German)",
        "source": "WHO ICD-11 Burn-out (QD85) · Techniker Krankenkasse",
        "lastVerifiedOn": "2025-10-15",
        "text": """Burnout ist Erschöpfung + Zynismus + verminderte Leistungsfähigkeit, meist durch andauernden Arbeits- oder Pflegestress. Unterscheidung zur Depression: Burnout lässt nach, wenn der Stressor wegfällt; Depression nicht.
Erholung: (1) echte Auszeit nehmen, (2) Entscheidungsmüdigkeit reduzieren (Mahlzeiten planen, Garderobe vereinfachen), (3) eine Grenze nach der anderen (z.B. kein Slack nach 20 Uhr), (4) erholsame Aktivitäten (Spaziergänge, Musik, Hobbys), (5) mit Vorgesetzten über Arbeitsbelastung sprechen.
Bei mehr als einem Monat oder Schlaflosigkeit/Panik → Therapeut*in konsultieren. In Deutschland: TK-Coach, AOK Lebenswelt, oder über den Hausarzt eine Überweisung zur Psychotherapie.""",
    },

    # MENTAL HEALTH — Hindi
    {
        "id": "mh-hi-1", "domain": "Mental Health", "lang": "hi",
        "topic": "मानसिक स्वास्थ्य हेल्पलाइन (Hindi)",
        "source": "Tele-MANAS 14416 · iCall · Vandrevala (MoHFW listed helplines)",
        "lastVerifiedOn": "2025-10-15",
        "text": """मानसिक स्वास्थ्य के लिए मुफ्त helpline numbers India में:
- Tele-MANAS: 14416 (केंद्र सरकार, 24x7, 20+ भाषाएं)
- iCall (TISS): +91 9152987821 (Mon-Sat, 8 AM-10 PM, free)
- Vandrevala Foundation: 1860-2662-345 (24x7 free chat + call)
- AASRA: +91 9820466726 (24x7 suicide prevention)
- NIMHANS Bengaluru: nimhans.ac.in (government, सस्ती consultation)
- Sanjivini Society Delhi: 011-40769002

जब call करें: अगर 2 हफ्ते से ज्यादा से उदास, चिंतित, या नींद नहीं आ रही। अगर खुद को नुकसान पहुंचाने के विचार आ रहे हैं तो तुरंत call करें — ये सब free और confidential हैं।

मानसिक बीमारी कोई कमज़ोरी नहीं है। जैसे शरीर की बीमारी के लिए doctor के पास जाते हैं, वैसे ही mental health के लिए therapist या psychiatrist के पास जाना normal है।""",
    },

    # ═════════════════════════════════════════════════════════════════════
    # LEGAL (English)
    # ═════════════════════════════════════════════════════════════════════
    {
        "id": "lg-1", "domain": "Legal", "lang": "en",
        "topic": "filing an FIR",
        "source": "Bharatiya Nagarik Suraksha Sanhita 2023 · Section 173 (formerly CrPC §154)",
        "lastVerifiedOn": "2025-10-15",
        "text": """FIR = First Information Report, prepared by police on receiving information about a cognizable offence. Section 154 CrPC, now Section 173 of the Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023.
How: (1) Go to police station with jurisdiction. (2) Give info orally or in writing. (3) Officer must record, read back, have you sign. (4) Free copy is your right — Section 154(2) CrPC / 173(2) BNSS.
If refused: written complaint to Superintendent of Police (Sec 154(3)), private complaint before Judicial Magistrate under Section 156(3) CrPC, or e-FIR via state portals (Delhi, UP, Karnataka).
Cognizable: theft, assault, rape, murder, kidnapping. Non-cognizable: get NCR, not FIR.""",
    },
    {
        "id": "lg-2", "domain": "Legal", "lang": "en",
        "topic": "RTI filing process",
        "source": "Right to Information Act 2005 · Sections 6, 7, 19",
        "lastVerifiedOn": "2025-10-15",
        "text": """Right to Information Act, 2005 lets any Indian citizen request information held by any public authority.
Section 6: Plain paper application in English, Hindi, or official language of the area. Address to the Public Information Officer (PIO).
Include: name, contact address, specific information sought (precise), preferred reply mode.
Fee: ₹10 for central bodies (IPO/demand draft/court fee stamp). BPL exempt under Section 7(5).
Section 7: PIO must respond within 30 days; 48 hours for life-or-liberty matters.
If denied/no reply: First Appeal to FAA within 30 days (Sec 19(1)); Second Appeal to Information Commission within 90 days (Sec 19(3)).
Online for central ministries: rtionline.gov.in.""",
    },
    {
        "id": "lg-3", "domain": "Legal", "lang": "en",
        "topic": "consumer protection",
        "source": "Consumer Protection Act 2019",
        "lastVerifiedOn": "2025-10-15",
        "text": """Consumer Protection Act, 2019 replaced the 1986 Act. Rights (Section 2(9)): protection, information, choice, hearing, redressal, education.
Where to complain (Section 35): District Commission ≤ ₹50 lakh; State Commission ₹50 lakh – ₹2 crore; National Commission > ₹2 crore.
Online: consumerhelpline.gov.in (NCH 1915), E-Daakhil (edaakhil.nic.in).
Time limit (Section 69): 2 years from cause of action.
Covers e-commerce, unfair contracts. Class actions (Section 2(5)), product liability (Chapter VI). Misleading ads attract penalties up to ₹10 lakh first offence.""",
    },
    {
        "id": "lg-4", "domain": "Legal", "lang": "en",
        "topic": "tenant rights",
        "source": "Transfer of Property Act 1882 · Section 106 + Model Tenancy Act 2021",
        "lastVerifiedOn": "2025-10-15",
        "text": """Tenancy = state Rent Control Acts + Transfer of Property Act, 1882 (Section 105+).
Notice: Section 106 TPA requires 15 days written notice ending with tenancy month for monthly tenancies.
Eviction grounds: non-payment ≥ 2 months, subletting without consent, bona fide need, material damage. Self-help eviction (changing locks, cutting power) is criminal trespass under Section 441 IPC.
Security deposit: state-specific; Model Tenancy Act 2021 caps at 2 months for residential.
Cut utilities / harassed → local police + Civil Court injunction. Free aid at District Legal Services Authority (DLSA).""",
    },
    {
        "id": "lg-5", "domain": "Legal", "lang": "en",
        "topic": "domestic violence (legal procedure)",
        "source": "Protection of Women from Domestic Violence Act 2005 · Sections 18–22",
        "lastVerifiedOn": "2025-10-15",
        "text": """Protection of Women from Domestic Violence Act, 2005 (PWDVA) — civil remedies. Separately IPC 498A (cruelty), 354 (assault) — criminal.
Who can file: any woman in a domestic relationship facing physical, sexual, verbal, emotional, or economic abuse.
Where: Magistrate's court via Protection Officer or service provider. DIR (Domestic Incident Report) is the basis.
Reliefs (Sections 18-22): Protection Order, Residence Order, Monetary Relief, Custody Order, Compensation.
Courts directed to dispose within 60 days.
NCW helpline: 7827170170. Sakhi One Stop Centres provide medical + legal + shelter.""",
    },
    {
        "id": "lg-6", "domain": "Legal", "lang": "en",
        "topic": "cheque bounce",
        "source": "Negotiable Instruments Act 1881 · Section 138",
        "lastVerifiedOn": "2025-10-15",
        "text": """Section 138 Negotiable Instruments Act, 1881. Criminal offence — imprisonment up to 2 years and/or fine up to twice the cheque amount.
Procedure: (1) Deposit cheque within 3 months. (2) On dishonour, bank issues return memo. (3) Within 30 days of memo, send Demand Notice via registered post. (4) If unpaid within 15 days, file complaint before Magistrate within 30 days of notice expiry.
Jurisdiction: where cheque was presented (Sec 142(2) post-2015).
Burden: Sec 139 — presumption favours holder; drawer must rebut.
Costs: nominal court fee. Lawyer notice ₹2000-5000. Mediation often mandatory pre-trial.""",
    },
    {
        "id": "lg-7", "domain": "Legal", "lang": "en",
        "topic": "free legal aid",
        "source": "Legal Services Authorities Act 1987 · Article 39A Constitution",
        "lastVerifiedOn": "2025-10-15",
        "text": """Article 39A Constitution + Legal Services Authorities Act 1987 guarantee free legal aid.
Eligibility (Section 12): Women, children, SC/ST, trafficking victims, persons with disability, industrial workmen, persons in custody, disaster victims, income below state threshold (~₹3-9 lakh).
Where: DLSA (district), SLSA (state), NALSA (national) — nalsa.gov.in.
Services: court representation, drafting, counselling, court fee, Lok Adalats.
Lok Adalat awards are binding and not appealable.""",
    },
    {
        "id": "lg-8", "domain": "Legal", "lang": "en",
        "topic": "workplace harassment (POSH)",
        "source": "Sexual Harassment of Women at Workplace (POSH) Act 2013",
        "lastVerifiedOn": "2025-10-15",
        "text": """Sexual Harassment of Women at Workplace Act, 2013 = POSH Act.
Coverage: 10+ employees → Internal Complaints Committee (ICC). Smaller → Local Complaints Committee (LCC) at district level.
What counts (Section 2(n), 3): unwelcome physical contact, demand for favours, sexually coloured remarks, pornography, any unwelcome conduct of sexual nature.
Process: written complaint within 3 months (extendable). ICC inquiry within 90 days.
Confidentiality mandatory (Sec 16). Retaliation is itself a violation.
She-Box portal (shebox.wcd.gov.in) for online complaints across sectors.""",
    },
    {
        "id": "lg-9", "domain": "Legal", "lang": "en",
        "topic": "divorce procedure",
        "source": "Hindu Marriage Act 1955 · Section 13B + Special Marriage Act 1954",
        "lastVerifiedOn": "2025-10-15",
        "text": """Divorce by personal law: Hindu Marriage Act 1955 (Hindus, Sikhs, Jains, Buddhists), Special Marriage Act 1954 (inter-faith), Indian Divorce Act 1869 (Christians), Dissolution of Muslim Marriages Act 1939.
Mutual consent (HMA Sec 13B): both agree, separated 1+ year. Two motions, 6-month cooling period (Supreme Court allows waiver). Total: 6-18 months.
Contested grounds: cruelty, adultery, desertion (2+ years), conversion, mental disorder, communicable disease. 2-5 years.
Maintenance: Section 125 CrPC / Section 144 BNSS. Permanent alimony HMA Sec 25.
Custody: child's best interest. Free aid via DLSA.""",
    },
    {
        "id": "lg-10", "domain": "Legal", "lang": "en",
        "topic": "labour law basics",
        "source": "Code on Wages 2019 · EPF Act 1952 · ESI Act 1948 · Gratuity Act 1972 · Maternity Benefit Act 1961",
        "lastVerifiedOn": "2025-10-15",
        "text": """Key labour rights:
Minimum Wages Act 1948 / Code on Wages 2019.
EPF: mandatory ≥ 20 employees. 12% employee + 12% employer of basic.
ESI: medical + sickness for employees earning ≤ ₹21,000/month (₹25k disabled).
Gratuity Act 1972: 15 days' wages × completed years after 5 years' service. Tax-exempt up to ₹20 lakh.
Maternity Benefit Act: 26 weeks paid leave for first two children, 12 weeks for third.
e-Shram (eshram.gov.in) for unorganised workers.""",
    },
    {
        "id": "lg-11", "domain": "Legal", "lang": "en",
        "topic": "key IPC / BNS sections everyone should know",
        "source": "Bharatiya Nyaya Sanhita 2023 (replaces IPC 1860) · in force 1 July 2024",
        "lastVerifiedOn": "2025-10-15",
        "text": """High-frequency criminal sections (IPC → Bharatiya Nyaya Sanhita 2023):
- Theft: IPC 378 / BNS 303. Up to 3 years or fine.
- Assault: IPC 351 / BNS 130.
- Outraging modesty of a woman: IPC 354 / BNS 74.
- Stalking: IPC 354D / BNS 78. Up to 3 years (first), 5 (repeat).
- Voyeurism: IPC 354C / BNS 77.
- Sexual harassment: IPC 354A / BNS 75.
- Defamation: IPC 499/500 / BNS 356.
- Cheating: IPC 415-420 / BNS 316-318.
- Criminal intimidation: IPC 503/506 / BNS 351.
- Hurt: IPC 319/323 / BNS 114/115.
- Grievous hurt: IPC 320/325 / BNS 116/117.
- Wrongful confinement: IPC 340/342 / BNS 126.
- Rape: IPC 376 / BNS 64-68.
- Murder: IPC 302 / BNS 103. Life or death.
- Culpable homicide not amounting to murder: IPC 304 / BNS 105.
- Dowry death: IPC 304B / BNS 80. 7 years to life.
- Abetment of suicide: IPC 306 / BNS 108. Up to 10 years.
- Kidnapping: IPC 363 / BNS 137.
BNS came into force 1 July 2024 and largely renumbers + modernises the IPC.""",
    },
    {
        "id": "lg-12", "domain": "Legal", "lang": "en",
        "topic": "Indian Contract Act essentials",
        "source": "Indian Contract Act 1872 · Specific Relief Act 1963",
        "lastVerifiedOn": "2025-10-15",
        "text": """Indian Contract Act, 1872 — every commercial promise.
Essentials (Section 10): offer + acceptance, lawful consideration, capacity (Sec 11 — major, sane), free consent (Sec 13-22), lawful object.
Void agreements (Sec 24-30): without consideration (with exceptions), restraint of marriage, restraint of trade, wagering.
Breach remedies: damages (Sec 73), specific performance (Specific Relief Act 1963), injunction.
For online clickwrap, IT Act 2000 Section 10A validates them. Retain a copy + timestamp of agreement.""",
    },
    {
        "id": "lg-13", "domain": "Legal", "lang": "en",
        "topic": "SC/ST Prevention of Atrocities Act",
        "source": "SC/ST (Prevention of Atrocities) Act 1989 (amended 2015)",
        "lastVerifiedOn": "2025-10-15",
        "text": """Scheduled Castes and Scheduled Tribes (Prevention of Atrocities) Act, 1989 — strict criminal law against caste-based offences.
Covers atrocities like physical assault, social boycott, forcible occupation of land, sexual exploitation, denial of access to public spaces / water sources, casteist slurs in public.
Punishments are higher and non-bailable; many offences carry 6 months to life imprisonment + fine.
Section 14: Special Courts in every district for speedy trial.
Section 15A: rights of victim and witness — protection, escort, separate waiting rooms.
Section 17: preventive arrests possible.
File FIR at any police station — police MUST register; failure to do so is itself an offence (Section 4 of the amended Act).
Free legal aid via DLSA. Travel + maintenance + medical compensation to victims under Rule 12. National Commission for Scheduled Castes (NCSC) and STs (NCST) handle complaints.""",
    },
    {
        "id": "lg-14", "domain": "Legal", "lang": "en",
        "topic": "Information Technology Act 2000",
        "source": "Information Technology Act 2000 · Sections 66, 67, 69A",
        "lastVerifiedOn": "2025-10-15",
        "text": """IT Act 2000 governs digital signatures, cybercrime, electronic records.
Key cybercrime sections:
- Section 66: hacking / unauthorised access — up to 3 years + ₹5 lakh fine.
- Section 66C: identity theft (stolen password / e-signature) — 3 years + ₹1 lakh.
- Section 66D: cheating by personation using computer (online fraud) — 3 years + ₹1 lakh.
- Section 66E: privacy violation (capturing/transmitting private image without consent) — 3 years.
- Section 67: publishing obscene material — first conviction up to 3 years + ₹5 lakh.
- Section 67A: sexually explicit material — up to 5 years.
- Section 67B: child sexual abuse material — up to 5 years (also POCSO applies).
- Section 69A: government can block content; intermediaries get safe harbour under Sec 79 if compliant.
Section 72: breach of confidentiality.
Report at cybercrime.gov.in or call 1930 for financial fraud (golden hour window).""",
    },
    {
        "id": "lg-15", "domain": "Legal", "lang": "en",
        "topic": "Digital Personal Data Protection Act 2023",
        "source": "Digital Personal Data Protection Act 2023",
        "lastVerifiedOn": "2025-10-15",
        "text": """DPDP Act 2023 (in force after Rules notification 2024-25). India's first comprehensive data-protection law.
Key terms: Data Principal (you, the user), Data Fiduciary (the organisation collecting data), Consent Manager.
Your rights: (1) access summary of your data (Sec 11), (2) correct/erase/update (Sec 12), (3) grievance redressal (Sec 13), (4) nominate someone to act on your behalf (Sec 14), (5) consent must be free, specific, informed, unconditional and revocable.
Children under 18 — verifiable parental consent required.
Penalties: up to ₹250 crore per violation. Data Protection Board adjudicates.
Cross-border transfers allowed except to countries on a restricted list.
File complaint with the Data Protection Board via dpb.gov.in (when operational). For now, the IT Act SPDI Rules 2011 also apply for sensitive personal data.""",
    },
    {
        "id": "lg-16", "domain": "Legal", "lang": "en",
        "topic": "Juvenile Justice Act",
        "source": "Juvenile Justice (Care and Protection of Children) Act 2015",
        "lastVerifiedOn": "2025-10-15",
        "text": """Juvenile Justice (Care and Protection of Children) Act, 2015 governs children in conflict with law (CCL) AND children in need of care and protection (CNCP).
Child = under 18. Two pathways:
- CCL (in conflict with law): Juvenile Justice Board (JJB) decides, not regular court. Heinous offences by 16-18 year olds can be tried as adult after JJB assessment (Section 15).
- CNCP: Child Welfare Committee (CWC) handles placement (foster care, adoption, children's home).
Adoption: CARA (cara.wcd.gov.in) is the only legal route. Inter-country adoption regulated.
POCSO Act 2012 (sexual offences against children) overlaps with JJA — see lg-/sf chunks.
Free legal aid mandatory. CHILDLINE 1098 (24x7).""",
    },
    {
        "id": "lg-17", "domain": "Legal", "lang": "en",
        "topic": "Right to Education Act 2009",
        "source": "Right of Children to Free and Compulsory Education Act 2009 · Article 21A Constitution",
        "lastVerifiedOn": "2025-10-15",
        "text": """RTE Act 2009 implements Article 21A (free and compulsory education for children 6-14).
Key entitlements:
- Free admission to a neighbourhood school until elementary education completes.
- No screening tests, capitation fees, or detention until Class 8.
- 25% reservation in private unaided schools for children from economically weaker / disadvantaged groups (Section 12(1)(c)) — government reimburses the school.
- Pupil-teacher ratio, infrastructure, working days, teacher qualifications specified.
- School Management Committees (Section 21) — 75% parents.
- Grievance: Block / District Education Officer; State Commission for Protection of Child Rights (SCPCR).
If admission denied: complaint to district education officer, escalate to SCPCR or High Court via writ.""",
    },
    {
        "id": "lg-18", "domain": "Legal", "lang": "en",
        "topic": "fundamental rights — Articles 14, 15, 19, 21",
        "source": "Constitution of India · Articles 14, 15, 17, 19, 21, 25, 32",
        "lastVerifiedOn": "2025-10-15",
        "text": """Part III of the Constitution — Fundamental Rights enforceable in court.
- Article 14: equality before law. State cannot discriminate without reasonable classification.
- Article 15: prohibits discrimination on grounds of religion, race, caste, sex, place of birth. Sec 15(3) allows special provisions for women / children, 15(4-6) for backward classes.
- Article 17: abolishes untouchability — operationalised by Protection of Civil Rights Act 1955 + SC/ST PoA Act 1989.
- Article 19: six freedoms — speech, assembly, association, movement, residence, profession. Reasonable restrictions in 19(2)-(6) (sovereignty, security, public order, decency, defamation, etc.).
- Article 21: protection of life and personal liberty. Read expansively by SC to cover privacy (Puttaswamy 2017), dignity, environment, livelihood, health, education.
- Article 25: freedom of religion.
- Article 32: right to constitutional remedies — file a writ DIRECTLY in the Supreme Court for fundamental rights violation.""",
    },
    {
        "id": "lg-19", "domain": "Legal", "lang": "en",
        "topic": "writ petitions (Articles 32 and 226)",
        "source": "Constitution of India · Articles 32 (Supreme Court) and 226 (High Court)",
        "lastVerifiedOn": "2025-10-15",
        "text": """Writs are court orders issued to enforce fundamental rights or correct illegal administrative action.
Where: Article 32 → Supreme Court (only for fundamental rights). Article 226 → High Court (wider scope, includes any legal right).
Five writs:
- Habeas Corpus — "produce the body". Used for illegal detention.
- Mandamus — "we command". Orders a public authority to do its duty.
- Prohibition — stops a lower court from exceeding jurisdiction.
- Certiorari — quashes an order of a lower court / tribunal.
- Quo Warranto — challenges someone holding a public office without authority.
Procedure: petition with affidavit, court fee minimal, can be filed in person or via advocate. Free legal aid via DLSA. Public Interest Litigation (PIL) — anyone can file for public cause (Article 32 or 226).""",
    },
    {
        "id": "lg-20", "domain": "Legal", "lang": "en",
        "topic": "Maintenance and Welfare of Parents and Senior Citizens Act",
        "source": "Maintenance and Welfare of Parents and Senior Citizens Act 2007",
        "lastVerifiedOn": "2025-10-15",
        "text": """Maintenance and Welfare of Parents and Senior Citizens Act, 2007 — parents/senior citizens (60+) can claim maintenance from children / heirs.
Where to file: Maintenance Tribunal in each district (presided by SDM or equivalent). NO lawyer needed.
Maintenance up to ₹10,000/month (states may notify higher).
Section 23: any property transferred by a senior citizen by gift / settlement on the condition that the transferee will provide basic amenities — if the transferee fails, the transfer is void.
Section 24: failure to maintain — punishable up to 3 months or fine.
Free legal aid available.
Helpline: 14567 (Elderline). HelpAge India: 1800-180-1253.""",
    },
    {
        "id": "lg-21", "domain": "Legal", "lang": "en",
        "topic": "Hindu Succession Act / inheritance",
        "source": "Hindu Succession Act 1956 (amended 2005)",
        "lastVerifiedOn": "2025-10-15",
        "text": """Hindu Succession Act 1956 (amended 2005) governs intestate succession for Hindus, Sikhs, Jains, Buddhists.
2005 Amendment: daughters have EQUAL coparcenary rights as sons in ancestral property — including by birth, retrospectively (Vineeta Sharma case, SC 2020).
Class I heirs (Schedule): widow, sons, daughters, mother, children of pre-deceased son/daughter. They inherit simultaneously and equally.
For self-acquired property: passes per will; if no will, per Class I heirs.
Muslim succession: governed by Muslim Personal Law (Shariat) — different shares based on relationships, no requirement of equal division.
Christians / Parsis / inter-faith marriages: Indian Succession Act 1925.
Will: Section 63 ISA — signed by testator + 2 witnesses. Registration not mandatory but recommended.""",
    },
    {
        "id": "lg-22", "domain": "Legal", "lang": "en",
        "topic": "Motor Vehicles Act and road accident liability",
        "source": "Motor Vehicles Act 1988 (amended 2019)",
        "lastVerifiedOn": "2025-10-15",
        "text": """Motor Vehicles Act 1988 (amended 2019) governs roads, licences, accidents, insurance.
Hit-and-run: Solatium Scheme — ₹2 lakh for death, ₹50,000 for grievous injury, paid by the central government even if offender untraceable.
Compulsory third-party insurance: Section 146 — driving without it is an offence (fine ₹2,000 first, ₹4,000 repeat, plus imprisonment).
Motor Accident Claims Tribunal (MACT): present in every district. Victim or family files claim, no court fee. Compensation under "no fault" liability (Section 163A — fixed structured formula) or "fault" (Section 166 — based on negligence proof).
Good Samaritan Law: SC guidelines + state rules protect bystanders who help accident victims from harassment, no obligation to give name / address, no legal liability if injury worsens.
Drunk driving: Sec 185 — up to 6 months or fine ₹10,000; repeat 2 years + ₹15,000.""",
    },
    {
        "id": "lg-23", "domain": "Legal", "lang": "en",
        "topic": "GST basics for small business / freelancer",
        "source": "Central Goods and Services Tax Act 2017 · CBIC notifications",
        "lastVerifiedOn": "2025-10-15",
        "text": """GST (Goods and Services Tax) introduced 2017, replaced VAT/service tax.
Registration threshold:
- Services: ₹20 lakh annual turnover (₹10 lakh in special-category states).
- Goods: ₹40 lakh.
- Voluntary registration possible at any turnover (gets you input tax credit).
Slabs: 0% (essentials), 5%, 12%, 18%, 28%.
Composition scheme: for turnover ≤ ₹1.5 crore (goods) / ₹50 lakh (services). 1-6% flat rate, no input credit, simpler filing.
Returns: GSTR-1 (sales) + GSTR-3B (summary, monthly or quarterly). Annual return GSTR-9.
Penalties: late filing ₹50/day (₹20 nil return), max ₹10,000.
Portal: gst.gov.in.
For invoices > ₹50,000 inter-state — e-way bill required.
Reverse Charge Mechanism: buyer pays GST on certain notified services.""",
    },
    {
        "id": "lg-24", "domain": "Legal", "lang": "en",
        "topic": "Insolvency and Bankruptcy Code 2016",
        "source": "Insolvency and Bankruptcy Code 2016 · IBBI guidelines",
        "lastVerifiedOn": "2025-10-15",
        "text": """IBC 2016 consolidates insolvency law for individuals and companies.
Corporate Insolvency Resolution Process (CIRP): if a company defaults on ≥ ₹1 crore, financial / operational creditor can file with NCLT (National Company Law Tribunal). Resolution professional takes over for 330 days (extendable). If no resolution → liquidation.
Pre-Pack Insolvency for MSMEs (added 2021): default threshold ₹10 lakh, faster.
Personal Insolvency (for individuals, sole proprietors): Fresh Start Process — for income < ₹60,000/year, debt < ₹35,000, no asset > ₹20,000 — debts written off after 6 months.
Insolvency Resolution Process (individuals): triggered by debt default ≥ ₹1,000.
Apply: NCLT (companies, LLPs) or DRT (individuals).
Read: ibbi.gov.in.""",
    },

    {
        "id": "lg-29", "domain": "Legal", "lang": "en",
        "topic": "money recovery — civil suit, summary suit, IBC, debt recovery tribunal",
        "source": "CPC 1908 Order XXXVII · RDDBFI Act 1993 · IBC 2016",
        "lastVerifiedOn": "2025-10-15",
        "text": """If someone owes you money and won't pay:
1. Section 138 NI Act (cheque bounce) — if you have a dishonoured cheque, see lg-6.
2. Civil suit for recovery — Order 37 CPC (summary suit) for liquidated debts based on written instrument (bill of exchange, promissory note, written contract). Faster — defendant must apply for leave to defend.
3. Regular civil suit — Order I-IV CPC. Slower, 2-5 years typical.
4. Section 25 PSCC Act 1887 (Presidency Small Causes) — quick small-amount recovery.
5. Debt Recovery Tribunal (DRT): for bank / financial-institution debts ≥ ₹20 lakh under SARFAESI 2002 + RDDBFI 1993.
6. Insolvency proceeding (lg-24): for corporate / financial creditor default ≥ ₹1 crore (NCLT) or personal ≥ ₹1,000.
7. Arbitration (Arbitration & Conciliation Act 1996): if the contract has an arbitration clause — bypass courts, generally faster.
Send a Legal Demand Notice first via registered post (₹2,000-5,000 lawyer fee). 30-day reply window. Use the reply (or lack of one) as evidence.""",
    },

    # LEGAL — German
    {
        "id": "lg-de-3", "domain": "Legal", "lang": "de",
        "topic": "Arbeitsrecht in Deutschland (German labour law basics)",
        "source": "BGB · Kündigungsschutzgesetz · MiLoG",
        "lastVerifiedOn": "2025-10-15",
        "text": """Deutsches Arbeitsrecht — sehr arbeitnehmerfreundlich:
Arbeitsvertrag: muss innerhalb eines Monats schriftlich übergeben werden (NachwG). Auch mündlich gültig, aber schriftlich besser.
Probezeit: max. 6 Monate, Kündigungsfrist 2 Wochen.
Kündigungsschutz nach 6 Monaten + 10+ Arbeitnehmer im Betrieb (KSchG): nur betriebs-, personen- oder verhaltensbedingte Kündigung. Sonst Kündigungsschutzklage beim Arbeitsgericht innerhalb von 3 Wochen.
Urlaub: gesetzlich mindestens 20 Tage bei 5-Tage-Woche (BUrlG), üblich 25-30 Tage.
Krankheit: bis 6 Wochen volles Gehalt (Entgeltfortzahlung). Danach Krankengeld der Krankenkasse (max. 78 Wochen).
Mutterschutz: 6 Wochen vor + 8 Wochen nach Geburt (MuSchG). Elternzeit bis 3 Jahre.
Mindestlohn (2025): 12,82 €/Stunde.
Beratung: DGB-Gewerkschaft (~1% Beitrag), Betriebsrat, Anwalt für Arbeitsrecht. Bei Streit: Arbeitsgericht — kein Anwaltszwang in erster Instanz.""",
    },

    # LEGAL — German
    {
        "id": "lg-de-1", "domain": "Legal", "lang": "de",
        "topic": "Mietrecht in Deutschland (German tenant rights)",
        "source": "BGB §§535–580a · Mieterschutzgesetz",
        "lastVerifiedOn": "2025-10-15",
        "text": """Deutsches Mietrecht (BGB §§ 535-580a) — sehr mieterfreundlich.
Mietvertrag: schriftlich empfohlen, aber auch mündlich gültig. Befristung nur mit konkretem Grund (Eigenbedarf, Renovierung).
Kaution: maximal 3 Nettokaltmieten (§ 551 BGB), zinsbringend angelegt, zurück nach Auszug (üblicherweise 6 Monate).
Mieterhöhung: nur nach 12 Monaten, maximal 20% in 3 Jahren (Kappungsgrenze; 15% in Gebieten mit Wohnraummangel), schriftlich begründet (Mietspiegel oder Vergleichswohnungen).
Kündigung Vermieter: nur mit berechtigtem Interesse — Eigenbedarf, erhebliche Vertragsverletzung. Kündigungsfrist je nach Mietdauer: 3 Monate (bis 5 Jahre) / 6 Monate (5-8 Jahre) / 9 Monate (über 8 Jahre).
Kündigung Mieter: jederzeit mit 3 Monaten Frist.
Beratung: Mieterverein (mieterbund.de) — Mitgliedschaft ~€80/Jahr inklusive Rechtsberatung. Bei Streitigkeiten: Amtsgericht; vorher oft Schlichtungsstelle.""",
    },
    {
        "id": "lg-de-2", "domain": "Legal", "lang": "de",
        "topic": "Beratungshilfe und Prozesskostenhilfe (German legal aid)",
        "source": "Beratungshilfegesetz (BerHG) · ZPO §§114–127",
        "lastVerifiedOn": "2025-10-15",
        "text": """In Deutschland gibt es zwei staatliche Hilfen für Menschen mit geringem Einkommen:
Beratungshilfe (außergerichtlich): für anwaltliche Beratung außerhalb des Gerichts. Antrag beim Amtsgericht des Wohnortes oder direkt beim Anwalt mit Berechtigungsschein. Eigenanteil: 15 € pauschal, in Härtefällen kostenfrei.
Prozesskostenhilfe (PKH, gerichtlich): bei Klagen oder Beklagtenrolle. Deckt Gerichts- und Anwaltskosten, ggf. mit monatlichen Raten. Antrag beim zuständigen Gericht.
Voraussetzung: Einkommen unter Freibetrag (ca. 700-900 € netto je nach Familienstand) und keine zumutbaren Vermögensmittel.
Kostenlose Erstinformation: Verbraucherzentrale (verbraucherzentrale.de), DGB (für Arbeitsrecht), Mieterbund (Mietrecht).
Notar: bei Verträgen — Kosten gesetzlich geregelt (GNotKG).""",
    },

    # LEGAL — Hindi
    {
        "id": "lg-hi-1", "domain": "Legal", "lang": "hi",
        "topic": "RTI कैसे file करें (Hindi)",
        "source": "सूचना का अधिकार अधिनियम 2005 · धारा 6, 7, 19",
        "lastVerifiedOn": "2025-10-15",
        "text": """RTI (सूचना का अधिकार) Act, 2005 के तहत कोई भी Indian citizen किसी भी public authority से जानकारी मांग सकता है।
कैसे file करें:
1. Plain paper पर application लिखें — English, Hindi, या local language में।
2. PIO (Public Information Officer) को address करें — हर government office में होते हैं।
3. Application में लिखें: अपना नाम, पता, exactly कौन सी जानकारी चाहिए, reply कैसे चाहिए।
4. ₹10 fee Central government bodies के लिए (IPO/demand draft/court fee stamp से)। BPL वालों को free है।
5. 30 दिन में reply आना चाहिए (life/liberty मामलों में 48 घंटे)।

अगर reply नहीं आया या मना किया:
- 30 दिन में First Appeal — उसी department के Appellate Authority को।
- फिर 90 दिन में Second Appeal — Central/State Information Commission को।

Online file करें: rtionline.gov.in (केंद्र सरकार के लिए)।
हर state का अपना portal भी है। DLSA से free legal aid मिलती है।""",
    },
    {
        "id": "lg-hi-2", "domain": "Legal", "lang": "hi",
        "topic": "FIR कैसे दर्ज करें (Hindi)",
        "source": "BNSS 2023 · धारा 173 (पूर्व CrPC §154)",
        "lastVerifiedOn": "2025-10-15",
        "text": """FIR (First Information Report) Section 154 CrPC के तहत police द्वारा cognizable offence की जानकारी पर लिखी जाती है। 2024 से Section 173 BNSS (Bharatiya Nagarik Suraksha Sanhita) लागू।
कैसे file करें:
1. उस police station जाएं जहां घटना हुई।
2. मौखिक या लिखित में जानकारी दें।
3. Officer उसे लिखेगा, आपको पढ़कर सुनाएगा, और sign करवाएगा।
4. FIR की copy free मिलना आपका कानूनी अधिकार है — Section 154(2) / 173(2)।

अगर police मना करे:
- Superintendent of Police को written complaint (Section 154(3))।
- Judicial Magistrate के सामने private complaint (Section 156(3) CrPC)।
- e-FIR portal (Delhi, UP, Karnataka जैसे states में)।

Cognizable offences: चोरी, मारपीट, बलात्कार, हत्या, अपहरण।
Non-cognizable: FIR नहीं, NCR मिलेगी।
Free legal aid: NALSA (nalsa.gov.in), DLSA हर district में।""",
    },

    # ═════════════════════════════════════════════════════════════════════
    # GOVERNMENT SCHEMES (English)
    # ═════════════════════════════════════════════════════════════════════
    {
        "id": "gs-1", "domain": "Government Schemes", "lang": "en",
        "topic": "Ayushman Bharat PM-JAY",
        "source": "Ayushman Bharat PM-JAY · NHA Guidelines (pmjay.gov.in)",
        "lastVerifiedOn": "2025-10-15",
        "text": """PM-JAY: ₹5 lakh per family per year for secondary and tertiary hospitalisation at empanelled public/private hospitals.
Eligibility: SECC 2011 — rural deprivation criteria + 11 urban occupational categories. Senior citizens 70+ now covered regardless of income (PM-JAY Vandana, 2024).
Check: pmjay.gov.in → "Am I Eligible?" — mobile + state. Or call 14555 / 1800-111-565.
Use: show Ayushman Bharat Card (or govt ID + ration card) at empanelled hospital. Cashless. Pre-existing covered day one.
Card: e-card from beneficiary portal, or physical at CSC. Free.""",
    },
    {
        "id": "gs-2", "domain": "Government Schemes", "lang": "en",
        "topic": "PM Kisan Samman Nidhi",
        "source": "PM-KISAN Yojana · Ministry of Agriculture (pmkisan.gov.in)",
        "lastVerifiedOn": "2025-10-15",
        "text": """PM-KISAN: ₹6,000/year to eligible farmer families in three ₹2,000 instalments via DBT.
Eligibility: landholding farmer families (cultivable land per state records). All sizes (was ≤ 2 hectares earlier).
Exclusions: institutional landholders, constitutional post holders, Group A/B salaried govt staff, PSU staff, professionals (doctors/CAs/engineers), income tax payers.
Apply: pmkisan.gov.in → "New Farmer Registration" with Aadhaar, bank account, land records. Or at CSC.
e-KYC mandatory (OTP on pmkisan.gov.in or biometric at CSC).
Status: pmkisan.gov.in → "Beneficiary Status".""",
    },
    {
        "id": "gs-3", "domain": "Government Schemes", "lang": "en",
        "topic": "scholarships (NSP)",
        "source": "National Scholarship Portal · Ministry of Education (scholarships.gov.in)",
        "lastVerifiedOn": "2025-10-15",
        "text": """National Scholarships Portal (scholarships.gov.in) — single window for central + state.
Major schemes:
- Pre-Matric SC/ST/OBC/Minorities (Class 1-10): family income < ₹2.5 lakh.
- Post-Matric SC (Class 11 through PhD): income < ₹2.5 lakh.
- Central Sector for College/University: top 80th percentile in Class 12, income < ₹4.5 lakh, ₹10k-20k/year.
- Pragati for Girls (AICTE): technical education, ₹50,000/year, income < ₹8 lakh.
- Saksham for Differently-Abled (AICTE): ₹50,000/year.
- Inspire (DST): top science students BSc/MSc, ₹80,000/year.
- ePass Karnataka, Maharashtra MahaDBT, Bihar — state portals.
Documents: Aadhaar, income, caste, bank, mark sheet, fee receipt. Apply Oct-Nov.""",
    },
    {
        "id": "gs-4", "domain": "Government Schemes", "lang": "en",
        "topic": "ration card (PDS)",
        "source": "National Food Security Act 2013 · PDS",
        "lastVerifiedOn": "2025-10-15",
        "text": """Ration cards under National Food Security Act, 2013 enable subsidised foodgrains:
- Antyodaya Anna Yojana (AAY): poorest — 35 kg per family per month.
- Priority Household (PHH): 5 kg per person per month.
- Non-Priority: no subsidy.
Apply: state Food & Civil Supplies portal (nfsa.up.gov.in, ahara.kar.nic.in, etc.) with address proof, ID, photo, income, family details.
One Nation One Ration Card (ONORC): PHH card usable anywhere via Aadhaar authentication.
Lost card: file FIR, then apply for duplicate.
Grievance: 1967 (national PDS helpline) or state number.""",
    },
    {
        "id": "gs-5", "domain": "Government Schemes", "lang": "en",
        "topic": "MGNREGA",
        "source": "Mahatma Gandhi NREGA 2005 (nrega.nic.in)",
        "lastVerifiedOn": "2025-10-15",
        "text": """MGNREGA 2005 — 100 days of unskilled manual work per rural household per FY.
Eligibility: adult rural household member. Apply at Gram Panchayat for job card (free, within 15 days).
Wage: state-specific, ₹220-310/day. Paid via bank/post office within 15 days; else unemployment allowance.
Work demanded: written application. Within 15 days, within 5 km of village (else 10% extra wage).
Women workers ≥ 1/3. Childcare if 5+ under-6 kids at site.
Status: nrega.nic.in. Grievance: 1800-345-22-44.""",
    },
    {
        "id": "gs-6", "domain": "Government Schemes", "lang": "en",
        "topic": "PM Awas Yojana (housing)",
        "source": "PM Awas Yojana Guidelines · MoHUA (pmaymis.gov.in)",
        "lastVerifiedOn": "2025-10-15",
        "text": """PMAY has two streams.
PMAY-Urban CLSS:
- EWS (≤ ₹3 lakh): ₹2.67 lakh on loan up to ₹6 lakh.
- LIG (₹3-6 lakh): ₹2.67 lakh on loan up to ₹6 lakh.
- MIG-I (₹6-12 lakh): ₹2.35 lakh on loan up to ₹9 lakh.
- MIG-II (₹12-18 lakh): ₹2.30 lakh on loan up to ₹12 lakh.
Apply: pmaymis.gov.in → "Citizen Assessment".
PMAY-Gramin: SECC 2011 selection. ₹1.20 lakh (plain) / ₹1.30 lakh (hilly), plus 90-95 days MGNREGA wages, ₹12,000 for toilet. pmayg.nic.in.""",
    },
    {
        "id": "gs-7", "domain": "Government Schemes", "lang": "en",
        "topic": "pension and insurance schemes",
        "source": "Atal Pension Yojana · PMSBY · PMJJBY · PMVVY (jansuraksha.gov.in)",
        "lastVerifiedOn": "2025-10-15",
        "text": """Jan Suraksha schemes:
PMJJBY (life): ₹2 lakh cover. Age 18-50, ₹436/year auto-debit. Renewable to 55.
PMSBY (accident): ₹2 lakh death/full disability, ₹1 lakh partial. Age 18-70, ₹20/year.
APY (Atal Pension Yojana): ₹1,000-5,000/month pension after 60. Age 18-40, unorganised sector. Government co-contribution closed for income-taxpayers since Oct 2022.
Enrolment: any bank or post office with auto-debit mandate.
PMVVY (LIC) — pension for 60+.""",
    },
    {
        "id": "gs-8", "domain": "Government Schemes", "lang": "en",
        "topic": "Mudra and Stand-Up India",
        "source": "Pradhan Mantri Mudra Yojana · Stand-Up India scheme (mudra.org.in · standupmitra.in)",
        "lastVerifiedOn": "2025-10-15",
        "text": """Mudra (PMMY) — collateral-free business loans:
- Shishu: up to ₹50,000.
- Kishore: ₹50,000 - ₹5 lakh.
- Tarun: ₹5 lakh - ₹10 lakh.
- Tarun Plus (Budget 2024): ₹10 lakh - ₹20 lakh for repaid Tarun.
Apply: commercial bank, RRB, small finance bank, NBFC. udyamimitra.in.
Stand-Up India: ₹10 lakh - ₹1 crore for greenfield enterprises in manufacturing/services/trading, for SC/ST and women entrepreneurs (≥1 in each branch of every scheduled bank). standupmitra.in.
Repayment: 7 years with 18-month moratorium.""",
    },
    {
        "id": "gs-9", "domain": "Government Schemes", "lang": "en",
        "topic": "schemes for girls and women",
        "source": "Sukanya Samriddhi · Beti Bachao Beti Padhao · Mahila Samman Savings Certificate",
        "lastVerifiedOn": "2025-10-15",
        "text": """Sukanya Samriddhi Yojana (SSY): for girl child under 10. 21-year tenure (or until marriage after 18). ~8.2% p.a., tax-exempt 80C. ₹250-1,50,000/year.
Beti Bachao Beti Padhao (BBBP): awareness + SSY linkage.
PM Matru Vandana Yojana (PMMVY): ₹5,000 (two instalments) to pregnant/lactating mothers for first child + ₹1,000 under JSY. Anganwadi Centre.
Mahila Samman Savings Certificate: 2-year deposit up to ₹2 lakh at 7.5%, any woman, post office.
PM Ujjwala (PMUY): free LPG connection + first refill for BPL women. ujjwala.petroleum.gov.in.""",
    },
    {
        "id": "gs-10", "domain": "Government Schemes", "lang": "en",
        "topic": "PM Vishwakarma (artisans)",
        "source": "PM Vishwakarma Yojana · MSME ministry (pmvishwakarma.gov.in)",
        "lastVerifiedOn": "2025-10-15",
        "text": """PM Vishwakarma 2023 — 18 traditional trades: carpenter, blacksmith, goldsmith, potter, sculptor, cobbler, mason, basket weaver, doll maker, barber, garland maker, washerman, tailor, fishing-net maker, etc.
Benefits: (1) certificate + ID. (2) 5-7 day basic + 15+ day advanced training (₹500/day stipend). (3) ₹15,000 toolkit voucher. (4) Collateral-free credit ₹1 lakh + ₹2 lakh at 5%. (5) ₹1/transaction digital incentive up to 100/month. (6) Marketing support.
Eligibility: 18+, self-employed in listed trade, no similar benefit in 5 years, one family member only.
Register: pmvishwakarma.gov.in or any CSC.""",
    },
    {
        "id": "gs-11", "domain": "Government Schemes", "lang": "en",
        "topic": "startup and skill schemes",
        "source": "Startup India · Skill India / NSDC · Atal Innovation Mission",
        "lastVerifiedOn": "2025-10-15",
        "text": """Startup India (DPIIT): 3-year income tax exemption out of first 10, self-certification labour/environment laws, 80% patent fee rebate, fund-of-funds. startupindia.gov.in.
PMKVY (Skill India): free short-term training in 250+ NSQF-aligned roles. skillindiadigital.gov.in.
DDU-GKY: rural placement-linked skilling, 15-35 from poor rural families.
PM-DAKSH (SC/OBC/EBC/De-notified): free training. pmdaksh.dosje.gov.in.
Atal Innovation Mission — Atal Tinkering Labs, AICs. aim.gov.in.""",
    },
    {
        "id": "gs-12", "domain": "Government Schemes", "lang": "en",
        "topic": "education loans and interest subsidy",
        "source": "Vidya Lakshmi Portal · Central Sector Interest Subsidy (CSIS)",
        "lastVerifiedOn": "2025-10-15",
        "text": """Vidya Lakshmi (vidyalakshmi.co.in): single-window for 30+ banks.
Typical: up to ₹10 lakh for study in India, ₹20 lakh abroad. Higher amounts on collateral. 4% rebate for girls at many PSU banks.
Central Sector Interest Subsidy (CSIS): full interest during moratorium for families with income < ₹4.5 lakh.
Padho Pardesh (Minorities, OBC, EBC): interest subsidy for overseas studies.
PM Vidyalaxmi (PMVL 2024): collateral-free loan up to ₹7.5 lakh with 75% credit guarantee for income < ₹8 lakh.""",
    },
    {
        "id": "gs-13", "domain": "Government Schemes", "lang": "en",
        "topic": "PM Surya Ghar Muft Bijli Yojana (rooftop solar)",
        "source": "PM Surya Ghar Muft Bijli Yojana · Ministry of New & Renewable Energy",
        "lastVerifiedOn": "2025-10-15",
        "text": """PM Surya Ghar Muft Bijli Yojana 2024 — central subsidy for rooftop solar in residential homes.
Subsidy slab (per kW capacity, max 3 kW per home):
- First 2 kW: ₹30,000 per kW
- Next 1 kW: ₹18,000 per kW
- Total for 3 kW system: ₹78,000 subsidy.
Eligibility: any Indian household with a roof and a valid electricity connection (single point).
Benefit: up to 300 units of free electricity per month (depending on roof + sunshine). Excess fed back to grid.
Apply: pmsuryaghar.gov.in. Steps: (1) register with DISCOM details. (2) get installation by empanelled vendor (state list on portal). (3) inspection by DISCOM. (4) subsidy in your bank account within 30 days of net-meter installation.
Bank loans: collateral-free up to ₹2 lakh at ~7% for residential.""",
    },
    {
        "id": "gs-14", "domain": "Government Schemes", "lang": "en",
        "topic": "PM SVAnidhi (street vendors)",
        "source": "PM SVANidhi · MoHUA (pmsvanidhi.mohua.gov.in)",
        "lastVerifiedOn": "2025-10-15",
        "text": """PM SVAnidhi — Pradhan Mantri Street Vendor's AtmaNirbhar Nidhi (2020).
Working-capital loans to street vendors:
- 1st loan: up to ₹10,000, repay in 12 months.
- 2nd loan: up to ₹20,000, after successful 1st repayment.
- 3rd loan: up to ₹50,000.
No collateral. Interest subsidy of 7% to those repaying on time.
Cashback for digital transactions: ₹50/month for monthly digital txn ≥ 50, ₹100/month for ≥ 100, ₹150 for ≥ 200.
Eligibility: street vendors operating before 24 March 2020 with vendor ID/certificate from Urban Local Body, OR letter of recommendation if not registered.
Apply: pmsvanidhi.mohua.gov.in. PSBLoansIn59Minutes.com for banks. Common Service Centre (CSC) for offline.""",
    },
    {
        "id": "gs-15", "domain": "Government Schemes", "lang": "en",
        "topic": "Karnataka state schemes (Gruha Lakshmi, Shakti, Anna Bhagya)",
        "source": "Karnataka guarantees 2024 · sevasindhuservices.karnataka.gov.in",
        "lastVerifiedOn": "2025-10-15",
        "text": """Karnataka flagship "Guarantee" schemes (2023-):
Gruha Lakshmi: ₹2,000/month to woman head of every BPL family (cash transfer via DBT). Apply via Seva Sindhu or local Karnataka Bhavana. Eligibility: woman of household with ration card.
Shakti: free travel for all women on state-run KSRTC, BMTC, KKRTC, NWKRTC non-AC buses (Ordinary, Express). Just show Aadhaar / ID. No card needed.
Anna Bhagya: free 10 kg rice (5 kg under NFSA + 5 kg additional) per person per month to BPL families. Equivalent cash via DBT if grain unavailable.
Gruha Jyothi: free electricity up to 200 units/month for residential consumers.
Yuva Nidhi: ₹3,000/month for unemployed graduates, ₹1,500 for diploma holders, for up to 2 years. Apply via Seva Sindhu.""",
    },
    {
        "id": "gs-16", "domain": "Government Schemes", "lang": "en",
        "topic": "Maharashtra state schemes (Ladki Bahin, Mahatma Phule)",
        "source": "Mukhyamantri Mazi Ladki Bahin · Mahatma Phule Jan Arogya · ladakibahin.maharashtra.gov.in",
        "lastVerifiedOn": "2025-10-15",
        "text": """Mukhyamantri Majhi Ladki Bahin Yojana (2024): ₹1,500/month to married/unmarried/widowed/divorced/destitute women aged 21-65 from Maharashtra with annual family income < ₹2.5 lakh. Apply via Aaple Sarkar portal or Anganwadi.
Mahatma Jyotiba Phule Jan Arogya Yojana (MJPJAY): health cover up to ₹1.5 lakh/year for orange/yellow ration card holders (since 2024 expanded to all residents up to ₹5 lakh). 1209 procedures covered at 1000+ empanelled hospitals.
Lek Ladki Yojana: ₹5,000 (at birth) → ₹4,000 (Class 1) → ₹6,000 (Class 6) → ₹8,000 (Class 11) → ₹75,000 (at 18) for girls born in yellow/orange-card families.
Annapurna: 3 free LPG cylinders/year for Ladki Bahin beneficiaries.
Mukhyamantri Yuva Karya Prashikshan: ₹6,000-10,000/month stipend for skilled youth doing internships.""",
    },
    {
        "id": "gs-17", "domain": "Government Schemes", "lang": "en",
        "topic": "UP state schemes (Kanya Sumangala, Mukhyamantri schemes)",
        "source": "Mukhyamantri Kanya Sumangala Yojana (mksy.up.gov.in)",
        "lastVerifiedOn": "2025-10-15",
        "text": """Mukhyamantri Kanya Sumangala Yojana (UP): ₹25,000 in 6 instalments to girl child — ₹5,000 (at birth) / ₹2,000 (1-year vaccination) / ₹3,000 (Class 1) / ₹3,000 (Class 6) / ₹5,000 (Class 9) / ₹7,000 (graduation/diploma). Annual family income < ₹3 lakh, max 2 girls per family. Apply via mksy.up.gov.in.
Mukhyamantri Yuva Swarozgar Yojana: subsidy + loan up to ₹25 lakh (manufacturing) / ₹10 lakh (services) for youth 18-40. Margin money 25% (general) / 35% (women/SC/ST/PH). diupmsme.upsdc.gov.in.
Mukhyamantri Abhyudaya Yojana: free UPSC / NEET / JEE coaching for select students.
Mukhyamantri Sahbhagita Yojana: monthly stipend to families fostering rescued children.
Niradhar Mahila Pension: ₹500/month to destitute / widowed women.""",
    },
    {
        "id": "gs-18", "domain": "Government Schemes", "lang": "en",
        "topic": "Tamil Nadu state schemes (CMCHIS, Pudhumai Penn)",
        "source": "CMCHIS · Pudhumai Penn · TN state portal (penkalvi.tn.gov.in)",
        "lastVerifiedOn": "2025-10-15",
        "text": """Chief Minister's Comprehensive Health Insurance Scheme (CMCHIS): ₹5 lakh/family/year for families with income < ₹1.2 lakh. 1027 procedures at 1000+ hospitals. Aadhaar-linked card. cmchistn.com.
Pudhumai Penn (2022): ₹1,000/month to girls who studied Class 6-12 in government schools and pursue higher education (UG / diploma / certificate). Direct to bank account till graduation. penkalvi.tn.gov.in.
Kalaignar Magalir Urimai Thogai: ₹1,000/month to eligible women heads of households. Apply through Anganwadi.
Naan Mudhalvan: skill development + free entrepreneurship coaching for college students. naanmudhalvan.tn.gov.in.
Free Bus Travel for Women: in all government-run city buses (since 2021).
Dr Muthulakshmi Reddy Maternity Benefit Scheme: ₹18,000 to pregnant women (split into instalments).""",
    },
    {
        "id": "gs-19", "domain": "Government Schemes", "lang": "en",
        "topic": "Delhi state schemes",
        "source": "Delhi Government welfare portal · edistrict.delhigovt.nic.in",
        "lastVerifiedOn": "2025-10-15",
        "text": """Free electricity (DISCOM): residential consumers using up to 200 units/month — fully waived. 201-400 units — 50% subsidy. Apply on DISCOM portals (BSES Rajdhani, BSES Yamuna, Tata Power).
Mukhyamantri Tirth Yatra Yojana: free pilgrimage for senior citizens (60+) to multiple destinations. delhi.gov.in.
Free bus travel for women: on DTC + cluster buses with a pink ticket.
Mukhyamantri Mahila Samman Yojana (announced): ₹1,000/month (proposed) — check current status.
Ladli Yojana (older scheme): financial aid to girl child at various milestones — birth, Class 1, 6, 9, 12. Total ~₹35,000 if education completed.
Mohalla Clinic: free OPD + diagnostics + medicines at neighbourhood clinics across Delhi.""",
    },
    {
        "id": "gs-20", "domain": "Government Schemes", "lang": "en",
        "topic": "West Bengal state schemes (Lakshmir Bhandar, Kanyashree)",
        "source": "Lakshmir Bhandar · Kanyashree Prakalpa · socialsecurity.wb.gov.in",
        "lastVerifiedOn": "2025-10-15",
        "text": """Lakshmir Bhandar: ₹1,000/month to general-category women aged 25-60, ₹1,200 for SC/ST. No income criterion. Bank account linked. wbgov.bangla-sahayata.gov.in.
Kanyashree Prakalpa: K1 — ₹1,000/year scholarship for unmarried girls 13-18 in school. K2 — one-time ₹25,000 at age 18 if still unmarried and continuing studies. K3 — for postgraduate (₹2,000-2,500/month).
Yuvasree: ₹1,500/month unemployment allowance for registered job-seekers under 1-year-old card (extendable).
Rupashree: ₹25,000 to families with income < ₹1.5 lakh for daughter's marriage (when girl is ≥ 18).
Swasthya Sathi: cashless health cover ₹5 lakh/family/year for all West Bengal residents at empanelled hospitals.
Krishak Bandhu: financial assistance for farmers — ₹4,000-10,000/year based on landholding.""",
    },
    {
        "id": "gs-25", "domain": "Government Schemes", "lang": "en",
        "topic": "PM Jan Dhan Yojana (financial inclusion)",
        "source": "PM Jan Dhan Yojana · Dept of Financial Services (pmjdy.gov.in)",
        "lastVerifiedOn": "2025-10-15",
        "text": """Pradhan Mantri Jan Dhan Yojana (PMJDY) — zero-balance basic savings bank account for the unbanked.
Features:
- No minimum balance required.
- Free RuPay debit card with built-in accident insurance cover ₹2 lakh (₹1 lakh for accounts opened before Aug 2018).
- Overdraft facility up to ₹10,000 for active accounts after 6 months satisfactory operation.
- Life insurance cover ₹30,000 for accounts opened between Aug 2014 – Jan 2015 (one-time).
- Direct Benefit Transfer (DBT) — all govt subsidies (LPG, MGNREGA wages, PM Kisan, PMAY) credit directly.
Apply: any bank (PSU, private, RRB, small finance), Post Office Payments Bank, or Common Service Centre with Aadhaar + a self-declaration if address proof unavailable.
Status: pmjdy.gov.in. Toll-free 1800-110-001.
Connected schemes: PMJJBY (life), PMSBY (accident), APY (pension) — all auto-debit from this account, cheap premiums (see gs-7).""",
    },
    {
        "id": "gs-22", "domain": "Government Schemes", "lang": "en",
        "topic": "Kerala state schemes",
        "source": "Kerala State Welfare portal · kerala.gov.in",
        "lastVerifiedOn": "2025-10-15",
        "text": """Kerala flagship schemes:
KASP (Karunya Arogya Suraksha Padhathi): merged with PM-JAY — ₹5 lakh/family/year health cover for ration-card holders below the cutoff.
Vidyakiranam — Free Higher Education Scheme: covers fee, hostel, books for SC/ST/OBC students in government colleges. Income < ₹2.5 lakh.
Kudumbashree — state poverty-eradication mission. Self-help groups + neighbourhood groups for women. Microcredit + livelihood support. Apply at local panchayat.
Snehapoorvam: financial assistance to orphan children (₹300-1000/month based on age) studying in Kerala. swd.kerala.gov.in.
LIFE Mission: comprehensive housing for landless / homeless / those in unsafe houses.
Mukhyamantri Pension Schemes: ₹1,600/month each for widow / disability / agricultural worker / unmarried women over 50.""",
    },
    {
        "id": "gs-23", "domain": "Government Schemes", "lang": "en",
        "topic": "Punjab and Haryana state schemes",
        "source": "Punjab welfare portal · Haryana Antyodaya SARAL",
        "lastVerifiedOn": "2025-10-15",
        "text": """PUNJAB:
- Aam Aadmi Clinic: free OPD + 80 diagnostic tests at hundreds of mohalla clinics.
- Mukh Mantri Punjab Yuvak Vikas Yojana: skill training + placement support.
- Free electricity up to 300 units/month domestic.
- Shagun Scheme: ₹51,000 to daughters of SC/BPL families at marriage.
- Punjab State Sukhmani Yojana: ₹2 lakh ex-gratia to families of farmers who die.

HARYANA:
- Mukhyamantri Parivar Samridhi Yojana: ₹6,000/year to families with income < ₹1.8 lakh.
- Lado Lakshmi Yojana (announced 2024): ₹2,100/month to all women 18-60. Status check at Antyodaya Saral portal.
- Mukhyamantri Vivah Shagun Yojana: ₹71,000 to SC/ST/BPL daughters' marriages.
- Old Age Samman Allowance: ₹3,000/month for 60+ residents.
- Atal Kisan Mazdoor Canteen: ₹10 meal in select districts.""",
    },
    {
        "id": "gs-24", "domain": "Government Schemes", "lang": "en",
        "topic": "Madhya Pradesh state schemes (Ladli Bahna, Sambal)",
        "source": "MP Ladli Behna · Sambal Yojana (cmladlibahna.mp.gov.in)",
        "lastVerifiedOn": "2025-10-15",
        "text": """Mukhyamantri Ladli Bahna Yojana (2023): ₹1,250/month to women 21-60 from MP with family income < ₹2.5 lakh, no income-tax payer in family, no 4-wheeler. Apply via cmladlibahna.mp.gov.in or Anganwadi.
Sambal 2.0 (Mukhyamantri Jan Kalyan Yojana): for unorganised workers — accident insurance, maternity benefit (₹16,000), antim sanskar (₹5,000), funeral assistance + free education for children.
Ladli Lakshmi Yojana: ₹1.43 lakh in instalments to girl child of MP family (Class 6, 9, 11, 12) plus ₹1 lakh at 21 if unmarried & graduated.
Mukhyamantri Tirth Darshan Yojana: free pilgrimage for senior citizens 60+.
Mukhyamantri Kanya Vivah Yojana: ₹56,000 to BPL families for daughter's marriage.""",
    },
    {
        "id": "gs-21", "domain": "Government Schemes", "lang": "en",
        "topic": "other state schemes (Bihar, Rajasthan, Gujarat, Telangana, AP)",
        "source": "Bihar Mukhyamantri Kanya Utthan · Rajasthan Mukhyamantri Chiranjeevi · Gujarat schemes · Telangana Rythu Bandhu / KCR Kit · AP YSR schemes",
        "lastVerifiedOn": "2025-10-15",
        "text": """Bihar: Mukhyamantri Kanya Utthan Yojana (₹50,000+ across milestones for girl child); Mukhyamantri Vridhajan Pension (₹400/month for 60+ poor); Bihar Student Credit Card (₹4 lakh higher education loan).
Rajasthan: Chiranjeevi Yojana — ₹25 lakh/family/year health cover (premium subsidised, ~₹850/year); Indira Rasoi — ₹8 meal at thousands of kitchens; Mukhya Mantri Anuprati Coaching — free UPSC/RAS coaching for SC/ST/OBC.
Gujarat: Mukhyamantri Amrutum (MA) Yojana — ₹5 lakh/family/year health cover for BPL; Vahli Dikri (₹1.10 lakh in three tranches for girls in BPL family); Namo Lakshmi (₹50,000 over 4 years for girls in Class 9-12).
Telangana: Rythu Bandhu (₹10,000/year/acre to farmers); Aasara (pensions ₹2,016 for elderly + widows + disabled); KCR Kit (cash + maternity kit, ₹13,000 for boy / ₹12,000 for girl); 2BHK housing scheme.
Andhra Pradesh: Amma Vodi (₹15,000/year to mothers per school-going child); YSR Aarogyasri (₹25 lakh health cover); YSR Pension Kanuka; YSR Rythu Bharosa.""",
    },

    # GOVERNMENT SCHEMES — German
    {
        "id": "gs-de-1", "domain": "Government Schemes", "lang": "de",
        "topic": "Krankenversicherung in Deutschland (German health insurance)",
        "source": "SGB V · Bundesministerium für Gesundheit",
        "lastVerifiedOn": "2025-10-15",
        "text": """In Deutschland besteht Versicherungspflicht: jede Person muss krankenversichert sein. Zwei Hauptsysteme:
GKV (gesetzliche Krankenversicherung): pflichtversichert sind Arbeitnehmer mit Bruttogehalt bis 73.800 € (2025). Beitrag ca. 14,6% des Bruttoeinkommens + Zusatzbeitrag (ca. 1,7%). Arbeitgeber zahlt die Hälfte. Familienmitglieder ohne Einkommen mitversichert. Beispiele: TK, Barmer, AOK, DAK.
PKV (private Krankenversicherung): für Selbstständige, Beamte, hohe Einkommen. Beitrag risikoabhängig.
Bürgergeld-Empfänger: über Jobcenter pflichtversichert (Beitrag übernommen).
Studenten: bis 25 in der Familienversicherung kostenfrei, danach studentische Krankenversicherung ca. 100-120 €/Monat.
Notwendige Karte: eGK (elektronische Gesundheitskarte). Für Notfall reicht Versicherungsnachweis.
Telefonische Beratung der Krankenkasse meist 24/7 kostenfrei. Verbraucherzentrale (verbraucherzentrale.de) hilft bei Streitigkeiten.""",
    },

    {
        "id": "gs-de-2", "domain": "Government Schemes", "lang": "de",
        "topic": "Bürgergeld und Sozialleistungen in Deutschland",
        "source": "Bürgergeld-Gesetz · SGB II · Bundesagentur für Arbeit",
        "lastVerifiedOn": "2025-10-15",
        "text": """Bürgergeld (ehem. ALG II / "Hartz IV", seit 2023):
Anspruch: für Erwerbsfähige (15-65) mit Einkommen + Vermögen unterhalb des Bedarfs, Wohnsitz in Deutschland.
Regelbedarf 2025: Single ca. 563 €/Monat + angemessene Miete + Nebenkosten + Heizung. Zuschläge für Kinder, Schwangerschaft, Mehrbedarfe.
Zusätzlich: Krankenversicherung übernommen, Rentenbeiträge, einmalige Leistungen (z.B. Erstausstattung Wohnung, Klassenfahrt).
Antrag: Jobcenter des Wohnortes. Online oder vor Ort. Unterlagen: Ausweis, Mietvertrag, Kontoauszüge, Einkommensnachweise.

Arbeitslosengeld I (ALG I) — Versicherungsleistung:
Anspruch: 12 Monate sozialversicherungspflichtig beschäftigt in den letzten 30 Monaten. Höhe: 60% (oder 67% mit Kind) des Nettoeinkommens. Dauer: 6-24 Monate je nach Alter und Beitragsdauer.
Antrag: Agentur für Arbeit, spätestens 3 Monate vor Beschäftigungsende.

Wohngeld: für Niedrigverdiener (nicht Bürgergeld-Empfänger). Antrag beim Wohngeldamt der Stadt.""",
    },

    # GOVERNMENT SCHEMES — Hindi
    {
        "id": "gs-hi-2", "domain": "Government Schemes", "lang": "hi",
        "topic": "महिलाओं के लिए सरकारी schemes (Hindi)",
        "source": "बेटी बचाओ बेटी पढ़ाओ · सुकन्या समृद्धि · प्रधानमंत्री मातृ वंदना योजना",
        "lastVerifiedOn": "2025-10-15",
        "text": """महिलाओं के लिए मुख्य केंद्रीय schemes:
- Sukanya Samriddhi Yojana (SSY): 10 साल से कम उम्र की बेटी के नाम account। 21 साल या शादी (18 के बाद) तक। ब्याज ~8.2%, tax-free। ₹250 से ₹1.5 लाख/साल जमा।
- Pradhan Mantri Matru Vandana Yojana (PMMVY): पहले बच्चे पर ₹5,000 दो instalments में (+ Janani Suraksha Yojana का ₹1,000)। Anganwadi में apply।
- PM Ujjwala (PMUY): BPL महिलाओं को free LPG connection + पहला refill। ujjwala.petroleum.gov.in।
- Mahila Samman Savings Certificate: 2 साल का deposit ₹2 लाख तक, 7.5% interest। Post office में।
- Pragati Scholarship (AICTE): technical education कर रही लड़कियों को ₹50,000/साल। Income limit ₹8 लाख।
- Beti Bachao Beti Padhao (BBBP): awareness + SSY से जुड़ी हुई।

State-specific:
- Karnataka Gruha Lakshmi: ₹2,000/month
- WB Lakshmir Bhandar: ₹1,000-1,200/month
- Maharashtra Ladki Bahin: ₹1,500/month
- MP Ladli Bahna: ₹1,250/month
- TN Magalir Urimai: ₹1,000/month
- अपने state portal पर check करें।

NCW helpline: 7827170170। Free legal aid: NALSA।""",
    },

    {
        "id": "gs-hi-1", "domain": "Government Schemes", "lang": "hi",
        "topic": "Ayushman Bharat PM-JAY (Hindi)",
        "source": "आयुष्मान भारत PM-JAY · NHA दिशानिर्देश (pmjay.gov.in)",
        "lastVerifiedOn": "2025-10-15",
        "text": """Pradhan Mantri Jan Arogya Yojana (PM-JAY) — दुनिया की सबसे बड़ी health-assurance scheme। प्रति परिवार ₹5 लाख/साल का free इलाज सरकारी + private empanelled hospitals में।
Eligibility:
- SECC 2011 की rural deprivation criteria (कच्चे घर, बेसहारा परिवार, SC/ST, भूमिहीन मज़दूर आदि)।
- शहरी 11 occupational categories (कूड़ा बीनने वाले, घरेलू कामगार, रिक्शा चालक आदि)।
- 70+ senior citizens — अब आय की कोई शर्त नहीं (PM-JAY Vandana, 2024)।

Eligibility कैसे check करें:
- pmjay.gov.in → "Am I Eligible?" — mobile + state डालें।
- Toll-free: 14555 या 1800-111-565।

Card कैसे बनवाएं:
- Common Service Centre (CSC) पर जाएं।
- Aadhaar + ration card लेकर जाएं।
- e-card free मिलेगा। Physical card भी free।

Use कैसे करें: empanelled hospital में Ayushman card दिखाएं — cashless treatment, कोई पैसा नहीं देना।""",
    },

    {
        "id": "lg-25", "domain": "Legal", "lang": "en",
        "topic": "Section 498A IPC / BNS 85-86 — cruelty by husband or in-laws",
        "source": "Bharatiya Nyaya Sanhita 2023 §§85–86 (formerly IPC §498A)",
        "lastVerifiedOn": "2025-10-15",
        "text": """Section 498A IPC (now BNS Section 85-86) — punishes a husband or his relative who subjects the wife to cruelty.
Cruelty defined: (a) any wilful conduct likely to drive the woman to suicide or cause grave injury / danger to life or health (mental or physical), OR (b) harassment to coerce her or her relatives to meet unlawful demand for dowry / property.
Punishment: up to 3 years + fine. Cognizable and non-bailable (police can arrest without warrant).
SC guidelines (Arnesh Kumar, 2014): police MUST follow Section 41A CrPC — issue notice and only arrest if absolutely necessary (to prevent automatic arrests).
Often filed alongside Dowry Prohibition Act 1961 (Section 3 — giving/taking dowry, Section 4 — demand for dowry).
For civil remedies → PWDVA 2005 (lg-5).
NCW helpline 7827170170. Free legal aid via DLSA.""",
    },
    {
        "id": "lg-26", "domain": "Legal", "lang": "en",
        "topic": "adoption — Hindu Adoption Act + CARA",
        "source": "Hindu Adoptions and Maintenance Act 1956 · Juvenile Justice Act 2015 · CARA guidelines",
        "lastVerifiedOn": "2025-10-15",
        "text": """Two routes for adoption in India:
1. Hindu Adoption and Maintenance Act 1956 — for Hindus, Sikhs, Jains, Buddhists. Conditions (Section 6-11): adoptive parent must be major & sound mind; if married, both spouses' consent needed; one parent must be at least 21 years older than child; max 1 child of each gender.
2. CARA — Juvenile Justice Act 2015 — for non-Hindus, inter-religious, or anyone preferring legal-formal route. Single window: cara.wcd.gov.in.
CARA process: register → home study (45 days) → referral of child → pre-adoption foster care → court order → follow-up visits.
In-country adoption priority. Inter-country only after attempts in India fail.
Free legal aid via DLSA. NEVER pay middlemen — private adoptions are illegal under Section 80 of JJ Act.""",
    },
    {
        "id": "lg-27", "domain": "Legal", "lang": "en",
        "topic": "Evidence Act / Bharatiya Sakshya Adhiniyam — what counts as proof",
        "source": "Bharatiya Sakshya Adhiniyam 2023 (replaces Indian Evidence Act 1872)",
        "lastVerifiedOn": "2025-10-15",
        "text": """Indian Evidence Act 1872, now replaced by Bharatiya Sakshya Adhiniyam (BSA) 2023 — in force from 1 July 2024.
Types of evidence: oral (witness testimony), documentary (writings), electronic (emails, WhatsApp, CCTV).
Electronic evidence — Section 65B IEA / Section 63 BSA: must be accompanied by a certificate identifying the device, integrity of data, and certifying authority. Without 65B certificate, electronic evidence is generally inadmissible (Anvar PV vs PK Basheer, 2014).
Hearsay generally not admissible (Section 60), with exceptions (dying declarations, res gestae).
Presumptions: (a) of innocence in criminal cases (prosecution must prove beyond reasonable doubt), (b) certain "deemed proven" facts (Section 4).
For digital evidence: keep original device, take hash, get cyber expert opinion.""",
    },
    {
        "id": "lg-28", "domain": "Legal", "lang": "en",
        "topic": "Limitation Act — deadlines for filing legal action",
        "source": "Limitation Act 1963",
        "lastVerifiedOn": "2025-10-15",
        "text": """Limitation Act 1963 — fixed deadlines to file most civil cases. If you miss them, the court can't entertain the case (with exceptions).
Common limitations:
- 3 years: suit for money based on contract, breach of contract, recovery of dues.
- 12 years: suit for possession of immovable property based on title.
- 30 years: suit by mortgagor to redeem mortgaged property.
- 1 year: suit for accounts, damages for defamation, malicious prosecution.
- 90 days: appeal from a decree of a subordinate court to High Court.
- 30 days: appeal from a decree of a subordinate court to District Court.
Criminal cases have separate limitations (Section 468 CrPC / Section 514 BNSS):
- 6 months for offences with imprisonment up to 1 year.
- 1 year for offences up to 3 years.
- 3 years for offences from 3 years.
- No limit for offences > 3 years or fine > certain limit, AND for offences against women / children under POCSO etc.
Section 5: courts can condone delay on "sufficient cause" — but discretionary, not automatic.""",
    },
    {
        "id": "lg-hi-3", "domain": "Legal", "lang": "hi",
        "topic": "घरेलू हिंसा — कानूनी मदद (Hindi)",
        "source": "घरेलू हिंसा से महिलाओं का संरक्षण अधिनियम 2005 · IPC §498A / BNS §§85–86",
        "lastVerifiedOn": "2025-10-15",
        "text": """घरेलू हिंसा से बचाव अधिनियम 2005 (PWDVA) — किसी भी महिला (पत्नी, साथी, बहन, बेटी, माँ) को physical, sexual, verbal, emotional, या economic abuse से कानूनी सुरक्षा देता है।
तुरंत मदद के लिए:
- 112 — कोई भी emergency
- 1091 — Women helpline
- 181 — Sakhi
- 7827170170 — National Commission for Women
- 1098 — Child helpline

कानूनी process:
- हर district में Protection Officer (PO) नियुक्त है — PO से contact करें।
- Magistrate court में application — DIR (Domestic Incident Report) के आधार पर।
- मिलने वाले reliefs (Section 18-22):
  - Protection Order — abuse रोकने का आदेश
  - Residence Order — saunsural ghar में रहने का हक
  - Monetary Relief — maintenance, medical खर्च
  - Custody Order — बच्चों की
  - Compensation
- 60 दिन में case decide करने का निर्देश है।
- Free वकील: NALSA (nalsa.gov.in), DLSA।

Sakhi One Stop Centre हर district में: medical + legal + police + psychological + 5 दिन shelter — सब free।""",
    },

    # ═════════════════════════════════════════════════════════════════════
    # SAFETY (English)
    # ═════════════════════════════════════════════════════════════════════
    {
        "id": "sf-1", "domain": "Safety", "lang": "en",
        "topic": "emergency helplines India",
        "source": "MHA · National Emergency Helpline Directory (112)",
        "lastVerifiedOn": "2025-10-15",
        "text": """Universal helplines:
112 — unified emergency (police + fire + ambulance + disaster).
100 — Police. 101 — Fire. 102 — Ambulance (free). 108 — Emergency Response Service (free most states).
1091 — Women. 1098 — Child. 1930 — Cyber-fraud (financial).
1800-11-2200 — Tourist. 14567 — Senior Citizen (Elderline). 181 — Sakhi (women). 14416 — Tele-MANAS (mental health).
139 — Indian Railways (Mahila). 1078 — NDRF Disaster.
112 India app: SOS via shake. Deaf/mute: SMS to 100/112.""",
    },
    {
        "id": "sf-2", "domain": "Safety", "lang": "en",
        "topic": "cybercrime reporting",
        "source": "MHA · National Cybercrime Reporting Portal (cybercrime.gov.in · 1930)",
        "lastVerifiedOn": "2025-10-15",
        "text": """1930 — National Cyber Crime Helpline. CALL IMMEDIATELY for financial fraud — can freeze transferred amount within "golden hour" (~1 hour).
cybercrime.gov.in — National Cyber Crime Reporting Portal. Categories: financial fraud, social media abuse, CSAM, hacking, ransomware, identity theft.
Steps: (1) Call 1930 within the hour. (2) Report to bank — RBI Limited Liability allows full reversal if reported within 3 working days. (3) File complaint on cybercrime.gov.in — keep ack number. (4) Local FIR if needed.
Non-consensual intimate images: cybercrime.gov.in → "Report Women/Child" — anonymous allowed.""",
    },
    {
        "id": "sf-3", "domain": "Safety", "lang": "en",
        "topic": "women's safety",
        "source": "NCW helplines · MWCD One Stop Centres · 181 women helpline",
        "lastVerifiedOn": "2025-10-15",
        "text": """112 unified / 1091 Women's / 181 Sakhi.
112 India app: shake phone 3 times for SOS to nearest police + nominated contacts.
One Stop Centre (Sakhi) — every district, 24x7 medical + police + legal + psychological + short-stay shelter (5 days).
Himmat App (Delhi), Suraksha (UP), Pukar (Mumbai) — state SOS apps.
Public transport harassment: photo/video, dial 112 or 1091, vehicle number, complaint. Railways Mahila 139.
Workplace harassment: ICC under POSH, or She-Box (shebox.wcd.gov.in).
Stalking: IPC 354D / BNS 78 — file FIR. Online: cybercrime.gov.in.""",
    },
    {
        "id": "sf-4", "domain": "Safety", "lang": "en",
        "topic": "fire emergency",
        "source": "National Disaster Management Authority (NDMA) · National Building Code",
        "lastVerifiedOn": "2025-10-15",
        "text": """(1) Raise the alarm. (2) Call 101 or 112. Clear address and floor. (3) Get out fast. Stairs, not lifts. Close (don't lock) doors behind you. (4) Stay low — smoke rises. Damp cloth over nose/mouth. (5) If trapped: room with window, seal door gaps with wet cloth, signal. (6) If clothes catch fire: STOP, DROP, ROLL. (7) STAY OUT — don't re-enter.
Prevention: smoke detector on every floor, ABC fire extinguisher in kitchen, no overloaded sockets, gas cylinder regulator closed at night.
NDRF: 011-26701728.""",
    },
    {
        "id": "sf-5", "domain": "Safety", "lang": "en",
        "topic": "medical emergency",
        "source": "American Heart Association CPR guidelines · 108 ambulance protocols",
        "lastVerifiedOn": "2025-10-15",
        "text": """Call 108 or 102. 112 also dispatches medical.
- Heart attack (chest pain, breathlessness, sweating): sit, loosen clothing, one aspirin 300mg to chew if not allergic.
- Stroke (sudden one-side weakness, slurred speech, facial drooping): note symptom-start time (4.5-hour window). No food/water/medication.
- Severe bleeding: firm direct pressure with clean cloth. Don't remove — add layers. Raise wound above heart.
- Choking: Heimlich — fist between navel and ribcage, thrust in + up. Infants <1 yr: 5 back blows + 5 chest thrusts.
- Unconscious but breathing: recovery position on side.
- Not breathing: CPR — 30 compressions (centre of chest, 5-6 cm deep, 100-120/min), 2 rescue breaths, repeat.""",
    },
    {
        "id": "sf-6", "domain": "Safety", "lang": "en",
        "topic": "domestic violence (immediate safety)",
        "source": "NCW 7827170170 · Sakhi One Stop Centres · 181 women helpline",
        "lastVerifiedOn": "2025-10-15",
        "text": """(1) Call 112 / 100 / 1091. Or 181 (Sakhi). (2) Can't speak openly → SMS to 112 with address. (3) Safer room with a lock. (4) "Go bag": ID copies, cash, medication, clothes, charger. (5) Tell one trusted person. (6) After immediate danger, contact Sakhi One Stop Centre — shelter 5 days, medical, police, legal. (7) NCW: 7827170170.
For PWDVA legal procedure, see Umang's tab.""",
    },
    {
        "id": "sf-7", "domain": "Safety", "lang": "en",
        "topic": "natural disaster preparedness",
        "source": "NDMA preparedness guidelines · IMD warnings",
        "lastVerifiedOn": "2025-10-15",
        "text": """72-hour emergency kit: water (4L/person), non-perishable food, torch, batteries, first-aid, medicines, whistle, power-bank, cash, copies of IDs in waterproof bag.
Apps: NDMA, Sachet — early warnings.
Earthquake: Drop, Cover, Hold — under sturdy desk. Avoid windows/mirrors/heavy furniture. After: evacuate to open ground.
Flood: higher ground. Don't walk/drive through moving water (6 inches knocks down, 2 ft floats a car). Don't touch wet electrical.
Cyclone: stay indoors, away from windows. Follow IMD/SDMA.
NDRF: 011-26701728.""",
    },
    {
        "id": "sf-8", "domain": "Safety", "lang": "en",
        "topic": "online financial fraud",
        "source": "I4C (Indian Cyber Crime Coordination Centre) · cybercrime.gov.in · 1930",
        "lastVerifiedOn": "2025-10-15",
        "text": """UPI/OTP fraud: never share OTP, PIN, CVV — banks never ask. If you did, call 1930 immediately. Block card via bank app or 24x7 helpline.
Loan-app harassment: illegal apps. Stop paying (illegal per RBI Digital Lending guidelines). Report on cybercrime.gov.in + RBI Sachet (sachet.rbi.org.in).
Job-offer scam: never pay upfront. Verify on MCA21.
Investment / crypto / WhatsApp tip groups: must be SEBI-registered advisor. Report at scores.sebi.gov.in.
SIM-swap: sudden signal loss = call telco then bank.
Defaults: 2FA on email/bank, UPI Lite for small payments, debit transaction limits.""",
    },
    {
        "id": "sf-9", "domain": "Safety", "lang": "en",
        "topic": "child safety and POCSO",
        "source": "Protection of Children from Sexual Offences Act 2012 · POCSO e-Box (NCPCR)",
        "lastVerifiedOn": "2025-10-15",
        "text": """POCSO Act 2012 — child = under 18. All sexual offences punishable; gender-neutral.
Mandatory reporting (Section 19); failure to report itself an offence (Section 21). Report to Special Juvenile Police Unit or local police. CHILDLINE 1098.
Online crimes against children: cybercrime.gov.in → "Report Women/Child" — anonymous allowed.
School safety: ICC + grievance redressal as per CBSE & NCPCR.
Missing child: file FIR within 24 hours (SC-mandatory), upload at trackthemissingchild.gov.in.
Adoption: CARA (cara.wcd.gov.in) is the only legal channel.""",
    },
    {
        "id": "sf-10", "domain": "Safety", "lang": "en",
        "topic": "travel safety",
        "source": "MEA travel advisories · Indian missions abroad",
        "lastVerifiedOn": "2025-10-15",
        "text": """Before going: share live location with trusted contact, copy ID + tickets to email/cloud, note 112 (national).
Accommodation: verified platforms with women's reviews. Check door lock + emergency exit on arrival.
Transport: pre-paid taxis at airports/stations. Share trip via Ola/Uber. Note vehicle number. Front seat for solo night rides.
Trains: Mahila 139, RPF 182.
Night: well-lit, phone in hand, no earphones in unfamiliar places.
If followed: enter a shop / hotel lobby; call 112; ask loudly + specifically for help.
Apps: 112 India, bSafe, Himmat (Delhi).""",
    },
    {
        "id": "sf-12", "domain": "Safety", "lang": "en",
        "topic": "acid attack first response",
        "source": "Laxmi v UoI (2014 SC) · MoHFW acid-attack management guidelines",
        "lastVerifiedOn": "2025-10-15",
        "text": """If acid is thrown on someone:
(1) IMMEDIATELY pour LARGE amounts of cool / room-temperature water over the affected area for at least 20-30 minutes. Use a tap, bucket, hose — anything continuous. Do NOT rub. Do NOT use creams, milk, oils, baking soda — water only.
(2) Remove contaminated clothing carefully (cut, don't pull over head) while still rinsing.
(3) Cover with clean, dry cloth or cling film. Don't pop blisters.
(4) Call 108 / 112 for ambulance. Specify "acid attack" — they should take to a hospital with burns unit.
Legal: IPC 326A / 326B (now BNS 124-125). 10 years to life imprisonment + ₹10 lakh fine. Acid sale regulated by SC order (2013) — only licensed sellers, buyer ID required.
Survivor support: Stop Acid Attacks (stopacidattacks.org), Chhanv Foundation. Free legal aid via DLSA. ₹3 lakh minimum compensation under SC guidelines + state-specific top-ups.""",
    },
    {
        "id": "sf-13", "domain": "Safety", "lang": "en",
        "topic": "road accident first response + Good Samaritan Law",
        "source": "Motor Vehicles (Amendment) Act 2019 §134A · SaveLIFE Foundation guidelines",
        "lastVerifiedOn": "2025-10-15",
        "text": """If you witness an accident:
(1) Call 108 (ambulance) or 112 immediately. Give clear location.
(2) Move victim ONLY if there's danger (fire, traffic). Otherwise wait for paramedics — spinal injury risk.
(3) Control severe bleeding with firm pressure using any clean cloth.
(4) Keep them warm, talk to them, keep airway clear.
(5) Don't give water — risk of aspiration if surgery needed.
Good Samaritan Law (Supreme Court 2016 + MV Amendment Act 2019):
- You are NOT legally obliged to give your name or address to police.
- Cannot be detained or harassed.
- No civil / criminal liability for any harm during help given in good faith.
- Hospitals MUST provide immediate care, cannot demand upfront payment.
Solatium Scheme: ₹2 lakh for death, ₹50,000 grievous injury for hit-and-run victims (paid by central govt).""",
    },
    {
        "id": "sf-14", "domain": "Safety", "lang": "en",
        "topic": "animal attack — dog bite, snake bite",
        "source": "WHO rabies post-exposure prophylaxis · ICMR snakebite management 2024",
        "lastVerifiedOn": "2025-10-15",
        "text": """Dog bite:
(1) Wash the wound thoroughly with running water + soap for 15 minutes. This reduces rabies virus load significantly.
(2) Apply antiseptic (povidone-iodine, alcohol). Don't suture immediately.
(3) Go to nearest hospital / government dispensary within 24 hours — Anti-Rabies Vaccine (ARV) free at govt hospitals under National Rabies Control Programme. Schedule: 5 doses (days 0, 3, 7, 14, 28) for unvaccinated; 2 doses (0, 3) for previously vaccinated.
(4) Rabies Immunoglobulin (RIG) for Category III bites (broken skin, mucous membrane contact).
(5) Tetanus booster if last shot > 5 years.

Snake bite:
(1) Keep victim still and calm — movement spreads venom.
(2) Remove tight items (rings, watches) from bitten limb.
(3) DO NOT cut, suck, tourniquet, ice, or use traditional remedies — these worsen outcome.
(4) Call 108. Get to a hospital with Anti-Snake Venom (ASV) within 1-2 hours.
(5) If possible, take photo of snake (DON'T try to kill it). Identification not strictly needed — polyvalent ASV covers 4 common Indian species (cobra, krait, Russell's viper, saw-scaled viper).""",
    },
    {
        "id": "sf-15", "domain": "Safety", "lang": "en",
        "topic": "elder abuse and senior citizen safety",
        "source": "Maintenance and Welfare of Parents and Senior Citizens Act 2007 · Elderline 14567 · HelpAge India",
        "lastVerifiedOn": "2025-10-15",
        "text": """Elder abuse includes: physical / financial / emotional / sexual abuse + neglect. Often by family caregivers or hired help.
Signs: unexplained bruises, sudden money / property transfers, isolation from family, fear around specific people, malnutrition / poor hygiene despite resources.
Reporting:
- Elderline 14567 (24x7 across India).
- Local police FIR — abuse covered under IPC / BNS general assault sections + Maintenance and Welfare of Parents and Senior Citizens Act 2007 (lg-20).
- Section 24 of MWPSC Act — abandoning a senior with intent → up to 3 months / fine.
- HelpAge India: 1800-180-1253 (legal + social support).
Senior citizen registration with local police: most states have a senior-citizen cell — register, get periodic wellness checks, panic-button service.
Online fraud particularly targets seniors — train them: never share OTP, never click "your account is blocked" links, prefer in-person banking.""",
    },

    # SAFETY — German
    {
        "id": "sf-11", "domain": "Safety", "lang": "de",
        "topic": "Notfallnummern in Deutschland (German emergency numbers)",
        "source": "Bundesministerium des Innern · 112 / 110 · Hilfetelefon 08000 116 016",
        "lastVerifiedOn": "2025-10-15",
        "text": """Notfallnummern in Deutschland:
112 — Europaweite Notrufnummer (Feuerwehr + Rettungsdienst). Funktioniert auch im EU-Ausland.
110 — Polizei.
116 117 — Ärztlicher Bereitschaftsdienst (nicht-lebensbedrohliche Fragen außerhalb der Praxiszeiten).
116 016 — Hilfetelefon Gewalt gegen Frauen (24/7, kostenlos, mehrsprachig).
0800 111 0 111 — Telefonseelsorge (24/7, kostenlos).
116 111 — Nummer gegen Kummer (Kinder/Jugendliche).
19222 — Krankentransport (nicht für Notfälle).
110 oder 112 funktionieren auch ohne SIM-Karte und ohne Guthaben.""",
    },
    {
        "id": "sf-de-3", "domain": "Safety", "lang": "de",
        "topic": "Kinderschutz und häusliche Gewalt in Deutschland (German)",
        "source": "Hilfetelefon Gewalt gegen Frauen 08000 116 016 · Nummer gegen Kummer 116 111",
        "lastVerifiedOn": "2025-10-15",
        "text": """Bei häuslicher Gewalt oder Kindeswohlgefährdung in Deutschland:
- 110 — Polizei (sofortige Hilfe bei akuter Gefahr).
- 116 016 — Hilfetelefon Gewalt gegen Frauen (24/7, kostenlos, anonym, 18 Sprachen).
- 0800 22 55 530 — Hilfetelefon Sexueller Missbrauch (anonym).
- 116 111 — Nummer gegen Kummer (Kinder/Jugendliche 14-20 Uhr, Mo-Sa).
- 0800 111 0 550 — Elterntelefon.
- Frauenhäuser: bundesweite Liste auf frauenhauskoordinierung.de. Aufnahme 24/7, kostenfrei.
- Jugendamt: jede Stadt — bei Verdacht auf Kindeswohlgefährdung sofort melden (auch anonym möglich). Pflicht zur Meldung für Lehrer*innen, Ärzt*innen, Erzieher*innen (§ 8a SGB VIII).
- Gewaltschutzgesetz: Schutzanordnung (Annäherungs-/Kontaktverbot) beim Familiengericht beantragen. Notfalls Eilantrag, innerhalb von Stunden möglich.
- Beratung: Pro Familia, Caritas, Diakonie, Weisser Ring (116 006).""",
    },
    {
        "id": "sf-de-2", "domain": "Safety", "lang": "de",
        "topic": "Cybercrime in Deutschland (German)",
        "source": "Bundeskriminalamt Cybercrime portal · Verbraucherzentrale",
        "lastVerifiedOn": "2025-10-15",
        "text": """Internetkriminalität in Deutschland:
- Phishing, Betrug, Identitätsdiebstahl → Online-Anzeige bei der Polizei: jede Landespolizei hat ein eigenes Online-Portal (z.B. polizei.berlin.de, polizei.nrw, polizei-bayern.de).
- Bei Geldverlust: SOFORT Bank anrufen, Karte / Konto sperren.
- BSI (Bundesamt für Sicherheit in der Informationstechnik): bsi.bund.de — kostenlose Beratung, Warnungen, Tipps. Hotline 0800 274 1000.
- Verbraucherzentrale: verbraucherzentrale.de — Beschwerden + Rechtsberatung.
- Strafanzeige bei jedem Polizeirevier oder online. Wichtig: Screenshots, E-Mails, Transaktionsdetails als Beweis sichern.
- Bei Stalking / Cybermobbing: Weisser Ring (weisser-ring.de) — Hilfe für Opfer von Straftaten, 116 006.""",
    },

    {
        "id": "sf-16", "domain": "Safety", "lang": "en",
        "topic": "heatwave and extreme weather safety",
        "source": "NDMA heatwave action plan · IMD red/orange alerts",
        "lastVerifiedOn": "2025-10-15",
        "text": """Heatwave precautions (when temperature crosses 40°C in plains, 30°C in hills):
- Avoid going out 12 PM – 4 PM. If you must, cover head with cap / umbrella / cloth, wear light cotton.
- Drink water frequently even if not thirsty. Use ORS, lassi, lemon water, coconut water. Avoid alcohol, caffeine, sugary drinks.
- Recognise heat-stroke: high body temp + hot dry skin + confusion + rapid pulse + seizures. CALL 108 immediately. Move to shade, remove tight clothing, cool with wet cloth + fan, give sips of water if conscious.
- Heat exhaustion (precursor): heavy sweating, weakness, dizziness, nausea. Rest in cool place, fluids, cool compress.
- Never leave anyone (especially children, elderly, pets) in a parked car.
- Check on elderly neighbours and outdoor workers (construction, street vendors, delivery agents).
- Weather alerts: IMD Mausam app (mausam.imd.gov.in), Sachet app for state warnings.

Cold wave: layer clothes, sleep in heated room (carbon-monoxide risk from indoor coal/gas — keep ventilation). Watch for hypothermia (shivering, drowsiness, slurred speech).""",
    },
    {
        "id": "sf-17", "domain": "Safety", "lang": "en",
        "topic": "lost passport / documents abroad",
        "source": "Ministry of External Affairs · Indian embassy passport-loss SOP",
        "lastVerifiedOn": "2025-10-15",
        "text": """If you lose your passport abroad:
(1) File a police report (FIR / "lost certificate") at the local police station. Get a copy — needed for emergency replacement.
(2) Contact the nearest Indian Embassy / High Commission / Consulate. List at mea.gov.in. Carry ID copy / scan if available.
(3) Apply for an Emergency Certificate (EC) — single-journey document to return to India. Or apply for a duplicate passport at the embassy (re-issue) if you intend to continue travel. Both possible online via Madad portal (madad.gov.in).
(4) Inform your bank (cards linked to passport ID), travel insurance, and airline.
(5) Block cards via bank app. Use a backup card / cash.
24x7 MEA helpline for distressed Indians abroad: country-specific numbers + central number +91 11 2301 7176. Madad portal complaint takes 1-3 days.
Future: always keep a digital copy in email + DigiLocker (digilocker.gov.in) — passport, Aadhaar, PAN.""",
    },

    # SAFETY — Hindi
    {
        "id": "sf-hi-1", "domain": "Safety", "lang": "hi",
        "topic": "Emergency numbers (Hindi)",
        "source": "MHA · 112 / 100 / 101 / 102 / 108 / 1091 / 1098 / 1930 (आधिकारिक हेल्पलाइन)",
        "lastVerifiedOn": "2025-10-15",
        "text": """India में emergency में call करने के numbers (हर phone से, बिना balance के भी):
112 — Universal emergency (Police + Fire + Ambulance + Disaster) — 1 ही number से सब कुछ।
100 — सिर्फ Police
101 — Fire / आग
102 — Ambulance / एम्बुलेंस (free)
108 — Emergency Response (free in most states)
1091 — Women helpline
1098 — Child helpline (CHILDLINE)
1930 — Cyber fraud (पैसे की चोरी online — तुरंत call करें, 1 hour में पैसे freeze हो सकते हैं)
14416 — Tele-MANAS (Mental health, 20+ भाषाएं, 24x7 free)
14567 — Senior citizen helpline
181 — Sakhi (women)
139 — Railway helpline (Mahila + general)
116 — Highway emergency

112 India app — phone को 3 बार हिलाने पर SOS automatic चला जाएगा।
Deaf/mute लोग: 100/112 पर SMS भेज सकते हैं।""",
    },
]

CHUNKS = CORE_CHUNKS + EXPANSION_CHUNKS
