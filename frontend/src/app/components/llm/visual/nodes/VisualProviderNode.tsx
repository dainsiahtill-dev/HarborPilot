import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import type { VisualProviderNodeData } from '../types/visual';

const STATUS_STYLES: Record<string, string> = {
  ready: 'text-emerald-300',
  failed: 'text-rose-300',
  testing: 'text-cyan-300',
};

export function VisualProviderNode({ data }: NodeProps<Node<VisualProviderNodeData>>) {
  const statusClass = data.status ? STATUS_STYLES[data.status] || 'text-text-dim' : 'text-text-dim';
  return (
    <div className="min-w-[200px] rounded-xl border border-fuchsia-400/40 bg-black/70 px-3 py-2 text-text-main shadow-[0_0_14px_rgba(217,70,239,0.2)]">
      <Handle type="source" position={Position.Right} className="!bg-fuchsia-300 !border-fuchsia-200" />
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold">{data.label}</div>
        <div className={`text-[9px] uppercase ${statusClass}`}>{data.status || 'IDLE'}</div>
      </div>
      <div className="mt-1 text-[10px] text-text-dim">
        {data.providerType ? data.providerType : 'provider'}
        {typeof data.modelCount === 'number' ? ` • ${data.modelCount} models` : ''}
      </div>
      {data.costClass ? (
        <div className="mt-2 inline-flex rounded bg-black/40 px-2 py-0.5 text-[9px] text-text-dim">
          {data.costClass}
        </div>
      ) : null}
    </div>
  );
}
