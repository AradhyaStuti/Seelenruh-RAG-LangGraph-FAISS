"""Rule-based eligibility checker for government schemes.
Income thresholds are 2024-25 best-effort values — the UI flags them as indicative."""
from typing import Callable

LPA = 100_000  # one lakh in rupees


def _and(*fns: Callable[[dict], bool]) -> Callable[[dict], bool]:
    return lambda a: all(f(a) for f in fns)


def _income_lt(threshold_rs: float) -> Callable[[dict], bool]:
    return lambda a: a.get("incomeAnnual") is None or float(a["incomeAnnual"]) < threshold_rs


def _age_in(low: int, high: int) -> Callable[[dict], bool]:
    return lambda a: a.get("age") is None or low <= int(a["age"]) <= high


def _gender_in(*g: str) -> Callable[[dict], bool]:
    s = {x.lower() for x in g}
    return lambda a: not a.get("gender") or a["gender"].lower() in s


def _states(*states: str) -> Callable[[dict], bool]:
    s = {x.lower() for x in states}
    return lambda a: bool(a.get("state")) and a["state"].lower() in s


def _student(value: bool) -> Callable[[dict], bool]:
    return lambda a: a.get("isStudent") is None or bool(a["isStudent"]) is value


def _farmer(value: bool) -> Callable[[dict], bool]:
    return lambda a: a.get("isFarmer") is None or bool(a["isFarmer"]) is value


SCHEMES = [
    {
        "id": "pmjay",
        "name": "Ayushman Bharat PM-JAY",
        "summary": "₹5 lakh/year cashless secondary + tertiary hospitalisation for the bottom-40% of households.",
        "link": "https://pmjay.gov.in",
        "level": "central",
        "match": _income_lt(2.5 * LPA),
        "reasonIf": "Household income under ₹2.5 LPA — likely fits SECC-deprivation criteria.",
    },
    {
        "id": "pmkisan",
        "name": "PM Kisan Samman Nidhi",
        "summary": "₹6,000/year (3 instalments of ₹2,000) direct to small/marginal farmers.",
        "link": "https://pmkisan.gov.in",
        "level": "central",
        "match": _farmer(True),
        "reasonIf": "You marked yourself as a farmer.",
    },
    {
        "id": "nsp",
        "name": "National Scholarship Portal scholarships",
        "summary": "Centralised portal for ~100+ pre-matric, post-matric and merit-cum-means scholarships.",
        "link": "https://scholarships.gov.in",
        "level": "central",
        "match": _and(_student(True), _age_in(10, 35)),
        "reasonIf": "You're a student between 10–35.",
    },
    {
        "id": "pmay-g",
        "name": "PM Awas Yojana (Gramin)",
        "summary": "Pucca house assistance of ₹1.2 lakh (plain) / ₹1.3 lakh (hilly) for rural BPL families.",
        "link": "https://pmayg.nic.in",
        "level": "central",
        "match": _income_lt(3 * LPA),
        "reasonIf": "Household income suggests EWS/LIG bracket.",
    },
    {
        "id": "nrega",
        "name": "MGNREGA — 100 days guaranteed wage employment",
        "summary": "Right to 100 days of unskilled wage employment per rural household per year.",
        "link": "https://nrega.nic.in",
        "level": "central",
        "match": _and(_age_in(18, 99), _income_lt(3 * LPA)),
        "reasonIf": "Adult in a low-income household — eligible to demand work at your Gram Panchayat.",
    },
    {
        "id": "pmuy",
        "name": "PM Ujjwala Yojana (LPG)",
        "summary": "Free LPG connection + first refill + stove for women from BPL households.",
        "link": "https://pmuy.gov.in",
        "level": "central",
        "match": _and(_gender_in("female", "f", "woman"), _income_lt(2.5 * LPA)),
        "reasonIf": "Adult woman in a low-income household.",
    },
    {
        "id": "pmsby",
        "name": "PM Suraksha Bima Yojana",
        "summary": "Accidental death + disability cover of ₹2 lakh at ₹20/year premium.",
        "link": "https://www.jansuraksha.gov.in",
        "level": "central",
        "match": _age_in(18, 70),
        "reasonIf": "Any adult 18–70 with a bank account can join.",
    },
    {
        "id": "pmjjby",
        "name": "PM Jeevan Jyoti Bima Yojana",
        "summary": "Life cover of ₹2 lakh at ₹436/year premium.",
        "link": "https://www.jansuraksha.gov.in",
        "level": "central",
        "match": _age_in(18, 50),
        "reasonIf": "Bank-account-holding adults 18–50.",
    },
    {
        "id": "apy",
        "name": "Atal Pension Yojana",
        "summary": "Guaranteed monthly pension of ₹1,000–₹5,000 after 60, for unorganised-sector workers.",
        "link": "https://www.npscra.nsdl.co.in/scheme-details.php",
        "level": "central",
        "match": _age_in(18, 40),
        "reasonIf": "Adults 18–40 can enrol; later you start, higher the contribution.",
    },
    {
        "id": "svanidhi",
        "name": "PM SVANidhi (street vendors)",
        "summary": "Collateral-free loans of ₹10k → ₹20k → ₹50k for street vendors.",
        "link": "https://pmsvanidhi.mohua.gov.in",
        "level": "central",
        "match": _age_in(18, 99),
        "reasonIf": "Adult street vendors — verify with the Town Vending Committee.",
    },
    # State schemes
    {
        "id": "ka-gruha-lakshmi",
        "name": "Karnataka · Gruha Lakshmi",
        "summary": "₹2,000/month to the woman head-of-family in eligible households.",
        "link": "https://sevasindhuservices.karnataka.gov.in",
        "level": "state",
        "match": _and(_states("karnataka", "ka"), _gender_in("female", "f", "woman")),
        "reasonIf": "Adult woman in Karnataka.",
    },
    {
        "id": "mh-ladki-bahin",
        "name": "Maharashtra · Mukhyamantri Mazi Ladki Bahin",
        "summary": "₹1,500/month for women aged 21–65 in eligible households.",
        "link": "https://ladakibahin.maharashtra.gov.in",
        "level": "state",
        "match": _and(
            _states("maharashtra", "mh"),
            _gender_in("female", "f", "woman"),
            _age_in(21, 65),
            _income_lt(2.5 * LPA),
        ),
        "reasonIf": "Maharashtra resident woman 21–65 below the income ceiling.",
    },
    {
        "id": "wb-lakshmir-bhandar",
        "name": "West Bengal · Lakshmir Bhandar",
        "summary": "₹1,000/month (₹1,200 for SC/ST) to women aged 25–60.",
        "link": "https://socialsecurity.wb.gov.in",
        "level": "state",
        "match": _and(_states("west bengal", "wb"), _gender_in("female", "f", "woman"), _age_in(25, 60)),
        "reasonIf": "West Bengal resident woman 25–60.",
    },
    {
        "id": "tn-pudhumai-penn",
        "name": "Tamil Nadu · Pudhumai Penn",
        "summary": "₹1,000/month to girls who complete classes 6–12 in govt schools and pursue higher studies.",
        "link": "https://penkalvi.tn.gov.in",
        "level": "state",
        "match": _and(
            _states("tamil nadu", "tn"),
            _gender_in("female", "f", "woman"),
            _student(True),
            _age_in(16, 30),
        ),
        "reasonIf": "TN girl student moving into higher education.",
    },
    {
        "id": "up-kanya-sumangala",
        "name": "Uttar Pradesh · Kanya Sumangala",
        "summary": "Up to ₹25,000 across 6 life stages of a girl child (birth → graduation).",
        "link": "https://mksy.up.gov.in",
        "level": "state",
        "match": _and(
            _states("uttar pradesh", "up"),
            _gender_in("female", "f", "woman"),
            _income_lt(3 * LPA),
        ),
        "reasonIf": "UP families with a daughter, income under ₹3 LPA.",
    },
    {
        "id": "mp-ladli-behna",
        "name": "Madhya Pradesh · Ladli Behna",
        "summary": "₹1,250/month to married women aged 21–60 in eligible households.",
        "link": "https://cmladlibahna.mp.gov.in",
        "level": "state",
        "match": _and(
            _states("madhya pradesh", "mp"),
            _gender_in("female", "f", "woman"),
            _age_in(21, 60),
            _income_lt(2.5 * LPA),
        ),
        "reasonIf": "MP resident woman 21–60 below the income ceiling.",
    },
    # Central — added expansion
    {
        "id": "sukanya-samriddhi",
        "name": "Sukanya Samriddhi Yojana",
        "summary": "Long-term saving for a girl child under 10. ₹250–1.5 lakh/year at 8.2% interest (FY24-25), EEE tax status, matures at 21.",
        "link": "https://www.indiapost.gov.in",
        "level": "central",
        # No applicant field directly checks "has a daughter <10" — we surface
        # this scheme to any adult, since it's most useful for parents.
        "match": _age_in(18, 99),
        "reasonIf": "Open to any guardian of a girl child under 10.",
    },
    {
        "id": "pmay-urban",
        "name": "PM Awas Yojana (Urban) — CLSS",
        "summary": "Credit-Linked Subsidy on home loan interest. EWS/LIG up to ₹6 LPA income, MIG-I up to ₹12 LPA, MIG-II up to ₹18 LPA.",
        "link": "https://pmaymis.gov.in",
        "level": "central",
        "match": _income_lt(18 * LPA),
        "reasonIf": "Annual income under ₹18 LPA — likely fits EWS/LIG/MIG eligibility.",
    },
    {
        "id": "pmmvy",
        "name": "PM Matru Vandana Yojana",
        "summary": "₹5,000 cash benefit for first living child to pregnant/lactating women. Second-child benefit ₹6,000 if girl.",
        "link": "https://wcd.nic.in/schemes/pradhan-mantri-matru-vandana-yojana",
        "level": "central",
        "match": _and(_gender_in("female", "f", "woman"), _age_in(18, 50)),
        "reasonIf": "Adult woman — eligible for the first-pregnancy cash benefit.",
    },
    {
        "id": "esic",
        "name": "ESI medical + sickness cover",
        "summary": "Free medical care + cash sickness/disablement/maternity benefits for employees earning ≤ ₹21,000/month (₹25,000 if disabled).",
        "link": "https://www.esic.gov.in",
        "level": "central",
        "match": _and(_income_lt(2.52 * LPA), _age_in(18, 65)),
        "reasonIf": "Low monthly income — likely eligible if employed in covered sector.",
    },
    {
        "id": "ujjwala",
        "name": "PM Ujjwala Yojana 2.0",
        "summary": "Free LPG connection + first refill + stove for BPL women. Expanded 2021 to cover migrant + previously-excluded families.",
        "link": "https://pmuy.gov.in",
        "level": "central",
        "match": _and(_gender_in("female", "f", "woman"), _income_lt(2.5 * LPA)),
        "reasonIf": "Adult woman in a low-income household — Ujjwala 2.0 eased earlier KYC barriers.",
    },
    {
        "id": "vishwakarma",
        "name": "PM Vishwakarma Yojana (traditional artisans)",
        "summary": "₹15,000 toolkit grant + 1-3% collateral-free loans up to ₹3 lakh + skill training stipend for 18 traditional trades.",
        "link": "https://pmvishwakarma.gov.in",
        "level": "central",
        "match": _age_in(18, 99),
        "reasonIf": "Adult artisans in covered trades (carpenter, blacksmith, tailor, potter, mason, etc.).",
    },
    # State — added expansion
    {
        "id": "tn-magalir-urimai",
        "name": "Tamil Nadu · Kalaignar Magalir Urimai Thittam",
        "summary": "₹1,000/month to woman head of family (income < ₹2.5 LPA + landholding < 5 acres). ~1.06 crore beneficiaries.",
        "link": "https://magalirurimai.tn.gov.in",
        "level": "state",
        "match": _and(
            _states("tamil nadu", "tn"),
            _gender_in("female", "f", "woman"),
            _income_lt(2.5 * LPA),
        ),
        "reasonIf": "TN resident woman in a low-income household.",
    },
    {
        "id": "ap-cheyutha",
        "name": "Andhra Pradesh · YSR Cheyutha",
        "summary": "₹18,750/year to BC/SC/ST/Minority women aged 45–60 for 4 years (₹75,000 total). Aimed at small-enterprise seed funding.",
        "link": "https://navasakam.ap.gov.in",
        "level": "state",
        "match": _and(
            _states("andhra pradesh", "ap"),
            _gender_in("female", "f", "woman"),
            _age_in(45, 60),
        ),
        "reasonIf": "AP resident woman 45–60.",
    },
    {
        "id": "telangana-aasara",
        "name": "Telangana · Aasara Pension",
        "summary": "₹2,016/month: old age (57+), widows, single women (35+), disabled (40%+), beedi workers, AIDS patients.",
        "link": "https://aasara.telangana.gov.in",
        "level": "state",
        "match": _and(_states("telangana", "ts"), _age_in(57, 99)),
        "reasonIf": "Telangana resident 57+.",
    },
    {
        "id": "wb-yuvashree",
        "name": "West Bengal · Yuvashree",
        "summary": "₹1,500/month unemployment allowance for 18–45 job-seekers registered with the employment exchange, max 1 year.",
        "link": "https://employmentbankwb.gov.in",
        "level": "state",
        "match": _and(_states("west bengal", "wb"), _age_in(18, 45)),
        "reasonIf": "WB resident 18–45, eligible to register with employment exchange.",
    },
    {
        "id": "jh-maiya-samman",
        "name": "Jharkhand · Mukhyamantri Maiya Samman Yojana",
        "summary": "₹2,500/month to women aged 21–50 with household income < ₹8 lakh.",
        "link": "https://mmmsy.jharkhand.gov.in",
        "level": "state",
        "match": _and(
            _states("jharkhand", "jh"),
            _gender_in("female", "f", "woman"),
            _age_in(21, 50),
            _income_lt(8 * LPA),
        ),
        "reasonIf": "Jharkhand resident woman 21–50 below ₹8 LPA.",
    },
    {
        "id": "cg-mahtari-vandan",
        "name": "Chhattisgarh · Mahtari Vandan Yojana",
        "summary": "₹1,000/month (₹12,000/year) to married women aged 21+. Excludes income-tax payers and government employees.",
        "link": "https://mahtarivandan.cgstate.gov.in",
        "level": "state",
        "match": _and(
            _states("chhattisgarh", "cg"),
            _gender_in("female", "f", "woman"),
            _age_in(21, 99),
        ),
        "reasonIf": "Chhattisgarh resident woman 21+.",
    },
    {
        "id": "odisha-kalia",
        "name": "Odisha · KALIA",
        "summary": "₹4,000/season cultivation support + ₹12,500 livelihood for landless agri workers + life and accident insurance.",
        "link": "https://kalia.odisha.gov.in",
        "level": "state",
        "match": _and(_states("odisha", "od"), _income_lt(3 * LPA)),
        "reasonIf": "Odisha resident in a low-income farming household.",
    },
    {
        "id": "assam-orunodoi",
        "name": "Assam · Orunodoi 2.0",
        "summary": "₹1,250/month to women heads of family in low-income households (~20 lakh beneficiaries).",
        "link": "https://orunodoi.assam.gov.in",
        "level": "state",
        "match": _and(
            _states("assam", "as"),
            _gender_in("female", "f", "woman"),
            _income_lt(2 * LPA),
        ),
        "reasonIf": "Assam resident woman heading a low-income household.",
    },
    {
        "id": "haryana-lado-lakshmi",
        "name": "Haryana · Lado Lakshmi",
        "summary": "₹2,100/month to women 18+ with state residence (announced 2024).",
        "link": "https://saralharyana.gov.in",
        "level": "state",
        "match": _and(
            _states("haryana", "hr"),
            _gender_in("female", "f", "woman"),
            _age_in(18, 99),
        ),
        "reasonIf": "Haryana resident woman 18+.",
    },
    # More state schemes
    {
        "id": "delhi-mukhyamantri-mahila-samman",
        "name": "Delhi · Mukhyamantri Mahila Samman Yojana",
        "summary": "₹1,000/month to women aged 18+ who are Delhi residents and registered voters.",
        "link": "https://www.delhi.gov.in",
        "level": "state",
        "match": _and(_states("delhi", "dl"), _gender_in("female", "f", "woman"), _age_in(18, 99)),
        "reasonIf": "Delhi resident woman 18+ registered as voter.",
    },
    {
        "id": "gujarat-vhali-dikri",
        "name": "Gujarat · Vhali Dikri Yojana",
        "summary": "₹4,000 at birth, ₹6,000 at class 9, ₹1 lakh FD on turning 18 — for first two girl children in BPL families.",
        "link": "https://vahlidikri.gujarat.gov.in",
        "level": "state",
        "match": _and(_states("gujarat", "gj"), _gender_in("female", "f", "woman"), _income_lt(2 * LPA)),
        "reasonIf": "Gujarat BPL family with a girl child.",
    },
    {
        "id": "rajasthan-lado-protsahan",
        "name": "Rajasthan · Lado Protsahan Yojana",
        "summary": "₹2 lakh savings bond at birth for girls from SC/ST/OBC/BPL families, paid out across 6 milestones up to age 21.",
        "link": "https://wcd.rajasthan.gov.in",
        "level": "state",
        "match": _and(_states("rajasthan", "rj"), _gender_in("female", "f", "woman"), _income_lt(2.5 * LPA)),
        "reasonIf": "Rajasthan BPL/SC/ST/OBC family with a girl child.",
    },
    {
        "id": "bihar-mukhyamantri-kanya-utthan",
        "name": "Bihar · Mukhyamantri Kanya Utthan Yojana",
        "summary": "₹50,000 total to girl children across milestones from birth to graduation. Covers sanitary hygiene kit and uniform allowance.",
        "link": "https://medhasoft.bih.nic.in",
        "level": "state",
        "match": _and(_states("bihar", "br"), _gender_in("female", "f", "woman"), _age_in(0, 25)),
        "reasonIf": "Bihar resident girl from birth up to graduation age.",
    },
    {
        "id": "punjab-ashirwad",
        "name": "Punjab · Ashirwad Scheme",
        "summary": "₹51,000 one-time assistance to daughters of AAY/BPL families at the time of marriage.",
        "link": "https://socialsecuritypb.gov.in",
        "level": "state",
        "match": _and(_states("punjab", "pb"), _gender_in("female", "f", "woman"), _income_lt(2 * LPA)),
        "reasonIf": "Punjab BPL/AAY family with a daughter approaching marriage age.",
    },
    {
        "id": "kerala-karunya",
        "name": "Kerala · Karunya Health Scheme",
        "summary": "Up to ₹2 lakh/year financial assistance for BPL families for serious illnesses not covered by other schemes.",
        "link": "https://karunya.kerala.gov.in",
        "level": "state",
        "match": _and(_states("kerala", "kl"), _income_lt(2 * LPA)),
        "reasonIf": "Kerala BPL household facing major medical expenses.",
    },
    {
        "id": "hp-sahara",
        "name": "Himachal Pradesh · Sahara Yojana",
        "summary": "₹3,000/month to patients with serious illnesses (cancer, Parkinson's, muscular dystrophy, renal failure, etc.) from BPL families.",
        "link": "https://hpssb.nic.in",
        "level": "state",
        "match": _and(_states("himachal pradesh", "hp"), _income_lt(4 * LPA)),
        "reasonIf": "HP BPL patient with a serious chronic illness.",
    },
    {
        "id": "goa-dayanand-social",
        "name": "Goa · Dayanand Social Security Scheme",
        "summary": "₹2,500–₹3,500/month pension for residents 18+ who are unemployed, disabled, or aged 60+.",
        "link": "https://socialjustice.goa.gov.in",
        "level": "state",
        "match": _and(_states("goa", "ga"), _age_in(18, 99)),
        "reasonIf": "Goa resident 18+ — covers unemployed, disabled, and elderly.",
    },
    # More central schemes
    {
        "id": "pmfby",
        "name": "PM Fasal Bima Yojana (Crop Insurance)",
        "summary": "Subsidised crop insurance — premium 2% (kharif), 1.5% (rabi), 5% (commercial). Covers loss from natural calamities.",
        "link": "https://pmfby.gov.in",
        "level": "central",
        "match": _farmer(True),
        "reasonIf": "You marked yourself as a farmer — crop insurance protects against crop loss.",
    },
    {
        "id": "mudra-loan",
        "name": "PM Mudra Yojana (Business Loan)",
        "summary": "Collateral-free loans: Shishu ≤ ₹50k, Kishore ₹50k–5L, Tarun ₹5L–10L for non-farm micro enterprises.",
        "link": "https://mudra.org.in",
        "level": "central",
        "match": _age_in(18, 65),
        "reasonIf": "Any adult with a small business or self-employment plan can apply through a bank/MFI.",
    },
    {
        "id": "standup-india",
        "name": "Stand-Up India",
        "summary": "Bank loans of ₹10 lakh–₹1 crore for SC/ST and women entrepreneurs setting up greenfield enterprises.",
        "link": "https://www.standupmitra.in",
        "level": "central",
        "match": _and(_gender_in("female", "f", "woman"), _age_in(18, 65)),
        "reasonIf": "Woman entrepreneur — at least one loan per bank branch is reserved for women.",
    },
    {
        "id": "naps",
        "name": "National Apprenticeship Promotion Scheme",
        "summary": "Government pays 25% of stipend (up to ₹1,500/month) to employers who take on apprentices. Good entry path for school/college leavers.",
        "link": "https://apprenticeshipindia.org",
        "level": "central",
        "match": _and(_age_in(14, 35), _student(False)),
        "reasonIf": "Young adult not currently in formal education — apprenticeship can provide skills + income.",
    },
]


def match(applicant: dict) -> list[dict]:
    """Return every scheme whose rule is satisfied by the applicant."""
    out: list[dict] = []
    for s in SCHEMES:
        try:
            if s["match"](applicant):
                out.append({
                    "id": s["id"],
                    "name": s["name"],
                    "summary": s["summary"],
                    "link": s["link"],
                    "level": s["level"],
                    "reason": s["reasonIf"],
                })
        except Exception:
            continue
    return out
