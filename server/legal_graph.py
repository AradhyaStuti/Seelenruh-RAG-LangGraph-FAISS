"""Umang's LangGraph sub-graph: analyze → prepare → compose. Invoked for Legal domain."""
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, START, END

from ai import legal_agents
from ai.provider import chat, _ollama_up, _is_fallback_worthy
from ai.quality_checker import check_response, append_quality_note
from ai.hallucination_guardrails import validate_citations, build_guardrail_note
from config import GROQ_MODEL_SMART
from logger import get_logger

log = get_logger("legal_graph")

# STATE
class LegalState(TypedDict, total=False):
    # Passed in from the outer graph
    query:         str
    history:       list[dict]
    retrieved:     list[dict]   # merged RAG + web results from outer graph
    emotion:       str
    lang:          str
    outer_context: str          # pre-built context string from graph._build_context()
    fast_mode:     bool

    # Agent 1 output
    case_analysis: dict

    # Agents 2–6 output
    organized_chunks:  dict         # {"rights": [...], "procedure": [...], "general": [...]}
    jurisdiction:      Optional[str]
    doc_template:      Optional[str]
    reasoning_context: str          # deterministic legal reasoning block (Agent 5)

    # Confidence from outer graph
    confidence:    str    # "High" | "Medium" | "Low" | "None" — from outer graph

    # Agent 7 output
    response: str
    via:      str

# NODES
async def _analyze(state: LegalState) -> dict:
    """
    Agent 1 — Case Analyzer (8B model, ~150 ms).
    Classifies the query and extracts structured facts for downstream agents.
    """
    if state.get("fast_mode"):
        # Skip analysis in fast/voice mode to save latency
        return {"case_analysis": {
            "category": "General", "urgency": "informational",
            "multi_domain": False, "secondary_categories": [],
            "known_facts": [], "missing_facts": [],
            "limitation_concern": False,
            "needs_rights": True, "needs_procedure": True,
            "needs_document": False, "doc_type": None,
            "needs_evidence_guide": False, "needs_cost_estimate": False,
            "state_hint": None, "personal_law": None, "follow_up": None,
        }}
    try:
        analysis = await legal_agents.analyze_case(
            query=state["query"],
            history=state.get("history", []),
            lang=state.get("lang", "auto"),
        )
        log.info("case_analyzer", category=analysis["category"], urgency=analysis["urgency"])
        return {"case_analysis": analysis}
    except Exception as err:
        log.warning("case_analyzer node error", error=str(err))
        return {"case_analysis": {
            "category": "General", "urgency": "informational",
            "multi_domain": False, "secondary_categories": [],
            "known_facts": [], "missing_facts": [],
            "limitation_concern": False,
            "needs_rights": True, "needs_procedure": True,
            "needs_document": False, "doc_type": None,
            "needs_evidence_guide": False, "needs_cost_estimate": False,
            "state_hint": None, "personal_law": None, "follow_up": None,
        }}

async def _prepare(state: LegalState) -> dict:
    """
    Agents 2–6 — Python-only preparation (no LLM, zero added latency).

    Agent 2 (Rights Organizer):    classify rights-relevant chunks
    Agent 3 (Procedure Organizer): classify procedure-relevant chunks
    Agent 4 (Document Assistant):  load template if document requested
    Agent 5 (Legal Reasoner):      build deterministic reasoning context from _LEGAL_KNOWLEDGE
    Agent 6 (Jurisdiction):        detect state/court from keywords
    """
    analysis   = state.get("case_analysis", {})
    retrieved  = state.get("retrieved", [])
    history    = state.get("history", [])
    category   = analysis.get("category", "General")

    # Agents 2 & 3: organize chunks (pure Python, no I/O)
    organized = legal_agents.organize_chunks(retrieved, category)

    # Agent 6: jurisdiction detection
    jurisdiction = analysis.get("state_hint") or legal_agents.detect_jurisdiction(
        state["query"], history
    )

    # Agent 4: template lookup
    doc_template = None
    if analysis.get("needs_document"):
        doc_template = legal_agents.get_document_template(analysis.get("doc_type"))

    # Agent 5: build deterministic legal reasoning context
    reasoning_context = legal_agents.build_legal_reasoning_context(
        category=category,
        case_analysis=analysis,
        jurisdiction=jurisdiction,
    )

    log.info(
        "prepare",
        rights=len(organized["rights"]),
        procedure=len(organized["procedure"]),
        general=len(organized["general"]),
        jurisdiction=jurisdiction,
        has_template=bool(doc_template),
        reasoning_laws=category,
    )

    return {
        "organized_chunks":  organized,
        "jurisdiction":      jurisdiction,
        "doc_template":      doc_template,
        "reasoning_context": reasoning_context,
    }

async def _compose(state: LegalState) -> dict:
    """
    Agent 7 — Response Composer (70B model).
    Receives structured output from all upstream agents and synthesises
    one coherent Umang response.
    """
    messages = legal_agents.build_composer_messages(
        query=state["query"],
        history=state.get("history", []),
        case_analysis=state.get("case_analysis", {}),
        organized_chunks=state.get("organized_chunks", {}),
        jurisdiction=state.get("jurisdiction"),
        reasoning_context=state.get("reasoning_context", ""),
        emotion=state.get("emotion", "neutral"),
        lang=state.get("lang", "auto"),
        outer_context=state.get("outer_context", ""),
        confidence=state.get("confidence", "None"),
        template=state.get("doc_template"),
    )
    max_tokens = 500 if state.get("fast_mode") else 900
    result = await chat(
        model=GROQ_MODEL_SMART,
        temperature=0.3,
        max_tokens=max_tokens,
        messages=messages,
    )
    response_text = result["content"]
    category = state.get("case_analysis", {}).get("category", "*")

    # Post-response quality gates (non-streaming path only)
    quality_result = check_response(response_text, category=category)
    if not quality_result.passed:
        log.warning(
            "quality_check_failed",
            issues=quality_result.summary(),
            category=category,
        )
        response_text = append_quality_note(response_text, quality_result)

    guardrail_result = validate_citations(response_text)
    if not guardrail_result.passed:
        log.warning(
            "citation_guardrail_failed",
            flagged=guardrail_result.flagged_sections,
            category=category,
        )
        response_text += build_guardrail_note(guardrail_result)

    return {"response": response_text, "via": result["via"]}

# GRAPH COMPILATION
_builder = StateGraph(LegalState)
_builder.add_node("analyze",  _analyze)
_builder.add_node("prepare",  _prepare)
_builder.add_node("compose",  _compose)

_builder.add_edge(START,     "analyze")
_builder.add_edge("analyze", "prepare")
_builder.add_edge("prepare", "compose")
_builder.add_edge("compose", END)

_compiled = _builder.compile()

# PUBLIC API — called by the outer graph
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
        "query":         query,
        "history":       history,
        "retrieved":     retrieved,
        "emotion":       emotion,
        "lang":          lang,
        "outer_context": outer_context,
        "confidence":    confidence,
        "fast_mode":     fast_mode,
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
    """
    Async generator — yields text tokens.
    Runs analyze + prepare synchronously, then streams the compose step.
    Fallback chain: Groq → Ollama → Anthropic → non-streaming.
    """
    from ai import groq_client, ollama_client, anthropic_client
    from ai.circuit_breaker import groq_breaker, ollama_breaker, anthropic_breaker

    # Phase 1 & 2: non-streaming (fast — one 8B call + Python)
    analysis    = await _analyze({"query": query, "history": history, "lang": lang, "fast_mode": False})
    preparation = await _prepare({
        "query":         query,
        "history":       history,
        "retrieved":     retrieved,
        "case_analysis": analysis["case_analysis"],
    })

    # Build composer messages (Agent 7 setup)
    messages = legal_agents.build_composer_messages(
        query=query,
        history=history,
        case_analysis=analysis["case_analysis"],
        organized_chunks=preparation["organized_chunks"],
        jurisdiction=preparation.get("jurisdiction"),
        reasoning_context=preparation.get("reasoning_context", ""),
        emotion=emotion,
        lang=lang,
        outer_context=outer_context,
        confidence=confidence,
        template=preparation.get("doc_template"),
    )
    _opts = dict(messages=messages, model=GROQ_MODEL_SMART, temperature=0.3, max_tokens=900)

    # Phase 3: stream the composed response (same fallback chain as responder)
    try:
        first = True
        async for token in groq_breaker.call_stream(groq_client.stream_chat, **_opts):
            if first and _via_bag is not None:
                _via_bag["via"] = "groq-legal"
                first = False
            yield token
        return
    except Exception as err:
        if not _is_fallback_worthy(err):
            raise
        log.warning("legal groq stream failed", error=type(err).__name__, next="ollama")

    if await _ollama_up():
        try:
            first = True
            async for token in ollama_breaker.call_stream(
                ollama_client.stream_chat, messages=messages, temperature=0.3, max_tokens=900,
            ):
                if first and _via_bag is not None:
                    _via_bag["via"] = "ollama-legal"
                    first = False
                yield token
            return
        except Exception as err:
            log.warning("legal ollama stream failed", error=str(err), next="anthropic")

    if anthropic_client.is_enabled():
        try:
            first = True
            async for token in anthropic_breaker.call_stream(
                anthropic_client.stream_chat, messages=messages, temperature=0.3, max_tokens=900,
            ):
                if first and _via_bag is not None:
                    _via_bag["via"] = "anthropic-legal"
                    first = False
                yield token
            return
        except Exception as err:
            log.warning("legal anthropic stream failed", error=str(err), next="non-streaming")

    # Last resort: single non-streamed chunk
    result = await chat(model=GROQ_MODEL_SMART, temperature=0.3, max_tokens=900, messages=messages)
    if _via_bag is not None:
        _via_bag["via"] = result.get("via", "fallback-legal")
    yield result["content"]
