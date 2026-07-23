# Main graph flow: START → load_memory → classify → route → retrieve → maybe_search → generate → save_memory → END.
#
# Domain dispatch is kept internal to the app:
#   "Mental Health"      → usha_graph
#   "Legal"              → legal_graph
#   "Government Schemes" → aarogya_graph
#   "Safety"             → raksha_graph
import asyncio
import re
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, START, END

from ai import emotion as emotion_flow
from ai import intent as intent_flow
from ai import responder
from ai import memory as memory_flow
from ai.tools import web_search, needs_web_search
import usha_graph
import legal_graph
import aarogya_graph
import raksha_graph
from logger import get_logger
from rag import retriever
from rag import knowledge_meta
import db

log = get_logger("graph")

_CITATION_RE = re.compile(r"\[(\d+)\]")

_TONE_HINTS = {
    # Original 6 states
    "sad":         "The user is sad or grieving. Be warm, slow, and present. No rush to fix — sit with them first.",
    "angry":       "The user is angry or feels wronged. Acknowledge the anger and the reason behind it BEFORE giving information. Don't argue or minimise.",
    "scared":      "The user is scared. Be calm, grounding, concrete. Address the fear before anything else. Short sentences.",
    "confused":    "The user is confused or overwhelmed by information. Be very clear and structured. Define terms. One step at a time. No jargon.",
    "happy":       "The user is in a positive or relieved state. Match their warmth. Be encouraging without being patronising.",
    "neutral":     "The user has no strong emotional signal. Be helpful, clear, and concise.",
    # Expanded states
    "hopeless":    "The user is in despair — they may feel nothing will change or there is no point. Do NOT immediately jump to solutions. First acknowledge the weight of what they feel. Then, gently, offer one small foothold. Never say 'things will get better' without grounding it in something concrete.",
    "overwhelmed": "The user feels like too much is happening at once. Be calm and ordered. Help them narrow down to ONE thing. Do not give a long list of advice — that will make it worse. One concrete next step only.",
    "anxious":     "The user is anxious — worried about something specific or generally fearful. Be steady, not alarmed. Acknowledge the worry first. Then offer grounding or one practical action. Avoid uncertainty — be specific wherever possible.",
    "frustrated":  "The user is frustrated — blocked, unheard, or repeatedly failing. Validate that the situation IS frustrating before offering help. Don't play devil's advocate. Don't suggest they're doing something wrong unless asked.",
    "numb":        "The user feels emotionally numb or disconnected — often harder to reach than sadness. Don't try to make them feel. Be gentle and present. Ask a single soft question. Don't pressure them to open up. Numbness sometimes needs space, not solutions.",
}


def _cited_indices(response: str, n_sources: int) -> list[int]:
    seen: list[int] = []
    for match in _CITATION_RE.finditer(response or ""):
        idx = int(match.group(1))
        if 1 <= idx <= n_sources and idx not in seen:
            seen.append(idx)
    return seen


class ChatState(TypedDict, total=False):
    # Inputs
    query: str
    domain: str
    history: list[dict]
    lang: str
    user_id: str
    session_id: str
    # Memory loaded from DB
    memory_summary: Optional[str]
    emotion_arc: list[str]
    active_goal: Optional[str]
    user_memory: Optional[str]
    # Classification
    intent: str
    reasoning: str
    emotion: str
    emergency: bool
    detected_goal: Optional[str]
    # Routing
    routed_domain: str
    # Retrieval
    retrieved: list[dict]
    retrieved_ids: list[str]
    web_results: list[dict]
    # Classification extras
    secondary_emotion: Optional[str]
    # Generation
    fast_mode: bool
    response: str
    via: str


def _build_context(state: ChatState, confidence: str = "None", web_searched: bool = False) -> str:
    """Assemble the CONVERSATION CONTEXT block injected into every persona's system prompt.

    Includes: domain, emotion + secondary, tone guidance, conversation depth,
    confidence level, memory, emotional arc, active goal, language, and safety flags.
    """
    emotion = state.get("emotion", "neutral")
    secondary_emotion = state.get("secondary_emotion")
    tone_hint = _TONE_HINTS.get(emotion, "")

    # Conversation depth — helps personas calibrate pacing and avoid repetition
    n_turns = len(state.get("history", [])) // 2  # rough turn count

    ctx_parts = [
        f"Domain: {state.get('routed_domain', state.get('domain', 'Mental Health'))}.",
        f"User emotion: {emotion}" + (f" (secondary: {secondary_emotion})" if secondary_emotion else "") + ".",
    ]

    if state.get("lang") and state["lang"] != "auto":
        ctx_parts.append(f"Detected language: {state['lang']}.")

    if tone_hint:
        ctx_parts.append(f"Tone guidance: {tone_hint}")

    if secondary_emotion and secondary_emotion in _TONE_HINTS:
        sec_hint = _TONE_HINTS[secondary_emotion]
        ctx_parts.append(f"Secondary emotion context: {sec_hint}")

    if state.get("reasoning"):
        ctx_parts.append(f"Intent reasoning: {state['reasoning']}.")

    # Conversation depth signal
    if n_turns >= 3:
        ctx_parts.append(
            f"This is turn {n_turns + 1} of an ongoing conversation. "
            "Do NOT repeat advice or information already given. Build on what has been said."
        )

    # Confidence awareness — low confidence = acknowledge limits, ask if needed
    if confidence == "None":
        ctx_parts.append(
            "Knowledge confidence: None. "
            "IMPORTANT: Your knowledge base has NO verified information on this specific topic. "
            "This question is outside your domain. "
            "You MUST give a SHORT response (2-3 sentences max) that: "
            "1) Acknowledges you are not the right resource for this. "
            "2) Directs them to the appropriate help (doctor for medical issues, police for crimes outside your scope, etc). "
            "Do NOT ask clarifying questions. Do NOT pretend you can help. Do NOT fabricate any information. "
            "For physical medical symptoms (pain, fever, injury), say: see a doctor or visit the nearest clinic. If severe, call 112."
            + (" Web search results are available but may be unverified." if web_searched else "")
        )
    elif confidence == "Low":
        ctx_parts.append(
            "Knowledge confidence: Low. "
            "Your knowledge base has limited information on this topic. "
            "Be explicit about uncertainty — say 'Based on what I have, ...' or 'I\u2019m not certain, but ...'. "
            "Prefer asking a clarifying question over fabricating details. "
            "Always tell the user where to verify any figures or legal details you mention."
            + (" Web search was used to supplement." if web_searched else "")
        )
    elif confidence == "High" and web_searched:
        ctx_parts.append("High-confidence RAG result supplemented with current web sources.")

    user_memory = state.get("user_memory")
    if user_memory:
        ctx_parts.append(
            f"What is known about this user across past sessions: {user_memory[:900]}"
        )

    memory_summary = state.get("memory_summary")
    if memory_summary:
        ctx_parts.append(
            f"Memory from earlier in this conversation: {memory_summary}"
        )

    emotion_arc = state.get("emotion_arc", [])
    if len(emotion_arc) >= 3:
        # Only mention arc when it shows a meaningful trend
        ctx_parts.append(f"Emotional arc (recent turns): {' → '.join(emotion_arc[-6:])}")
        # Detect worsening trend
        crisis_states = {"hopeless", "numb", "scared"}
        if emotion_arc and emotion_arc[-1] in crisis_states:
            ctx_parts.append(
                "TREND FLAG: The emotional arc shows a worsening pattern. "
                "Be especially attentive and consider gently checking in on their safety."
            )

    active_goal = state.get("active_goal") or state.get("detected_goal")
    if active_goal:
        ctx_parts.append(
            f"User's current goal: '{active_goal}'. "
            "Proactively guide progress toward this goal in your response."
        )

    # Emergency / safety flags
    if state.get("emergency"):
        routed = state.get("routed_domain", "")
        if routed == "Legal":
            ctx_parts.append(
                "SAFETY FLAG: Emergency signals detected. "
                "Address immediate physical safety BEFORE discussing legal procedure."
            )
        elif routed in ("Mental Health", "Government Schemes"):
            ctx_parts.append(
                "SAFETY FLAG: This message contains crisis or emergency signals. "
                "Prioritise safety and provide crisis resources (iCall 9152987821, Tele-MANAS 14416)."
            )

    return " ".join(ctx_parts)


async def _load_memory(state: ChatState) -> dict:
    user_id = state.get("user_id")
    session_id = state.get("session_id")
    if not user_id or not session_id:
        return {"memory_summary": None, "emotion_arc": [], "active_goal": None, "user_memory": None}

    try:
        mem_task = db.fetch_session_memory(user_id=user_id, session_id=session_id)
        goal_task = db.fetch_goal(
            user_id=user_id, session_id=session_id, domain=state.get("domain", "Mental Health")
        )
        user_mem_task = db.fetch_user_memory(user_id=user_id)
        mem, goal, user_mem = await asyncio.gather(mem_task, goal_task, user_mem_task, return_exceptions=True)
    except Exception as err:
        log.warning("load_memory gather failed", error=str(err))
        return {"memory_summary": None, "emotion_arc": [], "active_goal": None, "user_memory": None}

    return {
        "memory_summary": mem["summary"] if isinstance(mem, dict) and mem else None,
        "emotion_arc": mem["emotionArc"] if isinstance(mem, dict) and mem else [],
        "active_goal": goal if isinstance(goal, str) else None,
        "user_memory": user_mem if isinstance(user_mem, str) else None,
    }


async def _classify(state: ChatState) -> dict:
    # fast_mode: only run intent — skip emotion + goal to save ~2s
    if state.get("fast_mode"):
        i = await intent_flow.detect(state["query"])
        return {
            "intent": i["intent"],
            "reasoning": i["reasoning"],
            "emergency": i["intent"] == "Panic" or i["emergency"],
            "emotion": "neutral",
            "secondary_emotion": None,
            "detected_goal": None,
        }

    intent_task = intent_flow.detect(state["query"])
    emotion_task = emotion_flow.detect(state["query"])
    goal_task = memory_flow.detect_goal(
        query=state["query"],
        domain=state.get("domain", "Mental Health"),
        history=state.get("history", []),
        existing_goal=state.get("active_goal"),
    )

    i, e, goal = await asyncio.gather(intent_task, emotion_task, goal_task)

    return {
        "intent": i["intent"],
        "reasoning": i["reasoning"],
        "emergency": i["intent"] == "Panic" or i["emergency"],
        "emotion": e["emotion"] if isinstance(e, dict) and e else "neutral",
        "secondary_emotion": e.get("secondary") if isinstance(e, dict) and e else None,
        "detected_goal": goal if isinstance(goal, str) else None,
    }


async def _route(state: ChatState) -> dict:
    return {"routed_domain": "Safety" if state.get("intent") == "Panic" else state.get("domain", "Mental Health")}


async def _retrieve(state: ChatState) -> dict:
    try:
        hits = await retriever.retrieve(
            state["query"],
            domain=state["routed_domain"],
            history=state.get("history", []),
            lang=state.get("lang"),
        )
        ids = [f"{h['id']}({h.get('rerank_score', h['score']):.2f})" for h in hits]
        if ids:
            log.info("retrieve", domain=state["routed_domain"], hits=", ".join(ids))
        return {"retrieved": hits, "retrieved_ids": ids}
    except Exception as err:
        log.error("retrieve failed", error=str(err))
        return {"retrieved": [], "retrieved_ids": []}


async def _maybe_search(state: ChatState) -> dict:
    if state.get("fast_mode"):
        return {"web_results": []}

    hits = state.get("retrieved", [])
    top_score = float(hits[0].get("rerank_score", hits[0].get("score", 0.0))) if hits else 0.0
    conf = _confidence_from(hits)

    should_search = needs_web_search(
        state["query"],
        n_hits=len(hits),
        top_score=top_score,
        domain=state.get("domain", ""),
    ) or conf in ("Low", "None")

    if not should_search:
        return {"web_results": []}

    log.info("web search triggered", query=state["query"][:60])
    try:
        results = await web_search(state["query"])
    except Exception as err:
        log.error("web search failed", error=str(err))
        return {"web_results": []}

    if results:
        log.info("web search completed", results=len(results))
    return {"web_results": results}


_PERSONA_NAMES = {
    "Mental Health": "Usha",
    "Legal": "Umang",
    "Government Schemes": "Aarogya",
    "Safety": "Raksha",
}


def _merge_web_results(state: ChatState) -> list[dict]:
    """Combine RAG chunks and web results into one list for the generate step."""
    retrieved = list(state.get("retrieved", []))
    for i, wr in enumerate(state.get("web_results", [])):
        retrieved.append({
            "id": f"web_{i}",
            "topic": wr.get("title") or "Web search result",
            "domain": state.get("routed_domain", "Mental Health"),
            "score": 0.7,
            "text": wr["text"],
            "source": wr.get("url", ""),
        })
    return retrieved


_DOMAIN_GRAPHS = {
    "Mental Health":      "usha",
    "Legal":              "legal",
    "Government Schemes": "aarogya",
    "Safety":             "raksha",
}

async def _generate(state: ChatState) -> dict:
    retrieved = _merge_web_results(state)
    rag_hits  = state.get("retrieved", [])
    conf      = _confidence_from(rag_hits)
    context   = _build_context(state, confidence=conf, web_searched=bool(state.get("web_results")))
    domain    = state.get("routed_domain", "Mental Health")

    _common = dict(
        query=state["query"],
        history=state.get("history", []),
        retrieved=retrieved,
        emotion=state.get("emotion", "neutral"),
        lang=state.get("lang", "auto"),
        outer_context=context,
        confidence=conf,
        fast_mode=state.get("fast_mode", False),
    )

    if domain == "Mental Health":
        out = await usha_graph.run(**_common)
    elif domain == "Legal":
        out = await legal_graph.run(**_common)
    elif domain == "Government Schemes":
        out = await aarogya_graph.run(**_common)
    elif domain == "Safety":
        out = await raksha_graph.run(**_common)
    else:
        # Fallback — should not normally happen
        out = await responder.respond(
            query=state["query"],
            intent=domain,
            emotion=state.get("emotion", "neutral"),
            lang=state.get("lang", "auto"),
            history=state.get("history", []),
            retrieved=retrieved,
            context=context,
            fast_mode=state.get("fast_mode", False),
        )

    return {"response": out["response"], "via": out["via"]}


async def _save_memory(state: ChatState) -> dict:
    user_id = state.get("user_id")
    session_id = state.get("session_id")
    if not user_id or not session_id:
        return {}

    async def _background():
        try:
            all_messages = [
                *state.get("history", []),
                {"role": "user", "content": state["query"]},
                {"role": "assistant", "content": state.get("response", "")},
            ]
            persona = _PERSONA_NAMES.get(state.get("routed_domain", "Mental Health"), "assistant")
            old_arc = state.get("emotion_arc", [])
            summary = await memory_flow.build_rolling_summary(all_messages, persona, emotion_arc=old_arc)
            emotion = state.get("emotion", "neutral")
            new_arc = [*old_arc[-9:], emotion]

            if summary:
                await db.save_session_memory(
                    user_id=user_id,
                    session_id=session_id,
                    summary=summary,
                    emotion_arc=new_arc,
                )
                await db.upsert_user_memory(user_id=user_id)

            goal = state.get("detected_goal")
            if goal:
                await db.save_goal(
                    user_id=user_id,
                    session_id=session_id,
                    domain=state.get("routed_domain", "Mental Health"),
                    goal=goal,
                )
        except Exception as err:
            log.error("background memory update failed", error=str(err))

    asyncio.create_task(_background())
    return {}


def _build_sources(hits: list[dict]) -> list[dict]:
    return [
        knowledge_meta.build_source_meta(h)
        for h in hits
        if not str(h.get("id", "")).startswith("web_")
    ]


def _confidence_from(hits: list[dict]) -> str:
    return knowledge_meta.compute_confidence(hits)


def _confidence_with_reasoning(hits: list[dict]) -> tuple[str, str]:
    return knowledge_meta.compute_confidence_with_reasoning(hits)


_builder = StateGraph(ChatState)
_builder.add_node("load_memory", _load_memory)
_builder.add_node("classify", _classify)
_builder.add_node("route", _route)
_builder.add_node("retrieve", _retrieve)
_builder.add_node("maybe_search", _maybe_search)
_builder.add_node("generate", _generate)
_builder.add_node("save_memory", _save_memory)

_builder.add_edge(START, "load_memory")
_builder.add_edge("load_memory", "classify")
_builder.add_edge("classify", "route")
_builder.add_edge("route", "retrieve")
_builder.add_edge("retrieve", "maybe_search")
_builder.add_edge("maybe_search", "generate")
_builder.add_edge("generate", "save_memory")
_builder.add_edge("save_memory", END)

_compiled = _builder.compile()


async def stream_run(
    *,
    query: str,
    domain: str,
    history: Optional[list[dict]] = None,
    lang: str = "auto",
    user_id: str = "",
    session_id: str = "",
    fast_mode: bool = False,
):
    """Async generator — yields {"token": "..."} per token then {"done": True, ...metadata}."""
    history = history or []

    state: ChatState = {
        "query": query,
        "domain": domain,
        "history": history,
        "lang": lang,
        "user_id": user_id,
        "session_id": session_id,
        "fast_mode": fast_mode,
    }

    state.update(await _load_memory(state))
    state.update(await _classify(state))
    state.update(await _route(state))
    state.update(await _retrieve(state))  # passes lang via state["lang"]
    state.update(await _maybe_search(state))

    retrieved = _merge_web_results(state)
    conf, conf_reason = _confidence_with_reasoning(state.get("retrieved", []))
    context = _build_context(state, confidence=conf, web_searched=bool(state.get("web_results")))

    collected: list[str] = []
    via_bag = {"via": "stream"}

    routed_domain = state.get("routed_domain", "Mental Health")
    _skw = dict(
        query=query, history=history, retrieved=retrieved,
        emotion=state.get("emotion", "neutral"), lang=lang,
        outer_context=context, confidence=conf,
        fast_mode=fast_mode, _via_bag=via_bag,
    )

    if routed_domain == "Mental Health":
        stream_gen = usha_graph.stream_run(**_skw)
    elif routed_domain == "Legal":
        stream_gen = legal_graph.stream_run(**_skw)
    elif routed_domain == "Government Schemes":
        stream_gen = aarogya_graph.stream_run(**_skw)
    elif routed_domain == "Safety":
        stream_gen = raksha_graph.stream_run(**_skw)
    else:
        # Fallback — should not normally happen
        stream_gen = responder.stream_respond(
            query=query, intent=routed_domain, emotion=state.get("emotion", "neutral"),
            lang=lang, history=history, retrieved=retrieved, context=context,
            fast_mode=fast_mode, _via_bag=via_bag,
        )

    async for token in stream_gen:
        collected.append(token)
        yield {"token": token}

    full_response = "".join(collected)
    rag_hits = state.get("retrieved", [])
    cited = _cited_indices(full_response, len(rag_hits))
    goal = state.get("detected_goal") or state.get("active_goal")
    _conf_label, _conf_reason = conf, conf_reason

    state["response"] = full_response
    asyncio.create_task(_save_memory(state))

    yield {
        "done": True,
        "response": full_response,
        "isEmergency": bool(state.get("emergency", False)),
        "via": via_bag["via"],
        "routedDomain": state.get("routed_domain"),
        "emotion": state.get("emotion"),
        "retrievedIds": state.get("retrieved_ids", []),
        "sources": _build_sources(rag_hits),
        "citedIndices": cited,
        "confidence": _conf_label,
        "confidenceReasoning": _conf_reason,
        "goal": goal,
        "memorySummary": state.get("memory_summary"),
        "webSearched": bool(state.get("web_results")),
        "routing": {
            "intent": state.get("intent"),
            "reasoning": state.get("reasoning"),
            "emotion": state.get("emotion"),
            "routedDomain": state.get("routed_domain"),
            "requestedDomain": domain,
            "lang": lang,
            "isEmergency": bool(state.get("emergency", False)),
        },
    }


async def run(
    *,
    query: str,
    domain: str,
    history: Optional[list[dict]] = None,
    lang: str = "auto",
    user_id: str = "",
    session_id: str = "",
    fast_mode: bool = False,
) -> dict:
    final = await _compiled.ainvoke({
        "query": query,
        "domain": domain,
        "history": history or [],
        "lang": lang,
        "user_id": user_id,
        "session_id": session_id,
        "fast_mode": fast_mode,
    })

    rag_hits = final.get("retrieved", [])
    response_text = final.get("response", "")
    cited = _cited_indices(response_text, len(rag_hits))
    goal = final.get("detected_goal") or final.get("active_goal")
    _conf_label, _conf_reason = _confidence_with_reasoning(rag_hits)

    return {
        "response": response_text,
        "isEmergency": bool(final.get("emergency", False)),
        "via": final.get("via"),
        "routedDomain": final.get("routed_domain"),
        "emotion": final.get("emotion"),
        "retrievedIds": final.get("retrieved_ids", []),
        "sources": _build_sources(rag_hits),
        "citedIndices": cited,
        "confidence": _conf_label,
        "confidenceReasoning": _conf_reason,
        "goal": goal,
        "memorySummary": final.get("memory_summary"),
        "webSearched": bool(final.get("web_results")),
        "routing": {
            "intent": final.get("intent"),
            "reasoning": final.get("reasoning"),
            "emotion": final.get("emotion"),
            "routedDomain": final.get("routed_domain"),
            "requestedDomain": domain,
            "lang": lang,
            "isEmergency": bool(final.get("emergency", False)),
        },
    }
