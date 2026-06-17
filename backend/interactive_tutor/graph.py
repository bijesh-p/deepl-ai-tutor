"""LangGraph interactive tutor — state machine with diagnostic quiz and slide presentation.

Flow:
  generate_diagnostic  → [UI: student answers MCQ] → evaluate_diagnostic
  → present_concept (slide: diagram + audio + transcript)
  → ask_question → evaluate_response → router:
      concept_mastered  → advance_concept → present_concept (next topic)
      attempts < 3      → provide_hint → ask_question
      attempts >= 3     → simplify_foundations → ask_question
"""
from __future__ import annotations

import json
import os
from typing import TypedDict

from langgraph.graph import StateGraph, END

from backend.core.llm_client import LLMFactory


class GraphState(TypedDict):
    # Current position
    current_concept: str
    concept_content: str           # enriched Markdown (from pipeline or generated)
    concept_summary: str           # topic summary (always available from decomposer)
    current_question: dict | None
    student_answer: str

    # Diagnostic
    diagnostic_questions: list[dict]  # MCQ questions before presentation
    diagnostic_answers: list[int]     # student's chosen option indices
    diagnostic_score: float           # 0.0–1.0
    presentation_depth: str           # "beginner" | "intermediate" | "advanced"

    # Slide content
    topic_diagram: str             # Mermaid code for current concept
    topic_audio_path: str          # path to mp3 narration (empty if not ready)
    topic_top_concepts: list[str]  # 2-3 key concept labels
    enriched_topic: dict | None    # EnrichedTopic asdict — injected by UI if pipeline ready

    # Tracking
    attempts: int
    concept_mastered: bool
    mastered_concepts: list[str]
    remaining_concepts: list[str]

    # Conversation (slides + Q&A interleaved)
    chat_history: list[dict]

    # Identity
    user_id: str
    module_id: str
    feedback: str


def _get_llm():
    return LLMFactory.create()


def _retrieve_context(module_id: str, query_text: str, n_results: int = 2) -> str:
    """Best-effort retrieval of supporting chunks from ChromaDB via storage_server.

    Non-fatal: semantic search is a supporting feature, so any failure here
    must not break the tutor flow.
    """
    try:
        from backend.core.mcp_client import get_client

        raw = get_client("storage_server").call(
            "query_vector_db",
            query_text=query_text,
            n_results=n_results,
            where_filter={"module_id": module_id},
        )
        documents = json.loads(raw).get("documents", [])
        if documents and documents[0]:
            return "\n\n".join(documents[0])
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Diagnostic nodes
# ---------------------------------------------------------------------------

_DIAGNOSTIC_SCHEMA = {
    "name": "return_diagnostic_questions",
    "description": "Return 3-5 MCQ diagnostic questions on the topic.",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "question_text": {"type": "string"},
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 4,
                            "maxItems": 4,
                        },
                        "correct_index": {"type": "integer"},
                    },
                    "required": ["question_text", "options", "correct_index"],
                },
            }
        },
        "required": ["questions"],
    },
}

_DIAGNOSTIC_SYSTEM = (
    "You are an educator assessing a student's prior knowledge before teaching. "
    "Generate 3-5 multiple-choice diagnostic questions on the given topic. "
    "Each question must have exactly 4 options. "
    "Include a mix of easy and medium difficulty. "
    "Base questions only on what can be reasonably inferred from the topic title and summary — "
    "do not assume the student has read anything yet."
)


def generate_diagnostic(state: GraphState) -> dict:
    """Generate MCQ diagnostic questions from topic title + summary (no enriched content needed)."""
    llm = _get_llm()
    concept = state["current_concept"]
    summary = state.get("concept_summary", "")

    prompt = (
        f"Topic: {concept}\n"
        f"Summary: {summary}\n\n"
        "Generate diagnostic questions to assess the student's prior knowledge of this topic."
    )

    result = llm.generate(prompt, system=_DIAGNOSTIC_SYSTEM, tool_schema=_DIAGNOSTIC_SCHEMA)
    questions = result.get("questions", []) if isinstance(result, dict) else []

    return {
        "diagnostic_questions": questions,
        "diagnostic_answers": [],
        "diagnostic_score": 0.0,
        "presentation_depth": "intermediate",
    }


def evaluate_diagnostic(state: GraphState) -> dict:
    """Score diagnostic answers and set presentation depth."""
    questions = state.get("diagnostic_questions", [])
    answers = state.get("diagnostic_answers", [])

    if not questions:
        return {"diagnostic_score": 0.0, "presentation_depth": "intermediate"}

    correct = sum(
        1 for i, q in enumerate(questions)
        if i < len(answers) and answers[i] == q.get("correct_index", -1)
    )
    score = correct / len(questions)

    if score < 0.4:
        depth = "beginner"
    elif score < 0.7:
        depth = "intermediate"
    else:
        depth = "advanced"

    return {"diagnostic_score": score, "presentation_depth": depth}


# ---------------------------------------------------------------------------
# Slide presentation node
# ---------------------------------------------------------------------------

_SLIDE_SCHEMA = {
    "name": "return_slide",
    "description": "Return a slide presentation for the concept.",
    "input_schema": {
        "type": "object",
        "properties": {
            "top_concepts": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 3,
            },
            "transcript": {
                "type": "string",
                "description": "Conversational explanation adapted to the student's level.",
            },
            "mermaid_code": {
                "type": "string",
                "description": "Mermaid diagram code. Use flowchart or mindmap to show relationships.",
            },
        },
        "required": ["top_concepts", "transcript", "mermaid_code"],
    },
}

_SLIDE_SYSTEM = (
    "You are a tutor creating a visual slide to explain a concept. "
    "Produce a short conversational explanation (3-4 paragraphs) adapted to the student's level. "
    "Also produce a Mermaid diagram (concept map or flowchart) and 2-3 top concept labels. "
    "Use valid Mermaid v10 syntax. Never use double-quote characters inside Mermaid labels — "
    "use #quot; instead. Do not wrap the Mermaid code in ``` fences."
)

_DEPTH_GUIDANCE = {
    "beginner": (
        "The student is a BEGINNER — no prior knowledge assumed. "
        "Use simple words, everyday analogies, and explain every term."
    ),
    "intermediate": (
        "The student has SOME background. "
        "Use clear explanations with one or two analogies."
    ),
    "advanced": (
        "The student is ADVANCED — already understands the basics. "
        "Focus on nuance, edge cases, and deeper connections."
    ),
}


def present_concept(state: GraphState) -> dict:
    """Build a slide for the current concept, using enriched content if available."""
    concept = state["current_concept"]
    depth = state.get("presentation_depth", "intermediate")
    enriched = state.get("enriched_topic")

    # Pipeline hasn't enriched this topic yet (or session was resumed without
    # state) — fall back to ChromaDB-retrieved content for this concept.
    if not enriched or not enriched.get("content_md"):
        retrieved = _retrieve_context(state["module_id"], concept, n_results=1)
        if retrieved:
            enriched = {
                **(enriched or {}),
                "content_md": retrieved,
                "diagrams": (enriched or {}).get("diagrams", []),
                "top_concepts": (enriched or {}).get("top_concepts", []),
            }

    # If the pipeline already finished enriching this topic, use its assets directly
    if enriched:
        diagrams = enriched.get("diagrams", [])
        raw_mermaid = diagrams[0]["content"] if diagrams else ""
        if raw_mermaid:
            from backend.content.diagram_generator import _sanitize_mermaid
            mermaid_code = _sanitize_mermaid(raw_mermaid)
        else:
            mermaid_code = ""
        audio_path = enriched.get("audio_path", "")
        top_concepts = enriched.get("top_concepts", [])
        content_md = enriched.get("content_md", "")

        # Inline diagram fallback: generate on-the-fly if pipeline produced none
        if not mermaid_code and content_md:
            try:
                from backend.content.diagram_generator import _sanitize_mermaid, _try_diagram
                from backend.content.models import Topic as _Topic
                _llm = _get_llm()
                _topic = _Topic(
                    topic_id="inline", title=concept, summary="",
                    source_section_ids=[], order=0,
                )
                _diag = _try_diagram(content_md[:2000], _topic, _llm)
                if _diag:
                    mermaid_code = _diag.content
            except Exception:
                pass

        if content_md:
            # Fast path: pipeline audio is already diagram-synced and depth-annotated.
            # Only run depth-adaptation LLM when pipeline audio is missing.
            audio_enabled = state.get("audio_enabled", True)
            if audio_path:
                transcript = content_md
            else:
                llm = _get_llm()
                depth_note = _DEPTH_GUIDANCE[depth]
                adapted = llm.generate(
                    prompt=(
                        f"Here is an explanation of '{concept}':\n\n{content_md}\n\n"
                        f"{depth_note}\n"
                        "Rewrite it in 2-3 paragraphs matching the student's level. "
                        "Keep it conversational."
                    ),
                    system="You are a patient tutor adapting content for a specific learner.",
                )
                transcript = adapted if isinstance(adapted, str) else content_md
                # Generate audio synced to diagram only if audio is enabled
                if audio_enabled:
                    try:
                        from backend.content.audio_generator import generate_audio
                        diagram_caption = (enriched.get("diagrams", [{}])[0].get("caption", "")
                                           if enriched.get("diagrams") else "")
                        # Limit TTS to first 400 chars so audio stays ~30-60s
                        short_transcript = transcript[:400].rsplit(" ", 1)[0] + "..."
                        audio_path = generate_audio(
                            short_transcript,
                            f"{concept}_tutor",
                            diagram_caption=diagram_caption,
                            diagram_mermaid=mermaid_code,
                            topic_title=concept,
                        )
                    except Exception:
                        audio_path = ""
                else:
                    audio_path = ""

            # Estimate audio duration from file size so slide timer can sync to it
            audio_duration_s = _estimate_audio_duration(audio_path)

            slide_msg = {
                "role": "slide",
                "concept": concept,
                "top_concepts": top_concepts,
                "transcript": transcript,
                "mermaid_code": mermaid_code,
                "audio_path": audio_path,
                "audio_duration_s": audio_duration_s,
            }
            history = list(state.get("chat_history", []))
            history.append(slide_msg)
            return {
                "topic_diagram": mermaid_code,
                "topic_audio_path": audio_path,
                "topic_top_concepts": top_concepts,
                "concept_content": transcript,
                "chat_history": history,
                "attempts": 0,
                "concept_mastered": False,
                "feedback": "",
            }

    # Pipeline hasn't finished yet — generate a lightweight slide from title + summary
    llm = _get_llm()
    summary = state.get("concept_summary", "")
    depth_note = _DEPTH_GUIDANCE[depth]

    prompt = (
        f"Topic: {concept}\nSummary: {summary}\n\n"
        f"{depth_note}\n\n"
        "Create a slide to introduce this concept to the student."
    )

    result = llm.generate(prompt, system=_SLIDE_SYSTEM, tool_schema=_SLIDE_SCHEMA)
    if not isinstance(result, dict):
        result = {"top_concepts": [], "transcript": str(result), "mermaid_code": ""}

    from backend.content.diagram_generator import _sanitize_mermaid
    mermaid_code = _sanitize_mermaid(result.get("mermaid_code", ""))

    transcript = result.get("transcript", "")

    # Generate diagram-aware audio for the fallback slide (skip if disabled)
    fallback_audio = ""
    if state.get("audio_enabled", True):
        try:
            from backend.content.audio_generator import generate_audio
            fallback_audio = generate_audio(
                transcript,
                f"{concept}_tutor_fallback",
                diagram_mermaid=mermaid_code,
                topic_title=concept,
            )
        except Exception:
            fallback_audio = ""

    audio_duration_s = _estimate_audio_duration(fallback_audio)

    slide_msg = {
        "role": "slide",
        "concept": concept,
        "top_concepts": result.get("top_concepts", []),
        "transcript": transcript,
        "mermaid_code": mermaid_code,
        "audio_path": fallback_audio,
        "audio_duration_s": audio_duration_s,
    }

    history = list(state.get("chat_history", []))
    history.append(slide_msg)

    return {
        "topic_diagram": mermaid_code,
        "topic_audio_path": fallback_audio,
        "topic_top_concepts": result.get("top_concepts", []),
        "concept_content": transcript,
        "chat_history": history,
        "attempts": 0,
        "concept_mastered": False,
        "feedback": "",
    }


def _estimate_audio_duration(audio_path: str) -> int:
    """Estimate mp3 duration in seconds from file size.

    edge-tts produces ~16 kbps mono mp3. At 16000 bits/s = 2000 bytes/s.
    We add 15s buffer so the slide never auto-advances while audio is playing.
    Falls back to 60s if the file is missing or unreadable.
    """
    try:
        if audio_path and os.path.exists(audio_path):
            size_bytes = os.path.getsize(audio_path)
            estimated_s = size_bytes // 2000
            return max(30, estimated_s + 15)
    except Exception:
        pass
    return 60


# ---------------------------------------------------------------------------
# Question / evaluation nodes (unchanged logic, updated prompts)
# ---------------------------------------------------------------------------

def ask_question(state: GraphState) -> dict:
    """Generate a targeted open-ended question about the current concept."""
    llm = _get_llm()
    concept = state["current_concept"]
    content = state.get("concept_content", "")
    depth = state.get("presentation_depth", "intermediate")
    attempts = state.get("attempts", 0)

    depth_note = _DEPTH_GUIDANCE[depth]
    context = ""
    if attempts > 0 and state.get("feedback"):
        context = f"\nThe student previously struggled with: {state['feedback']}\nAsk a question that approaches the concept differently."

    schema = {
        "name": "generate_question",
        "description": "Generate a comprehension question",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "expected_answer": {"type": "string"},
                "misconceptions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["question", "expected_answer", "misconceptions"],
        },
    }

    prompt = (
        f"Generate a single comprehension question about: {concept}\n\n"
        f"Explanation given to student:\n{content}\n"
        f"{depth_note}\n{context}\n\n"
        "The question difficulty should match the student's level. "
        "Return via the tool."
    )

    result = llm.generate(prompt, tool_schema=schema)
    question_data = result if isinstance(result, dict) else {"question": str(result), "expected_answer": "", "misconceptions": []}

    history = list(state.get("chat_history", []))
    history.append({"role": "tutor", "content": question_data["question"], "concept": concept})

    return {"current_question": question_data, "chat_history": history}


def evaluate_response(state: GraphState) -> dict:
    """LLM analyses the student's answer and sets concept_mastered flag."""
    llm = _get_llm()
    question = state.get("current_question", {})
    answer = state.get("student_answer", "")

    schema = {
        "name": "evaluate_answer",
        "description": "Evaluate student answer",
        "input_schema": {
            "type": "object",
            "properties": {
                "is_correct": {"type": "boolean"},
                "feedback": {"type": "string"},
                "misconception_identified": {"type": "string"},
            },
            "required": ["is_correct", "feedback"],
        },
    }

    prompt = (
        f"Evaluate this student's answer.\n\n"
        f"Question: {question.get('question', '')}\n"
        f"Expected answer: {question.get('expected_answer', '')}\n"
        f"Common misconceptions: {json.dumps(question.get('misconceptions', []))}\n"
        f"Student's answer: {answer}\n\n"
        "Identify specific misconceptions if present. Be encouraging."
    )

    result = llm.generate(prompt, tool_schema=schema)
    evaluation = result if isinstance(result, dict) else {"is_correct": False, "feedback": str(result)}

    concept = state.get("current_concept", "")
    history = list(state.get("chat_history", []))
    history.append({"role": "student", "content": answer, "concept": concept})
    history.append({"role": "tutor", "content": evaluation.get("feedback", ""), "concept": concept})

    return {
        "concept_mastered": evaluation.get("is_correct", False),
        "feedback": evaluation.get("feedback", ""),
        "attempts": state.get("attempts", 0) + 1,
        "chat_history": history,
    }


def provide_hint(state: GraphState) -> dict:
    """Tailor a hint to the student's specific error."""
    llm = _get_llm()
    concept = state["current_concept"]
    feedback = state.get("feedback", "")

    prompt = (
        f"The student is struggling with: {concept}\n"
        f"Their specific difficulty: {feedback}\n\n"
        "Provide a targeted hint that acknowledges their attempt, "
        "points them toward the right thinking without giving the answer, "
        "and uses a different analogy or example than before."
    )

    context = _retrieve_context(state["module_id"], feedback or concept)
    if context:
        prompt = f"Relevant material:\n{context}\n\n{prompt}"

    hint = llm.generate(prompt, system="You are a patient tutor giving a helpful hint.")
    history = list(state.get("chat_history", []))
    history.append({"role": "tutor", "content": f"Hint: {hint}", "concept": concept})
    return {"chat_history": history}


def simplify_foundations(state: GraphState) -> dict:
    """Break concept into simpler building blocks and re-teach from basics."""
    llm = _get_llm()
    concept = state["current_concept"]
    content = state.get("concept_content", "")

    prompt = (
        f"The student has struggled with '{concept}' after multiple attempts.\n"
        f"Original explanation:\n{content}\n\n"
        "Break this concept into 2-3 simpler building blocks. "
        "Explain each one simply, then show how they combine. "
        "Use very simple language and concrete examples."
    )

    simplified = llm.generate(prompt, system="You are explaining to a complete beginner.")
    history = list(state.get("chat_history", []))
    history.append({"role": "tutor", "content": f"Let me break this down differently:\n\n{simplified}", "concept": concept})
    return {"chat_history": history, "attempts": 0}


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------

def _router(state: GraphState) -> str:
    if state.get("concept_mastered", False):
        return "next_concept" if state.get("remaining_concepts") else "session_complete"
    return "simplify" if state.get("attempts", 0) >= 3 else "hint"


def _advance_concept(state: GraphState) -> dict:
    remaining = list(state.get("remaining_concepts", []))
    mastered = list(state.get("mastered_concepts", []))
    mastered.append(state["current_concept"])
    next_concept = remaining.pop(0) if remaining else ""
    return {
        "current_concept": next_concept,
        "remaining_concepts": remaining,
        "mastered_concepts": mastered,
        "concept_mastered": False,
        "attempts": 0,
        "current_question": None,
        "feedback": "",
        "diagnostic_questions": [],
        "diagnostic_answers": [],
        "enriched_topic": None,
        "topic_diagram": "",
        "topic_audio_path": "",
        "topic_top_concepts": [],
    }


def _session_complete(state: GraphState) -> dict:
    mastered = list(state.get("mastered_concepts", []))
    mastered.append(state["current_concept"])
    history = list(state.get("chat_history", []))
    summary = (
        f"Session complete! You have mastered {len(mastered)} concept(s): "
        + ", ".join(mastered)
    )
    history.append({"role": "tutor", "content": summary})
    return {"mastered_concepts": mastered, "chat_history": history}


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_tutor_graph():
    """Build and compile the LangGraph tutor state machine."""
    graph = StateGraph(GraphState)

    graph.add_node("generate_diagnostic", generate_diagnostic)
    graph.add_node("evaluate_diagnostic", evaluate_diagnostic)
    graph.add_node("present_concept", present_concept)
    graph.add_node("ask_question", ask_question)
    graph.add_node("evaluate_response", evaluate_response)
    graph.add_node("provide_hint", provide_hint)
    graph.add_node("simplify_foundations", simplify_foundations)
    graph.add_node("advance_concept", _advance_concept)
    graph.add_node("session_complete", _session_complete)

    graph.set_entry_point("generate_diagnostic")

    # Diagnostic runs, then UI pauses for student answers
    graph.add_edge("generate_diagnostic", END)

    # After UI submits answers: evaluate → present → question loop
    graph.add_edge("evaluate_diagnostic", "present_concept")
    graph.add_edge("present_concept", "ask_question")

    graph.add_conditional_edges(
        "evaluate_response",
        _router,
        {
            "next_concept": "advance_concept",
            "session_complete": "session_complete",
            "hint": "provide_hint",
            "simplify": "simplify_foundations",
        },
    )

    graph.add_edge("provide_hint", "ask_question")
    graph.add_edge("simplify_foundations", "ask_question")
    graph.add_edge("advance_concept", "generate_diagnostic")
    graph.add_edge("session_complete", END)

    return graph.compile()
