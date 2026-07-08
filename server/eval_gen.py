"""LLM-as-judge generation eval for Seelenruh.

Runs the full pipeline (classify → route → retrieve → generate) on a
small hand-labelled set of queries with `must_mention` keywords, then asks
a judge model to score the reply on three axes:

  - faithfulness  (1-5): did the answer use the retrieved chunks correctly?
  - persona_fit   (1-5): did the tone match the persona's character?
  - helpfulness   (1-5): did the answer actually address the user's question?

A simple deterministic check also verifies that each `must_mention` keyword
literally appears in the reply — catches dropped facts even when the judge
gives a generous score.

Cheaper than the LLM-as-judge harness in heavyweight RAG eval suites, but
enough to catch persona drift before users do.

Run:
  cd server && .venv/Scripts/python eval_gen.py
"""
import asyncio
import time
from collections import defaultdict
from statistics import mean

from ai import intent as intent_flow
from ai import emotion as emotion_flow
from ai import responder
from ai.provider import chat_json
from config import GROQ_MODEL_FAST
from rag import retriever


# Smaller test set — each generation call is ~1-2s and costs a Groq token
# budget, so we keep this targeted. 12 queries, 3 per persona, picked to
# exercise the most common real failure modes (panic override, code-mixed
# Hinglish, scheme-vs-legal ambiguity, faithful citation).
GEN_CASES = [
    # Usha — must keep helpline numbers + suggest a coping technique
    {
        "q": "I keep waking up at 3am with my heart racing",
        "domain": "Mental Health",
        "must_mention": ["112", "Tele-MANAS", "breathing"],  # any one is OK
        "must_mention_mode": "any",
    },
    {
        "q": "I'm a college student and the exam stress is destroying me",
        "domain": "Mental Health",
        "must_mention": ["box breathing", "5-4-3-2-1", "iCall", "Vandrevala", "Tele-MANAS"],
        "must_mention_mode": "any",
    },
    {
        "q": "Mood bahut down hai aaj subah se, kya karu",
        "domain": "Mental Health",
        "must_mention": ["iCall", "Vandrevala", "Tele-MANAS", "14416"],
        "must_mention_mode": "any",
    },

    # Umang — must cite the right Act/section
    {
        "q": "How do I file an RTI application for a central ministry",
        "domain": "Legal",
        "must_mention": ["Section 6", "Right to Information", "2005"],
        "must_mention_mode": "any",
    },
    {
        "q": "My cheque bounced what's the legal process",
        "domain": "Legal",
        "must_mention": ["Section 138", "Negotiable Instruments", "30 days"],
        "must_mention_mode": "any",
    },
    {
        "q": "Boss is sexually harassing me at workplace",
        "domain": "Legal",
        "must_mention": ["ICC", "POSH", "2013", "Internal Complaints Committee"],
        "must_mention_mode": "any",
    },

    # Aarogya — must surface the right scheme name
    {
        "q": "I'm a marginal farmer in Maharashtra, what central schemes",
        "domain": "Government Schemes",
        "must_mention": ["PM-KISAN", "PM Kisan", "6000", "₹6,000"],
        "must_mention_mode": "any",
    },
    {
        "q": "I want a small loan to start a tea stall",
        "domain": "Government Schemes",
        "must_mention": ["Mudra", "Shishu", "Kishore", "SVANidhi", "10"],
        "must_mention_mode": "any",
    },
    {
        "q": "My daughter is 5, what schemes for her future",
        "domain": "Government Schemes",
        "must_mention": ["Sukanya", "Beti Bachao", "Kanya"],
        "must_mention_mode": "any",
    },

    # Raksha — must lead with the helpline + numbered steps
    {
        "q": "Someone is following me right now and I'm scared",
        "domain": "Safety",
        "must_mention": ["112", "Step 1"],
        "must_mention_mode": "all",
    },
    {
        "q": "I just got scammed on a loan app",
        "domain": "Safety",
        "must_mention": ["1930", "cybercrime.gov.in"],
        "must_mention_mode": "any",
    },
    {
        "q": "Heart attack symptoms what to do right now",
        "domain": "Safety",
        "must_mention": ["108", "102", "112", "CPR", "ambulance"],
        "must_mention_mode": "any",
    },
]


JUDGE_SYSTEM = """You are evaluating a reply from a four-persona Indian wellbeing assistant.
The personas are:
- Usha: warm, slow, mental-health focused, always names a helpline when distress is present.
- Umang: direct, structured, MUST cite the relevant Indian Act / Section when one applies.
- Aarogya: checklist-oriented for government schemes, lists eligibility + how-to-apply.
- Raksha: emergency-first, MUST lead with helpline number in Step 1, action in Step 2-3.

You will be given the user's question, the persona that was supposed to answer,
the retrieved knowledge chunks the model could use, and the reply that was produced.

Score the reply on three axes from 1 (terrible) to 5 (excellent):
- faithfulness: did the reply ground its claims in the retrieved chunks, or invent things?
- persona_fit: did the tone, structure and citations match the persona's character?
- helpfulness: did the reply actually address the user's question with usable next steps?

Return ONLY this JSON:
{ "faithfulness": <1-5>, "persona_fit": <1-5>, "helpfulness": <1-5>, "notes": "<one short sentence>" }"""


async def _full_pipeline(query: str, domain: str) -> dict:
    """Run the same flow as the live chat — classify, route, retrieve, generate."""
    i, e = await asyncio.gather(
        intent_flow.detect(query),
        emotion_flow.detect(query),
    )
    routed = "Safety" if i["intent"] == "Panic" else domain
    hits = await retriever.retrieve(query, domain=routed)
    out = await responder.respond(
        query=query,
        intent=routed,
        emotion=e["emotion"],
        lang="auto",
        history=[],
        retrieved=hits,
        context=f"Domain: {routed}. Emotion: {e['emotion']}. Intent: {i.get('reasoning','')}",
    )
    return {
        "intent": i["intent"],
        "emotion": e["emotion"],
        "routed_domain": routed,
        "retrieved": hits,
        "response": out["response"],
        "via": out.get("via"),
    }


def _check_must_mention(reply: str, kws: list[str], mode: str) -> tuple[bool, list[str]]:
    """Returns (passed, missing_keywords). 'any' = at least one match; 'all' = every kw."""
    lower = reply.lower()
    hits = [k for k in kws if k.lower() in lower]
    if mode == "all":
        missing = [k for k in kws if k.lower() not in lower]
        return (len(missing) == 0, missing)
    # 'any'
    return (len(hits) > 0, [] if hits else kws)


async def _judge(case: dict, pipeline_result: dict) -> dict:
    prompt = f"""USER QUESTION: {case['q']}
PERSONA: {pipeline_result['routed_domain']}
RETRIEVED CHUNKS:
""" + "\n---\n".join(
        f"[{h['id']} · {h['topic']}]\n{h['text'][:600]}" for h in pipeline_result["retrieved"]
    ) + f"""

ASSISTANT REPLY:
{pipeline_result['response']}
"""
    try:
        result = await chat_json(
            model=GROQ_MODEL_FAST,
            temperature=0.0,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
        )
        data = result["data"]
        return {
            "faithfulness": int(data.get("faithfulness", 0)),
            "persona_fit": int(data.get("persona_fit", 0)),
            "helpfulness": int(data.get("helpfulness", 0)),
            "notes": str(data.get("notes", "")),
        }
    except Exception as err:
        return {"faithfulness": 0, "persona_fit": 0, "helpfulness": 0, "notes": f"judge-error: {err}"}


async def main():
    print(f"\nSeelenruh generation eval — {len(GEN_CASES)} cases\n")
    await retriever.init()
    await retriever.warmup()
    print()

    by_domain_faith: dict[str, list[int]] = defaultdict(list)
    by_domain_fit: dict[str, list[int]] = defaultdict(list)
    by_domain_help: dict[str, list[int]] = defaultdict(list)
    kw_pass = 0

    for case in GEN_CASES:
        t0 = time.time()
        pr = await _full_pipeline(case["q"], case["domain"])
        scores = await _judge(case, pr)
        kw_ok, missing = _check_must_mention(
            pr["response"], case["must_mention"], case["must_mention_mode"]
        )
        elapsed = (time.time() - t0) * 1000

        d = pr["routed_domain"]
        by_domain_faith[d].append(scores["faithfulness"])
        by_domain_fit[d].append(scores["persona_fit"])
        by_domain_help[d].append(scores["helpfulness"])
        if kw_ok:
            kw_pass += 1

        marker = "OK" if kw_ok else "MISS"
        print(
            f"  [{marker:>4}] {d:<20} F={scores['faithfulness']} P={scores['persona_fit']} H={scores['helpfulness']} "
            f"({int(elapsed)}ms)  '{case['q'][:55]}'"
        )
        if not kw_ok:
            print(f"          missing keywords: {missing}")
        if scores["notes"]:
            print(f"          judge: {scores['notes']}")

    n = len(GEN_CASES)
    print()
    print(f"  Keyword-coverage pass : {kw_pass}/{n} = {kw_pass/n*100:.1f}%")
    print()
    print("  Per-domain judge scores (1-5):")
    for d in sorted(by_domain_faith.keys()):
        f = mean(by_domain_faith[d])
        p = mean(by_domain_fit[d])
        h = mean(by_domain_help[d])
        nd = len(by_domain_faith[d])
        print(f"    {d:<22} n={nd}  faithfulness={f:.2f}  persona_fit={p:.2f}  helpfulness={h:.2f}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
