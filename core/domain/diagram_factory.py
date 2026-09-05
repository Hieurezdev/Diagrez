import re
from typing import Any

from core.domain.diagram_ir import UseCaseIR
from core.domain.normalizer import normalize_use_case_payload
from core.domain.other_ir import (
    ActivityDiagramIR,
    ClassDiagramIR,
    SequenceDiagramIR,
    StateMachineDiagramIR,
)


SCHEMAS = {
    "class": ClassDiagramIR,
    "sequence": SequenceDiagramIR,
    "activity": ActivityDiagramIR,
    "state_machine": StateMachineDiagramIR,
}


def build_prompt(diagram_type: str) -> str:
    common = "Return only JSON. Use stable snake_case ids. Keep human-readable Vietnamese labels. Every referenced id must exist. "
    prompts = {
        "use_case": "Root type is use_case. Use keys title, actors, scopes, use_cases, relationships, assumptions. Scopes are system boundaries with id and name. Each use case has a scope_id. Actors are external roles; use cases are verb+noun goals. Relationship types: association, include, extend; every relationship has string source and target.",
        "class": "Root type is class. Use keys title, classes, relationships. Each class has id, name, attributes, methods, optional is_abstract. Members have name, optional type, visibility public/private/protected/package. Relationship types: association, aggregation (shared whole-part), composition (owned lifecycle), generalization (child to parent), dependency (dashed usage). Relationships may have label, source_role, target_role, source_multiplicity, target_multiplicity. Do not model methods as classes.",
        "sequence": "Root type is sequence. Use keys title, participants, messages, notes, fragments. Participants are ordered and have id, name, kind actor/object/system/database. Messages are chronological and have source, target, label, type sync/async/return/self/recursive/create/destroy/duration. Use self or recursive for same-lifeline calls, create when instantiating a participant, destroy when ending a participant lifecycle, duration when showing time between instants, and return only for a meaningful response. Notes have id, text, and optional participant_id or message_index. Fragments have id, operator alt/opt/par/loop/break/critical/neg/ref/assert, message_start, message_end, optional guard and label. Use fragments for branching, optional, parallel, looping or referenced interaction blocks. Keep every endpoint declared.",
        "activity": "Root type is activity. Use keys title, nodes, flows, partitions. Node types are initial (solid circle), action (rounded action), decision/merge (diamond), fork/join (thick synchronization bar), object (rectangle), final (bullseye). Include exactly one initial and at least one final. Flows connect existing nodes and have type control/object plus optional guard. Outgoing decision flows use mutually exclusive guards. Model parallel work with explicit fork/join nodes. Partitions are swimlanes with id, name, and node_ids; use them when responsibilities belong to different actors or roles.",
        "state_machine": "Root type is state_machine. Use keys title, states, transitions. State types are initial (solid circle), state (stable condition), final (bullseye), history (H pseudo-state), choice (diamond). A state may have entry_action, do_activity, exit_action, parent_id for composite substates, and region for concurrent regions. Include exactly one initial and at least one final state. Transitions connect existing states and label event [guard] / action. Do not use activity steps as states; use states for stable lifecycle conditions and actions for entry/do/exit behavior.",
    }
    return common + prompts[diagram_type]


def _message_index(value: Any, message_ids: dict[str, int], message_count: int) -> Any:
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return value
    reference = value.strip()
    if reference in message_ids:
        return message_ids[reference]
    match = re.fullmatch(r"(?:msg|message)[_-](\d+)", reference.casefold())
    if not match:
        return value
    number = int(match.group(1))
    # Generated payloads commonly use msg_N as a zero-based array reference.
    if 0 <= number < message_count:
        return number
    # Also accept one-based references when the model numbers messages that way.
    if 1 <= number <= message_count:
        return number - 1
    return value


def normalize_sequence_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize model-friendly message IDs to the indexed fragment interface."""
    normalized = dict(payload)
    normalized["type"] = "sequence"
    messages = normalized.get("messages", [])
    message_ids = {
        str(message["id"]): index
        for index, message in enumerate(messages)
        if isinstance(message, dict) and isinstance(message.get("id"), str)
    }
    for index, message in enumerate(messages):
        message_ids.setdefault(f"msg_{index}", index)
        message_ids.setdefault(f"message_{index}", index)
    fragments = []
    for fragment in normalized.get("fragments", []):
        if not isinstance(fragment, dict):
            fragments.append(fragment)
            continue
        item = dict(fragment)
        item["message_start"] = _message_index(
            item.get("message_start"), message_ids, len(messages)
        )
        item["message_end"] = _message_index(
            item.get("message_end"), message_ids, len(messages)
        )
        fragments.append(item)
    normalized["fragments"] = fragments
    notes = []
    for note in normalized.get("notes", []):
        if not isinstance(note, dict):
            notes.append(note)
            continue
        item = dict(note)
        if "message_index" in item:
            item["message_index"] = _message_index(
                item["message_index"], message_ids, len(messages)
            )
        notes.append(item)
    normalized["notes"] = notes
    return normalized


def normalize_state_machine_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize common state aliases before strict state-machine validation."""
    normalized = dict(payload)
    normalized["type"] = "state_machine"
    states = []
    for state in normalized.get("states", []):
        if not isinstance(state, dict):
            states.append(state)
            continue
        item = dict(state)
        if not item.get("name"):
            item["name"] = (
                item.get("label") or item.get("display_name") or item.get("id", "State")
            )
        if item.get("entry") and not item.get("entry_action"):
            item["entry_action"] = item["entry"]
        if item.get("do") and not item.get("do_activity"):
            item["do_activity"] = item["do"]
        if item.get("exit") and not item.get("exit_action"):
            item["exit_action"] = item["exit"]
        states.append(item)
    normalized["states"] = states
    return normalized


def parse_diagram(diagram_type: str, payload: dict[str, Any]):
    if diagram_type == "use_case":
        return UseCaseIR.model_validate(normalize_use_case_payload(payload))
    if diagram_type == "sequence":
        return SequenceDiagramIR.model_validate(normalize_sequence_payload(payload))
    if diagram_type == "state_machine":
        return StateMachineDiagramIR.model_validate(
            normalize_state_machine_payload(payload)
        )
    normalized = dict(payload)
    normalized["type"] = diagram_type
    return SCHEMAS[diagram_type].model_validate(normalized)
