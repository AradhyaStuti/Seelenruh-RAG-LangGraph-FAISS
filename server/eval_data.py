"""Labelled query set and the frozen DEV / TEST_HELDOUT split.

`gold` is a list of chunk IDs; any of them landing top-1 counts as P@1.
Stratified 50/50 split (seed below). DEV is used for threshold tuning,
TEST_HELDOUT for headline numbers.
"""

TEST_CASES = [
    # ===== Usha / Mental Health (25) =====
    {"q": "I can't sleep, my mind keeps racing all night",        "gold": ["mh-3", "mh-x-98"],                      "domain": "Mental Health"},
    {"q": "I have constant low mood and lost interest",           "gold": ["mh-2", "mh-x-14"],                      "domain": "Mental Health"},
    {"q": "My heart is pounding and I can't breathe - panic",     "gold": ["mh-9", "mh-x-02"],                      "domain": "Mental Health"},
    {"q": "Where do I find a therapist in India",                 "gold": ["mh-4", "mh-x-87", "mh-x-92"],           "domain": "Mental Health"},
    {"q": "I'm completely burned out from work",                  "gold": ["mh-5"],                                 "domain": "Mental Health"},
    {"q": "I'm constantly anxious about my exams",                "gold": ["mh-10"],                                "domain": "Mental Health"},
    {"q": "I lost my mother and can't move on",                   "gold": ["mh-7", "mh-x-52", "mh-x-148"],          "domain": "Mental Health"},
    {"q": "I feel scared talking to people in groups",            "gold": ["mh-11", "mh-x-12"],                     "domain": "Mental Health"},
    {"q": "We keep fighting about the same things",               "gold": ["mh-6", "mh-x-72"],                      "domain": "Mental Health"},
    {"q": "Aaj subah se mood bahut down hai",                     "gold": ["mh-2", "mh-x-127", "mh-x-14"],          "domain": "Mental Health"},
    {"q": "What is anxiety and how do I cope with it",            "gold": ["mh-1", "mh-20", "mh-x-01"],             "domain": "Mental Health"},
    {"q": "Basic self care when I feel overwhelmed",              "gold": ["mh-8"],                                 "domain": "Mental Health"},
    {"q": "I keep washing my hands and checking the lock",        "gold": ["mh-14"],                                "domain": "Mental Health"},
    {"q": "I had a baby and feel hopeless and disconnected",      "gold": ["mh-15", "mh-x-18", "mh-x-19"],          "domain": "Mental Health"},
    {"q": "I drink every day and can't stop drinking",            "gold": ["mh-16", "mh-x-106", "mh-x-113"],        "domain": "Mental Health"},
    {"q": "My elderly father seems isolated and lonely",          "gold": ["mh-19", "mh-x-133", "mh-x-144"],        "domain": "Mental Health"},
    {"q": "Manasik swasthya ki helpline number kya hai",          "gold": ["mh-hi-1", "mh-x-126", "mh-x-135"],      "domain": "Mental Health"},
    {"q": "Ich kann nachts nicht schlafen, was tun",              "gold": ["mh-13", "mh-x-141"],                    "domain": "Mental Health"},
    {"q": "Was sind Anzeichen von Burnout",                       "gold": ["mh-17", "mh-x-138"],                    "domain": "Mental Health"},
    {"q": "Ich habe Angstzustande und Panik",                     "gold": ["mh-12", "mh-x-137"],                    "domain": "Mental Health"},
    {"q": "I lie awake worrying about every small thing",         "gold": ["mh-3", "mh-x-98", "mh-x-01"],           "domain": "Mental Health"},
    {"q": "Sad and hopeless for the last three weeks",            "gold": ["mh-2", "mh-x-14", "mh-x-17"],           "domain": "Mental Health"},
    {"q": "How to handle a sudden panic attack",                  "gold": ["mh-9", "mh-x-02", "mh-x-129"],          "domain": "Mental Health"},
    {"q": "Online therapist platforms in India affordable",       "gold": ["mh-4", "mh-x-87", "mh-x-92", "mh-x-93"],"domain": "Mental Health"},
    {"q": "Got into a big fight with my partner today",           "gold": ["mh-6", "mh-x-72", "mh-x-131"],          "domain": "Mental Health"},

    # ===== Umang / Legal (25) =====
    {"q": "How do I file an RTI application",                     "gold": ["lg-2", "lg-hi-1", "lg-x-202"],          "domain": "Legal"},
    {"q": "How do I file an FIR against my neighbour",            "gold": ["lg-1", "lg-hi-2", "lg-x-01", "lg-x-153", "lg-x-154", "lg-x-169", "lg-x-201"], "domain": "Legal"},
    {"q": "My landlord wants to evict me without notice",         "gold": ["lg-4", "lg-x-110", "lg-x-111", "lg-x-205"], "domain": "Legal"},
    {"q": "My cheque bounced what can I do",                      "gold": ["lg-6", "lg-x-78", "lg-x-247"],          "domain": "Legal"},
    {"q": "I want to divorce my husband",                         "gold": ["lg-9", "lg-x-46", "lg-x-47", "lg-x-203"],"domain": "Legal"},
    {"q": "Boss is harassing me at workplace",                    "gold": ["lg-8", "lg-x-22", "lg-x-86", "lg-x-87", "lg-x-88", "lg-x-89", "lg-x-92"], "domain": "Legal"},
    {"q": "Consumer complaint about defective washing machine",   "gold": ["lg-3", "lg-x-141", "lg-x-142", "lg-x-143", "lg-x-202"], "domain": "Legal"},
    {"q": "Am I entitled to gratuity after 6 years of service",   "gold": ["lg-10", "lg-x-81", "lg-x-84"],          "domain": "Legal"},
    {"q": "Where do I get free legal aid as a poor person",       "gold": ["lg-7", "lg-x-206", "lg-x-250"],         "domain": "Legal"},
    {"q": "Husband is violent - what legal protection do I have", "gold": ["lg-5", "lg-hi-3", "lg-x-56", "lg-x-57", "lg-x-204"], "domain": "Legal"},
    {"q": "Difference between IPC and the new BNS sections",      "gold": ["lg-11", "lg-x-21", "lg-x-26", "lg-x-27", "lg-x-28", "lg-x-29"], "domain": "Legal"},
    {"q": "What makes a contract enforceable in India",           "gold": ["lg-12", "lg-x-69", "lg-x-70", "lg-x-71", "lg-x-72"], "domain": "Legal"},
    {"q": "Caste discrimination at workplace how to file case",   "gold": ["lg-13"],                                "domain": "Legal"},
    {"q": "My account got hacked - which IT Act section",         "gold": ["lg-14", "lg-x-131", "lg-x-132", "lg-x-140"], "domain": "Legal"},
    {"q": "Company is misusing my personal data DPDP rights",     "gold": ["lg-15", "lg-x-136", "lg-x-137", "lg-x-138"], "domain": "Legal"},
    {"q": "Procedure when a minor commits an offence",            "gold": ["lg-16"],                                "domain": "Legal"},
    {"q": "RTE Act free school admission",                        "gold": ["lg-17"],                                "domain": "Legal"},
    {"q": "What are my fundamental rights under Article 21",      "gold": ["lg-18", "lg-x-118"],                    "domain": "Legal"},
    {"q": "Filing a writ petition in High Court",                 "gold": ["lg-19", "lg-x-122"],                    "domain": "Legal"},
    {"q": "Son refuses to take care of elderly parent",           "gold": ["lg-20", "lg-x-146", "lg-x-211"],        "domain": "Legal"},
    {"q": "Daughter's share in ancestral property",               "gold": ["lg-21", "lg-x-58", "lg-x-59", "lg-x-209"], "domain": "Legal"},
    {"q": "Hit and run accident compensation claim",              "gold": ["lg-22"],                                "domain": "Legal"},
    {"q": "Do I need GST registration as a freelancer",           "gold": ["lg-23", "lg-x-98", "lg-x-244"],         "domain": "Legal"},
    {"q": "Dowry harassment by in-laws Section 498A",             "gold": ["lg-25", "lg-x-28", "lg-x-208"],         "domain": "Legal"},
    {"q": "RTI kaise file karein hindi me",                       "gold": ["lg-hi-1", "lg-2", "lg-x-201"],          "domain": "Legal"},

    # ===== Aarogya / Government Schemes (25) =====
    {"q": "Am I eligible for Ayushman Bharat PM-JAY",             "gold": ["gs-1", "gs-hi-1", "gs-x-01", "gs-x-02", "gs-x-138", "gs-x-172"], "domain": "Government Schemes"},
    {"q": "I'm a small farmer how do I get PM Kisan",             "gold": ["gs-2", "gs-x-16", "gs-x-17", "gs-x-29", "gs-x-30", "gs-x-171"], "domain": "Government Schemes"},
    {"q": "Engineering girl student which scholarships apply",    "gold": ["gs-3", "gs-x-32", "gs-x-33", "gs-x-38", "gs-x-39"], "domain": "Government Schemes"},
    {"q": "How to apply for a ration card online",                "gold": ["gs-4", "gs-x-149", "gs-x-173"],         "domain": "Government Schemes"},
    {"q": "NREGA 100 days of work how to register",               "gold": ["gs-5", "gs-x-174"],                     "domain": "Government Schemes"},
    {"q": "PM Awas Yojana housing eligibility",                   "gold": ["gs-6", "gs-x-46", "gs-x-47", "gs-x-48", "gs-x-179"], "domain": "Government Schemes"},
    {"q": "Pension scheme for unorganised sector worker",         "gold": ["gs-7", "gs-x-131", "gs-x-132", "gs-x-137", "gs-x-178", "gs-x-182"], "domain": "Government Schemes"},
    {"q": "Collateral free loan to start a small shop",           "gold": ["gs-8", "gs-x-153", "gs-x-154", "gs-x-156", "gs-x-175"], "domain": "Government Schemes"},
    {"q": "Savings scheme for my newborn daughter",               "gold": ["gs-9", "gs-x-56", "gs-x-57", "gs-x-58", "gs-x-181"], "domain": "Government Schemes"},
    {"q": "PM Vishwakarma carpenter toolkit grant",               "gold": ["gs-10"],                                "domain": "Government Schemes"},
    {"q": "Government grant for a new tech startup",              "gold": ["gs-11", "gs-x-155"],                    "domain": "Government Schemes"},
    {"q": "Education loan interest subsidy scheme",               "gold": ["gs-12", "gs-x-39", "gs-x-40", "gs-x-41"],"domain": "Government Schemes"},
    {"q": "Rooftop solar panel subsidy household",                "gold": ["gs-13", "gs-x-49"],                     "domain": "Government Schemes"},
    {"q": "Street vendor working capital loan",                   "gold": ["gs-14"],                                "domain": "Government Schemes"},
    {"q": "Karnataka Gruha Lakshmi 2000 per month women",         "gold": ["gs-15", "gs-x-71", "gs-x-72", "gs-x-73"],"domain": "Government Schemes"},
    {"q": "Maharashtra Ladki Bahin Yojana eligibility",           "gold": ["gs-16", "gs-x-75", "gs-x-77", "gs-x-78"],"domain": "Government Schemes"},
    {"q": "UP Kanya Sumangala scheme for girl child",             "gold": ["gs-17", "gs-x-68"],                     "domain": "Government Schemes"},
    {"q": "Tamil Nadu Pudhumai Penn girl student",                "gold": ["gs-18", "gs-x-79", "gs-x-80", "gs-x-81", "gs-x-82"], "domain": "Government Schemes"},
    {"q": "Delhi state subsidy schemes for residents",            "gold": ["gs-19", "gs-x-83", "gs-x-84", "gs-x-85"],"domain": "Government Schemes"},
    {"q": "West Bengal Lakshmir Bhandar monthly amount",          "gold": ["gs-20", "gs-x-86", "gs-x-87", "gs-x-88", "gs-x-89", "gs-x-90"], "domain": "Government Schemes"},
    {"q": "Telangana Rythu Bandhu farmer scheme",                 "gold": ["gs-21", "gs-x-96", "gs-x-97", "gs-x-98"],"domain": "Government Schemes"},
    {"q": "Kerala state pension and welfare schemes",             "gold": ["gs-22", "gs-x-119", "gs-x-120"],        "domain": "Government Schemes"},
    {"q": "MP Ladli Behna eligibility income limit",              "gold": ["gs-24", "gs-x-109", "gs-x-110"],        "domain": "Government Schemes"},
    {"q": "Jan Dhan zero balance bank account",                   "gold": ["gs-25"],                                "domain": "Government Schemes"},
    {"q": "Mahilao ke liye sarkari yojanaye Hindi",               "gold": ["gs-hi-2", "gs-x-56", "gs-x-57", "gs-x-181"], "domain": "Government Schemes"},

    # ===== Raksha / Safety (25) =====
    {"q": "Someone stole money from my UPI account",              "gold": ["sf-2", "sf-x-02", "sf-x-05", "sf-x-08", "sf-x-76"], "domain": "Safety"},
    {"q": "There's a fire in my building right now",              "gold": ["sf-4", "sf-x-51", "sf-x-52", "sf-x-81"],"domain": "Safety"},
    {"q": "My husband is hitting me right now",                   "gold": ["sf-6", "sf-x-77"],                      "domain": "Safety"},
    {"q": "I'm being stalked online by an ex",                    "gold": ["sf-3", "sf-x-11", "sf-x-12", "sf-x-18"],"domain": "Safety"},
    {"q": "Heart attack symptoms what to do first",               "gold": ["sf-5", "sf-x-31", "sf-x-32", "sf-x-79"],"domain": "Safety"},
    {"q": "Loan app is threatening my contacts",                  "gold": ["sf-8", "sf-x-03", "sf-x-05", "sf-x-76"],"domain": "Safety"},
    {"q": "What's the emergency helpline number in India",        "gold": ["sf-1", "sf-hi-1", "sf-x-85"],           "domain": "Safety"},
    {"q": "Earthquake just happened what to do next",             "gold": ["sf-7", "sf-x-46", "sf-x-47", "sf-x-82"],"domain": "Safety"},
    {"q": "Child being abused at school POCSO",                   "gold": ["sf-9", "sf-x-56", "sf-x-57", "sf-x-58", "sf-x-60", "sf-x-78"], "domain": "Safety"},
    {"q": "Travel safety tips for solo woman in India",           "gold": ["sf-10", "sf-x-16", "sf-x-17", "sf-x-20", "sf-x-25"], "domain": "Safety"},
    {"q": "Acid was thrown on someone first aid",                 "gold": ["sf-12", "sf-x-23", "sf-x-38"],          "domain": "Safety"},
    {"q": "Witnessed a road accident what should I do",           "gold": ["sf-13", "sf-x-66", "sf-x-67", "sf-x-84"],"domain": "Safety"},
    {"q": "Dog bit me on the street first aid",                   "gold": ["sf-14", "sf-x-44", "sf-x-80"],          "domain": "Safety"},
    {"q": "Elderly mother being neglected by son",                "gold": ["sf-15", "sf-x-62", "sf-x-63", "sf-x-64", "sf-x-83"], "domain": "Safety"},
    {"q": "Heatwave safety tips for elders",                      "gold": ["sf-16", "sf-x-41"],                     "domain": "Safety"},
    {"q": "I lost my passport while travelling abroad",           "gold": ["sf-17", "sf-x-98", "sf-x-99"],          "domain": "Safety"},
    {"q": "Notrufnummer in Deutschland Polizei",                  "gold": ["sf-11", "sf-x-86", "sf-x-90"],          "domain": "Safety"},
    {"q": "Cybercrime melden in Deutschland",                     "gold": ["sf-de-2", "sf-x-90"],                   "domain": "Safety"},
    {"q": "Hausliche Gewalt sofortige Hilfe Deutschland",         "gold": ["sf-de-3", "sf-x-88"],                   "domain": "Safety"},
    {"q": "Bhag rahi hu mere pati se aaj raat",                   "gold": ["sf-6", "sf-x-77"],                      "domain": "Safety"},
    {"q": "Pulis ka number kya hai",                              "gold": ["sf-hi-1", "sf-1", "sf-x-85"],           "domain": "Safety"},
    {"q": "Snake bite in the village - what to do",               "gold": ["sf-14", "sf-x-43", "sf-x-44", "sf-x-80"],"domain": "Safety"},
    {"q": "Stalked by a stranger near my college",                "gold": ["sf-3", "sf-x-11", "sf-x-18"],           "domain": "Safety"},
    {"q": "Cyclone warning - how to prepare house",               "gold": ["sf-7", "sf-x-46", "sf-x-49", "sf-x-50"],"domain": "Safety"},
    {"q": "Phishing call asking for OTP - did I lose money",      "gold": ["sf-8", "sf-x-01", "sf-x-02", "sf-x-05", "sf-x-76"], "domain": "Safety"},
]


FROZEN_AT = "2026-06-01"
SPLIT_SEED = 20260601

DEV_INDICES = [
    # Mental Health (0..24): 12 cases
    0, 2, 3, 4, 6, 8, 11, 13, 14, 18, 19, 23,
    # Legal (25..49): 12 cases
    25, 26, 27, 29, 30, 32, 34, 36, 38, 41, 42, 47,
    # Government Schemes (50..74): 13 cases
    50, 51, 53, 54, 56, 58, 60, 62, 63, 67, 69, 71, 73,
    # Safety (75..99): 13 cases
    75, 77, 78, 80, 82, 84, 87, 89, 90, 91, 94, 96, 98,
]

TEST_HELDOUT_INDICES = [
    # Mental Health: 13 cases
    1, 5, 7, 9, 10, 12, 15, 16, 17, 20, 21, 22, 24,
    # Legal: 13 cases
    28, 31, 33, 35, 37, 39, 40, 43, 44, 45, 46, 48, 49,
    # Government Schemes: 12 cases
    52, 55, 57, 59, 61, 64, 65, 66, 68, 70, 72, 74,
    # Safety: 12 cases
    76, 79, 81, 83, 85, 86, 88, 92, 93, 95, 97, 99,
]


def _check_split() -> None:
    n = len(TEST_CASES)
    assert len(DEV_INDICES) + len(TEST_HELDOUT_INDICES) == n
    assert set(DEV_INDICES).isdisjoint(set(TEST_HELDOUT_INDICES))
    assert set(DEV_INDICES) | set(TEST_HELDOUT_INDICES) == set(range(n))


_check_split()


DEV_CASES = [TEST_CASES[i] for i in DEV_INDICES]
TEST_CASES_HELDOUT = [TEST_CASES[i] for i in TEST_HELDOUT_INDICES]


def by_split(name: str) -> list[dict]:
    name = name.strip().lower()
    if name in ("dev", "tune", "validation", "val"):
        return DEV_CASES
    if name in ("test", "heldout", "held-out", "test_heldout"):
        return TEST_CASES_HELDOUT
    if name in ("all", "full", "everything"):
        return TEST_CASES
    raise ValueError(f"unknown split: {name!r}")


if __name__ == "__main__":
    from collections import Counter
    print(f"\nSeelenruh eval split (frozen {FROZEN_AT}, seed={SPLIT_SEED})\n")
    print(f"  Full set     : n = {len(TEST_CASES)}")
    print(f"  DEV split    : n = {len(DEV_CASES)}   (used for hyper-parameter tuning)")
    print(f"  TEST_HELDOUT : n = {len(TEST_CASES_HELDOUT)}   (held out — headline numbers)\n")
    for label, cases in (("DEV", DEV_CASES), ("TEST_HELDOUT", TEST_CASES_HELDOUT)):
        counter = Counter(c["domain"] for c in cases)
        breakdown = ", ".join(f"{d}={counter[d]}" for d in sorted(counter))
        print(f"  {label:<12}  {breakdown}")
    print()
