from datetime import datetime, timezone

from pydantic import BaseModel, Field

from core.domain.diagram_ir import UseCaseIR
from core.domain.other_ir import DiagramIR
from core.domain.diagnostics import Diagnostic


class CompiledDiagram(BaseModel):
    source: str
    svg: str


class DiagramRevision(BaseModel):
    id: str
    thread_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ir: UseCaseIR | DiagramIR
    compiled: CompiledDiagram
    diagnostics: list[Diagnostic] = Field(default_factory=list)
