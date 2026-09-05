import { PointerEvent, useEffect, useMemo, useRef, useState } from "react";

export type Actor = { id: string; name: string; display_name?: string | null };
export type SystemScope = { id: string; name: string };
export type UseCase = { id: string; name: string; display_name?: string | null; scope_id?: string | null };
export type Relationship = { type: "association" | "include" | "extend"; source: string; target: string };
export type SequenceParticipant = { id: string; name: string; kind: "actor" | "object" | "system" | "database" };
export type SequenceMessage = { source: string; target: string; label: string; type: "sync" | "async" | "return" };
export type SequenceFragment = { id: string; operator: "alt" | "opt" | "par" | "loop" | "break" | "critical" | "neg" | "ref" | "assert"; message_start: number; message_end: number; guard?: string | null; label?: string | null };
export type SequenceDiagramIR = { type: "sequence"; title: string; participants: SequenceParticipant[]; messages: SequenceMessage[]; notes?: { id: string; text: string; participant_id?: string | null; message_index?: number | null }[]; fragments?: SequenceFragment[] };
export type ClassMember = { name: string; type?: string | null; visibility?: "public" | "private" | "protected" | "package" };
export type UmlClass = { id: string; name: string; attributes: ClassMember[]; methods: ClassMember[]; is_abstract?: boolean };
export type ClassRelationship = { type: "association" | "aggregation" | "composition" | "generalization" | "dependency"; source: string; target: string; label?: string | null };
export type ClassDiagramIR = { type: "class"; title: string; classes: UmlClass[]; relationships: ClassRelationship[] };
export type ActivityNode = { id: string; label: string; type: "initial" | "action" | "decision" | "merge" | "fork" | "join" | "object" | "final" };
export type ActivityFlow = { source: string; target: string; guard?: string | null; type?: "control" | "object" };
export type ActivityPartition = { id: string; name: string; node_ids: string[] };
export type ActivityDiagramIR = { type: "activity"; title: string; nodes: ActivityNode[]; flows: ActivityFlow[]; partitions: ActivityPartition[] };
export type StateNode = { id: string; name: string; type: "initial" | "state" | "final" | "history" | "choice"; entry_action?: string | null; do_activity?: string | null; exit_action?: string | null; parent_id?: string | null; region?: string | null };
export type StateTransition = { source: string; target: string; event?: string | null; guard?: string | null; action?: string | null };
export type StateMachineDiagramIR = { type: "state_machine"; title: string; states: StateNode[]; transitions: StateTransition[] };
export type UseCaseIR = {
  type: "use_case";
  title: string;
  actors: Actor[];
  scopes?: SystemScope[];
  use_cases: UseCase[];
  relationships: Relationship[];
};
export type Selection =
  | { kind: "actor" | "use_case" | "scope"; id: string }
  | { kind: "relationship"; index: number }
  | null;

type Point = { x: number; y: number };
type ScopeBox = Point & { width: number; height: number };
type DragTarget = { kind: "node" | "scope"; id: string; last: Point };

const CANVAS_WIDTH = 1180;

function effectiveScopes(ir: UseCaseIR): SystemScope[] {
  return ir.scopes?.length ? ir.scopes : [{ id: "system", name: ir.title }];
}

type SequenceSelection = { kind: "participant"; id: string } | { kind: "message"; index: number } | null;

type StructuralIR = ClassDiagramIR | ActivityDiagramIR | StateMachineDiagramIR;

export function StructuralEditor({ ir }: { ir: StructuralIR }) {
  const width = 980;
  const height = Math.max(520, 150 + (ir.type === "class" ? ir.classes.length : ir.type === "activity" ? ir.nodes.length : ir.states.length) * 95);
  const items = ir.type === "class" ? ir.classes : ir.type === "activity" ? ir.nodes : ir.states;
  const ids = items.map((item) => item.id);
  const initialPositions = useMemo(() => Object.fromEntries(items.map((item, index) => [item.id, { x: 180 + (index % 3) * 300, y: 110 + Math.floor(index / 3) * 115 }])), [ids.join("|")]);
  const [positions, setPositions] = useState<Record<string, Point>>(initialPositions);
  const [dragging, setDragging] = useState<{ id: string; last: Point } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  useEffect(() => {
    setPositions((current) => {
      const next: Record<string, Point> = {};
      items.forEach((item, index) => {
        next[item.id] = current[item.id] ?? { x: 180 + (index % 3) * 300, y: 110 + Math.floor(index / 3) * 115 };
      });
      return next;
    });
  }, [ids.join("|")]);

  function pointFromClient(clientX: number, clientY: number): Point {
    const rect = svgRef.current!.getBoundingClientRect();
    return { x: ((clientX - rect.left) / rect.width) * width, y: ((clientY - rect.top) / rect.height) * height };
  }

  function startDrag(event: PointerEvent<SVGGElement>, id: string): void {
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging({ id, last: pointFromClient(event.clientX, event.clientY) });
  }

  function move(event: PointerEvent<SVGSVGElement>): void {
    if (!dragging) return;
    const point = pointFromClient(event.clientX, event.clientY);
    const current = positions[dragging.id];
    if (!current) return;
    setPositions((value) => ({ ...value, [dragging.id]: { x: Math.max(120, Math.min(width - 120, current.x + point.x - dragging.last.x)), y: Math.max(90, Math.min(height - 55, current.y + point.y - dragging.last.y)) } }));
    setDragging({ id: dragging.id, last: point });
  }

  const edges = ir.type === "class" ? ir.relationships : ir.type === "activity" ? ir.flows : ir.transitions;
  return <div className="editor-shell structural-shell"><div className="editor-toolbar"><span>NATIVE UML CANVAS</span><span>Drag nodes to reposition · edit details in the Inspector</span></div><svg ref={svgRef} className="uml-editor structural-editor" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${ir.title} ${ir.type} diagram`} onPointerMove={move} onPointerUp={() => setDragging(null)} onPointerCancel={() => setDragging(null)}>
    <defs><marker id={`structural-arrow-${ir.type}`} markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="none" stroke="#20242a" strokeWidth="1.4" /></marker></defs>
    <rect width={width} height={height} fill="#fff" /><text x="28" y="42" className="diagram-title">{ir.title}</text>
    {edges.map((edge, index) => { const source = positions[edge.source]; const target = positions[edge.target]; return source && target ? <line key={`${edge.source}-${edge.target}-${index}`} x1={source.x} y1={source.y} x2={target.x} y2={target.y} className="structural-edge" markerEnd={`url(#structural-arrow-${ir.type})`} /> : null; })}
    {items.map((item, index) => { const position = positions[item.id] ?? { x: 180 + (index % 3) * 300, y: 110 + Math.floor(index / 3) * 115 }; const label = "name" in item ? item.name : item.label; const isActivity = ir.type === "activity"; const isState = ir.type === "state_machine"; return <g key={item.id} className="draggable-node" transform={`translate(${position.x} ${position.y})`} onPointerDown={(event) => startDrag(event, item.id)}>
      {isActivity ? <rect x="-92" y="-27" width="184" height="54" rx="18" className="activity-node" /> : <rect x="-108" y="-30" width="216" height="60" rx={isState ? 13 : 2} className="structural-node" />}
      <text className="node-label" y="5">{label}</text>
      {ir.type === "class" && <line x1="-108" y1="-10" x2="108" y2="-10" className="class-divider" />}
    </g>; })}
  </svg></div>;
}

export function SequenceEditor({ ir }: { ir: SequenceDiagramIR }) {
  const [selection, setSelection] = useState<SequenceSelection>(null);
  const left = 120;
  const gap = Math.max(150, Math.min(210, 860 / Math.max(ir.participants.length, 1)));
  const positions = Object.fromEntries(ir.participants.map((item, index) => [item.id, left + index * gap]));
  const width = Math.max(860, left * 2 + Math.max(ir.participants.length - 1, 0) * gap);
  const height = Math.max(560, 220 + ir.messages.length * 78);

  return <div className="editor-shell sequence-shell">
    <div className="editor-toolbar"><span>OBJECT DIMENSION →</span><span>TIME ↓ · Select a lifeline or message</span></div>
    <svg className="uml-editor sequence-editor" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${ir.title} sequence diagram`}>
      <defs><marker id="sequence-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="none" stroke="#20242a" strokeWidth="1.4" /></marker></defs>
      <rect width={width} height={height} fill="#fff" />
      <text x="28" y="42" className="diagram-title">{ir.title}</text>
      {ir.participants.map((participant) => {
        const x = positions[participant.id];
        const selected = selection?.kind === "participant" && selection.id === participant.id;
        return <g key={participant.id} className={selected ? "sequence-selected" : ""} onClick={() => setSelection({ kind: "participant", id: participant.id })}>
          {participant.kind === "actor" ? <g transform={`translate(${x} 86)`}><circle cy="-12" r="10" className="actor-head" /><path d="M0 -2v25m-19-14h38M0 23l-13 21M0 23l13 21" className="actor-body" /></g> : <rect x={x - 66} y="60" width="132" height="46" rx="3" className="participant-box" />}
          <text x={x} y={participant.kind === "actor" ? 151 : 88} className="sequence-label">{participant.name}</text>
          <line x1={x} y1="166" x2={x} y2={height - 24} className="lifeline" />
        </g>;
      })}
      {(ir.fragments ?? []).map((fragment) => {
        const start = 210 + fragment.message_start * 78 - 28;
        const end = 210 + fragment.message_end * 78 + 48;
        return <g key={fragment.id} className="sequence-fragment">
          <rect x="48" y={start} width={width - 96} height={end - start} className="fragment-frame" />
          <rect x="48" y={start} width="58" height="24" className="fragment-operator" />
          <text x="77" y={start + 16} className="fragment-label">{fragment.operator}</text>
          {(fragment.guard || fragment.label) && <text x="116" y={start + 16} className="fragment-guard">{fragment.guard || fragment.label}</text>}
        </g>;
      })}
      {ir.messages.map((message, index) => {
        const source = positions[message.source]; const target = positions[message.target];
        if (source === undefined || target === undefined) return null;
        const y = 210 + index * 78;
        const self = source === target;
        const returnMessage = message.type === "return";
        return <g key={`${message.source}-${message.target}-${index}`} className={selection?.kind === "message" && selection.index === index ? "sequence-message-selected" : ""} onClick={(event) => { event.stopPropagation(); setSelection({ kind: "message", index }); }}>
          {self ? <path d={`M ${source} ${y} C ${source + 90} ${y}, ${source + 90} ${y + 36}, ${source} ${y + 36}`} className="sequence-message" fill="none" strokeDasharray={returnMessage ? "8 6" : undefined} markerEnd="url(#sequence-arrow)" /> : <line x1={source} y1={y} x2={target} y2={y} className="sequence-message" strokeDasharray={returnMessage ? "8 6" : undefined} markerEnd="url(#sequence-arrow)" />}
          <text x={self ? source + 48 : (source + target) / 2} y={y - 10} className="message-label">{message.label}{message.type === "async" ? "  ↝" : ""}</text>
          <rect x={source - 5} y={y} width="10" height="54" className="activation" />
          {!self && <rect x={target - 5} y={y} width="10" height="54" className="activation" />}
        </g>;
      })}
      {(ir.notes ?? []).map((note, index) => {
        const x = positions[note.participant_id ?? ir.participants[0]?.id] ?? 120;
        const y = 132 + (note.message_index ?? index) * 78;
        return <g key={note.id}><path d={`M${x + 45} ${y}h150v48h-150z`} className="sequence-note" /><text x={x + 55} y={y + 20} className="note-label">{note.text}</text></g>;
      })}
    </svg>
  </div>;
}

export function DiagramEditor({ ir, selection, onSelectionChange }: { ir: UseCaseIR; selection: Selection; onSelectionChange: (selection: Selection) => void }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [dragging, setDragging] = useState<DragTarget | null>(null);
  const scopes = useMemo(() => effectiveScopes(ir), [ir]);
  const initialScopeBoxes = useMemo(() => {
    const boxes: Record<string, ScopeBox> = {};
    if (scopes.length === 1) {
      boxes[scopes[0].id] = { x: 245, y: 72, width: 900, height: Math.max(520, 170 + ir.use_cases.length * 82) };
      return boxes;
    }
    const columns = Math.min(2, scopes.length);
    const width = (900 - (columns - 1) * 22) / columns;
    scopes.forEach((scope, index) => {
      boxes[scope.id] = {
        x: 245 + (index % columns) * (width + 22),
        y: 72 + Math.floor(index / columns) * 370,
        width,
        height: 340,
      };
    });
    return boxes;
  }, [ir.use_cases.length, scopes]);
  const initialPositions = useMemo(() => {
    const positions: Record<string, Point> = {};
    ir.actors.forEach((actor, index) => { positions[actor.id] = { x: 105, y: 175 + index * 110 }; });
    const caseCounts: Record<string, number> = {};
    ir.use_cases.forEach((item) => {
      const scopeId = item.scope_id && initialScopeBoxes[item.scope_id] ? item.scope_id : scopes[0]?.id;
      const box = initialScopeBoxes[scopeId];
      const index = caseCounts[scopeId] ?? 0;
      caseCounts[scopeId] = index + 1;
      positions[item.id] = { x: box.x + box.width / 2, y: box.y + 100 + index * 82 };
    });
    return positions;
  }, [initialScopeBoxes, ir.actors, ir.use_cases, scopes]);
  const [positions, setPositions] = useState(initialPositions);
  const [scopeBoxes, setScopeBoxes] = useState(initialScopeBoxes);
  useEffect(() => { setPositions(initialPositions); setScopeBoxes(initialScopeBoxes); }, [initialPositions, initialScopeBoxes]);
  const height = Math.max(
    650,
    ...Object.values(scopeBoxes).map((box) => box.y + box.height + 35),
    230 + ir.actors.length * 110,
  );

  function pointFromClient(clientX: number, clientY: number): Point {
    const rect = svgRef.current!.getBoundingClientRect();
    return { x: ((clientX - rect.left) / rect.width) * CANVAS_WIDTH, y: ((clientY - rect.top) / rect.height) * height };
  }

  function startDrag(event: PointerEvent<SVGGElement>, id: string, kind: DragTarget["kind"], selectionKind: "actor" | "use_case" | "scope") {
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging({ kind, id, last: pointFromClient(event.clientX, event.clientY) });
    onSelectionChange({ kind: selectionKind, id });
  }

  function move(event: PointerEvent<SVGSVGElement>) {
    if (!dragging) return;
    const point = pointFromClient(event.clientX, event.clientY);
    if (dragging.kind === "node") {
      setPositions((current) => ({
        ...current,
        [dragging.id]: {
          x: Math.max(55, Math.min(CANVAS_WIDTH - 45, point.x)),
          y: Math.max(105, Math.min(height - 45, point.y)),
        },
      }));
    } else {
      const box = scopeBoxes[dragging.id];
      if (!box) return;
      const dx = Math.max(205, Math.min(CANVAS_WIDTH - box.width - 20, box.x + point.x - dragging.last.x)) - box.x;
      const dy = Math.max(60, box.y + point.y - dragging.last.y) - box.y;
      setScopeBoxes((current) => ({ ...current, [dragging.id]: { ...box, x: box.x + dx, y: box.y + dy } }));
      const assignedIds = new Set(ir.use_cases.filter((item) => (item.scope_id ?? scopes[0]?.id) === dragging.id).map((item) => item.id));
      setPositions((current) => Object.fromEntries(Object.entries(current).map(([id, value]) => [id, assignedIds.has(id) ? { x: value.x + dx, y: value.y + dy } : value])));
    }
    setDragging({ ...dragging, last: point });
  }

  return <div className="editor-shell">
    <div className="editor-toolbar"><span>Drag actors, use cases, and scope boundaries</span><span>Click any element to edit</span></div>
    <svg ref={svgRef} className="uml-editor" viewBox={"0 0 " + CANVAS_WIDTH + " " + height} onPointerMove={move} onPointerUp={() => setDragging(null)} onPointerCancel={() => setDragging(null)} onPointerDown={() => onSelectionChange(null)}>
      <defs><marker id="editor-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="none" stroke="#20242a" strokeWidth="1.4" /></marker></defs>
      <rect width={CANVAS_WIDTH} height={height} fill="#fff" />
      <text x="28" y="42" className="diagram-title">Use Case Diagram</text>
      {scopes.map((scope) => {
        const box = scopeBoxes[scope.id];
        const selected = selection?.kind === "scope" && selection.id === scope.id;
        return <g key={scope.id} className={"scope-boundary " + (selected ? "selected" : "")} onPointerDown={(event) => startDrag(event, scope.id, "scope", "scope")}>
          <rect x={box.x} y={box.y} width={box.width} height={box.height} className="scope-shape" />
          <rect x={box.x} y={box.y} width={box.width} height="38" className="scope-header" />
          <text x={box.x + 18} y={box.y + 25} className="boundary-title">{scope.name}</text>
        </g>;
      })}
      {ir.relationships.map((relationship, index) => {
        const source = positions[relationship.source]; const target = positions[relationship.target];
        if (!source || !target) return null;
        const dashed = relationship.type !== "association";
        const selected = selection?.kind === "relationship" && selection.index === index;
        return <g key={relationship.source + "-" + relationship.target + "-" + index} onPointerDown={(event) => { event.stopPropagation(); onSelectionChange({ kind: "relationship", index }); }}>
          <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} className={"relationship " + (selected ? "selected" : "")} strokeDasharray={dashed ? "8 6" : undefined} markerEnd={dashed ? "url(#editor-arrow)" : undefined} />
          <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} className="relationship-hit" />
          {dashed && <text x={(source.x + target.x) / 2} y={(source.y + target.y) / 2 - 9} className="relationship-label">{"<<" + relationship.type + ">>"}</text>}
        </g>;
      })}
      {ir.actors.map((actor) => {
        const position = positions[actor.id]; const selected = selection?.kind === "actor" && selection.id === actor.id;
        return <g key={actor.id} className={"draggable-node " + (selected ? "selected" : "")} transform={"translate(" + position.x + " " + position.y + ")"} onPointerDown={(event) => startDrag(event, actor.id, "node", "actor")}>
          <circle cy="-22" r="11" className="actor-head" /><path d="M0 -11v31m-22-15h44M0 20l-16 25M0 20l16 25" className="actor-body" /><text y="65" className="node-label">{actor.display_name || actor.name}</text>
        </g>;
      })}
      {ir.use_cases.map((item) => {
        const position = positions[item.id]; const selected = selection?.kind === "use_case" && selection.id === item.id;
        return <g key={item.id} className={"draggable-node " + (selected ? "selected" : "")} transform={"translate(" + position.x + " " + position.y + ")"} onPointerDown={(event) => startDrag(event, item.id, "node", "use_case")}>
          <ellipse rx="145" ry="34" className="use-case-shape" /><text y="5" className="node-label">{item.display_name || item.name}</text>
        </g>;
      })}
    </svg>
  </div>;
}
