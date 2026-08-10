from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.models.flow_reflection_record import ReflectionRecord  # noqa: E402
from app.services.automated_learning_service import AutomatedLearningService  # noqa: E402


def test_reflection_is_written_beside_output(tmp_path: Path) -> None:
    output = tmp_path / "job-123" / "output.md"
    output.parent.mkdir(parents=True)
    output.write_text("finished", encoding="utf-8")
    reflection = ReflectionRecord(
        reflection_id="reflection-123",
        task_id="task-123",
        job_id="job-123",
        owner="alpha",
        what_worked="The real artifact passed validation.",
        what_failed="No significant issues identified.",
        pattern_observed="Validate files before completion.",
        context_type="content_prep",
        sensitivity_level="internal",
    )

    path = AutomatedLearningService._write_reflection_artifact(
        reflection=reflection,
        result_pointer=str(output),
    )

    assert path == output.parent / "reflection.md"
    text = path.read_text(encoding="utf-8")
    assert "The real artifact passed validation." in text
    assert "Validate files before completion." in text
