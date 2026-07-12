"""
Aarogya's multi-agent government scheme reasoning sub-graph.

User sees: one helpful, practical guide named Aarogya.
Internally: specialized agents collaborate via LangGraph.

Graph:
  START
    → analyze     [Agent 1: 8B LLM — classify scheme category, extract user profile]
    → prepare     [Agents 2-4: Python — organize chunks, state specialist, document checker]
    → compose     [Agent 5: 70B LLM — synthesize final Aarogya response]
    → END

Invoked from graph.py when routed_domain == "Government Schemes".
"""
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, START, END

from ai import aarogya_agents
from ai.provider import chat, _ollama_up, _is_fallback_worthy
from config import GROQ_MODEL_SMART
from logger import get_logger

log = get_logger("aarogya_graph")


class AaroyaState(TypedDict, total=False):
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
    scheme_analysis: dict

    # Agents 2-4 output
    organized_chunks:   dict
    document_checklist: Optional[list]

    # Agent 5 output
    composer_messages: list[dict]
    response:          str
    via:               str


async def _analyze(state: AaroyaState) -> dict:
    """Agent 1 — Scheme Analyzer (8B, ~150 ms)."""
    if state.get("fast_mode"):
        return {"scheme_analysis": {
            "scheme_category": "General", "state_mentioned": None,
            "income_level": None, "social_category": None, "occupation": None,
            "gender": None, "needs_eligibility_check": True,
            "needs_document_list": False, "needs_application_steps": False,
            "is_specific_scheme": False, "specific_scheme_name": None, "missing_info": None,
        }}
    try:
        analysis = await aarogya_agents.analyze_scheme_query(
            query=state["query"],
            history=state.get("history", []),
        )
        log.info("scheme_analyzer", category=analysis["scheme_category"], state=analysis.get("state_mentioned"))
        return {"scheme_analysis": analysis}
    except Exception as err:
        log.warning("scheme_analyzer node error", error=str(err))
        return {"scheme_analysis": {
            "scheme_category": "General", "state_mentioned": None,
            "income_level": None, "social_category": None, "occupation": None,
            "gender": None, "needs_eligibility_check": True,
            "needs_document_list": False, "needs_application_steps": False,
            "is_specific_scheme": False, "specific_scheme_name": None, "missing_info": None,
        }}


async def _prepare(state: AaroyaState) -> dict:
    """
    Agents 2-4 — Python-only preparation (zero added latency).
    Organizes chunks by scheme/application/document type and prepares document checklist.
    """
    analysis  = state.get("scheme_analysis", {})
    retrieved = state.get("retrieved", [])

    organized  = aarogya_agents.organize_chunks(retrieved, analysis)
    doc_list   = None
    if analysis.get("needs_document_list"):
        doc_list = aarogya_agents.get_document_checklist(analysis.get("scheme_category", "General"))

    log.info(
        "aarogya_prepare",
        scheme=len(organized["scheme"]),
        application=len(organized["application"]),
        document=len(organized["document"]),
        doc_list=bool(doc_list),
    )

    return {"organized_chunks": organized, "document_checklist": doc_list}


async def _compose(state: AaroyaState) -> dict:
    """Agent 5 — Response Composer (70B model)."""
    messages = aarogya_agents.build_composer_messages(
        query=state["query"],
        history=state.get("history", []),
        scheme_analysis=state.get("scheme_analysis", {}),
        organized_chunks=state.get("organized_chunks", {}),
        document_checklist=state.get("document_checklist"),
        lang=state.get("lang", "auto"),
        outer_context=state.get("outer_context", ""),
        confidence=state.get("confidence", "None"),
    )
    max_tokens = 500 if state.get("fast_mode") else 900
    result = await chat(model=GROQ_MODEL_SMART, temperature=0.2, max_tokens=max_tokens, messages=messages)
    return {"response": result["content"], "via": result["via"], "composer_messages": messages}


_builder = StateGraph(AaroyaState)
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
        "scheme_analysis": analysis["scheme_analysis"],
    })
    messages = aarogya_agents.build_composer_messages(
        query=query, history=history,
        scheme_analysis=analysis["scheme_analysis"],
        organized_chunks=preparation["organized_chunks"],
        document_checklist=preparation.get("document_checklist"),
        lang=lang, outer_context=outer_context, confidence=confidence,
    )
    _opts = dict(messages=messages, model=GROQ_MODEL_SMART, temperature=0.2, max_tokens=900)

    try:
        first = True
        async for token in groq_breaker.call_stream(groq_client.stream_chat, **_opts):
            if first and _via_bag is not None:
                _via_bag["via"] = "groq-aarogya"
                first = False
            yield token
        return
    except Exception as err:
        if not _is_fallback_worthy(err):
            raise
        log.warning("aarogya groq stream failed", error=type(err).__name__, next="ollama")

    if await _ollama_up():
        try:
            first = True
            async for token in ollama_breaker.call_stream(
                ollama_client.stream_chat, messages=messages, temperature=0.2, max_tokens=900,
            ):
                if first and _via_bag is not None:
                    _via_bag["via"] = "ollama-aarogya"
                    first = False
                yield token
            return
        except Exception as err:
            log.warning("aarogya ollama stream failed", error=str(err), next="anthropic")

    if anthropic_client.is_enabled():
        try:
            first = True
            async for token in anthropic_breaker.call_stream(
                anthropic_client.stream_chat, messages=messages, temperature=0.2, max_tokens=900,
            ):
                if first and _via_bag is not None:
                    _via_bag["via"] = "anthropic-aarogya"
                    first = False
                yield token
            return
        except Exception as err:
            log.warning("aarogya anthropic stream failed", error=str(err), next="non-streaming")

    result = await chat(model=GROQ_MODEL_SMART, temperature=0.2, max_tokens=900, messages=messages)
    if _via_bag is not None:
        _via_bag["via"] = result.get("via", "fallback-aarogya")
    yield result["content"]
