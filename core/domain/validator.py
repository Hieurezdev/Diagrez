from core.domain.diagnostics import Diagnostic, ValidationResult
from core.domain.diagram_ir import UseCaseIR
from core.domain.other_ir import (
    ActivityDiagramIR,
    ClassDiagramIR,
    SequenceDiagramIR,
    StateMachineDiagramIR,
)


def validate_use_case_ir(ir: UseCaseIR) -> ValidationResult:
    nodes = {actor.id for actor in ir.actors} | {
        use_case.id for use_case in ir.use_cases
    }
    diagnostics: list[Diagnostic] = []
    scope_ids = {scope.id for scope in ir.scopes}
    for use_case in ir.use_cases:
        if use_case.scope_id and use_case.scope_id not in scope_ids:
            diagnostics.append(
                Diagnostic(
                    code="missing_scope_reference",
                    severity="error",
                    message=f"Use case '{use_case.display_name or use_case.name}' references missing scope '{use_case.scope_id}'.",
                    node_ids=[use_case.id],
                )
            )
    if len(ir.use_cases) > 20:
        diagnostics.append(
            Diagnostic(
                code="too_many_use_cases",
                severity="warning",
                message="A use case diagram should remain a high-level summary; consider splitting it into smaller diagrams.",
            )
        )
    connected_actors = {
        node_id
        for relationship in ir.relationships
        if relationship.type == "association"
        for node_id in (relationship.source, relationship.target)
    }
    for actor in ir.actors:
        if actor.id not in connected_actors:
            diagnostics.append(
                Diagnostic(
                    code="unconnected_actor",
                    severity="warning",
                    message=f"Actor '{actor.display_name or actor.name}' is not linked to a use case.",
                    node_ids=[actor.id],
                )
            )
    for relationship in ir.relationships:
        missing = [
            node_id
            for node_id in (relationship.source, relationship.target)
            if node_id not in nodes
        ]
        if missing:
            diagnostics.append(
                Diagnostic(
                    code="missing_node_reference",
                    severity="error",
                    message=f"Relationship references missing node(s): {', '.join(missing)}",
                    node_ids=[relationship.source, relationship.target],
                )
            )
        if relationship.source == relationship.target:
            diagnostics.append(
                Diagnostic(
                    code="self_relationship",
                    severity="error",
                    message="A relationship cannot connect a node to itself.",
                    node_ids=[relationship.source],
                )
            )
        source_actor = relationship.source in {actor.id for actor in ir.actors}
        target_actor = relationship.target in {actor.id for actor in ir.actors}
        if relationship.type == "association" and source_actor == target_actor:
            diagnostics.append(
                Diagnostic(
                    code="invalid_association",
                    severity="error",
                    message="An association must connect exactly one actor to one use case.",
                    node_ids=[relationship.source, relationship.target],
                )
            )
        if relationship.type in {"include", "extend"} and (
            source_actor or target_actor
        ):
            diagnostics.append(
                Diagnostic(
                    code="invalid_use_case_relationship",
                    severity="error",
                    message="include and extend relationships must connect use cases.",
                    node_ids=[relationship.source, relationship.target],
                )
            )
    return ValidationResult(
        valid=not any(item.severity == "error" for item in diagnostics),
        diagnostics=diagnostics,
    )


def _endpoint_diagnostics(
    relationships: list[tuple[str, str]],
    node_ids: set[str],
    relationship_name: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for index, (source, target) in enumerate(relationships):
        missing = [node_id for node_id in (source, target) if node_id not in node_ids]
        if missing:
            diagnostics.append(
                Diagnostic(
                    code="missing_node_reference",
                    severity="error",
                    message=f"{relationship_name} {index + 1} references missing node(s): {', '.join(missing)}",
                    node_ids=[source, target],
                )
            )
    return diagnostics


def validate_diagram_ir(
    ir: UseCaseIR
    | ClassDiagramIR
    | SequenceDiagramIR
    | ActivityDiagramIR
    | StateMachineDiagramIR,
) -> ValidationResult:
    """Validate the semantic invariants shared by all supported UML diagram types."""
    if isinstance(ir, UseCaseIR):
        return validate_use_case_ir(ir)

    diagnostics: list[Diagnostic] = []
    if isinstance(ir, ClassDiagramIR):
        node_ids = {item.id for item in ir.classes}
        diagnostics.extend(
            _endpoint_diagnostics(
                [(item.source, item.target) for item in ir.relationships],
                node_ids,
                "Class relationship",
            )
        )
        if any(item.source == item.target for item in ir.relationships):
            diagnostics.append(
                Diagnostic(
                    code="self_relationship",
                    severity="error",
                    message="A class relationship cannot connect a class to itself.",
                )
            )
    elif isinstance(ir, SequenceDiagramIR):
        node_ids = {item.id for item in ir.participants}
        diagnostics.extend(
            _endpoint_diagnostics(
                [(item.source, item.target) for item in ir.messages],
                node_ids,
                "Message",
            )
        )
        if not ir.participants:
            diagnostics.append(
                Diagnostic(
                    code="missing_participants",
                    severity="error",
                    message="A sequence diagram needs at least one participant.",
                )
            )
        for note in ir.notes:
            if note.participant_id and note.participant_id not in node_ids:
                diagnostics.append(
                    Diagnostic(
                        code="missing_note_participant",
                        severity="error",
                        message=f"Note '{note.id}' references a missing participant.",
                        node_ids=[note.participant_id],
                    )
                )
            if note.message_index is not None and note.message_index >= len(
                ir.messages
            ):
                diagnostics.append(
                    Diagnostic(
                        code="missing_note_message",
                        severity="error",
                        message=f"Note '{note.id}' references a missing message.",
                    )
                )
        for fragment in ir.fragments:
            if (
                fragment.message_start > fragment.message_end
                or fragment.message_end >= len(ir.messages)
            ):
                diagnostics.append(
                    Diagnostic(
                        code="invalid_fragment_range",
                        severity="error",
                        message=f"Fragment '{fragment.id}' must cover an existing message range.",
                    )
                )
    elif isinstance(ir, ActivityDiagramIR):
        node_ids = {item.id for item in ir.nodes}
        diagnostics.extend(
            _endpoint_diagnostics(
                [(item.source, item.target) for item in ir.flows],
                node_ids,
                "Activity flow",
            )
        )
        initial_count = sum(item.type == "initial" for item in ir.nodes)
        final_count = sum(item.type == "final" for item in ir.nodes)
        if initial_count != 1:
            diagnostics.append(
                Diagnostic(
                    code="invalid_initial_count",
                    severity="error",
                    message="An activity diagram must have exactly one initial node.",
                )
            )
        if final_count < 1:
            diagnostics.append(
                Diagnostic(
                    code="missing_final_node",
                    severity="error",
                    message="An activity diagram must have at least one activity final node.",
                )
            )
        decision_ids = {item.id for item in ir.nodes if item.type == "decision"}
        outgoing: dict[str, list[str | None]] = {
            node_id: [] for node_id in decision_ids
        }
        for flow in ir.flows:
            if flow.source in outgoing:
                outgoing[flow.source].append(flow.guard)
        for node_id, guards in outgoing.items():
            if len(guards) > 1 and any(not guard for guard in guards):
                diagnostics.append(
                    Diagnostic(
                        code="unguarded_decision_flow",
                        severity="error",
                        message="Every outgoing flow from a decision with multiple paths needs a guard.",
                        node_ids=[node_id],
                    )
                )
        partition_node_ids = [
            node_id for partition in ir.partitions for node_id in partition.node_ids
        ]
        for node_id in partition_node_ids:
            if node_id not in node_ids:
                diagnostics.append(
                    Diagnostic(
                        code="missing_partition_node",
                        severity="error",
                        message=f"Activity partition references missing node '{node_id}'.",
                        node_ids=[node_id],
                    )
                )
    else:
        node_ids = {item.id for item in ir.states}
        diagnostics.extend(
            _endpoint_diagnostics(
                [(item.source, item.target) for item in ir.transitions],
                node_ids,
                "State transition",
            )
        )
        if sum(item.type == "initial" for item in ir.states) != 1:
            diagnostics.append(
                Diagnostic(
                    code="invalid_initial_count",
                    severity="error",
                    message="A state machine must have exactly one initial pseudo-state.",
                )
            )
        if sum(item.type == "final" for item in ir.states) < 1:
            diagnostics.append(
                Diagnostic(
                    code="missing_final_state",
                    severity="error",
                    message="A state machine must have at least one final state.",
                )
            )
        for state in ir.states:
            if state.parent_id and state.parent_id not in node_ids:
                diagnostics.append(
                    Diagnostic(
                        code="missing_parent_state",
                        severity="error",
                        message=f"State '{state.name}' references a missing composite parent.",
                        node_ids=[state.id, state.parent_id],
                    )
                )
        for transition in ir.transitions:
            if not any((transition.event, transition.guard, transition.action)):
                diagnostics.append(
                    Diagnostic(
                        code="unlabeled_transition",
                        severity="error",
                        message="Every state transition must identify an event, guard, or action.",
                        node_ids=[transition.source, transition.target],
                    )
                )
            source_state = next(
                (state for state in ir.states if state.id == transition.source), None
            )
            target_state = next(
                (state for state in ir.states if state.id == transition.target), None
            )
            if source_state and source_state.type == "final":
                diagnostics.append(
                    Diagnostic(
                        code="outgoing_from_final",
                        severity="error",
                        message="A final state cannot have an outgoing transition.",
                        node_ids=[transition.source],
                    )
                )
            if target_state and target_state.type == "initial":
                diagnostics.append(
                    Diagnostic(
                        code="incoming_to_initial",
                        severity="error",
                        message="An initial pseudo-state cannot have an incoming transition.",
                        node_ids=[transition.target],
                    )
                )
    return ValidationResult(
        valid=not any(item.severity == "error" for item in diagnostics),
        diagnostics=diagnostics,
    )
