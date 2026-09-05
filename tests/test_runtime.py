from pathlib import Path

from core.runtime.events import JsonlWorkflowEventLog, WorkflowEventRecorder
from core.runtime.profiles import load_profile


def test_workflow_event_log_preserves_turn_and_step_boundaries(tmp_path: Path) -> None:
    log = JsonlWorkflowEventLog(tmp_path)
    recorder = WorkflowEventRecorder("thread/with spaces", log)
    recorder.start_turn()
    recorder.start_step("analyze_intent")
    recorder.start_step("build_ir")
    recorder.end_turn("completed")

    events = log.list("thread/with spaces")
    assert [event.event for event in events] == [
        "turn/start",
        "step/start",
        "step/end",
        "step/start",
        "step/end",
        "turn/end",
    ]
    assert events[-1].payload == {"reason": "completed"}


def test_profile_file_is_a_small_override_layer(tmp_path: Path, monkeypatch) -> None:
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    (profile_dir / "development.json").write_text(
        '{"max_reflection_rounds": 4, "workflow_event_dir": ".data/dev-events"}',
        encoding="utf-8",
    )
    monkeypatch.setenv("UML_PROFILE_DIR", str(profile_dir))
    profile = load_profile("development")
    assert profile.max_reflection_rounds == 4
    assert profile.workflow_event_dir == Path(".data/dev-events")
