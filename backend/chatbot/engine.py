"""Module Chatbot — answer user questions grounded in training module content."""
from __future__ import annotations

import json
from dataclasses import dataclass


_RELEVANCE_THRESHOLD = 1.8

_SYSTEM_PROMPT = """\
You are a helpful teaching assistant for the AI Tutor platform.
You have access to the user's training modules and their content.

Your capabilities:
1. **Module discovery** — List what modules and topics are available when asked.
2. **Content Q&A** — Answer specific questions using the training material provided.
3. **Learning guidance** — Recommend which module to study for a given concept.

Rules:
- Answer using ONLY the module catalog and retrieved content provided below.
- When answering content questions, cite the source module and topic.
- When recommending modules, explain what topics they cover and why they're relevant.
- If no module covers the user's question, say so clearly and suggest uploading relevant material.
- Keep answers concise, educational, and well-formatted with bullet points or numbered lists where appropriate.
- Use markdown formatting: **bold** for key terms, bullet lists for multiple items."""

_NO_MODULE_RESPONSE = (
    "I don't have any training modules that cover this topic. "
    "Please upload a document related to your question, or try rephrasing."
)

_MAX_HISTORY_TURNS = 10


@dataclass
class ChatResponse:
    answer: str
    sources: list[dict]
    is_relevant: bool


def build_module_catalog(modules: list[dict], db) -> str:
    """Build a text catalog of all modules with their topics for the LLM context."""
    from backend.analytics.persistence import load_module

    catalog_parts = []
    for m in modules:
        mid = m["module_id"]
        title = m["title"]
        source = m.get("source_filename", "")

        topics_text = ""
        raw = load_module(mid, db=db)
        if raw and raw.get("module_json"):
            try:
                mod_data = json.loads(raw["module_json"])
                topic_list = mod_data.get("topics", [])
                topic_lines = []
                for t in topic_list:
                    topic_info = t.get("topic", {})
                    t_title = topic_info.get("title", "Unknown")
                    t_summary = topic_info.get("summary", "")
                    concepts = t.get("top_concepts", [])
                    line = f"  - {t_title}"
                    if t_summary:
                        line += f": {t_summary[:150]}"
                    if concepts:
                        line += f" (concepts: {', '.join(concepts[:5])})"
                    topic_lines.append(line)
                topics_text = "\n".join(topic_lines)
            except (json.JSONDecodeError, KeyError):
                pass

        entry = f"**{title}**"
        if source:
            entry += f" (source: {source})"
        if topics_text:
            entry += f"\n  Topics:\n{topics_text}"
        else:
            entry += "\n  (no topic details available)"
        catalog_parts.append(entry)

    return "\n\n".join(catalog_parts)


def _format_history(history: list[dict]) -> str:
    """Format recent conversation history for multi-turn context."""
    if not history:
        return ""
    recent = history[-_MAX_HISTORY_TURNS * 2:]
    lines = []
    for msg in recent:
        role = "Student" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


def ask(
    question: str,
    module_ids: list[str],
    llm,
    module_catalog: str = "",
    n_results: int = 5,
    history: list[dict] | None = None,
) -> ChatResponse:
    """Query training modules and generate a grounded answer."""
    from backend.core.guardrails.rules import check_prompt_injection

    if not module_ids:
        return ChatResponse(answer=_NO_MODULE_RESPONSE, sources=[], is_relevant=False)

    injection = check_prompt_injection(question)
    if injection:
        return ChatResponse(
            answer="Your question couldn't be processed. Please rephrase it normally.",
            sources=[],
            is_relevant=False,
        )

    chunks, sources = _retrieve_chunks(question, module_ids, n_results)

    prompt_parts = []

    if module_catalog:
        prompt_parts.append(f"## Available Training Modules\n\n{module_catalog}")

    if chunks:
        content_lines = []
        for chunk, s in zip(chunks, sources):
            label = f"[Module: {s.get('title') or 'Unknown'} | Topic: {s.get('topic_title') or 'Unknown'}]"
            content_lines.append(f"{label}\n{chunk}")
        prompt_parts.append(
            "## Retrieved Content\n\n" + "\n\n---\n\n".join(content_lines)
        )

    if not prompt_parts:
        return ChatResponse(answer=_NO_MODULE_RESPONSE, sources=[], is_relevant=False)

    history_text = _format_history(history or [])
    if history_text:
        prompt_parts.append(f"## Conversation History\n\n{history_text}")

    prompt_parts.append(
        f"Student question: {question}\n\n"
        "Answer the question using the module catalog and retrieved content above. "
        "If the conversation history is relevant, use it for context."
    )

    prompt = "\n\n---\n\n".join(prompt_parts)

    try:
        from backend.core.guardrails.exceptions import GuardrailViolation

        response = llm.generate(prompt=prompt, system=_SYSTEM_PROMPT,
                                skip_input_guardrails=True)
        answer = response if isinstance(response, str) else str(response)
    except GuardrailViolation:
        answer = (
            "Sorry, I couldn't generate a response for that question. "
            "Please try rephrasing."
        )
    except Exception as exc:
        answer = f"Sorry, I encountered an error generating a response: {exc}"

    is_relevant = bool(chunks) or bool(module_catalog)
    return ChatResponse(answer=answer, sources=sources, is_relevant=is_relevant)


def _retrieve_chunks(
    question: str,
    module_ids: list[str],
    n_results: int,
) -> tuple[list[str], list[dict]]:
    """Query ChromaDB for relevant chunks across the user's modules."""
    try:
        from backend.core.mcp_client import get_client

        where_filter = {"module_id": {"$in": module_ids}} if len(module_ids) > 1 else {"module_id": module_ids[0]}

        raw = get_client("storage_server").call(
            "query_vector_db",
            query_text=question,
            n_results=n_results,
            where_filter=where_filter,
        )
        result = json.loads(raw) if isinstance(raw, str) else raw
    except Exception as exc:
        print(f"[chatbot] ChromaDB query failed: {exc}")
        return [], []

    documents = result.get("documents", [[]])[0]
    ids = result.get("ids", [[]])[0]
    distances = result.get("distances", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]

    chunks = []
    sources = []
    for i, (doc, doc_id, dist) in enumerate(zip(documents, ids, distances)):
        if dist > _RELEVANCE_THRESHOLD:
            continue
        meta = metadatas[i] if i < len(metadatas) else {}
        parts = doc_id.split(":", 1)
        module_id = meta.get("module_id") or (parts[0] if parts else "")
        topic_id = meta.get("topic_id") or (parts[1] if len(parts) > 1 else "")
        chunks.append(doc)
        sources.append({
            "module_id": module_id,
            "topic_id": topic_id,
            "distance": dist,
            "title": meta.get("title", ""),
            "topic_title": meta.get("title", ""),
        })

    return chunks, sources
