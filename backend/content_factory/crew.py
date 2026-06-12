"""CrewAI crew for content generation pipeline.

Entry point: run_pipeline(file_path, user_id) -> module_id
"""
from __future__ import annotations

import uuid

from crewai import Crew, Process

from backend.content_factory.agents import (
    create_information_architect,
    create_assessment_designer,
    create_formatting_specialist,
)
from backend.content_factory.tasks import (
    create_extraction_task,
    create_assessment_task,
    create_formatting_task,
)


def run_pipeline(file_path: str, user_id: str) -> str:
    """Run the full content generation pipeline on a PDF.

    Returns the module_id of the generated module.
    """
    module_id = str(uuid.uuid4())

    info_architect = create_information_architect()
    assessment_designer = create_assessment_designer()
    formatting_specialist = create_formatting_specialist()

    extraction_task = create_extraction_task(info_architect, file_path)
    assessment_task = create_assessment_task(assessment_designer)
    formatting_task = create_formatting_task(formatting_specialist, module_id, user_id)

    crew = Crew(
        agents=[info_architect, assessment_designer, formatting_specialist],
        tasks=[extraction_task, assessment_task, formatting_task],
        process=Process.sequential,
        verbose=True,
    )

    crew.kickoff()
    return module_id
