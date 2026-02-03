import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { VisualRoleNodeData } from '../types/visual';

export function VisualRoleNode({ data }: NodeProps<VisualRoleNodeData>) {
  const readiness = data.readiness;
  const statusColor = readiness?.ready
    ? 'bg-emerald-400'
    : readiness?.grade
      ? 'bg-rose-400'
      : 'bg-amber-400';
  const statusLabel = readiness?.ready ? 'READY' : readiness?.grade || 'PENDING';

  return (
    <div className="min-w-[180px] rounded-xl border border-cyan-400/40 bg-black/70 px-3 py-2 text-text-main shadow-[0_0_12px_rgba(34,211,238,0.2)]">
      <Handle type="target" position={Position.Left} className="!bg-cyan-300 !border-cyan-200" />
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold tracking-wide">{data.label}</span>
        <span className={`inline-flex items-center gap-1 rounded-full border border-white/10 px-2 py-0.5 text-[9px] uppercase ${statusColor} text-black`}>
          {statusLabel}
        </span>
      </div>
      {data.description ? (
        <div className="mt-1 text-[10px] text-text-dim">{data.description}</div>
      ) : null}
      <div className="mt-2 flex flex-wrap gap-1 text-[9px]">
        {data.requiresThinking ? (
          <span className="rounded bg-purple-500/20 px-2 py-0.5 text-purple-200">思考要求</span>
        ) : (
          <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-emerald-200">基础能力</span>
        )}
        {typeof data.minConfidence === 'number' ? (
          <span className="rounded bg-black/40 px-2 py-0.5 text-text-dim">最低置信 {data.minConfidence}</span>
        ) : null}
      </div>
    </div>
  );
}
