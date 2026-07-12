"""
Usha's multi-agent mental health reasoning sub-graph.

User sees: one warm, present assistant named Usha.
Internally: specialized agents collaborate via LangGraph.

Graph:
  START
    → analyze     [Agent 1: 8B LLM — classify emotion, detect crisis]
    → prepare     [Agents 2-3: Python — organize chunks, check crisis override]
    → compose     [Agent 4: 70B LLM — synthesize final Usha response]
    → END

Crisis detection is Python-hardcoded (Agent 3) — never delegated to LLM alone.
Invoked from graph.py when routed_domain == "Mental Health".
"""
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, START, END

from ai import usha_agents
from ai.provider import chat, _ollama_up, _is_fallback_worthy
from config import GROQ_MODEL_SMART
from logger import get_logger

log = get_logger("usha_graph")


class UshaState(TypedDict, total=False):
    # Input from outer graph
    query:         str
    history:       list[dict]
    retrieved:     list[dict]
    emotion:       str          # outer graph emotion detector
    lang:          str
    outer_context: str
    fast_mode:     bool
    confidence:    str

    # Agent 1 output
    emotion_analysis: dict

    # Agents 2-3 output
    organized_chunks: dict
    crisis_override:  bool

    # Agent 4 output
    composer_messages: list[dict]
    response:          str
    via:               str


async def _analyze(state: UshaState) -> dict:
    """Agent 1 — Emotion Analyzer (8B, ~150 ms)."""
    if state.get("fast_mode"):
        return {"emotion_analysis": {
            "emotional_state": state.get("emotion", "neutral"),
            "intensity": "low", "crisis_type": None,
            "topic_type": "venting", "needs_grounding": False,
            "needs_resources": False, "follow_up": None,
        }}
    try:
        analysis = await usha_agents.analyze_emotional_state(
            query=state["query"],
            history=state.get("history", []),
        )
        log.info("emotion_analyzer", state=analysis["emotional_state"], intensity=analysis["intensity"])
        return {"emotion_analysis": analysis}
    except Exception as err:
        log.warning("emotion_analyzer node error", error=str(err))
        return {"emotion_analysis": {
            "emotional_state": "neutral", "intensity": "low", "crisis_type": None,
            "topic_type": "venting", "needs_grounding": False,
            "needs_resources": False, "follow_up": None,
        }}


async def _prepare(state: UshaState) -> dict:
    """
    Agents 2 & 3 — Python-only preparation (zero added latency).
    Organizes chunks and runs hard-coded crisis check.
    """
    analysis  = state.get("emotion_analysis", {})
    retrieved = state.get("retrieved", [])

    organized = usha_agents.organize_chunks(retrieved, analysis.get("topic_type", "venting"))
    crisis    = usha_agents.is_crisis(state["query"], analysis)

    log.info(
        "usha_prepare",
        primary=len(organized["primary"]),
        secondary=len(organized["secondary"]),
        crisis_override=crisis,
    )

    return {"organized_chunks": organized, "crisis_override": crisis}


async def _compose(state: UshaState) -> dict:
    """Agent 4 — Response Composer (70B model)."""
    messages = usha_agents.build_composer_messages(
        query=state["query"],
        history=state.get("history", []),
        emotion_analysis=state.get("emotion_analysis", {}),
        organized_chunks=state.get("organized_chunks", {}),
        crisis_override=bool(state.get("crisis_override", False)),
        emotion=state.get("emotion", "neutral"),
        lang=state.get("lang", "auto"),
        outer_context=state.get("outer_context", ""),
        confidence=state.get("confidence", "None"),
    )
    max_tokens = 500 if state.get("fast_mode") else 900
    result = await chat(model=GROQ_MODEL_SMART, temperature=0.35, max_tokens=max_tokens, messages=messages)
    return {"response": result["content"], "via": result["via"], "composer_messages": messages}


_builder = StateGraph(UshaState)
_builder.add_node("analyze", _analyze)
_builder.add_node("prepare", _prepare)
_builder.add_node("compose", _compose)

_builder.add_edge(START,     "analyze")
_builder.add_edge("analyze", "prepare")
_builder.add_edge("prepare", "compose")
_builder.add_edge("compose", END)

_compiled = _builder.compile()


async def run(
    *,
    query:         str,
    history:       list[dict],
    retrieved:     list[dict],
    emotion:       str,
    lang:          str,
    outer_context: str,
    confidence:    str = "None",
    fast_mode:     bool = False,
) -> dict:
    """Non-streaming entry point. Returns {"response": str, "via": str}."""
    final = await _compiled.ainvoke({
        "query": query, "history": history, "retrieved": retrieved,
        "emotion": emotion, "lang": lang, "outer_context": outer_context,
        "confidence": confidence, "fast_mode": fast_mode,
    })
    return {"response": final.get("response", ""), "via": final.get("via", "groq")}


async def stream_run(
    *,
    query:         str,
    history:       list[dict],
    retrieved:     list[dict],
    emotion:       str,
    lang:          str,
    outer_context: str,
    confidence:    str = "None",
    _via_bag:      Optional[dict] = None,
):
    """Async generator — analyze+prepare first, then stream compose."""
    from ai import groq_client, ollama_client, anthropic_client
    from ai.circuit_breaker import groq_breaker, ollama_breaker, anthropic_breaker

    analysis    = await _analyze({"query": query, "history": history, "fast_mode": False})
    preparation = await _prepare({
        "query": query, "retrieved": retrieved,
        "emotion_analysis": analysis["emotion_analysis"],
    })
    messages = usha_agents.build_composer_messages(
        query=query, history=history,
        emotion_analysis=analysis["emotion_analysis"],
        organized_chunks=preparation["organized_chunks"],
        crisis_override=bool(preparation.get("crisis_override", False)),
        emotion=emotion, lang=lang, outer_context=outer_context, confidence=confidence,
    )
    _opts = dict(messages=messages, model=GROQ_MODEL_SMART, temperature=0.35, max_tokens=900)

    try:
        first = True
        async for token in groq_breaker.call_stream(groq_client.stream_chat, **_opts):
            if first and _via_bag is not None:
                _via_bag["via"] = "groq-usha"
                first = False
            yield token
        return
    except Exception as err:
        if not _is_fallback_worthy(err):
            raise
        log.warning("usha groq stream failed", error=type(err).__name__, next="ollama")

    if await _ollama_up():
        try:
            first = True
            async for token in ollama_breaker.call_stream(
                ollama_client.stream_chat, messages=messages, temperature=0.35, max_tokens=900,
            ):
                if first and _via_bag is not None:
                    _via_bag["via"] = "ollama-usha"
                    first = False
                yield token
            return
        except Exception as err:
            log.warning("usha ollama stream failed", error=str(err), next="anthropic")

    if anthropic_client.is_enabled():
        try:
            first = True
            async for token in anthropic_breaker.call_stream(
                anthropic_client.stream_chat, messages=messages, temperature=0.35, max_tokens=900,
            ):
                if first and _via_bag is not None:
                    _via_bag["via"] = "anthropic-usha"
                    first = False
                yield token
            return
        except Exception as err:
            log.warning("usha anthropic stream failed", error=str(err), next="non-streaming")

    result = await chat(model=GROQ_MODEL_SMART, temperature=0.35, max_tokens=900, messages=messages)
    if _via_bag is not None:
        _via_bag["via"] = result.get("via", "fallback-usha")
    yield result["content"]
