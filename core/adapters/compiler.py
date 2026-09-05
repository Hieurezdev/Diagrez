from html import escape

from core.domain.diagram_ir import UseCaseIR
from core.domain.other_ir import (
    ActivityDiagramIR,
    ClassDiagramIR,
    SequenceDiagramIR,
    StateMachineDiagramIR,
)
from core.domain.revision import CompiledDiagram


class PlantUMLCompiler:
    """Compile typed UML IRs to PlantUML source and standalone SVG previews."""

    def compile(
        self,
        ir: UseCaseIR
        | ClassDiagramIR
        | SequenceDiagramIR
        | ActivityDiagramIR
        | StateMachineDiagramIR,
    ) -> CompiledDiagram:
        if isinstance(ir, ClassDiagramIR):
            return self._compile_class(ir)
        if isinstance(ir, SequenceDiagramIR):
            return self._compile_sequence(ir)
        if isinstance(ir, ActivityDiagramIR):
            return self._compile_activity(ir)
        if isinstance(ir, StateMachineDiagramIR):
            return self._compile_state_machine(ir)
        lines = ["@startuml", "left to right direction", f"title {ir.title}"]
        lines.extend(
            f'actor "{actor.display_name or actor.name}" as {actor.id}'
            for actor in ir.actors
        )
        scoped_case_ids: set[str] = set()
        for scope in ir.scopes:
            lines.append(f'rectangle "{scope.name}" as {scope.id} {{')
            for item in ir.use_cases:
                if item.scope_id == scope.id:
                    lines.append(
                        f'  usecase "{item.display_name or item.name}" as {item.id}'
                    )
                    scoped_case_ids.add(item.id)
            lines.append("}")
        lines.extend(
            f'usecase "{item.display_name or item.name}" as {item.id}'
            for item in ir.use_cases
            if item.id not in scoped_case_ids
        )
        for relationship in ir.relationships:
            arrow = "-->" if relationship.type == "association" else "..>"
            label = (
                ""
                if relationship.type == "association"
                else f" : <<{relationship.type}>>"
            )
            lines.append(f"{relationship.source} {arrow} {relationship.target}{label}")
        lines.append("@enduml")
        return CompiledDiagram(source="\n".join(lines), svg=self._svg(ir))

    @staticmethod
    def _svg(ir: UseCaseIR) -> str:
        # Deliberately uses a flat UML drafting style: the notation carries the
        # visual weight, while color is reserved for use-case shapes.
        width = 1040
        row_height = 92
        height = max(560, 220 + row_height * max(len(ir.actors), len(ir.use_cases)))
        actor_x = 105
        case_x, case_rx = 490, 150
        side_case_x = 825
        black, blue = "#202020", "#69c9ec"
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(ir.title)}">',
            '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="none" stroke="#202020" stroke-width="1.2"/></marker></defs>',
            f'<rect width="100%" height="100%" fill="#ffffff"/><text x="28" y="38" font-family="Arial,sans-serif" font-size="22" font-weight="700" fill="{black}">Use Case Diagram</text>',
            f'<rect x="250" y="76" width="740" height="{height - 112}" fill="#ffffff" stroke="{black}" stroke-width="1.5"/><text x="270" y="101" font-family="Arial,sans-serif" font-size="14" font-weight="700" fill="{black}">{escape(ir.title)}</text>',
        ]
        actor_index = {actor.id: index for index, actor in enumerate(ir.actors)}
        case_index = {item.id: index for index, item in enumerate(ir.use_cases)}
        actor_ids = set(actor_index)
        right_case_ids = {
            relationship.target
            for relationship in ir.relationships
            if relationship.type in {"include", "extend"}
            and relationship.target in case_index
        }

        main_cases = [item.id for item in ir.use_cases if item.id not in right_case_ids]
        right_cases = [item.id for item in ir.use_cases if item.id in right_case_ids]
        case_pos = {
            node_id: (case_x, 175 + index * row_height)
            for index, node_id in enumerate(main_cases)
        }
        case_pos.update(
            {
                node_id: (side_case_x, 175 + index * row_height)
                for index, node_id in enumerate(right_cases)
            }
        )

        def case_center(node_id: str) -> int:
            return case_pos[node_id][0]

        for relationship in ir.relationships:
            source_actor = relationship.source in actor_ids
            target_actor = relationship.target in actor_ids
            source_case = relationship.source in case_index
            target_case = relationship.target in case_index
            if source_actor and target_case:
                y1, y2 = (
                    175 + actor_index[relationship.source] * row_height,
                    case_pos[relationship.target][1],
                )
                path = f"M {actor_x + 28} {y1} L {case_center(relationship.target) - case_rx} {y2}"
            elif source_case and target_case:
                y1, y2 = (
                    case_pos[relationship.source][1],
                    case_pos[relationship.target][1],
                )
                source_x, target_x = (
                    case_center(relationship.source),
                    case_center(relationship.target),
                )
                if source_x <= target_x:
                    path = f"M {source_x + case_rx} {y1} L {target_x - case_rx} {y2}"
                else:
                    path = f"M {source_x - case_rx} {y1} L {target_x + case_rx} {y2}"
            elif source_case and target_actor:
                y1, y2 = (
                    case_pos[relationship.source][1],
                    175 + actor_index[relationship.target] * row_height,
                )
                path = f"M {case_center(relationship.source) - case_rx} {y1} L {actor_x + 28} {y2}"
            else:
                continue
            dashed = (
                ' stroke-dasharray="7 5"' if relationship.type != "association" else ""
            )
            marker = (
                ' marker-end="url(#arrow)"'
                if relationship.type != "association"
                else ""
            )
            label = (
                ""
                if relationship.type == "association"
                else f'<text x="{(case_center(relationship.source) + case_center(relationship.target)) / 2:.0f}" y="{min(y1, y2) - 8:.0f}" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" fill="{black}">&lt;&lt;{relationship.type}&gt;&gt;</text>'
            )
            parts.append(
                f'<path d="{path}" fill="none" stroke="{black}" stroke-width="1.5"{dashed}{marker}/>{label}'
            )

        for index, actor in enumerate(ir.actors):
            y = 175 + index * row_height
            label = actor.display_name or actor.name
            parts.append(
                f'<g aria-label="Actor {escape(label)}"><circle cx="{actor_x}" cy="{y - 18}" r="10" fill="{blue}" stroke="{black}" stroke-width="1.5"/><path d="M{actor_x} {y - 8}v27m-20-14h40m-20 14-14 23m14-23 14 23" fill="none" stroke="{black}" stroke-width="1.5"/><text x="{actor_x}" y="{y + 50}" text-anchor="middle" font-family="Arial,sans-serif" font-size="13" fill="{black}">{escape(label)}</text></g>'
            )
        for index, item in enumerate(ir.use_cases):
            x, y = case_pos[item.id]
            label = item.display_name or item.name
            parts.append(
                f'<g aria-label="Use case {escape(label)}"><ellipse cx="{x}" cy="{y}" rx="{case_rx}" ry="29" fill="{blue}" stroke="{black}" stroke-width="1.5"/><text x="{x}" y="{y + 4}" text-anchor="middle" font-family="Arial,sans-serif" font-size="13" fill="{black}">{escape(label)}</text></g>'
            )
        parts.append("</svg>")
        return "".join(parts)

    @staticmethod
    def _compile_class(ir: ClassDiagramIR) -> CompiledDiagram:
        lines = ["@startuml", f"title {ir.title}"]
        visibility = {"public": "+", "private": "-", "protected": "#", "package": "~"}
        for item in ir.classes:
            lines.append(f'class "{item.name}" as {item.id} {{')
            lines.extend(
                f"  {visibility[member.visibility]}{member.name}{': ' + member.type if member.type else ''}"
                for member in item.attributes
            )
            lines.extend(
                f"  {visibility[member.visibility]}{member.name}(){': ' + member.type if member.type else ''}"
                for member in item.methods
            )
            lines.append("}")
        arrows = {
            "association": "--",
            "aggregation": "o--",
            "composition": "*--",
            "generalization": "--|>",
            "dependency": "..>",
        }
        lines.extend(
            f"{item.source} {arrows[item.type]} {item.target}{' : ' + item.label if item.label else ''}"
            for item in ir.relationships
        )
        lines.append("@enduml")
        width, box_w = 1180, 250
        rows = (len(ir.classes) + 2) // 3
        height = max(430, 100 + rows * 240)
        positions = {
            item.id: (55 + index % 3 * 360, 90 + index // 3 * 240)
            for index, item in enumerate(ir.classes)
        }
        box_sizes = {
            item.id: (box_w, 54 + (len(item.attributes) + len(item.methods)) * 18)
            for item in ir.classes
        }
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"><defs><marker id="c-arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto"><path d="M0 0 L9 5 L0 10" fill="none" stroke="#20242a"/></marker><marker id="c-generalization" markerWidth="12" markerHeight="12" refX="11" refY="6" orient="auto"><path d="M0 0 L11 6 L0 12 Z" fill="#fff" stroke="#20242a"/></marker></defs><rect width="100%" height="100%" fill="#fff"/><text x="28" y="40" font-family="Arial" font-size="22" font-weight="700">{escape(ir.title)} · Class Diagram</text>'
        ]
        for relation in ir.relationships:
            if relation.source not in positions or relation.target not in positions:
                continue
            sx, sy = positions[relation.source]
            tx, ty = positions[relation.target]
            sw, sh = box_sizes[relation.source]
            tw, th = box_sizes[relation.target]
            x1, y1 = sx + sw / 2, sy + sh / 2
            x2, y2 = tx + tw / 2, ty + th / 2
            dashed = ' stroke-dasharray="7 5"' if relation.type == "dependency" else ""
            marker = (
                ' marker-end="url(#c-generalization)"'
                if relation.type == "generalization"
                else ' marker-end="url(#c-arrow)"'
                if relation.type == "dependency"
                else ""
            )
            parts.append(
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#20242a" stroke-width="1.5"{dashed}{marker}/>'
            )
            if relation.type in {"aggregation", "composition"}:
                diamond_x, diamond_y = x1, y1
                fill = "#20242a" if relation.type == "composition" else "#fff"
                parts.append(
                    f'<path d="M{diamond_x - 10} {diamond_y}l10 -7 10 7-10 7z" fill="{fill}" stroke="#20242a"/>'
                )
            if relation.label:
                parts.append(
                    f'<text x="{(x1 + x2) / 2}" y="{(y1 + y2) / 2 - 9}" text-anchor="middle" font-family="Arial" font-size="11">{escape(relation.label)}</text>'
                )
            if relation.source_multiplicity:
                parts.append(
                    f'<text x="{x1 + 12}" y="{y1 - 8}" font-family="Arial" font-size="11">{escape(relation.source_multiplicity)}</text>'
                )
            if relation.target_multiplicity:
                parts.append(
                    f'<text x="{x2 + 12}" y="{y2 - 8}" font-family="Arial" font-size="11">{escape(relation.target_multiplicity)}</text>'
                )
        for item in ir.classes:
            x, y = positions[item.id]
            box_w_actual, box_h = box_sizes[item.id]
            attr_y = y + 54
            method_y = attr_y + len(item.attributes) * 18
            name_style = "font-style:italic;" if item.is_abstract else ""
            parts.append(
                f'<g><rect x="{x}" y="{y}" width="{box_w_actual}" height="{box_h}" fill="#fff" stroke="#20242a" stroke-width="1.5"/><rect x="{x}" y="{y}" width="{box_w_actual}" height="36" fill="#69c9ec" stroke="#20242a"/><text x="{x + box_w_actual / 2}" y="{y + 24}" text-anchor="middle" font-family="Arial" font-size="14" font-weight="700" style="{name_style}">{escape(item.name)}</text><line x1="{x}" y1="{attr_y}" x2="{x + box_w_actual}" y2="{attr_y}" stroke="#20242a"/><line x1="{x}" y1="{method_y}" x2="{x + box_w_actual}" y2="{method_y}" stroke="#20242a"/>'
            )
            for index, member in enumerate(item.attributes):
                parts.append(
                    f'<text x="{x + 12}" y="{attr_y + 16 + index * 18}" font-family="Arial" font-size="12">{visibility[member.visibility]} {escape(member.name)}{escape(": " + member.type) if member.type else ""}</text>'
                )
            for index, member in enumerate(item.methods):
                parts.append(
                    f'<text x="{x + 12}" y="{method_y + 16 + index * 18}" font-family="Arial" font-size="12">{visibility[member.visibility]} {escape(member.name)}(){escape(": " + member.type) if member.type else ""}</text>'
                )
            parts.append("</g>")
        parts.append("</svg>")
        return CompiledDiagram(source="\n".join(lines), svg="".join(parts))

    @staticmethod
    def _compile_sequence(ir: SequenceDiagramIR) -> CompiledDiagram:
        lines = ["@startuml", f"title {ir.title}"]
        lines.extend(
            f'{item.kind} "{item.name}" as {item.id}' for item in ir.participants
        )
        arrows = {
            "sync": "->",
            "async": "->>",
            "return": "--> ",
            "self": "->",
            "recursive": "->",
            "create": "->",
            "destroy": "->x",
            "duration": "->",
        }
        for index, item in enumerate(ir.messages):
            for fragment in ir.fragments:
                if fragment.message_start == index:
                    lines.append(
                        f"{fragment.operator} {fragment.guard or fragment.label or ''}".rstrip()
                    )
            lines.append(
                f"{item.source} {arrows[item.type].strip()} {item.target} : {item.label}"
            )
            for fragment in reversed(ir.fragments):
                if fragment.message_end == index:
                    lines.append("end")
        lines.extend(
            f"note right of {note.participant_id}\n  {note.text}\nend note"
            for note in ir.notes
            if note.participant_id
        )
        lines.append("@enduml")
        width = max(800, 180 + len(ir.participants) * 190)
        height = max(480, 180 + len(ir.messages) * 62)
        pos = {item.id: 110 + index * 190 for index, item in enumerate(ir.participants)}
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"><defs><marker id="s-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="none" stroke="#20242a"/></marker></defs><rect width="100%" height="100%" fill="#fff"/><text x="28" y="40" font-family="Arial" font-size="22" font-weight="700">{escape(ir.title)} · Sequence Diagram</text>'
        ]
        for participant in ir.participants:
            x = pos[participant.id]
            parts.append(
                f'<rect x="{x - 70}" y="72" width="140" height="42" fill="#69c9ec" stroke="#20242a"/><text x="{x}" y="98" text-anchor="middle" font-family="Arial" font-size="13">{escape(participant.name)}</text><line x1="{x}" y1="114" x2="{x}" y2="{height - 30}" stroke="#777" stroke-dasharray="7 5"/>'
            )
        for index, message in enumerate(ir.messages):
            if message.source not in pos or message.target not in pos:
                continue
            y = 155 + index * 62
            source, target = pos[message.source], pos[message.target]
            if message.type in {"self", "recursive"} or source == target:
                path = f"M {source} {y} C {source + 62} {y}, {source + 62} {y + 28}, {source} {y + 28}"
                parts.append(
                    f'<path d="{path}" fill="none" stroke="#20242a" stroke-width="1.5" marker-end="url(#s-arrow)"/><text x="{source + 42}" y="{y - 8}" text-anchor="middle" font-family="Arial" font-size="12">{escape(message.label)}</text>'
                )
                continue
            dashed = (
                ' stroke-dasharray="7 5"'
                if message.type in {"return", "create"}
                else ""
            )
            end_marker = (
                "" if message.type == "destroy" else ' marker-end="url(#s-arrow)"'
            )
            parts.append(
                f'<line x1="{source}" y1="{y}" x2="{target}" y2="{y}" stroke="#20242a" stroke-width="1.5"{dashed}{end_marker}/><text x="{(source + target) / 2}" y="{y - 8}" text-anchor="middle" font-family="Arial" font-size="12">{escape(message.label)}</text>'
            )
            if message.type == "destroy":
                parts.append(
                    f'<path d="M{target - 7} {y - 9}l14 18m0-18-14 18" stroke="#20242a" stroke-width="1.5"/>'
                )
            if message.type == "duration":
                parts.append(
                    f'<line x1="{source}" y1="{y}" x2="{target}" y2="{y + 32}" stroke="#20242a" stroke-width="1.2" stroke-dasharray="4 4"/>'
                )
        for index, note in enumerate(ir.notes):
            x = pos.get(note.participant_id or ir.participants[0].id, 120) + 44
            y = (
                135
                + (note.message_index if note.message_index is not None else index) * 62
            )
            parts.append(
                f'<path d="M{x} {y}h118v48h-118z" fill="#fff4cc" stroke="#20242a"/><text x="{x + 8}" y="{y + 20}" font-family="Arial" font-size="11">{escape(note.text[:28])}</text>'
            )
        parts.append("</svg>")
        return CompiledDiagram(source="\n".join(lines), svg="".join(parts))

    @staticmethod
    def _compile_activity(ir: ActivityDiagramIR) -> CompiledDiagram:
        lines = ["@startuml", f"title {ir.title}", "start"]
        lines.extend(f":{node.label};" for node in ir.nodes if node.type == "action")
        lines.extend(["stop", "@enduml"])
        node_ids = {node.id for node in ir.nodes}
        outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        for flow in ir.flows:
            if flow.source in outgoing and flow.target in node_ids:
                outgoing[flow.source].append(flow.target)
        ranks: dict[str, int] = {}
        queue = [(node.id, 0) for node in ir.nodes if node.type == "initial"]
        while queue:
            node_id, rank = queue.pop(0)
            if node_id in ranks and ranks[node_id] >= rank:
                continue
            ranks[node_id] = rank
            queue.extend((target, rank + 1) for target in outgoing.get(node_id, []))
        next_rank = max(ranks.values(), default=-1) + 1
        for node in ir.nodes:
            if node.id not in ranks:
                ranks[node.id] = next_rank
                next_rank += 1
        partition_by_node = {
            node_id: index
            for index, partition in enumerate(ir.partitions)
            for node_id in partition.node_ids
        }
        lane_count = max(1, len(ir.partitions))
        lane_width = 260
        rank_groups: dict[int, list[str]] = {}
        for node in ir.nodes:
            rank_groups.setdefault(ranks[node.id], []).append(node.id)
        pos: dict[str, tuple[int, int]] = {}
        for rank, group in rank_groups.items():
            for index, node_id in enumerate(group):
                x = (
                    150 + partition_by_node[node_id] * lane_width
                    if node_id in partition_by_node
                    else 150 + index * 230
                )
                pos[node_id] = (x, 110 + rank * 125)
        width = max(
            720,
            180
            + max(
                lane_count,
                max((len(group) for group in rank_groups.values()), default=1),
            )
            * lane_width,
        )
        height = max(500, 180 + max(ranks.values(), default=0) * 125)
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"><defs><marker id="a-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="none" stroke="#20242a"/></marker></defs><rect width="100%" height="100%" fill="#fff"/><text x="28" y="40" font-family="Arial" font-size="22" font-weight="700">{escape(ir.title)} · Activity Diagram</text>'
        ]
        for index, partition in enumerate(ir.partitions):
            x = 20 + index * lane_width
            parts.append(
                f'<rect x="{x}" y="66" width="{lane_width}" height="{height - 86}" fill="#f7fbfc" stroke="#9baeb5" stroke-width="1"/><text x="{x + 12}" y="88" font-family="Arial" font-size="12" font-weight="700">{escape(partition.name)}</text>'
            )
        for flow in ir.flows:
            if flow.source not in pos or flow.target not in pos:
                continue
            sx, sy = pos[flow.source]
            tx, ty = pos[flow.target]
            dashed = ' stroke-dasharray="7 5"' if flow.type == "object" else ""
            parts.append(
                f'<line x1="{sx}" y1="{sy + 28}" x2="{tx}" y2="{ty - 28}" stroke="#20242a" stroke-width="1.5"{dashed} marker-end="url(#a-arrow)"/>{f'<text x="{(sx + tx) / 2}" y="{(sy + ty) / 2 - 8}" text-anchor="middle" font-family="Arial" font-size="12">[{escape(flow.guard)}]</text>' if flow.guard else ""}'
            )
        for node in ir.nodes:
            x, y = pos[node.id]
            if node.type == "initial":
                parts.append(f'<circle cx="{x}" cy="{y}" r="13" fill="#20242a"/>')
            elif node.type == "final":
                parts.append(
                    f'<circle cx="{x}" cy="{y}" r="16" fill="#fff" stroke="#20242a" stroke-width="2"/><circle cx="{x}" cy="{y}" r="10" fill="#20242a"/>'
                )
            elif node.type in {"decision", "merge"}:
                parts.append(
                    f'<path d="M{x} {y - 31} L{x + 48} {y} L{x} {y + 31} L{x - 48} {y} Z" fill="#fff4cc" stroke="#20242a"/><text x="{x}" y="{y + 4}" text-anchor="middle" font-family="Arial" font-size="12">{escape(node.label)}</text>'
                )
            elif node.type in {"fork", "join"}:
                parts.append(
                    f'<rect x="{x - 72}" y="{y - 7}" width="144" height="14" rx="2" fill="#20242a"/><text x="{x}" y="{y + 28}" text-anchor="middle" font-family="Arial" font-size="11">{escape(node.label)}</text>'
                )
            elif node.type == "object":
                parts.append(
                    f'<rect x="{x - 105}" y="{y - 25}" width="210" height="50" fill="#fff" stroke="#20242a"/><text x="{x}" y="{y + 5}" text-anchor="middle" font-family="Arial" font-size="13">{escape(node.label)}</text>'
                )
            else:
                parts.append(
                    f'<rect x="{x - 105}" y="{y - 28}" width="210" height="56" rx="18" fill="#69c9ec" stroke="#20242a"/><text x="{x}" y="{y + 4}" text-anchor="middle" font-family="Arial" font-size="13">{escape(node.label)}</text>'
                )
        parts.append("</svg>")
        return CompiledDiagram(source="\n".join(lines), svg="".join(parts))

    @staticmethod
    def _compile_state_machine(ir: StateMachineDiagramIR) -> CompiledDiagram:
        lines = ["@startuml", f"title {ir.title}"]
        for state in ir.states:
            if state.type != "state":
                continue
            actions = [
                f"entry / {state.entry_action}" if state.entry_action else "",
                f"do / {state.do_activity}" if state.do_activity else "",
                f"exit / {state.exit_action}" if state.exit_action else "",
            ]
            action_lines = [action for action in actions if action]
            if action_lines:
                lines.append(f'state "{state.name}" as {state.id} {{')
                lines.extend(f"  {action}" for action in action_lines)
                lines.append("}")
            else:
                lines.append(f'state "{state.name}" as {state.id}')
        lines.extend(
            f"[*] --> {state.id}" for state in ir.states if state.type == "initial"
        )
        lines.extend(
            f"{state.id} --> [*]" for state in ir.states if state.type == "final"
        )
        lines.extend(
            f"state {state.id} <<history>>"
            for state in ir.states
            if state.type == "history"
        )
        lines.extend(
            f"state {state.id} <<choice>>"
            for state in ir.states
            if state.type == "choice"
        )
        lines.extend(
            f"{item.source} --> {item.target}{' : ' + ' / '.join(filter(None, [item.event, f'[{item.guard}]' if item.guard else None, item.action])) if any((item.event, item.guard, item.action)) else ''}"
            for item in ir.transitions
        )
        lines.append("@enduml")
        state_ids = {state.id for state in ir.states}
        outgoing: dict[str, list[str]] = {state_id: [] for state_id in state_ids}
        for transition in ir.transitions:
            if transition.source in outgoing and transition.target in state_ids:
                outgoing[transition.source].append(transition.target)
        initial_ids = [state.id for state in ir.states if state.type == "initial"]
        ranks: dict[str, int] = {}
        queue = [(state_id, 0) for state_id in initial_ids]
        while queue:
            state_id, rank = queue.pop(0)
            if state_id in ranks and ranks[state_id] >= rank:
                continue
            ranks[state_id] = rank
            queue.extend((target, rank + 1) for target in outgoing.get(state_id, []))
        next_rank = max(ranks.values(), default=-1) + 1
        for state in ir.states:
            if state.id not in ranks:
                ranks[state.id] = next_rank
                next_rank += 1
        rank_groups: dict[int, list[str]] = {}
        for state in ir.states:
            rank_groups.setdefault(ranks[state.id], []).append(state.id)
        rank_gap = 300
        width = max(1100, 180 + (max(rank_groups, default=0) + 1) * rank_gap)
        height = max(
            500,
            180 + max((len(group) for group in rank_groups.values()), default=1) * 150,
        )
        pos = {
            state_id: (110 + rank * rank_gap, 110 + index * 150)
            for rank, group in rank_groups.items()
            for index, state_id in enumerate(group)
        }
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"><defs><marker id="m-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="none" stroke="#20242a"/></marker></defs><rect width="100%" height="100%" fill="#fff"/><text x="28" y="40" font-family="Arial" font-size="22" font-weight="700">{escape(ir.title)} · State Machine Diagram</text>'
        ]
        for state in ir.states:
            if state.parent_id not in pos or state.type != "state":
                continue
            parent_x, parent_y = pos[state.parent_id]
            parts.append(
                f'<rect x="{parent_x - 205}" y="{parent_y - 70}" width="410" height="150" rx="16" fill="#eaf5f8" stroke="#20242a" stroke-width="1.5"/><text x="{parent_x - 185}" y="{parent_y - 45}" font-family="Arial" font-size="12" font-weight="700">{escape(next(item.name for item in ir.states if item.id == state.parent_id))}</text>'
            )
            break
        for transition in ir.transitions:
            if transition.source not in pos or transition.target not in pos:
                continue
            sx, sy = pos[transition.source]
            tx, ty = pos[transition.target]
            label = " / ".join(
                filter(
                    None,
                    [
                        transition.event,
                        f"[{transition.guard}]" if transition.guard else None,
                        transition.action,
                    ],
                )
            )
            source_offset = (
                105
                if next(
                    state for state in ir.states if state.id == transition.source
                ).type
                == "state"
                else 22
            )
            target_offset = (
                105
                if next(
                    state for state in ir.states if state.id == transition.target
                ).type
                == "state"
                else 22
            )
            start_x = sx + source_offset if tx >= sx else sx - source_offset
            end_x = tx - target_offset if tx >= sx else tx + target_offset
            bend = (sy + ty) / 2
            path = f"M {start_x} {sy} C {start_x + (end_x - start_x) / 3} {bend}, {end_x - (end_x - start_x) / 3} {bend}, {end_x} {ty}"
            label_y = min(sy, ty) - 48 if abs(sy - ty) < 20 else bend - 8
            parts.append(
                f'<path d="{path}" fill="none" stroke="#20242a" stroke-width="1.5" marker-end="url(#m-arrow)"/><text x="{(start_x + end_x) / 2}" y="{label_y}" text-anchor="middle" font-family="Arial" font-size="12">{escape(label)}</text>'
            )
        for state in ir.states:
            x, y = pos[state.id]
            if state.type == "initial":
                parts.append(f'<circle cx="{x}" cy="{y}" r="13" fill="#20242a"/>')
            elif state.type == "final":
                parts.append(
                    f'<circle cx="{x}" cy="{y}" r="16" fill="#fff" stroke="#20242a" stroke-width="2"/><circle cx="{x}" cy="{y}" r="10" fill="#20242a"/>'
                )
            elif state.type == "history":
                parts.append(
                    f'<circle cx="{x}" cy="{y}" r="18" fill="#fff" stroke="#20242a" stroke-width="1.5"/><text x="{x}" y="{y + 5}" text-anchor="middle" font-family="Arial" font-size="13">H</text>'
                )
            elif state.type == "choice":
                parts.append(
                    f'<path d="M{x} {y - 22} L{x + 22} {y} L{x} {y + 22} L{x - 22} {y} Z" fill="#fff4cc" stroke="#20242a"/><text x="{x}" y="{y + 4}" text-anchor="middle" font-family="Arial" font-size="11">?</text>'
                )
            else:
                action_lines = [
                    line
                    for line in [
                        f"entry / {state.entry_action}" if state.entry_action else None,
                        f"do / {state.do_activity}" if state.do_activity else None,
                        f"exit / {state.exit_action}" if state.exit_action else None,
                    ]
                    if line
                ]
                box_height = 60 + len(action_lines) * 16
                parts.append(
                    f'<rect x="{x - 105}" y="{y - 30}" width="210" height="{box_height}" rx="12" fill="#69c9ec" stroke="#20242a"/><text x="{x}" y="{y - 7}" text-anchor="middle" font-family="Arial" font-size="13">{escape(state.name)}</text>'
                    + "".join(
                        f'<text x="{x - 92}" y="{y + 13 + index * 15}" font-family="Arial" font-size="10">{escape(line)}</text>'
                        for index, line in enumerate(action_lines)
                    )
                )
        parts.append("</svg>")
        return CompiledDiagram(source="\n".join(lines), svg="".join(parts))
