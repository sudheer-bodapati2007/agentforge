import '@xyflow/react/dist/style.css'
import { Background, Handle, MarkerType, Position, ReactFlow, useNodesState, type Edge, type Node, type NodeProps } from '@xyflow/react'
import clsx from 'clsx'
import { memo, useEffect, useMemo } from 'react'
import { WORKFLOW_EDGES, WORKFLOW_NODES, type NodeState, type WorkflowNodeId } from '@/domain/run'
import { STATE_CLASSES, STATE_LABEL } from './workflow-states'

// Layout: the main path left to right, the debug loop above the test run, the endings below
// (documentation directly under the review, so the paths into it do not share a line).
const COL = 205
const POSITIONS: Record<WorkflowNodeId, { x: number; y: number }> = {
  plan: { x: 0, y: 120 },
  architect: { x: COL, y: 120 },
  plan_approval: { x: 2 * COL, y: 120 },
  schema: { x: 2.5 * COL, y: 0 }, // database projects only
  code: { x: 3 * COL, y: 120 },
  write_tests: { x: 4 * COL, y: 120 },
  run_tests: { x: 5 * COL, y: 120 },
  debug: { x: 5.5 * COL, y: 0 },
  review: { x: 6 * COL, y: 120 },
  correction_approval: { x: 7 * COL, y: 120 },
  correct: { x: 8 * COL, y: 120 },
  document: { x: 6 * COL, y: 270 },
  report: { x: 7.5 * COL, y: 270 },
}

// Shorter canvas labels where the full condition does not fit between two steps.
const SHORT_LABELS: Record<string, string> = {
  'review->correction_approval': 'blocking',
  'run_tests->document': 'limit reached',
}

interface StepData extends Record<string, unknown> {
  label: string
  state: NodeState
  attempts: number
  selected: boolean
}

const HANDLES = (['top', 'bottom', 'left', 'right'] as const).flatMap((side) => [
  { id: `${side}-in`, type: 'target' as const, side },
  { id: `${side}-out`, type: 'source' as const, side },
])
const SIDE = { top: Position.Top, bottom: Position.Bottom, left: Position.Left, right: Position.Right }

const StepNode = memo(function StepNode({ data }: NodeProps<Node<StepData>>) {
  return (
    <div
      className={clsx(
        'w-[140px] cursor-pointer rounded-md border px-2.5 py-1.5',
        STATE_CLASSES[data.state],
        data.selected && 'ring-2 ring-accent ring-offset-2 ring-offset-panel',
      )}
    >
      {HANDLES.map((h) => (
        <Handle key={h.id} id={h.id} type={h.type} position={SIDE[h.side]} isConnectable={false} className="!size-1 !min-h-0 !min-w-0 !border-0 !bg-transparent" />
      ))}
      <p className="text-[12px] font-medium">{data.label}</p>
      <p className="text-[10px] text-fg-subtle">
        {STATE_LABEL[data.state]}
        {data.attempts > 1 ? ` · ${data.attempts} attempts` : ''}
      </p>
    </div>
  )
})

const NODE_TYPES = { step: StepNode }

/** Which sides an edge leaves and enters, from where its ends sit in the layout. */
function handlesFor(from: WorkflowNodeId, to: WorkflowNodeId): { sourceHandle: string; targetHandle: string } {
  if (from === 'plan_approval' && to === 'report') {
    return { sourceHandle: 'bottom-out', targetHandle: 'bottom-in' } // rare path: routed under everything
  }
  const a = POSITIONS[from]
  const b = POSITIONS[to]
  if (b.y > a.y) return { sourceHandle: 'bottom-out', targetHandle: 'top-in' }
  if (b.y < a.y) return { sourceHandle: 'top-out', targetHandle: 'left-in' }
  if (b.x > a.x) return { sourceHandle: 'right-out', targetHandle: 'left-in' }
  return { sourceHandle: 'bottom-out', targetHandle: 'bottom-in' } // a loop back along the same row
}

export default function WorkflowCanvas({
  states,
  attempts,
  selected,
  onSelect,
}: {
  states: Record<WorkflowNodeId, NodeState>
  attempts: Record<string, number>
  selected: WorkflowNodeId | null
  onSelect: (node: WorkflowNodeId) => void
}) {
  // Nodes live in React Flow's own state so the sizes it measures are kept. Rebuilding node
  // objects on every render (live data re-renders the page often) dropped those
  // measurements and left every node hidden; only each node's data is updated instead.
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<StepData>>(
    WORKFLOW_NODES.map((n) => ({
      id: n.id,
      type: 'step',
      position: POSITIONS[n.id],
      data: { label: n.label, state: states[n.id], attempts: attempts[n.id] ?? 0, selected: selected === n.id },
      draggable: false,
      connectable: false,
    })),
  )
  const dataKey = WORKFLOW_NODES.map((n) => `${states[n.id]}:${attempts[n.id] ?? 0}`).join('|') + `|${selected}`
  useEffect(() => {
    setNodes((current) =>
      current.map((node) => {
        const id = node.id as WorkflowNodeId
        const data = { ...node.data, state: states[id], attempts: attempts[id] ?? 0, selected: selected === id }
        const same = data.state === node.data.state && data.attempts === node.data.attempts && data.selected === node.data.selected
        return same ? node : { ...node, data }
      }),
    )
    // dataKey captures every value read here; states/attempts are new objects on each render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataKey, setNodes])
  const edges = useMemo<Edge[]>(
    () =>
      WORKFLOW_EDGES.map((e) => {
        // An edge is "taken" once its target has started, so the path a run followed stands out.
        const taken = states[e.from] !== 'pending' && states[e.from] !== 'skipped' && states[e.to] !== 'pending' && states[e.to] !== 'skipped'
        const color = e.loop ? 'var(--color-accent)' : taken ? 'var(--color-fg-muted)' : 'var(--color-line-strong)'
        return {
          id: `${e.from}->${e.to}`,
          source: e.from,
          target: e.to,
          ...handlesFor(e.from, e.to),
          type: 'smoothstep',
          label: SHORT_LABELS[`${e.from}->${e.to}`] ?? e.label,
          labelStyle: { fill: 'var(--color-fg-subtle)', fontSize: 10 },
          labelBgStyle: { fill: 'var(--color-panel)' },
          style: { stroke: color, strokeWidth: taken ? 1.75 : 1.25 },
          markerEnd: { type: MarkerType.ArrowClosed, color, width: 14, height: 14 },
        }
      }),
    [states],
  )

  return (
    <div className="h-[380px] w-full" data-testid="workflow-canvas">
      <ReactFlow
        nodes={nodes}
        onNodesChange={onNodesChange}
        edges={edges}
        nodeTypes={NODE_TYPES}
        onNodeClick={(_, node) => onSelect(node.id as WorkflowNodeId)}
        colorMode="dark"
        fitView
        fitViewOptions={{ padding: 0.12 }}
        nodesDraggable={false}
        nodesConnectable={false}
        // The step list is the keyboard and screen-reader view; the canvas stays out of the tab order.
        nodesFocusable={false}
        edgesFocusable={false}
        zoomOnScroll={false}
        preventScrolling={false}
        minZoom={0.4}
        maxZoom={1.5}
        style={{ background: 'transparent' }}
      >
        <Background color="var(--color-line)" gap={24} size={1} />
      </ReactFlow>
    </div>
  )
}
