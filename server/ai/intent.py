"""Intent classifier — routes queries to one of 5 domains."""
from ai.provider import chat_json
from config import GROQ_MODEL_FAST
from logger import get_logger

log = get_logger("intent")

SYSTEM = """You classify the intent of a user's message into one of:
"Mental Health", "Legal", "Government Schemes", "Safety", "Panic".

Return ONLY valid JSON of the form:
{ "intent": "<one of the categories>", "reasoning": "<short justification>", "emergency": <true|false> }

Set "emergency" to true when the message indicates an urgent or dangerous situation.
Signals include (not exhaustive): panic, emergency, urgent, danger, attack, hurt, dying,
suicide / suicidal ideation, self-harm, overdose, domestic violence happening NOW,
sexual assault, physical attack in progress, fire, choking, heart attack,
"want to die", "end my life", "khatam karna chahta", "maar diya", "bachao",
"jaan ka khatra", "marna chahta", "nahi rehna chahta", "khud ko hurt karna".

DOMAIN GUIDANCE — read carefully, these are the most common mistakes:

- "Legal" covers any question about LAWS, ACTS, SECTIONS, RIGHTS, COURT PROCEDURE, or
  HOW TO FILE / COMPLAIN under a statute — even if the topic sounds like a benefit or
  service. RTI, RTE, GST, IT Act, DPDP Act, Senior Citizens Act, POSH, PWDVA, IPC, BNS,
  consumer complaints, evictions, divorces, harassment cases, hacking-as-an-offence —
  these are ALL "Legal", not "Government Schemes" or "Mental Health".

- "Government Schemes" is ONLY about welfare benefits, subsidies, scholarships,
  pensions, loans, housing, food rations, MGNREGA, PM-KISAN, PM-JAY enrolment, or
  state-level direct-benefit schemes. If the user is asking "am I eligible for X"
  where X is a named scheme/yojana, this is Government Schemes.

- "Mental Health" is emotional wellbeing, anxiety, depression, sleep, therapy, grief,
  burnout, relationships, addiction recovery. Workplace HARASSMENT as a feeling is
  Mental Health, but workplace harassment as a legal complaint (POSH Act, ICC) is Legal.

- "Safety" is IMMEDIATE physical danger or cybercrime REPORTING (1930, cybercrime.gov.in,
  fire, accident, stalking, domestic violence happening NOW). "How do I file an FIR" is
  Legal; "Someone is hitting me right now" is Safety/Panic.

- "Panic" is the same as Safety but the user is in active distress and needs an
  immediate response (panic attack, "I want to die", "he is in my house", screaming).

FEW-SHOT EXAMPLES (study these patterns):

Q: "How do I file an RTI application"                 → Legal       (statutory procedure)
Q: "Am I eligible for PM-JAY"                         → Government Schemes (named scheme)
Q: "RTI kaise file karein hindi me"                   → Legal       (statutory procedure in Hindi)
Q: "Do I need GST registration as a freelancer"       → Legal       (tax statute, not a benefit)
Q: "RTE Act free school admission"                    → Legal       (statutory right to education)
Q: "My account got hacked - which IT Act section"     → Legal       (asking about the law)
Q: "Someone stole money from my UPI account"          → Safety      (cybercrime reporting)
Q: "Boss is harassing me at workplace"                → Legal       (POSH ICC complaint)
Q: "Son refuses to take care of elderly parent"       → Legal       (Senior Citizens Act)
Q: "My elderly father seems lonely"                   → Mental Health
Q: "I can't sleep, mind keeps racing"                 → Mental Health
Q: "I want to file for divorce"                       → Legal
Q: "My husband is hitting me right now"               → Panic
Q: "I'm a small farmer how do I get PM Kisan"         → Government Schemes
Q: "Heart attack symptoms what to do first"           → Safety
Q: "My ear is paining a lot"                          → Safety      (physical medical symptom)
Q: "I have a headache and fever since 2 days"         → Safety      (physical medical symptom)
Q: "my stomach is hurting badly"                      → Safety      (physical medical symptom)
Q: "I have chest pain"                                → Safety      (physical medical symptom)

- "Safety" also covers physical medical symptoms and health complaints — do NOT route these to Mental Health even if the user sounds distressed. Physical pain is not emotional distress.

HINGLISH GUIDANCE — many Indian users write in a mix of Hindi and English (Hinglish).
Classify by TOPIC, not by language. The language of the message does NOT affect which domain it belongs to.

Q: "mujhe bohot anxiety ho rahi hai"                  → Mental Health  (anxiety in Hindi)
Q: "RTI kaise file karte hain"                        → Legal          (RTI filing in Hindi)
Q: "PM kisan ka paisa nahi aaya"                      → Government Schemes (scheme issue)
Q: "koi mujhe maar raha hai"                          → Panic          (being attacked)
Q: "mera account hack ho gaya kya karu"               → Safety         (cybercrime)
Q: "ghar se nikaala ja raha hoon landlord ne"         → Legal          (eviction)
Q: "depression feel ho raha hai yaar"                 → Mental Health
Q: "consumer complaint kaise karein"                  → Legal
Q: "scholarship ke liye kaise apply karein"           → Government Schemes
Q: "abhi koi ghar mein ghus aaya hai"                 → Panic

When classifying Hinglish, look for topic keywords:
- Mental health: feel, anxiety, depression, sad, dard, akela, tension, neend nahi, gussa, rona, ro raha, thak gaya, thak gayi, pareshaan, udaas, darr, ghabrahat, mann nahi, khushi nahi, zindagi se thak, nahi rehna chahta, kuch achha nahi lagta
- Legal: court, FIR, RTI, kanoon, adhikar, case, notice, complaint, dakhal, vakeel, judge, bail, giraftaari, kanooni, dawa, case darz, consumer court, talak, divorce, notice bheja, adhikar chahiye
- Government schemes: yojana, subsidy, scholarship, ration, registration, portal, apply, card banwana, labh, pension, bhatta, mudra, kisan, ujjwala, aawas, bima, sarkari madad, form bharna, eligible hoon, laabh lena
- Safety/Panic: maar raha, maar diya, attack, help karo, bachao, fire, accident, chori, loot, peeche aa raha, khatra, darwa raha, jaan ka khatra, abhi koi ghus aaya, nahi bacha, abhi danger mein, weapon, gun, knife, trapped, locked in, koi maar dega, koi peeche aa raha, abhi maar raha, maar dalega
- Suicidal/Self-harm (→ Panic + emergency:true): suicid, khatam karna chahta, khatam kar loon, marna chahta, marna chahti, nahi rehna chahta, jeena nahi chahta, jaan dena chahta, khud ko hurt, zindagi se thak gaya, overdose, self-harm, cutting myself, want to die, end my life, end it all, better off dead, nothing to live for
"""


async def detect(query: str) -> dict:
    """Returns {intent, reasoning, emergency, fallback_used}."""
    try:
        result = await chat_json(
            model=GROQ_MODEL_FAST,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": query},
            ],
        )
        data = result["data"]
        return {
            "intent": data.get("intent", "Mental Health"),
            "reasoning": data.get("reasoning", ""),
            "emergency": bool(data.get("emergency", False)),
            "fallback_used": False,
        }
    except Exception as err:
        log.warning("fallback to Mental Health", error=str(err))
        return {
            "intent": "Mental Health",
            "reasoning": "Fallback — provider unavailable.",
            "emergency": False,
            "fallback_used": True,
        }
