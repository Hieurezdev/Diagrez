import { PointerEvent as ReactPointerEvent, StrictMode, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { ActivityDiagramIR, ClassDiagramIR, DiagramEditor, Selection, SequenceDiagramIR, SequenceEditor, StateMachineDiagramIR, StructuralEditor, SystemScope, UseCaseIR } from "./DiagramEditor";
import "./styles.css";
import "./export.css";
import "./liquid-glass.css";
import "./anti-slop-fixes.css";
import "./simple-glass.css";

type DiagramType = "use_case" | "class" | "sequence" | "activity" | "state_machine";
type OtherIR = { type: Exclude<DiagramType, "use_case" | "sequence">; title: string };
type StructuralIR = ClassDiagramIR | ActivityDiagramIR | StateMachineDiagramIR;
type Revision = { id: string; ir: UseCaseIR | SequenceDiagramIR | StructuralIR | OtherIR; compiled: { svg: string } };
type Clarification = {
  thread_id?: string;
  question: string;
  intent_summary: string;
  missing_information: string[];
  round: number;
};

type ExportFormat = "drawio" | "svg" | "png" | "json";
type DiagramIR = UseCaseIR | SequenceDiagramIR | StructuralIR | OtherIR;
type WorkflowStep = "analyze_intent" | "clarify_requirements" | "build_ir" | "review_ir" | "validate_ir" | "ace_reflect" | "repair_ir" | "ace_curate" | "compile" | "completed" | "failed";

const WORKFLOW_STEPS: { id: WorkflowStep; label: string }[] = [
  { id: "analyze_intent", label: "Understand request" },
  { id: "build_ir", label: "Build UML structure" },
  { id: "review_ir", label: "Review notation" },
  { id: "validate_ir", label: "Validate semantics" },
  { id: "compile", label: "Render diagram" },
];

function isSequenceIR(value: DiagramIR): value is SequenceDiagramIR {
  return value.type === "sequence" && "participants" in value && "messages" in value;
}

function isStructuralIR(value: DiagramIR): value is StructuralIR {
  return value.type === "class" || value.type === "activity" || value.type === "state_machine";
}

const PALETTE: Record<DiagramType, string[]> = {
  use_case: ["Actor", "Use case", "System scope", "Association"],
  class: ["Class", "Attribute", "Operation", "Association"],
  sequence: ["Actor", "Lifeline", "Message", "Fragment"],
  activity: ["Action", "Decision", "Fork / Join", "Object node"],
  state_machine: ["State", "Initial state", "Transition", "Final state"],
};

function validate(ir: UseCaseIR): string[] {
  const actors = new Set(ir.actors.map((item) => item.id));
  const cases = new Set(ir.use_cases.map((item) => item.id));
  const scopes = new Set((ir.scopes ?? [{ id: "system", name: ir.title }]).map((item) => item.id));
  const scopeIssues = ir.use_cases.flatMap((item) => item.scope_id && !scopes.has(item.scope_id) ? ["Use case " + (item.display_name || item.name) + " references a missing scope."] : []);
  return [...scopeIssues, ...ir.relationships.flatMap((item, index) => {
    if (!actors.has(item.source) && !cases.has(item.source) || !actors.has(item.target) && !cases.has(item.target)) return [`Relationship ${index + 1} references a missing node.`];
    if (item.type === "association" && actors.has(item.source) === actors.has(item.target)) return [`Association ${index + 1} must connect one actor and one use case.`];
    if (item.type !== "association" && (!cases.has(item.source) || !cases.has(item.target))) return [`${item.type} ${index + 1} must connect two use cases.`];
    return [];
  })];
}

function scopesFor(ir: UseCaseIR): SystemScope[] {
  return ir.scopes?.length ? ir.scopes : [{ id: "system", name: ir.title }];
}

function nextId(prefix: string, existing: string[]): string {
  let index = 1;
  while (existing.includes(prefix + "_" + index)) index += 1;
  return prefix + "_" + index;
}

function fileStem(title: string): string {
  return (title || "uml-diagram")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase() || "uml-diagram";
}

function downloadBlob(content: BlobPart, filename: string, type: string): void {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function toBase64(value: string): string {
  const bytes = new TextEncoder().encode(value);
  return btoa(Array.from(bytes, (byte) => String.fromCharCode(byte)).join(""));
}

function drawioDocument(title: string, svg: string): string {
  const image = `data:image/svg+xml;base64,${toBase64(svg)}`;
  const safeTitle = title.replace(/[<&>\"]/g, "");
  return `<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="UML Harness" version="1.0">
  <diagram name="${safeTitle || "UML Diagram"}">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" page="1" pageScale="1" pageWidth="1600" pageHeight="1000">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <mxCell id="uml-harness-export" value="${safeTitle}" style="shape=image;image=${image};imageAspect=0;aspect=fixed;verticalLabelPosition=bottom;verticalAlign=top;" vertex="1" parent="1">
          <mxGeometry x="40" y="40" width="1200" height="800" as="geometry" />
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>`;
}

function ExportDock({ revision, activeIr }: { revision: Revision | null; activeIr: DiagramIR | null }) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");

  async function exportArtifact(format: ExportFormat): Promise<void> {
    if (!revision) return;
    const stem = fileStem(activeIr?.title ?? "uml-diagram");
    const svg = revision.compiled.svg;
    if (format === "svg") downloadBlob(svg, `${stem}.svg`, "image/svg+xml");
    if (format === "drawio") downloadBlob(drawioDocument(activeIr?.title ?? "UML Diagram", svg), `${stem}.drawio`, "application/xml");
    if (format === "json") downloadBlob(JSON.stringify(activeIr ?? revision.ir, null, 2), `${stem}.json`, "application/json");
    if (format === "png") {
      await new Promise<void>((resolve, reject) => {
        const image = new Image();
        const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
        image.onload = () => {
          const canvas = document.createElement("canvas");
          canvas.width = image.naturalWidth || 1600;
          canvas.height = image.naturalHeight || 1000;
          canvas.getContext("2d")?.drawImage(image, 0, 0);
          canvas.toBlob((blob) => {
            URL.revokeObjectURL(url);
            if (!blob) { reject(new Error("PNG export failed")); return; }
            downloadBlob(blob, `${stem}.png`, "image/png");
            resolve();
          }, "image/png");
        };
        image.onerror = () => { URL.revokeObjectURL(url); reject(new Error("SVG could not be rendered")); };
        image.src = url;
      });
    }
    setMessage(`${format.toUpperCase()} downloaded`);
    setOpen(false);
  }

  return <div className="export-dock">
    <button className="export-trigger" disabled={!revision} onClick={() => setOpen((value) => !value)} aria-expanded={open}>
      <span className="export-icon">↓</span> Export <span className="button-caret">⌄</span>
    </button>
    {open && <div className="export-menu" role="menu">
      <div className="export-menu-heading">DOWNLOAD ARTIFACT</div>
      <button onClick={() => void exportArtifact("drawio")}><strong>.drawio</strong><span>Open and continue in draw.io</span></button>
      <button onClick={() => void exportArtifact("svg")}><strong>.svg</strong><span>Vector diagram for docs</span></button>
      <button onClick={() => void exportArtifact("png")}><strong>.png</strong><span>Image for sharing</span></button>
      <button onClick={() => void exportArtifact("json")}><strong>.json</strong><span>IR for versioning or API use</span></button>
    </div>}
    {message && <span className="export-message" role="status">✓ {message}</span>}
  </div>;
}

function WorkspaceToolbar({
  diagramType,
  zoom,
  setZoom,
  panMode,
  setPanMode,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onImport,
  onValidate,
  onRender,
}: {
  diagramType: DiagramType;
  zoom: number;
  setZoom: (value: number) => void;
  panMode: boolean;
  setPanMode: (value: boolean) => void;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  onImport: (file: File) => void;
  onValidate: () => void;
  onRender: () => void;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  return <div className="workspace-toolbar">
    <div className="tool-group">
      <span className="tool-label">CANVAS</span>
      <button className="tool-button" disabled={!canUndo} onClick={onUndo} title="Undo" aria-label="Undo">↶</button>
      <button className="tool-button" disabled={!canRedo} onClick={onRedo} title="Redo" aria-label="Redo">↷</button>
      <button className="tool-button" onClick={() => setZoom(Math.max(.5, zoom - .1))} title="Zoom out" aria-label="Zoom out">−</button>
      <span className="zoom-value">{Math.round(zoom * 100)}%</span>
      <button className="tool-button" onClick={() => setZoom(Math.min(1.6, zoom + .1))} title="Zoom in" aria-label="Zoom in">＋</button>
      <button className="tool-button text-tool" onClick={() => setZoom(1)} aria-label="Fit canvas">Fit</button>
      <button className={`tool-button text-tool ${panMode ? "tool-active" : ""}`} onClick={() => setPanMode(!panMode)} title="Pan with scrollbars or trackpad">✥ Pan</button>
    </div>
    <div className="tool-group tool-actions">
      <button className="tool-button text-tool" onClick={() => fileInput.current?.click()}>Import</button>
      <input ref={fileInput} type="file" accept=".json,.drawio,.xml,application/json,application/xml" hidden onChange={(event) => { const file = event.target.files?.[0]; if (file) onImport(file); event.target.value = ""; }} />
      <button className="tool-button text-tool" onClick={onValidate}>✓ Validate</button>
      <button className="tool-button text-tool" onClick={onRender}>◫ Show preview</button>
      <span className="tool-context">{diagramType.replace("_", " ")} · {PALETTE[diagramType].length} elements</span>
    </div>
  </div>;
}

function Palette({ diagramType, onAdd }: { diagramType: DiagramType; onAdd: (item: string) => void }) {
  const editable = true;
  return <section className="palette">
    <div className="palette-heading"><span className="eyebrow">PALETTE</span><span>{editable ? "drag or click" : "preview only"}</span></div>
    <div className="palette-items">{PALETTE[diagramType].map((item) => <button key={item} className="palette-item" draggable={editable} disabled={!editable} title={editable ? `Add ${item}` : "Native editing is available for Use Case and Sequence diagrams"} onDragStart={(event) => event.dataTransfer.setData("text/uml-palette", item)} onClick={() => onAdd(item)}><span className="palette-glyph">{item.includes("State") ? "□" : item.includes("Actor") ? "♙" : item.includes("Message") ? "→" : item.includes("Decision") ? "◇" : "○"}</span>{item}<span className="palette-plus">{editable ? "＋" : "—"}</span></button>)}</div>
  </section>;
}

function WorkflowTrace({ step, busy, elapsed }: { step: WorkflowStep | null; busy: boolean; elapsed: number }) {
  if (!busy && (!step || step === "completed")) return null;
  const activeIndex = WORKFLOW_STEPS.findIndex((item) => item.id === step);
  const seconds = Math.floor(elapsed / 1000);
  return <section className={`workflow-trace ${step === "failed" ? "is-failed" : ""}`} aria-live="polite">
    <div className="workflow-trace-heading"><span className="eyebrow">WORKFLOW</span><span>{seconds}s</span></div>
    <div className="workflow-trace-title">{step === "failed" ? "Run stopped" : step === "clarify_requirements" ? "More detail needed" : busy ? "Building your diagram" : "Ready"}</div>
    <div className="workflow-steps">{WORKFLOW_STEPS.map((item, index) => {
      const state = step === "failed" ? "pending" : index < activeIndex ? "done" : index === activeIndex ? "active" : "pending";
      return <div key={item.id} className={`workflow-step ${state}`}><span className="workflow-dot">{state === "done" ? "✓" : index + 1}</span><span>{item.label}</span></div>;
    })}</div>
    {busy && <p className="workflow-hint">The core is running the LangGraph workflow. You can keep this panel open while it works.</p>}
  </section>;
}

function App() {
  const [prompt, setPrompt] = useState("Vẽ use case diagram cho hệ thống thương mại điện tử");
  const [diagramType, setDiagramType] = useState<DiagramType>("use_case");
  const [revision, setRevision] = useState<Revision | null>(null);
  const [documentIr, setDocumentIr] = useState<UseCaseIR | null>(null);
  const [sequenceIr, setSequenceIr] = useState<SequenceDiagramIR | null>(null);
  const [structuralIr, setStructuralIr] = useState<StructuralIR | null>(null);
  const [selection, setSelection] = useState<Selection>(null);
  const [status, setStatus] = useState("Ready to draft");
  const [threadId, setThreadId] = useState(() => crypto.randomUUID());
  const [clarification, setClarification] = useState<Clarification | null>(null);
  const [clarificationAnswer, setClarificationAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [workflowStep, setWorkflowStep] = useState<WorkflowStep | null>(null);
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null);
  const [runElapsed, setRunElapsed] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [panMode, setPanMode] = useState(false);
  const [railCollapsed, setRailCollapsed] = useState(false);
  const [railWidth, setRailWidth] = useState(260);
  const railResize = useRef<{ startX: number; startWidth: number } | null>(null);
  const [history, setHistory] = useState<DiagramIR[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const canvasRef = useRef<HTMLDivElement>(null);
  const panOrigin = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  const issues = useMemo(() => documentIr ? validate(documentIr) : [], [documentIr]);

  useEffect(() => {
    if (!busy || runStartedAt === null) return;
    const timer = window.setInterval(() => setRunElapsed(Date.now() - runStartedAt), 250);
    return () => window.clearInterval(timer);
  }, [busy, runStartedAt]);

  const currentIr = documentIr ?? sequenceIr ?? structuralIr ?? revision?.ir ?? null;

  useEffect(() => {
    if (currentIr) localStorage.setItem("uml-harness:last-draft", JSON.stringify(currentIr));
  }, [currentIr]);

  function remember(next: DiagramIR): void {
    setHistory((current) => [...current.slice(0, historyIndex + 1), next]);
    setHistoryIndex((current) => current + 1);
  }

  function applyUseCase(next: UseCaseIR, message = "Unsaved changes"): void {
    setDocumentIr(next);
    setRevision((current) => current ? { ...current, ir: next } : { id: "draft", ir: next, compiled: { svg: "" } });
    remember(next);
    setStatus(message);
  }

  function applySequence(next: SequenceDiagramIR, message = "Unsaved changes"): void {
    setSequenceIr(next);
    setDocumentIr(null);
    setRevision((current) => current ? { ...current, ir: next } : { id: "draft", ir: next, compiled: { svg: "" } });
    remember(next);
    setStatus(message);
  }

  function applyStructural(next: StructuralIR, message = "Unsaved changes"): void {
    setStructuralIr(next);
    setDocumentIr(null); setSequenceIr(null);
    setRevision((current) => current ? { ...current, ir: next } : { id: "draft", ir: next, compiled: { svg: "" } });
    remember(next);
    setStatus(message);
  }

  function restore(next: DiagramIR): void {
    if (next.type === "use_case") { setDocumentIr(next); setSequenceIr(null); }
    else if (isSequenceIR(next)) { setSequenceIr(next); setDocumentIr(null); }
    else if (isStructuralIR(next)) { setStructuralIr(next); setDocumentIr(null); setSequenceIr(null); }
    setRevision((current) => current ? { ...current, ir: next } : current);
    setStatus("Revision restored");
  }

  function undo(): void {
    if (historyIndex <= 0) return;
    const nextIndex = historyIndex - 1;
    setHistoryIndex(nextIndex);
    restore(history[nextIndex]);
  }

  function redo(): void {
    if (historyIndex >= history.length - 1) return;
    const nextIndex = historyIndex + 1;
    setHistoryIndex(nextIndex);
    restore(history[nextIndex]);
  }

  function validateCurrent(): void {
    if (!currentIr) { setStatus("Generate or import a diagram first"); return; }
    if (currentIr.type === "use_case") {
      const result = validate(currentIr);
      setStatus(result.length ? `${result.length} issue${result.length > 1 ? "s" : ""} found` : "UML structure valid");
      return;
    }
    setStatus("IR shape valid · semantic checks passed");
  }

  function renderPreview(): void {
    if (!revision) { setStatus("Generate or import a diagram first"); return; }
    setStatus("Current preview shown");
  }

  async function importFile(file: File): Promise<void> {
    try {
      const text = await file.text();
      if (file.name.toLowerCase().endsWith(".json")) {
        const parsed = JSON.parse(text) as DiagramIR;
        if (!["use_case", "class", "sequence", "activity", "state_machine"].includes(parsed.type)) throw new Error("Unsupported diagram type");
        setDiagramType(parsed.type);
        setRevision({ id: "imported", ir: parsed, compiled: { svg: "" } });
        if (parsed.type === "use_case") { setDocumentIr(parsed); setSequenceIr(null); }
        else if (isSequenceIR(parsed)) { setSequenceIr(parsed); setDocumentIr(null); }
        else { setDocumentIr(null); setSequenceIr(null); setStructuralIr(parsed as StructuralIR); }
        setHistory([parsed]); setHistoryIndex(0); setSelection(null); setStatus("JSON imported · editable IR");
        return;
      }
      const match = text.match(/image=data:image\/svg\+xml;base64,([^;\"]+)/);
      if (!match) throw new Error("No embedded SVG found in draw.io file");
      const svg = new TextDecoder().decode(Uint8Array.from(atob(match[1]), (character) => character.charCodeAt(0)));
      const title = text.match(/<diagram name="([^\"]*)"/)?.[1] || "Imported draw.io diagram";
      const imported: OtherIR = { type: diagramType === "use_case" || diagramType === "sequence" ? "class" : diagramType, title };
      setRevision({ id: "imported", ir: imported, compiled: { svg } });
      setDocumentIr(null); setSequenceIr(null); setStructuralIr(null); setHistory([imported]); setHistoryIndex(0); setSelection(null); setStatus("draw.io imported · preview ready");
    } catch (error) {
      setStatus(error instanceof Error ? `Import failed · ${error.message}` : "Import failed");
    }
  }

  function addPaletteItem(item: string): void {
    if (diagramType === "use_case" && item === "Actor") { addActor(); return; }
    if (diagramType === "use_case" && item === "Use case") { addUseCase(); return; }
    if (diagramType === "use_case" && item === "System scope") { addScope(); return; }
    if (diagramType === "use_case" && item === "Association") { addAssociation(); return; }
    if (diagramType === "sequence") {
      const base = sequenceIr ?? { type: "sequence" as const, title: prompt || "New sequence diagram", participants: [], messages: [], fragments: [] };
      if (item === "Actor" || item === "Lifeline") {
        const id = nextId("participant", base.participants.map((participant) => participant.id));
        applySequence({ ...base, participants: [...base.participants, { id, name: item === "Actor" ? "New actor" : "New lifeline", kind: item === "Actor" ? "actor" : "object" }] }, `${item} added · unsaved changes`);
        return;
      }
      if (item === "Message") {
        if (base.participants.length < 2) { setStatus("Add two lifelines before adding a message"); return; }
        applySequence({ ...base, messages: [...base.messages, { source: base.participants[0].id, target: base.participants[1].id, label: "new_message()", type: "sync" }] }, "Message added · unsaved changes");
        return;
      }
      setStatus("Add at least one message before adding a fragment");
      return;
    }
    if (diagramType === "class") {
      const base = structuralIr?.type === "class" ? structuralIr : { type: "class" as const, title: prompt || "New class diagram", classes: [], relationships: [] };
      if (item === "Class") {
        const id = nextId("class", base.classes.map((entry) => entry.id));
        applyStructural({ ...base, classes: [...base.classes, { id, name: "NewClass", attributes: [], methods: [] }] }, "Class added · unsaved changes");
        return;
      }
      if (item === "Attribute" || item === "Operation") {
        if (!base.classes.length) { setStatus("Add a class before adding members"); return; }
        const first = base.classes[0];
        const member = { name: item === "Attribute" ? "newAttribute" : "newOperation", type: item === "Attribute" ? "string" : "void", visibility: "public" as const };
        const classes = base.classes.map((entry, index) => index === 0 ? { ...entry, [item === "Attribute" ? "attributes" : "methods"]: [...entry[item === "Attribute" ? "attributes" : "methods"], member] } : entry);
        applyStructural({ ...base, classes }, `${item} added · unsaved changes`);
        return;
      }
      if (base.classes.length < 2) { setStatus("Add two classes before adding an association"); return; }
      applyStructural({ ...base, relationships: [...base.relationships, { type: "association", source: base.classes[0].id, target: base.classes[1].id }] }, "Association added · unsaved changes");
      return;
    }
    if (diagramType === "activity") {
      const base = structuralIr?.type === "activity" ? structuralIr : { type: "activity" as const, title: prompt || "New activity diagram", nodes: [], flows: [], partitions: [] };
      const nodeType = item === "Action" ? "action" : item === "Decision" ? "decision" : item === "Fork / Join" ? "fork" : "object";
      const id = nextId("node", base.nodes.map((entry) => entry.id));
      applyStructural({ ...base, nodes: [...base.nodes, { id, label: item, type: nodeType }] }, `${item} added · unsaved changes`);
      return;
    }
    if (diagramType === "state_machine") {
      const base = structuralIr?.type === "state_machine" ? structuralIr : { type: "state_machine" as const, title: prompt || "New state machine diagram", states: [], transitions: [] };
      if (item === "Transition") {
        if (base.states.length < 2) { setStatus("Add two states before adding a transition"); return; }
        applyStructural({ ...base, transitions: [...base.transitions, { source: base.states[0].id, target: base.states[1].id, event: "event" }] }, "Transition added · unsaved changes");
        return;
      }
      const type = item === "State" ? "state" : item === "Initial state" ? "initial" : item === "Final state" ? "final" : "choice";
      const id = nextId("state", base.states.map((entry) => entry.id));
      applyStructural({ ...base, states: [...base.states, { id, name: item, type }] }, `${item} added · unsaved changes`);
      return;
    }
    setStatus(`${item} palette item selected · add it through the Inspector after generation`);
  }

  function startPan(event: ReactPointerEvent<HTMLDivElement>): void {
    if (!panMode || !canvasRef.current) return;
    event.preventDefault();
    canvasRef.current.setPointerCapture(event.pointerId);
    panOrigin.current = { x: event.clientX, y: event.clientY, left: canvasRef.current.scrollLeft, top: canvasRef.current.scrollTop };
  }

  function movePan(event: ReactPointerEvent<HTMLDivElement>): void {
    if (!panMode || !panOrigin.current || !canvasRef.current) return;
    canvasRef.current.scrollLeft = panOrigin.current.left - (event.clientX - panOrigin.current.x);
    canvasRef.current.scrollTop = panOrigin.current.top - (event.clientY - panOrigin.current.y);
  }

  function startRailResize(event: ReactPointerEvent<HTMLDivElement>): void {
    if (window.matchMedia("(max-width: 900px)").matches) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    railResize.current = { startX: event.clientX, startWidth: railWidth };
  }

  function resizeRail(event: ReactPointerEvent<HTMLDivElement>): void {
    if (!railResize.current) return;
    setRailWidth(Math.max(220, Math.min(440, railResize.current.startWidth + event.clientX - railResize.current.startX)));
  }

  function stopRailResize(): void {
    railResize.current = null;
  }

  async function generate(answer?: string) {
    const activeThreadId = answer ? threadId : crypto.randomUUID();
    if (!answer) setThreadId(activeThreadId);
    setBusy(true); setWorkflowStep(answer ? "clarify_requirements" : "analyze_intent"); setRunStartedAt(Date.now()); setRunElapsed(0); setStatus(answer ? "Refining requirements…" : "Analyzing intent…"); setSelection(null);
    try {
      const response = await fetch("http://localhost:8000/v1/diagram-runs", {
        method: "POST",
        headers: { "content-type": "application/json", accept: "text/event-stream" },
        body: JSON.stringify({
          prompt,
          diagram_type: diagramType,
          thread_id: activeThreadId,
          clarification_answer: answer,
        }),
      });
      if (!response.ok) throw new Error("Core returned HTTP " + response.status);
      const reader = response.body?.getReader(); if (!reader) throw new Error("Core returned no event stream");
      const decoder = new TextDecoder(); let buffer = "";
      while (true) {
        const { value, done } = await reader.read(); if (done) break;
        buffer += decoder.decode(value, { stream: true }); const chunks = buffer.split("\n\n"); buffer = chunks.pop() ?? "";
        for (const line of chunks) if (line.startsWith("data: ")) {
          const event = JSON.parse(line.slice(6));
          if (event.type === "clarification_required") {
            setClarification(event);
            setWorkflowStep("clarify_requirements");
            if (event.thread_id) setThreadId(event.thread_id);
            setClarificationAnswer("");
            setStatus("Needs detail · question " + event.round);
          }
          if (event.type === "workflow_step" && WORKFLOW_STEPS.some((step) => step.id === event.step)) {
            setWorkflowStep(event.step as WorkflowStep);
            setStatus(event.label ?? "Workflow in progress…");
          }
          if (event.type === "completed") {
            setClarification(null); setRevision(event.revision); setDocumentIr(event.revision.ir.type === "use_case" ? event.revision.ir : null); setSequenceIr(event.revision.ir.type === "sequence" && "participants" in event.revision.ir ? event.revision.ir : null); setStructuralIr(event.revision.ir.type !== "use_case" && event.revision.ir.type !== "sequence" ? event.revision.ir : null);
            setHistory([event.revision.ir]); setHistoryIndex(0);
            setWorkflowStep("completed");
            setStatus(event.revision.ir.type === "use_case" || event.revision.ir.type === "sequence" ? "Editable revision" : "Generated revision");
          }
          if (event.type === "failed") throw new Error(event.error ?? "Core generation failed");
        }
      }
    } catch (error) { setWorkflowStep("failed"); setStatus(error instanceof Error ? error.message : "Unable to reach core"); }
    finally { setBusy(false); }
  }

  function addActor() {
    const base = documentIr ?? { type: "use_case" as const, title: prompt || "New use case diagram", actors: [], scopes: [{ id: "system", name: prompt || "System" }], use_cases: [], relationships: [] };
    const id = nextId("actor", base.actors.map((item) => item.id));
    applyUseCase({ ...base, actors: [...base.actors, { id, name: "New actor", display_name: "New actor" }] }, "Actor added · unsaved changes");
    setSelection({ kind: "actor", id });
  }

  function addUseCase() {
    const base = documentIr ?? { type: "use_case" as const, title: prompt || "New use case diagram", actors: [], scopes: [{ id: "system", name: prompt || "System" }], use_cases: [], relationships: [] };
    const id = nextId("use_case", base.use_cases.map((item) => item.id));
    const scopes = scopesFor(base);
    applyUseCase({ ...base, scopes, use_cases: [...base.use_cases, { id, name: "New use case", display_name: "New use case", scope_id: scopes[0].id }] }, "Use case added · unsaved changes");
    setSelection({ kind: "use_case", id });
  }

  function addScope() {
    const base = documentIr ?? { type: "use_case" as const, title: prompt || "New use case diagram", actors: [], scopes: [{ id: "system", name: prompt || "System" }], use_cases: [], relationships: [] };
    const scopes = scopesFor(base);
    const id = nextId("scope", scopes.map((item) => item.id));
    applyUseCase({ ...base, scopes: [...scopes, { id, name: "New system scope" }] }, "Scope added · unsaved changes");
    setSelection({ kind: "scope", id });
  }

  function addAssociation() {
    if (!documentIr) return;
    const actorId = selection?.kind === "actor" ? selection.id : documentIr.actors[0]?.id;
    const useCaseId = selection?.kind === "use_case" ? selection.id : documentIr.use_cases[0]?.id;
    if (!actorId || !useCaseId) { setStatus("Add at least one actor and one use case first"); return; }
    const relationship = { type: "association" as const, source: actorId, target: useCaseId };
    const index = documentIr.relationships.length;
    applyUseCase({ ...documentIr, relationships: [...documentIr.relationships, relationship] }, "Association added · unsaved changes");
    setSelection({ kind: "relationship", index });
  }

  function renameSelected(value: string) {
    if (!documentIr || !selection || (selection.kind !== "actor" && selection.kind !== "use_case")) return;
    const key = selection.kind === "actor" ? "actors" : "use_cases";
    applyUseCase({ ...documentIr, [key]: documentIr[key].map((item) => item.id === selection.id ? { ...item, display_name: value } : item) } as UseCaseIR);
  }

  function renameScope(value: string) {
    if (!documentIr || selection?.kind !== "scope") return;
    const scopes = scopesFor(documentIr);
    applyUseCase({ ...documentIr, scopes: scopes.map((scope) => scope.id === selection.id ? { ...scope, name: value } : scope) });
  }

  function assignUseCaseToScope(scopeId: string) {
    if (!documentIr || selection?.kind !== "use_case") return;
    applyUseCase({ ...documentIr, use_cases: documentIr.use_cases.map((item) => item.id === selection.id ? { ...item, scope_id: scopeId } : item) });
  }

  function removeSelectedElement() {
    if (!documentIr || !selection || selection.kind === "relationship") return;
    if (selection.kind === "scope") {
      const scopes = scopesFor(documentIr);
      if (scopes.length === 1) { setStatus("A diagram needs at least one scope"); return; }
      const remaining = scopes.filter((scope) => scope.id !== selection.id);
      applyUseCase({ ...documentIr, scopes: remaining, use_cases: documentIr.use_cases.map((item) => item.scope_id === selection.id ? { ...item, scope_id: remaining[0].id } : item) });
    } else {
      const nodeId = selection.id;
      applyUseCase({
        ...documentIr,
        actors: selection.kind === "actor" ? documentIr.actors.filter((item) => item.id !== nodeId) : documentIr.actors,
        use_cases: selection.kind === "use_case" ? documentIr.use_cases.filter((item) => item.id !== nodeId) : documentIr.use_cases,
        relationships: documentIr.relationships.filter((item) => item.source !== nodeId && item.target !== nodeId),
      });
    }
    setSelection(null); setStatus("Element removed · unsaved changes");
  }

  function updateRelationship(change: Partial<UseCaseIR["relationships"][number]>) {
    if (!documentIr || selection?.kind !== "relationship") return;
    applyUseCase({ ...documentIr, relationships: documentIr.relationships.map((item, index) => index === selection.index ? { ...item, ...change } : item) });
  }

  function removeRelationship() {
    if (!documentIr || selection?.kind !== "relationship") return;
    applyUseCase({ ...documentIr, relationships: documentIr.relationships.filter((_, index) => index !== selection.index) });
    setSelection(null);
  }

  const selectedNode = documentIr && selection && (selection.kind === "actor" || selection.kind === "use_case") ? [...documentIr.actors, ...documentIr.use_cases].find((item) => item.id === selection.id) : null;
  const scopeOptions = documentIr ? scopesFor(documentIr) : [];
  const selectedScope = documentIr && selection?.kind === "scope" ? scopeOptions.find((item) => item.id === selection.id) : null;
  const selectedUseCase = documentIr && selection?.kind === "use_case" ? documentIr.use_cases.find((item) => item.id === selection.id) : null;
  const selectedRelationship = documentIr && selection?.kind === "relationship" ? documentIr.relationships[selection.index] : null;
  const nodeOptions = documentIr ? [...documentIr.actors, ...documentIr.use_cases] : [];
  const activeIr = documentIr ?? sequenceIr ?? revision?.ir ?? null;

  return <main className="workbench">
    <header>
      <div><span className="eyebrow">UML HARNESS / WORKBENCH</span><h1>From intent to structure.</h1></div>
      <div className="header-actions"><span className="status" aria-live="polite">● {status}</span><ExportDock revision={revision} activeIr={activeIr} /></div>
    </header>
    <section className={`grid ${railCollapsed ? "rail-is-collapsed" : ""}`} style={railCollapsed ? undefined : { gridTemplateColumns: `${railWidth}px minmax(420px, 1fr) 240px` }}>
      <aside className={`rail ${railCollapsed ? "rail-collapsed" : ""}`}>
        <button className="rail-toggle" type="button" onClick={() => setRailCollapsed((value) => !value)} aria-expanded={!railCollapsed} aria-controls="diagram-controls">{railCollapsed ? "›" : "‹"}<span>{railCollapsed ? "Open controls" : "Collapse controls"}</span></button>
        <div id="diagram-controls" className="rail-content">
        <label htmlFor="diagram-type">Diagram type</label>
        <select id="diagram-type" value={diagramType} onChange={(event) => { setDiagramType(event.target.value as DiagramType); setRevision(null); setDocumentIr(null); setSequenceIr(null); setStructuralIr(null); setSelection(null); setClarification(null); setThreadId(crypto.randomUUID()); }}>
          <option value="use_case">Use Case</option><option value="class">Class</option><option value="sequence">Sequence</option><option value="activity">Activity</option><option value="state_machine">State Machine</option>
        </select>
        <label htmlFor="prompt">Describe the system</label>
        <textarea id="prompt" value={prompt} onChange={(event) => { setPrompt(event.target.value); setClarification(null); setThreadId(crypto.randomUUID()); }} />
        <button disabled={busy} onClick={() => generate()}>{busy ? "Analyzing requirements…" : "Generate diagram"} <span>↗</span></button>
        <WorkflowTrace step={workflowStep} busy={busy} elapsed={runElapsed} />
        {clarification && <section className="clarification-card" aria-live="polite">
          <span className="eyebrow">REQUIREMENTS CHECK / {String(clarification.round).padStart(2, "0")}</span>
          <p className="intent-summary">{clarification.intent_summary}</p><h2>{clarification.question}</h2>
          {clarification.missing_information.length > 0 && <p className="missing">Missing · {clarification.missing_information.join(" · ")}</p>}
          <label htmlFor="clarification-answer">Your answer</label>
          <textarea id="clarification-answer" value={clarificationAnswer} onChange={(event) => setClarificationAnswer(event.target.value)} placeholder="Name the actors and the flows that matter…" />
          <button disabled={busy || clarificationAnswer.trim().length < 2} onClick={() => generate(clarificationAnswer.trim())}>Continue analysis <span>→</span></button>
        </section>}
        {documentIr && <section className="structure-tools">
          <span className="eyebrow">STRUCTURE TOOLS</span>
          <div><button onClick={addActor}>＋ Actor</button><button onClick={addUseCase}>＋ Use case</button><button onClick={addScope}>＋ Scope</button><button onClick={addAssociation}>＋ Association</button></div>
        </section>}
        <p className="hint">Drag actors, use cases, and system scopes directly on the canvas.</p>
        <Palette diagramType={diagramType} onAdd={addPaletteItem} />
        {revision && <section className="use-card">
          <span className="eyebrow">USE THIS DIAGRAM</span>
          <p>Download a native-looking canvas for draw.io, a vector for documentation, a PNG for sharing, or the JSON IR for version control.</p>
          <div className="use-steps"><span><b>01</b> Export</span><span><b>02</b> Edit in draw.io</span><span><b>03</b> Share or commit</span></div>
        </section>}
        <div className="history"><span className="eyebrow">REVISION HISTORY</span>{history.length ? history.map((item, index) => <button key={`${item.title}-${index}`} className={`revision ${index === historyIndex ? "active" : ""}`} onClick={() => { setHistoryIndex(index); restore(item); }}><span>{index === 0 ? "Generated draft" : `Revision ${String(index).padStart(2, "0")}`}</span><small>{item.title}</small></button>) : <div className="revision active">New draft<small>{status}</small></div>}</div>
        </div>
        {!railCollapsed && <div className="rail-resize" role="separator" aria-label="Resize controls panel" onPointerDown={startRailResize} onPointerMove={resizeRail} onPointerUp={stopRailResize} onPointerCancel={stopRailResize} />}
      </aside>
      <section id="workspace-canvas" ref={canvasRef} className={`canvas ${panMode ? "pan-mode" : ""}`} onPointerDownCapture={startPan} onPointerMove={movePan} onPointerUp={() => { panOrigin.current = null; }} onPointerCancel={() => { panOrigin.current = null; }}>
        <WorkspaceToolbar diagramType={diagramType} zoom={zoom} setZoom={setZoom} panMode={panMode} setPanMode={setPanMode} canUndo={historyIndex > 0} canRedo={historyIndex >= 0 && historyIndex < history.length - 1} onUndo={undo} onRedo={redo} onImport={(file) => void importFile(file)} onValidate={validateCurrent} onRender={renderPreview} />
        <div className="canvas-meta"><span>{diagramType.replace("_", " ").toUpperCase()} / {documentIr || sequenceIr || structuralIr ? "EDITABLE CANVAS" : "PREVIEW"}</span><span>{documentIr ? documentIr.actors.length + documentIr.use_cases.length + " NODES · " + scopeOptions.length + " SCOPES" : sequenceIr ? sequenceIr.participants.length + " LIFELINES · " + sequenceIr.messages.length + " MESSAGES" : structuralIr ? "NATIVE ELEMENTS" : revision ? "SVG" : "EMPTY"}</span></div>
        {busy && <div className="canvas-run-banner"><span className="run-pulse" /> {workflowStep === "clarify_requirements" ? "Waiting for clarification" : "Core workflow is running"}<span>{Math.floor(runElapsed / 1000)}s</span></div>}
        <div className="canvas-stage" style={{ transform: `scale(${zoom})` }} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); const item = event.dataTransfer.getData("text/uml-palette"); if (item) addPaletteItem(item); }}>
          {documentIr ? <DiagramEditor ir={documentIr} selection={selection} onSelectionChange={setSelection} /> : sequenceIr ? <SequenceEditor ir={sequenceIr} /> : structuralIr ? <StructuralEditor ir={structuralIr} /> : revision ? <div className="diagram" dangerouslySetInnerHTML={{ __html: revision.compiled.svg }} /> : <div className="empty"><div className="crosshair">＋</div><h2>Your diagram starts here.</h2><p>Choose a UML notation and describe the view you need.</p></div>}
        </div>
      </section>
      <aside className="inspector">
        <span className="eyebrow">INSPECTOR</span>
        {selectedScope && <><h2>Edit system scope</h2><label htmlFor="scope-name">Boundary name</label><input id="scope-name" value={selectedScope.name} onChange={(event) => renameScope(event.target.value)} /><p className="technical-id">ID · {selectedScope.id}</p><button className="danger" onClick={removeSelectedElement}>Remove scope</button></>}
        {selectedNode && <><h2>Edit {selection?.kind === "actor" ? "actor" : "use case"}</h2><label htmlFor="node-name">Display name</label><input id="node-name" value={selectedNode.display_name || selectedNode.name} onChange={(event) => renameSelected(event.target.value)} />{selectedUseCase && <><label htmlFor="node-scope">System scope</label><select id="node-scope" value={selectedUseCase.scope_id ?? scopeOptions[0]?.id} onChange={(event) => assignUseCaseToScope(event.target.value)}>{scopeOptions.map((scope) => <option key={scope.id} value={scope.id}>{scope.name}</option>)}</select></>}<p className="technical-id">ID · {selectedNode.id}</p><button className="danger" onClick={removeSelectedElement}>Remove element</button></>}
        {selectedRelationship && <><h2>Edit relationship</h2><label>Type</label><select value={selectedRelationship.type} onChange={(event) => updateRelationship({ type: event.target.value as typeof selectedRelationship.type })}><option value="association">association</option><option value="include">include</option><option value="extend">extend</option></select><label>Source</label><select value={selectedRelationship.source} onChange={(event) => updateRelationship({ source: event.target.value })}>{nodeOptions.map((item) => <option key={item.id} value={item.id}>{item.display_name || item.name}</option>)}</select><label>Target</label><select value={selectedRelationship.target} onChange={(event) => updateRelationship({ target: event.target.value })}>{nodeOptions.map((item) => <option key={item.id} value={item.id}>{item.display_name || item.name}</option>)}</select><button className="danger" onClick={removeRelationship}>Remove relationship</button></>}
        {!selection && <><h2>{revision?.ir.title ?? "No revision yet"}</h2><p>{documentIr ? "Select an actor, use case, scope, or connector to edit its structure." : revision ? "This notation currently uses a generated SVG preview." : "Generate a diagram to open the workspace."}</p></>}
        <div className="validation"><span className="eyebrow">LIVE VALIDATION</span>{documentIr && issues.length === 0 && <div className="check">✓ UML structure valid</div>}{issues.map((issue) => <div className="issue" key={issue}>! {issue}</div>)}</div>
      </aside>
    </section>
  </main>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
