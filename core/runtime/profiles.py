"""Named runtime profiles shared by the server and command line tools."""

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeProfile:
    name: str
    ace_playbook_dir: Path
    max_reflection_rounds: int
    max_clarification_rounds: int
    workflow_event_dir: Path


_PROFILE_NAMES = ("default", "development", "headless")


def list_profiles() -> tuple[str, ...]:
    """Return profiles available without requiring a config file."""
    return _PROFILE_NAMES


def load_profile(name: str | None = None) -> RuntimeProfile:
    """Build a profile from environment variables with a stable named default."""
    profile_name = name or os.getenv("UML_PROFILE", "default")
    if profile_name not in _PROFILE_NAMES:
        valid = ", ".join(_PROFILE_NAMES)
        raise ValueError(
            f"Unknown UML profile '{profile_name}'. Choose one of: {valid}"
        )
    values = _profile_file_values(profile_name)
    return RuntimeProfile(
        name=profile_name,
        ace_playbook_dir=Path(
            os.getenv(
                "ACE_PLAYBOOK_DIR",
                values.get("ace_playbook_dir", ".data/ace-playbooks"),
            )
        ),
        max_reflection_rounds=_env_or_profile_int(
            "ACE_MAX_REFLECTION_ROUNDS", values, "max_reflection_rounds", 2
        ),
        max_clarification_rounds=_env_or_profile_int(
            "MAX_CLARIFICATION_ROUNDS", values, "max_clarification_rounds", 2
        ),
        workflow_event_dir=Path(
            os.getenv(
                "WORKFLOW_EVENT_DIR",
                values.get("workflow_event_dir", ".data/workflow-events"),
            )
        ),
    )


def _env_or_profile_int(
    env_name: str, values: dict[str, str], key: str, default: int
) -> int:
    raw_value = os.getenv(env_name, values.get(key, str(default)))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{env_name} must be an integer, got '{raw_value}'") from exc
    if value < 0:
        raise ValueError(f"{env_name} must be non-negative, got '{raw_value}'")
    return value


def _profile_file_values(name: str) -> dict[str, str]:
    profile_path = Path(os.getenv("UML_PROFILE_DIR", ".data/profiles")) / f"{name}.json"
    if not profile_path.exists():
        return {}
    value = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Profile '{name}' must be a JSON object")
    allowed = {
        "ace_playbook_dir",
        "workflow_event_dir",
        "max_reflection_rounds",
        "max_clarification_rounds",
    }
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(
            f"Profile '{name}' contains unsupported keys: {', '.join(sorted(unknown))}"
        )
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(item, (str, int)):
            raise TypeError(
                f"Profile '{name}' field '{key}' must be a string or integer"
            )
        result[key] = str(item)
    return result
