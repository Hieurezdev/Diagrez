from pydantic import BaseModel, Field, model_validator


class IntentAnalysis(BaseModel):
    intent_summary: str = Field(min_length=5, max_length=500)
    domain: str = Field(min_length=2, max_length=120)
    requested_view: str = Field(min_length=2, max_length=200)
    actors: list[str] = Field(default_factory=list, max_length=30)
    goals: list[str] = Field(default_factory=list, max_length=50)
    constraints: list[str] = Field(default_factory=list, max_length=30)
    assumptions: list[str] = Field(default_factory=list, max_length=30)
    missing_information: list[str] = Field(default_factory=list, max_length=10)
    sufficient: bool
    clarification_question: str | None = Field(default=None, max_length=500)
    normalized_requirements: list[str] = Field(default_factory=list, max_length=80)

    @model_validator(mode="after")
    def validate_clarification(self) -> "IntentAnalysis":
        if not self.sufficient and not self.clarification_question:
            raise ValueError(
                "clarification_question is required when information is insufficient"
            )
        if self.sufficient:
            self.clarification_question = None
        return self

    def generation_context(self) -> str:
        sections = {
            "Intent": [self.intent_summary],
            "Requested view": [self.requested_view],
            "Actors or participants": self.actors,
            "Goals or behaviors": self.goals,
            "Constraints": self.constraints,
            "Assumptions": self.assumptions,
            "Normalized requirements": self.normalized_requirements,
        }
        lines: list[str] = []
        for title, values in sections.items():
            if not values:
                continue
            lines.append(f"{title}:")
            lines.extend(f"- {value}" for value in values)
        return "\n".join(lines)


class ClarificationRequest(BaseModel):
    thread_id: str
    question: str
    intent_summary: str
    missing_information: list[str] = Field(default_factory=list)
    round: int = Field(ge=1)
