"""LangGraph interactive tutor — 5-node state machine with conditional router.

Nodes:
  1. present_concept  — load concept content, deliver explanation
  2. ask_question     — generate a targeted question
  3. evaluate_response — LLM analyses answer, sets concept_mastered flag
  4. provide_hint     — tailor hint to student's specific error
  5. simplify_foundations — break concept into simpler building blocks

Router (after evaluate_response):
  - concept_mastered → next concept (or session_complete)
  - attempts < 3     → provide_hint → ask_question
  - attempts >= 3    → simplify_foundations → ask_question
"""
from __future__ import annotations

import json
import operator
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, END

from backend.core.llm_client import LLMFactory


class GraphState(TypedDict):
    current_concept: str
    concept_content: str
    current_question: dict | None
    student_answer: str
    attempts: int
    concept_mastered: bool
    mastered_concepts: list[str]
    remaining_concepts: list[str]
    chat_history: list[dict]
    user_id: str
    module_id: str
    feedback: str


def _get_llm():
    return LLMFactory.create()


def present_concept(state: GraphState) -> dict:
    """Load concept content and deliver explanation to student."""
    llm = _get_llm()
    concept = state["current_concept"]
    content = state.get("concept_content", "")

    prompt = (
        f"You are an expert tutor. Present the following concept to a student "
        f"in a clear, engaging way. Use examples and analogies.\n\n"
        f"Concept: {concept}\n\n"
        f"Source content:\n{content}\n\n"
        f"Deliver a concise explanation (3-5 paragraphs) that builds understanding step by step."
    )

    explanation = llm.generate(prompt, system="You are a patient, encouraging tutor.")

    history = list(state.get("chat_history", []))
    history.append({"role": "tutor", "content": explanation})

    return {
        "chat_history": history,
        "attempts": 0,
        "concept_mastered": False,
        "feedback": "",
    }


def ask_question(state: GraphState) -> dict:
    """Generate a targeted question assessing the current concept."""
    llm = _get_llm()
    concept = state["current_concept"]
    content = state.get("concept_content", "")
    attempts = state.get("attempts", 0)

    context = ""
    if attempts > 0 and state.get("feedback"):
        context = f"\nThe student previously struggled with: {state['feedback']}\nAsk a question that approaches the concept differently."

    prompt = (
        f"Generate a single comprehension question about: {concept}\n\n"
        f"Source content:\n{content}\n{context}\n\n"
        f"Return a JSON object with:\n"
        f'- "question": the question text\n'
        f'- "expected_answer": what a correct answer should include\n'
        f'- "misconceptions": common wrong answers to watch for'
    )

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

    result = llm.generate(prompt, tool_schema=schema)
    question_data = result if isinstance(result, dict) else {"question": str(result), "expected_answer": "", "misconceptions": []}

    history = list(state.get("chat_history", []))
    history.append({"role": "tutor", "content": question_data["question"]})

    return {
        "current_question": question_data,
        "chat_history": history,
    }


def evaluate_response(state: GraphState) -> dict:
    """LLM analyses the student's answer and sets concept_mastered flag."""
    llm = _get_llm()
    question = state.get("current_question", {})
    answer = state.get("student_answer", "")

    prompt = (
        f"Evaluate this student's answer.\n\n"
        f"Question: {question.get('question', '')}\n"
        f"Expected answer: {question.get('expected_answer', '')}\n"
        f"Common misconceptions: {json.dumps(question.get('misconceptions', []))}\n"
        f"Student's answer: {answer}\n\n"
        f"Determine if the student has mastered this concept. "
        f"Identify specific misconceptions if present."
    )

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

    result = llm.generate(prompt, tool_schema=schema)
    evaluation = result if isinstance(result, dict) else {"is_correct": False, "feedback": str(result)}

    history = list(state.get("chat_history", []))
    history.append({"role": "student", "content": answer})
    history.append({"role": "tutor", "content": evaluation.get("feedback", "")})

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
        f"Provide a targeted hint that:\n"
        f"1. Acknowledges their attempt\n"
        f"2. Points them toward the right thinking without giving the answer\n"
        f"3. Uses a different analogy or example than before"
    )

    hint = llm.generate(prompt, system="You are a patient tutor giving a helpful hint.")

    history = list(state.get("chat_history", []))
    history.append({"role": "tutor", "content": f"Hint: {hint}"})

    return {"chat_history": history}


def simplify_foundations(state: GraphState) -> dict:
    """Break concept into simpler building blocks and re-teach from basics."""
    llm = _get_llm()
    concept = state["current_concept"]
    content = state.get("concept_content", "")

    prompt = (
        f"The student has struggled with '{concept}' after multiple attempts.\n"
        f"Original content:\n{content}\n\n"
        f"Break this concept down into its simplest building blocks:\n"
        f"1. Identify 2-3 prerequisite sub-concepts\n"
        f"2. Explain each sub-concept simply\n"
        f"3. Show how they combine into the main concept\n"
        f"Use very simple language and concrete examples."
    )

    simplified = llm.generate(prompt, system="You are explaining to a complete beginner.")

    history = list(state.get("chat_history", []))
    history.append({"role": "tutor", "content": f"Let me break this down differently:\n\n{simplified}"})

    return {
        "chat_history": history,
        "attempts": 0,
    }


def _router(state: GraphState) -> str:
    """Conditional router after evaluate_response."""
    if state.get("concept_mastered", False):
        remaining = state.get("remaining_concepts", [])
        if remaining:
            return "next_concept"
        return "session_complete"

    attempts = state.get("attempts", 0)
    if attempts >= 3:
        return "simplify"

    return "hint"


def _advance_concept(state: GraphState) -> dict:
    """Move to the next concept in the sequence."""
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
    }


def _session_complete(state: GraphState) -> dict:
    """Summarize mastery and end the session."""
    mastered = list(state.get("mastered_concepts", []))
    mastered.append(state["current_concept"])

    history = list(state.get("chat_history", []))
    summary = (
        f"Session complete! You've mastered {len(mastered)} concept(s): "
        + ", ".join(mastered)
    )
    history.append({"role": "tutor", "content": summary})

    return {
        "mastered_concepts": mastered,
        "chat_history": history,
    }


def build_tutor_graph():
    """Build and compile the LangGraph tutor state machine."""
    graph = StateGraph(GraphState)

    graph.add_node("present_concept", present_concept)
    graph.add_node("ask_question", ask_question)
    graph.add_node("evaluate_response", evaluate_response)
    graph.add_node("provide_hint", provide_hint)
    graph.add_node("simplify_foundations", simplify_foundations)
    graph.add_node("advance_concept", _advance_concept)
    graph.add_node("session_complete", _session_complete)

    graph.set_entry_point("present_concept")

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
    graph.add_edge("advance_concept", "present_concept")
    graph.add_edge("session_complete", END)

    return graph.compile()
