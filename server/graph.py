# Graph flow:
#   START → load_memory → classify → route → retrieve → maybe_search → generate → save_memory → END
#
# Domain dispatch (all invisible to user):
#   "Mental Health"      → usha_graph     (Usha multi-agent)
#   "Legal"              → legal_graph    (Umang multi-agent)
#   "Government Schemes" → aarogya_graph  (Aarogya multi-agent)
#   "Safety"             → raksha_graph   (Raksha multi-agent)
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
    "sad":      "The user seems sad or low. Be especially gentle, warm, and present. Don't rush to solutions.",
    "angry":    "The user seems frustrated or angry. Acknowledge their feeling first before any information.",
    "scared":   "The user seems scared or anxious. Be calm, grounding, and reassuring before anything else.",
    "confused": "The user seems confused. Be clear, structured, and patient — no jargon.",
    "happy":    "The user seems positive. Match their energy while staying helpful.",
    "neutral":  "",
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
    # Generation
    fast_mode: bool
    response: str
    via: str


def _build_context(state: ChatState) -> str:
    """Assemble the CONVERSATION CONTEXT block injected into the system prompt."""
    emotion = state.get("emotion", "neutral")
    tone_hint = _TONE_HINTS.get(emotion, "")

    ctx_parts = [
        f"Domain: {state.get('routed_domain', state.get('domain', 'Mental Health'))}.",
        f"User emotion: {emotion}.",
    ]
    if state.get("reasoning"):
        ctx_parts.append(f"Intent reasoning: {state['reasoning']}.")
    if tone_hint:
        ctx_parts.append(f"Tone guidance: {tone_hint}")

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
    if emotion_arc:
        ctx_parts.append(f"Emotional arc (recent): {' → '.join(emotion_arc[-5:])}")

    active_goal = state.get("active_goal") or state.get("detected_goal")
    if active_goal:
        ctx_parts.append(
            f"User's current goal: '{active_goal}'. "
            "Keep this in mind and proactively guide progress toward it."
        )

    # If emergency flag is set but routed to Legal (not Panic), surface a safety note
    # so the legal persona knows to address danger before diving into law.
    if state.get("emergency") and state.get("routed_domain") == "Legal":
        ctx_parts.append(
            "SAFETY FLAG: The user's message contains signals of danger or distress. "
            "Address immediate safety before discussing legal procedure."
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
        "detected_goal": goal if isinstance(goal, str) else None,
    }


async def _route(state: ChatState) -> dict:
    return {"routed_domain": "Safety" if state.get("intent") == "Panic" else state.get("domain", "Mental Health")}


async def _retrieve(state: ChatState) -> dict:
    try:
        hits = await retriever.retrieve(state["query"], domain=state["routed_domain"])
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

    if not needs_web_search(
        state["query"],
        n_hits=len(hits),
        top_score=top_score,
        domain=state.get("domain", ""),
    ):
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
    context   = _build_context(state)
    domain    = state.get("routed_domain", "Mental Health")
    rag_hits  = state.get("retrieved", [])
    conf      = _confidence_from(rag_hits)

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
            summary = await memory_flow.build_rolling_summary(all_messages, persona)

            old_arc = state.get("emotion_arc", [])
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
    state.update(await _retrieve(state))
    state.update(await _maybe_search(state))

    retrieved = _merge_web_results(state)
    context = _build_context(state)     # shared helper — includes tone hints

    collected: list[str] = []
    via_bag = {"via": "stream"}

    routed_domain = state.get("routed_domain", "Mental Health")
    conf     = _confidence_from(state.get("retrieved", []))
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
            lang=lang, history=history, retrieved=retrieved, context=context, _via_bag=via_bag,
        )

    async for token in stream_gen:
        collected.append(token)
        yield {"token": token}

    full_response = "".join(collected)
    rag_hits = state.get("retrieved", [])
    cited = _cited_indices(full_response, len(rag_hits))
    goal = state.get("detected_goal") or state.get("active_goal")

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
        "confidence": _confidence_from(rag_hits),
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

    return {
        "response": response_text,
        "isEmergency": bool(final.get("emergency", False)),
        "via": final.get("via"),
        "routedDomain": final.get("routed_domain"),
        "emotion": final.get("emotion"),
        "retrievedIds": final.get("retrieved_ids", []),
        "sources": _build_sources(rag_hits),
        "citedIndices": cited,
        "confidence": _confidence_from(rag_hits),
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
