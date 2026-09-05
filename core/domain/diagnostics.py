from typing import Literal

from pydantic import BaseModel, Field


class Diagnostic(BaseModel):
    code: str
    severity: Literal["error", "warning"]
    message: str
    node_ids: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    valid: bool
    diagnostics: list[Diagnostic] = Field(default_factory=list)
