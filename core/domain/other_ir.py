from typing import Literal

from pydantic import BaseModel, Field


class ClassMember(BaseModel):
    name: str
    type: str | None = None
    visibility: Literal["public", "private", "protected", "package"] = "public"


class UmlClass(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    name: str
    attributes: list[ClassMember] = Field(default_factory=list)
    methods: list[ClassMember] = Field(default_factory=list)
    is_abstract: bool = False


class ClassRelationship(BaseModel):
    type: Literal[
        "association", "aggregation", "composition", "generalization", "dependency"
    ]
    source: str
    target: str
    label: str | None = None
    source_role: str | None = None
    target_role: str | None = None
    source_multiplicity: str | None = None
    target_multiplicity: str | None = None


class ClassDiagramIR(BaseModel):
    type: Literal["class"] = "class"
    title: str
    classes: list[UmlClass]
    relationships: list[ClassRelationship] = Field(default_factory=list)


class Participant(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    name: str
    kind: Literal["actor", "object", "system", "database"] = "object"


class Message(BaseModel):
    source: str
    target: str
    label: str
    type: Literal[
        "sync", "async", "return", "self", "recursive", "create", "destroy", "duration"
    ] = "sync"


class SequenceNote(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    text: str
    participant_id: str | None = None
    message_index: int | None = Field(default=None, ge=0)


class SequenceFragment(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    operator: Literal[
        "alt", "opt", "par", "loop", "break", "critical", "neg", "ref", "assert"
    ]
    message_start: int = Field(ge=0)
    message_end: int = Field(ge=0)
    guard: str | None = None
    label: str | None = None


class SequenceDiagramIR(BaseModel):
    type: Literal["sequence"] = "sequence"
    title: str
    participants: list[Participant]
    messages: list[Message]
    notes: list[SequenceNote] = Field(default_factory=list)
    fragments: list[SequenceFragment] = Field(default_factory=list)


class ActivityNode(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    label: str
    type: Literal[
        "initial", "action", "decision", "merge", "fork", "join", "object", "final"
    ] = "action"


class ActivityFlow(BaseModel):
    source: str
    target: str
    guard: str | None = None
    type: Literal["control", "object"] = "control"


class ActivityPartition(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    name: str
    node_ids: list[str] = Field(default_factory=list)


class ActivityDiagramIR(BaseModel):
    type: Literal["activity"] = "activity"
    title: str
    nodes: list[ActivityNode]
    flows: list[ActivityFlow]
    partitions: list[ActivityPartition] = Field(default_factory=list)


class StateNode(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    name: str
    type: Literal["initial", "state", "final", "history", "choice"] = "state"
    entry_action: str | None = None
    do_activity: str | None = None
    exit_action: str | None = None
    parent_id: str | None = None
    region: str | None = None


class StateTransition(BaseModel):
    source: str
    target: str
    event: str | None = None
    guard: str | None = None
    action: str | None = None


class StateMachineDiagramIR(BaseModel):
    type: Literal["state_machine"] = "state_machine"
    title: str
    states: list[StateNode]
    transitions: list[StateTransition]


DiagramIR = (
    ClassDiagramIR | SequenceDiagramIR | ActivityDiagramIR | StateMachineDiagramIR
)
