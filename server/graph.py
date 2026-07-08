# Graph flow:
#   START → load_memory → classify → route → retrieve → maybe_search → generate → save_memory → END
import asyncio
import re
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, START, END

from ai import emotion as emotion_flow
from ai import intent as intent_flow
from ai import responder
from ai import memory as memory_flow
from ai.tools import web_search, needs_web_search
from logger import get_logger
from rag import retriever
import db

log = get_logger("graph")

_CITATION_RE = re.compile(r"\[(\d+)\]")


def _cited_indices(response: str, n_sources: int) -> list[int]:
    seen: list[int] = []
    for match in _CITATION_RE.finditer(response or ""):
        try:
            idx = int(match.group(1))
        except (ValueError, IndexError):
            continue
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
    user_memory: Optional[str]   # cross-session aggregated user memory
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


async def _load_memory(state: ChatState) -> dict:
    user_id = state.get("user_id")
    session_id = state.get("session_id")
    if not user_id or not session_id or state.get("fast_mode"):
        return {"memory_summary": None, "emotion_arc": [], "active_goal": None, "user_memory": None}

    mem_task = db.fetch_session_memory(user_id=user_id, session_id=session_id)
    goal_task = db.fetch_goal(
        user_id=user_id, session_id=session_id, domain=state.get("domain", "Mental Health")
    )
    user_mem_task = db.fetch_user_memory(user_id=user_id)
    mem, goal, user_mem = await asyncio.gather(mem_task, goal_task, user_mem_task)

    return {
        "memory_summary": mem["summary"] if mem else None,
        "emotion_arc": mem["emotionArc"] if mem else [],
        "active_goal": goal,
        "user_memory": user_mem,
    }


async def _classify(state: ChatState) -> dict:
    # fast_mode (voice): only run intent — skip emotion + goal to save ~2s
    if state.get("fast_mode"):
        i = await intent_flow.detect(state["query"])
        return {
            "intent": i["intent"],
            "reasoning": i["reasoning"],
            "emergency": i["intent"] == "Panic" or i["emergency"],
            "emotion": "neutral",
            "detected_goal": None,
        }

    history_len = len(state.get("history", []))

    intent_task = intent_flow.detect(state["query"])
    # Run emotion always (turn 1+) — even first message can signal emotional state
    # Run goal from turn 1 — user may state a goal in their very first message
    emotion_task = emotion_flow.detect(state["query"])
    goal_task = memory_flow.detect_goal(
        query=state["query"],
        domain=state.get("domain", "Mental Health"),
        history=state.get("history", []),
    )

    results = await asyncio.gather(intent_task, emotion_task, goal_task)

    i, e, goal = results

    return {
        "intent": i["intent"],
        "reasoning": i["reasoning"],
        "emergency": i["intent"] == "Panic" or i["emergency"],
        "emotion": e["emotion"] if e else "neutral",
        "detected_goal": goal,
    }


async def _route(state: ChatState) -> dict:
    return {"routed_domain": "Safety" if state["intent"] == "Panic" else state["domain"]}


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
    # skip web search in voice mode — too slow for real-time conversation
    if state.get("fast_mode"):
        return {"web_results": []}

    hits = state.get("retrieved", [])
    top_score = float(hits[0].get("rerank_score", hits[0].get("score", 0.0))) if hits else 0.0

    if not needs_web_search(state["query"], n_hits=len(hits), top_score=top_score, domain=state.get("domain", "")):
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


async def _generate(state: ChatState) -> dict:
    memory_summary = state.get("memory_summary")
    active_goal = state.get("active_goal") or state.get("detected_goal")
    web_results = state.get("web_results", [])
    emotion_arc = state.get("emotion_arc", [])

    emotion = state.get("emotion", "neutral")
    # Emotion-driven tone hint — gives persona explicit guidance without overriding character
    _TONE_HINT = {
        "sad":     "The user seems sad or low. Be especially gentle, warm, and present. Don't rush to solutions.",
        "angry":   "The user seems frustrated or angry. Acknowledge their feeling first before any information.",
        "scared":  "The user seems scared or anxious. Be calm, grounding, and reassuring first.",
        "confused": "The user seems confused. Be clear, structured, and patient — avoid jargon.",
        "happy":   "The user seems positive. Match their energy while staying helpful.",
        "neutral": "",
    }
    tone_hint = _TONE_HINT.get(emotion, "")

    ctx_parts = [
        f"Domain: {state['routed_domain']}.",
        f"User emotion: {emotion}.",
        f"Intent: {state.get('reasoning')}.",
    ]
    if tone_hint:
        ctx_parts.append(f"Tone guidance: {tone_hint}")
    user_memory = state.get("user_memory")
    if user_memory:
        ctx_parts.append(f"What is known about this user across past conversations: {user_memory[:900]}")
    if memory_summary:
        ctx_parts.append(f"Memory from earlier in this conversation: {memory_summary}")
    if emotion_arc:
        arc_str = " → ".join(emotion_arc[-5:])
        ctx_parts.append(f"Emotional arc (recent): {arc_str}")
    if active_goal:
        ctx_parts.append(
            f"The user's current goal: '{active_goal}'. "
            "Keep this goal in mind and proactively guide progress toward it."
        )

    # merge web results so the responder can cite them alongside RAG chunks
    retrieved = list(state.get("retrieved", []))
    for i, wr in enumerate(web_results):
        retrieved.append({
            "id": f"web_{i}",
            "topic": wr.get("title") or "Web search result",
            "domain": state["routed_domain"],
            "score": 0.7,
            "text": wr["text"],
            "source": wr.get("url", ""),
        })

    out = await responder.respond(
        query=state["query"],
        intent=state["routed_domain"],
        emotion=state.get("emotion", "neutral"),
        lang=state.get("lang", "auto"),
        history=state.get("history", []),
        retrieved=retrieved,
        context=" ".join(ctx_parts),
        fast_mode=state.get("fast_mode", False),
    )
    return {"response": out["response"], "via": out["via"]}


async def _save_memory(state: ChatState) -> dict:
    # fires in background so it never blocks the response
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
            new_arc = [*old_arc[-9:], emotion]  # keep last 10 entries

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
        except Exception as e:
            log.error("background memory update failed", error=str(e))

    asyncio.create_task(_background())
    return {}


def _build_sources(hits: list[dict]) -> list[dict]:
    return [
        {
            "id": h["id"],
            "topic": h["topic"],
            "domain": h["domain"],
            "score": float(h.get("score", 0.0)),
            "rerankScore": float(h["rerank_score"]) if "rerank_score" in h else None,
            "source": h.get("source"),
            "lastVerifiedOn": h.get("lastVerifiedOn"),
            "verifiedBy": h.get("verifiedBy", "human"),
        }
        for h in hits
        if not str(h.get("id", "")).startswith("web_")  # web hits are cited inline, not shown in source panel
    ]


def _confidence_from(hits: list[dict]) -> str:
    rag_hits = [h for h in hits if not str(h.get("id", "")).startswith("web_")]
    if not rag_hits:
        return "None"
    top = rag_hits[0]
    if "rerank_score" in top:
        s = float(top["rerank_score"])
        if s >= 5.0:
            return "High"
        if s >= 2.0:
            return "Medium"
        return "Low"
    s = float(top.get("score", 0.0))
    if s >= 0.88:
        return "High"
    if s >= 0.78:
        return "Medium"
    return "Low"


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
    }

    state.update(await _load_memory(state))
    state.update(await _classify(state))
    state.update(await _route(state))
    state.update(await _retrieve(state))
    state.update(await _maybe_search(state))

    memory_summary = state.get("memory_summary")
    user_memory = state.get("user_memory")
    active_goal = state.get("active_goal") or state.get("detected_goal")
    emotion_arc = state.get("emotion_arc", [])
    web_results = state.get("web_results", [])

    ctx_parts = [
        f"Domain: {state['routed_domain']}.",
        f"Emotion: {state.get('emotion')}.",
        f"Intent: {state.get('reasoning')}.",
    ]
    if user_memory:
        ctx_parts.append(f"What is known about this user across past conversations: {user_memory[:900]}")
    if memory_summary:
        ctx_parts.append(f"Memory from earlier in this conversation: {memory_summary}")
    if emotion_arc:
        ctx_parts.append(f"Emotional arc: {' → '.join(emotion_arc[-5:])}")
    if active_goal:
        ctx_parts.append(
            f"The user's current goal: '{active_goal}'. "
            "Keep this goal in mind and proactively guide progress toward it."
        )

    retrieved = list(state.get("retrieved", []))
    for i, wr in enumerate(web_results):
        retrieved.append({
            "id": f"web_{i}",
            "topic": wr.get("title") or "Web search result",
            "domain": state["routed_domain"],
            "score": 0.7,
            "text": wr["text"],
            "source": wr.get("url", ""),
        })

    collected: list[str] = []
    via_bag = {"via": "stream"}
    async for token in responder.stream_respond(
        query=query,
        intent=state["routed_domain"],
        emotion=state.get("emotion", "neutral"),
        lang=lang,
        history=history,
        retrieved=retrieved,
        context=" ".join(ctx_parts),
        _via_bag=via_bag,
    ):
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
        "memorySummary": memory_summary,
        "webSearched": bool(web_results),
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
