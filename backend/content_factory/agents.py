"""CrewAI agent definitions for the content generation pipeline.

Three sequential agents:
1. Information Architect — extracts and structures content from PDF
2. Assessment Designer — generates questions and tags them
3. Formatting Specialist — generates diagrams, formats output, persists
"""
from __future__ import annotations

from crewai import Agent

from backend.core.llm_client import LLMFactory


def _get_llm():
    """Return a LiteLLM-compatible model string for CrewAI."""
    import os
    provider = os.environ.get("AI_TUTOR_LLM_PROVIDER", "anthropic")
    model = os.environ.get("AI_TUTOR_LLM_MODEL", "claude-sonnet-4-6")

    if provider == "anthropic":
        return f"anthropic/{model}"
    elif provider == "ollama":
        return f"ollama/{model}"
    elif provider == "portkey":
        return f"anthropic/{model}"
    return f"anthropic/{model}"


def create_information_architect() -> Agent:
    return Agent(
        role="Information Architect",
        goal=(
            "Extract text from the uploaded PDF using the document_server MCP tools, "
            "then decompose the content into a structured hierarchy of learning topics. "
            "Each topic should have a clear title, learning objectives, and source section references."
        ),
        backstory=(
            "You are an expert curriculum designer who specializes in breaking down "
            "complex documents into digestible learning modules. You understand how "
            "to identify key concepts, establish prerequisite relationships, and "
            "create a logical learning progression."
        ),
        llm=_get_llm(),
        verbose=True,
        allow_delegation=False,
    )


def create_assessment_designer() -> Agent:
    return Agent(
        role="Assessment Designer",
        goal=(
            "Generate inline comprehension questions for each topic and build "
            "a comprehensive quiz question bank. Tag each question with Bloom's "
            "taxonomy level and difficulty using the assessment_server MCP tools. "
            "Questions should test understanding, not just recall."
        ),
        backstory=(
            "You are an assessment expert trained in Bloom's taxonomy and "
            "educational measurement. You create questions that reveal "
            "misconceptions, test application of concepts, and provide "
            "clear explanations for correct answers."
        ),
        llm=_get_llm(),
        verbose=True,
        allow_delegation=False,
    )


def create_formatting_specialist() -> Agent:
    return Agent(
        role="Formatting Specialist",
        goal=(
            "Generate Mermaid diagrams to illustrate key concepts, format all "
            "content as clean learner-friendly Markdown, validate the output "
            "against the LearningModule schema, and persist the final module "
            "to the database and vector store using storage_server MCP tools."
        ),
        backstory=(
            "You are a technical writer and data visualization specialist. "
            "You create clear Mermaid diagrams, write accessible explanations, "
            "and ensure all output conforms to required schemas before storage."
        ),
        llm=_get_llm(),
        verbose=True,
        allow_delegation=False,
    )
