"""Raksha's LangGraph sub-graph: analyze → prepare → compose. Invoked for Safety domain."""
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, START, END

from ai import raksha_agents
from ai.provider import chat, _ollama_up, _is_fallback_worthy
from config import GROQ_MODEL_SMART
from logger import get_logger

log = get_logger("raksha_graph")


class RakshaState(TypedDict, total=False):
    # Input from outer graph
    query:         str
    history:       list[dict]
    retrieved:     list[dict]
    emotion:       str
    lang:          str
    outer_context: str
    fast_mode:     bool
    confidence:    str

    # Agent 1 output
    situation_analysis: dict

    # Agents 2-3 output
    organized_chunks: dict
    safety_plan:      Optional[list]

    # Agent 4 output
    composer_messages: list[dict]
    response:          str
    via:               str


async def _analyze(state: RakshaState) -> dict:
    """Agent 1 — Situation Classifier (8B, ~150 ms)."""
    if state.get("fast_mode"):
        return {"situation_analysis": {
            "situation_type": "safety_awareness", "threat_category": "general",
            "urgency": "informational", "needs_helpline": True,
            "needs_evidence_preservation": False, "needs_safety_plan": False,
            "needs_reporting_steps": False, "is_child_involved": False, "follow_up": None,
        }}
    try:
        analysis = await raksha_agents.classify_situation(
            query=state["query"],
            history=state.get("history", []),
        )
        log.info(
            "situation_classifier",
            situation=analysis["situation_type"],
            threat=analysis["threat_category"],
            urgency=analysis["urgency"],
        )
        return {"situation_analysis": analysis}
    except Exception as err:
        log.warning("situation_classifier node error", error=str(err))
        return {"situation_analysis": {
            "situation_type": "recent_incident", "threat_category": "general",
            "urgency": "informational", "needs_helpline": True,
            "needs_evidence_preservation": False, "needs_safety_plan": False,
            "needs_reporting_steps": False, "is_child_involved": False, "follow_up": None,
        }}


async def _prepare(state: RakshaState) -> dict:
    """
    Agents 2 & 3 — Python-only preparation (zero added latency).
    Organizes chunks by type and generates deterministic safety plan when needed.
    """
    analysis  = state.get("situation_analysis", {})
    retrieved = state.get("retrieved", [])

    organized   = raksha_agents.organize_chunks(retrieved, analysis)
    safety_plan = None
    if analysis.get("needs_safety_plan") or analysis.get("urgency") in ("immediate", "recent"):
        safety_plan = raksha_agents.get_safety_plan(
            threat_category=analysis.get("threat_category", "general"),
            urgency=analysis.get("urgency", "informational"),
        )

    log.info(
        "raksha_prepare",
        contacts=len(organized["contacts"]),
        women=len(organized["women"]),
        cyber=len(organized["cyber"]),
        has_plan=bool(safety_plan),
    )

    return {"organized_chunks": organized, "safety_plan": safety_plan}


async def _compose(state: RakshaState) -> dict:
    """Agent 4 — Response Composer (70B model)."""
    messages = raksha_agents.build_composer_messages(
        query=state["query"],
        history=state.get("history", []),
        situation_analysis=state.get("situation_analysis", {}),
        organized_chunks=state.get("organized_chunks", {}),
        safety_plan=state.get("safety_plan"),
        lang=state.get("lang", "auto"),
        outer_context=state.get("outer_context", ""),
        confidence=state.get("confidence", "None"),
    )
    max_tokens = 500 if state.get("fast_mode") else 900
    result = await chat(model=GROQ_MODEL_SMART, temperature=0.2, max_tokens=max_tokens, messages=messages)
    return {"response": result["content"], "via": result["via"], "composer_messages": messages}


_builder = StateGraph(RakshaState)
_builder.add_node("analyze",  _analyze)
_builder.add_node("prepare",  _prepare)
_builder.add_node("compose",  _compose)

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
        "situation_analysis": analysis["situation_analysis"],
    })
    messages = raksha_agents.build_composer_messages(
        query=query, history=history,
        situation_analysis=analysis["situation_analysis"],
        organized_chunks=preparation["organized_chunks"],
        safety_plan=preparation.get("safety_plan"),
        lang=lang, outer_context=outer_context, confidence=confidence,
    )
    _opts = dict(messages=messages, model=GROQ_MODEL_SMART, temperature=0.2, max_tokens=900)

    try:
        first = True
        async for token in groq_breaker.call_stream(groq_client.stream_chat, **_opts):
            if first and _via_bag is not None:
                _via_bag["via"] = "groq-raksha"
                first = False
            yield token
        return
    except Exception as err:
        if not _is_fallback_worthy(err):
            raise
        log.warning("raksha groq stream failed", error=type(err).__name__, next="ollama")

    if await _ollama_up():
        try:
            first = True
            async for token in ollama_breaker.call_stream(
                ollama_client.stream_chat, messages=messages, temperature=0.2, max_tokens=900,
            ):
                if first and _via_bag is not None:
                    _via_bag["via"] = "ollama-raksha"
                    first = False
                yield token
            return
        except Exception as err:
            log.warning("raksha ollama stream failed", error=str(err), next="anthropic")

    if anthropic_client.is_enabled():
        try:
            first = True
            async for token in anthropic_breaker.call_stream(
                anthropic_client.stream_chat, messages=messages, temperature=0.2, max_tokens=900,
            ):
                if first and _via_bag is not None:
                    _via_bag["via"] = "anthropic-raksha"
                    first = False
                yield token
            return
        except Exception as err:
            log.warning("raksha anthropic stream failed", error=str(err), next="non-streaming")

    result = await chat(model=GROQ_MODEL_SMART, temperature=0.2, max_tokens=900, messages=messages)
    if _via_bag is not None:
        _via_bag["via"] = result.get("via", "fallback-raksha")
    yield result["content"]
