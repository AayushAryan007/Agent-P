import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/base.css'
import clsx from 'clsx'
import ELK from 'elkjs/lib/elk.bundled.js'
import { Bot, Cog, Hand, type LucideIcon } from 'lucide-react'
import { memo, useEffect, useMemo, useState } from 'react'
import type { StepKind } from '@/domain/events'
import type { RunState, StepState } from '@/domain/runState'
import { statusMeta, toneBorder, toneStroke, toneText } from '@/domain/status'
import { durationBetween, formatDuration, formatTokens } from '@/lib/format'

const NODE_W = 216
const NODE_H = 76
const elk = new ELK()

const KIND_ICON: Record<StepKind, LucideIcon> = { agent: Bot, system: Cog, approval: Hand }
const KIND_LABEL: Record<StepKind, string> = { agent: 'Agent', system: 'System step', approval: 'Human approval' }

type StepNodeData = { step: StepState; selected: boolean; now: number }
type StepNode = Node<StepNodeData, 'step'>

const StepNodeView = memo(function StepNodeView({ data }: NodeProps<StepNode>) {
  const { step, selected, now } = data
  const meta = statusMeta(step.status)
  const KindIcon = KIND_ICON[step.kind]
  const StatusIcon = meta.icon
  const elapsed = durationBetween(step.startedAt, step.finishedAt, now)
  const tokens = step.inputTokens + step.outputTokens

  return (
    <div
      className={clsx(
        'rounded-panel border bg-surface-2 px-3 py-2.5 transition-[border-color,box-shadow] duration-200',
        step.status === 'pending' ? 'border-border' : toneBorder[meta.tone],
        step.status === 'running' && 'animate-pulse-ring',
        selected && 'ring-2 ring-blue/60 ring-offset-2 ring-offset-bg',
      )}
      style={{ width: NODE_W, height: NODE_H }}
    >
      <Handle type="target" position={Position.Left} className="!size-1.5 !border-0 !bg-border-strong" />
      <div className="flex items-center gap-2">
        <span
          className={clsx(
            'grid size-6 shrink-0 place-items-center rounded-md',
            step.kind === 'agent' ? 'bg-violet/15 text-violet' : step.kind === 'approval' ? 'bg-amber/15 text-amber' : 'bg-cyan/15 text-cyan',
          )}
        >
          <KindIcon className="size-3.5" aria-hidden />
        </span>
        <span className="truncate text-[13px] font-medium text-fg">{step.title}</span>
      </div>
      <div className="mt-2 flex items-center justify-between text-[11px]">
        <span className={clsx('flex items-center gap-1', toneText[meta.tone])}>
          <StatusIcon className={clsx('size-3', meta.spin && 'animate-spin')} aria-hidden />
          {meta.label}
          {step.attempt > 1 && <span className="text-fg-3">· try {step.attempt}</span>}
        </span>
        <span className="font-mono text-fg-3">
          {elapsed != null && formatDuration(elapsed)}
          {tokens > 0 && ` · ${formatTokens(tokens)} tok`}
        </span>
      </div>
      <Handle type="source" position={Position.Right} className="!size-1.5 !border-0 !bg-border-strong" />
    </div>
  )
})

const nodeTypes = { step: StepNodeView }

/** Positions depend only on the DAG shape, so layout runs once per distinct structure. */
function useElkLayout(state: RunState): Record<string, { x: number; y: number }> {
  const structureKey = state.stepOrder.map((id) => `${id}:${state.steps[id]?.depends_on.join(',')}`).join('|')
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({})

  useEffect(() => {
    if (state.stepOrder.length === 0) return
    let cancelled = false
    const idByKey = new Map(state.stepOrder.map((id) => [state.steps[id]?.key, id]))
    const graph = {
      id: 'root',
      layoutOptions: {
        'elk.algorithm': 'layered',
        'elk.direction': 'RIGHT',
        'elk.layered.spacing.nodeNodeBetweenLayers': '64',
        'elk.spacing.nodeNode': '28',
        'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
      },
      children: state.stepOrder.map((id) => ({ id, width: NODE_W, height: NODE_H })),
      edges: state.stepOrder.flatMap((id) =>
        (state.steps[id]?.depends_on ?? []).flatMap((depKey) => {
          const src = idByKey.get(depKey)
          return src ? [{ id: `${src}->${id}`, sources: [src], targets: [id] }] : []
        }),
      ),
    }
    elk.layout(graph).then((res) => {
      if (cancelled) return
      const out: Record<string, { x: number; y: number }> = {}
      for (const c of res.children ?? []) out[c.id] = { x: c.x ?? 0, y: c.y ?? 0 }
      setPositions(out)
    })
    return () => {
      cancelled = true
    }
    // structureKey captures everything layout depends on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [structureKey])

  return positions
}

export function AgentGraph({
  state,
  selectedStepId,
  onSelectStep,
  now,
}: {
  state: RunState
  selectedStepId: string | null
  onSelectStep: (id: string | null) => void
  now: number
}) {
  const positions = useElkLayout(state)
  const ready = state.stepOrder.every((id) => positions[id])

  const nodes: StepNode[] = useMemo(
    () =>
      state.stepOrder.flatMap((id) => {
        const step = state.steps[id]
        const pos = positions[id]
        if (!step || !pos) return []
        return [
          {
            id,
            type: 'step' as const,
            position: pos,
            data: { step, selected: id === selectedStepId, now },
            ariaLabel: `${KIND_LABEL[step.kind]} ${step.title}: ${statusMeta(step.status).label}`,
            draggable: false,
          },
        ]
      }),
    [state.stepOrder, state.steps, positions, selectedStepId, now],
  )

  const edges: Edge[] = useMemo(() => {
    const idByKey = new Map(state.stepOrder.map((id) => [state.steps[id]?.key, id]))
    return state.stepOrder.flatMap((id) => {
      const target = state.steps[id]
      if (!target) return []
      return target.depends_on.flatMap((depKey) => {
        const srcId = idByKey.get(depKey)
        const source = srcId ? state.steps[srcId] : undefined
        if (!srcId || !source) return []
        // Edge reflects the hand-off: done when upstream completed, live while the downstream runs.
        const live = source.status === 'completed' && target.status === 'running'
        const done = source.status === 'completed' && target.status !== 'pending'
        const tone = live ? 'blue' : done ? statusMeta(target.status).tone : 'slate'
        return [
          {
            id: `${srcId}->${id}`,
            source: srcId,
            target: id,
            type: 'smoothstep',
            animated: live,
            style: {
              stroke: toneStroke[tone],
              strokeWidth: live || done ? 1.6 : 1,
              strokeDasharray: source.status === 'completed' ? undefined : '4 4',
              opacity: done || live ? 1 : 0.6,
            },
            markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: toneStroke[tone] },
          },
        ]
      })
    })
  }, [state.stepOrder, state.steps])

  return (
    <div className="relative size-full">
      {ready && (
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={(_, n) => onSelectStep(n.id)}
          onPaneClick={() => onSelectStep(null)}
          nodesConnectable={false}
          fitView
          // Long DAGs would shrink to unreadable; keep text legible and let the user pan instead.
          fitViewOptions={{ padding: 0.15, minZoom: 0.8, maxZoom: 1.1 }}
          minZoom={0.3}
          maxZoom={1.75}
          proOptions={{ hideAttribution: true }}
        >
          <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="var(--color-border)" />
          <Controls showInteractive={false} position="bottom-right" />
        </ReactFlow>
      )}
    </div>
  )
}
