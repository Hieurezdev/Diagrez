from datetime import UTC, datetime

from pydantic import BaseModel, Field

from core.domain.diagnostics import Diagnostic
from core.domain.diagram_ir import UseCaseIR
from core.domain.other_ir import DiagramIR


class CompiledDiagram(BaseModel):
    source: str
    svg: str


class DiagramRevision(BaseModel):
    id: str
    thread_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ir: UseCaseIR | DiagramIR
    compiled: CompiledDiagram
    diagnostics: list[Diagnostic] = Field(default_factory=list)
