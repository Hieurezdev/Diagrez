"""Durable, provider-safe workflow events for replay and diagnostics."""

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Protocol

EventValue = str | int | bool | None | list[str]


@dataclass(frozen=True)
class WorkflowEvent:
    sequence: int
    event: str
    thread_id: str
    timestamp: str
    turn: int
    step: int
    node: str | None = None
    payload: dict[str, EventValue] | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "event": self.event,
            "thread_id": self.thread_id,
            "timestamp": self.timestamp,
            "turn": self.turn,
            "step": self.step,
            "node": self.node,
            "payload": self.payload or {},
        }


class WorkflowEventLog(Protocol):
    def append(self, event: WorkflowEvent) -> None: ...

    def list(self, thread_id: str) -> list[WorkflowEvent]: ...


class MemoryWorkflowEventLog:
    def __init__(self) -> None:
        self._events: dict[str, list[WorkflowEvent]] = {}

    def append(self, event: WorkflowEvent) -> None:
        self._events.setdefault(event.thread_id, []).append(event)

    def list(self, thread_id: str) -> list[WorkflowEvent]:
        return list(self._events.get(thread_id, []))


class JsonlWorkflowEventLog:
    """Append events to one JSONL file per thread without storing prompts."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._lock = Lock()

    def append(self, event: WorkflowEvent) -> None:
        path = self._path(event.thread_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event.as_dict(), ensure_ascii=False) + "\n")

    def list(self, thread_id: str) -> list[WorkflowEvent]:
        path = self._path(thread_id)
        if not path.exists():
            return []
        events: list[WorkflowEvent] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(_event_from_dict(json.loads(line)))
        return events

    def _path(self, thread_id: str) -> Path:
        safe_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", thread_id)
        if not safe_id:
            raise ValueError("thread_id cannot be empty")
        return self._directory / f"{safe_id}.jsonl"


class WorkflowEventRecorder:
    """Own turn/step boundaries while LangGraph nodes remain pure handlers."""

    def __init__(self, thread_id: str, log: WorkflowEventLog) -> None:
        self.thread_id = thread_id
        self._log = log
        previous = log.list(thread_id)
        self._sequence = previous[-1].sequence if previous else 0
        self.turn = max((event.turn for event in previous), default=0) + 1
        self.step = 0
        self._open_node: str | None = None

    def start_turn(self) -> None:
        self._write("turn/start")

    def start_step(
        self, node: str, payload: dict[str, EventValue] | None = None
    ) -> None:
        self.end_step()
        self.step += 1
        self._open_node = node
        self._write("step/start", node=node, payload=payload)

    def end_step(self) -> None:
        if self._open_node is not None:
            self._write("step/end", node=self._open_node)
            self._open_node = None

    def end_turn(self, reason: str) -> None:
        self.end_step()
        self._write("turn/end", payload={"reason": reason})

    def _write(
        self,
        event: str,
        *,
        node: str | None = None,
        payload: dict[str, EventValue] | None = None,
    ) -> None:
        self._sequence += 1
        self._log.append(
            WorkflowEvent(
                sequence=self._sequence,
                event=event,
                thread_id=self.thread_id,
                timestamp=datetime.now(UTC).isoformat(),
                turn=self.turn,
                step=self.step,
                node=node,
                payload=payload,
            )
        )


def _event_from_dict(value: dict[str, object]) -> WorkflowEvent:
    payload = value.get("payload")
    return WorkflowEvent(
        sequence=_required_int(value, "sequence"),
        event=str(value["event"]),
        thread_id=str(value["thread_id"]),
        timestamp=str(value["timestamp"]),
        turn=_required_int(value, "turn"),
        step=_required_int(value, "step"),
        node=str(value["node"]) if value.get("node") is not None else None,
        payload=payload if isinstance(payload, dict) else {},
    )


def _required_int(value: dict[str, object], key: str) -> int:
    item = value.get(key)
    if not isinstance(item, int):
        raise TypeError(f"Workflow event field '{key}' must be an integer")
    return item
