"""CrewAI task definitions for the content generation pipeline."""
from __future__ import annotations

from crewai import Task, Agent


def create_extraction_task(agent: Agent, file_path: str) -> Task:
    return Task(
        description=(
            f"Extract and structure content from the PDF at: {file_path}\n\n"
            "Steps:\n"
            "1. Extract all text from the PDF (up to 4 pages)\n"
            "2. Identify the document title and main sections\n"
            "3. Decompose the content into 3-6 learning topics\n"
            "4. For each topic, provide:\n"
            "   - title: clear, concise topic name\n"
            "   - learning_objectives: list of 2-3 objectives\n"
            "   - content: the relevant source text\n"
            "   - source_section_ids: which sections this topic draws from\n\n"
            "Return a JSON object with keys: title, topics (array)"
        ),
        expected_output=(
            "A JSON object with 'title' (string) and 'topics' (array of objects, "
            "each with 'title', 'learning_objectives', 'content', 'source_section_ids')"
        ),
        agent=agent,
    )


def create_assessment_task(agent: Agent) -> Task:
    return Task(
        description=(
            "Generate assessment questions for each topic from the previous step.\n\n"
            "For each topic:\n"
            "1. Create 2-3 inline comprehension questions (embedded in learning flow)\n"
            "2. Create 3-5 quiz questions for the question bank\n\n"
            "Each question must have:\n"
            "- question_id: unique identifier\n"
            "- question_text: clear question\n"
            "- question_type: 'single_choice' or 'multiple_choice'\n"
            "- options: list of 4 answer options\n"
            "- correct_answers: list of correct option indices (0-based)\n"
            "- explanation: why the correct answer is right\n"
            "- bloom_level: one of remember/understand/apply/analyze/evaluate/create\n"
            "- difficulty: easy/medium/hard (derived from bloom level)\n"
            "- topic_id: which topic this question belongs to\n\n"
            "Return JSON with keys: inline_questions (per topic), question_bank (all quiz questions)"
        ),
        expected_output=(
            "A JSON object with 'inline_questions' (dict of topic_id -> questions) "
            "and 'question_bank' (array of all quiz questions)"
        ),
        agent=agent,
    )


def create_formatting_task(agent: Agent, module_id: str, user_id: str) -> Task:
    return Task(
        description=(
            f"Format and persist the learning module (module_id: {module_id}).\n\n"
            "Steps:\n"
            "1. For each topic, generate 1-2 Mermaid diagrams illustrating key concepts\n"
            "2. Format topic content as clean Markdown with:\n"
            "   - Clear headings and subheadings\n"
            "   - Bullet points for key concepts\n"
            "   - Code blocks for any technical content\n"
            "3. Assemble the complete LearningModule JSON with all topics, "
            "   inline questions, diagrams, and metadata\n"
            "4. Assemble the QuestionBank JSON\n"
            "5. Store the module content chunks in the vector database for "
            "   semantic retrieval by the interactive tutor\n"
            f"6. Save the module to the database (created_by: {user_id})\n\n"
            "Return the final module_id confirming successful storage."
        ),
        expected_output=(
            f"The module_id '{module_id}' confirming the module was saved successfully"
        ),
        agent=agent,
    )
