from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

PlaybookSection = Literal[
    "notation_rules",
    "semantic_checks",
    "layout_guidance",
    "common_mistakes",
    "prompt_clues",
]


class PlaybookBullet(BaseModel):
    id: str = Field(pattern=r"^[a-z]{3}-\d{5}$")
    section: PlaybookSection
    content: str = Field(min_length=5, max_length=600)
    helpful: int = Field(default=0, ge=0)
    harmful: int = Field(default=0, ge=0)


class Playbook(BaseModel):
    scope: str = Field(min_length=1, max_length=80)
    next_id: int = Field(default=1, ge=1)
    bullets: list[PlaybookBullet] = Field(default_factory=list)

    @field_validator("bullets")
    @classmethod
    def unique_bullet_ids(cls, bullets: list[PlaybookBullet]) -> list[PlaybookBullet]:
        ids = [bullet.id for bullet in bullets]
        if len(ids) != len(set(ids)):
            raise ValueError("playbook bullet ids must be unique")
        return bullets


class ACEContext(BaseModel):
    scope: str
    prompt: str
    bullet_ids: list[str]


class ACEGenerationRequest(BaseModel):
    scope: str
    question: str
    task_contract: str
    context: str = ""
    reflection: "Reflection | None" = None


class GeneratorResponse(BaseModel):
    reasoning_summary: str = ""
    bullet_ids: list[str] = Field(default_factory=list)
    final_answer: dict[str, Any]


class ACEGeneration(BaseModel):
    reasoning_summary: str = ""
    bullet_ids: list[str] = Field(default_factory=list)
    payload: dict[str, Any]


class ACEObservation(BaseModel):
    scope: str
    request: str
    generated_ir: str
    diagnostics: list[str] = Field(default_factory=list)
    valid: bool
    bullet_ids: list[str] = Field(default_factory=list)
    reasoning_trace: str = ""
    ground_truth: str | None = None


class BulletTag(BaseModel):
    id: str
    tag: Literal["helpful", "harmful", "neutral"]


class Reflection(BaseModel):
    error_identification: str = ""
    root_cause_analysis: str = ""
    correct_approach: str = ""
    key_insight: str = ""
    bullet_tags: list[BulletTag] = Field(default_factory=list)

    @field_validator(
        "error_identification",
        "root_cause_analysis",
        "correct_approach",
        "key_insight",
        mode="before",
    )
    @classmethod
    def coerce_text_fields(cls, value: object) -> str:
        """Accept the list-shaped prose some JSON models return for a text field."""
        if value is None:
            return ""
        if isinstance(value, list):
            return "\n".join(str(item) for item in value)
        return str(value)


class CuratorOperation(BaseModel):
    type: Literal["ADD"]
    section: PlaybookSection
    content: str = Field(min_length=5, max_length=600)


class CuratorResponse(BaseModel):
    operations: list[CuratorOperation] = Field(default_factory=list)


class ACEUpdate(BaseModel):
    reflection: Reflection
    added_bullet_ids: list[str] = Field(default_factory=list)
