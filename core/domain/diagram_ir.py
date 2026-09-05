from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Actor(BaseModel):
    id: str = Field(min_length=1, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    display_name: str | None = Field(default=None, max_length=120)
    external: bool = True


class UseCase(BaseModel):
    id: str = Field(min_length=1, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    display_name: str | None = Field(default=None, max_length=120)
    scope_id: str | None = Field(default=None, pattern=r"^[a-z0-9_-]+$")


class SystemScope(BaseModel):
    id: str = Field(min_length=1, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=160)


class Relationship(BaseModel):
    type: Literal["association", "include", "extend"]
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)


class Assumption(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    confidence: Literal["low", "medium", "high"] = "medium"


class UseCaseIR(BaseModel):
    type: Literal["use_case"] = "use_case"
    title: str = Field(min_length=1, max_length=160)
    actors: list[Actor] = Field(default_factory=list)
    scopes: list[SystemScope] = Field(default_factory=list)
    use_cases: list[UseCase] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)

    @field_validator("actors", "scopes", "use_cases")
    @classmethod
    def unique_ids(cls, values):
        ids = [value.id for value in values]
        if len(ids) != len(set(ids)):
            raise ValueError("node ids must be unique")
        return values


class DiagramRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=8000)
    thread_id: str = Field(min_length=1, max_length=120)
    diagram_type: Literal[
        "use_case", "class", "sequence", "activity", "state_machine"
    ] = "use_case"
    ground_truth: str | None = Field(default=None, max_length=20000)
    clarification_answer: str | None = Field(
        default=None, min_length=1, max_length=4000
    )


class PatchOperation(BaseModel):
    op: Literal["add_actor", "add_use_case", "add_relationship", "remove_node"]
    actor: Actor | None = None
    use_case: UseCase | None = None
    relationship: Relationship | None = None
    node_id: str | None = None


class PatchRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=120)
    revision_id: str = Field(min_length=1, max_length=120)
    operations: list[PatchOperation] = Field(min_length=1, max_length=30)
