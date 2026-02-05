import { useEffect, useMemo, useState } from 'react';
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Connection,
  type Node,
  type NodeChange,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useVisualLLMConfig } from './hooks/useVisualLLMConfig';
import { nodeTypes, edgeTypes } from './utils/nodeTypes';
import { isValidVisualConnection } from './utils/validation';
import type { VisualGraphConfig, VisualGraphStatus, VisualNodeData } from './types/visual';

interface LLMVisualEditorProps {
  config: VisualGraphConfig | null;
  status?: VisualGraphStatus | null;
  onConfigChange?: (config: VisualGraphConfig) => void;
  onSave?: () => void;
}

export function LLMVisualEditor({ config, status, onConfigChange, onSave }: LLMVisualEditorProps) {
  const {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onEdgesDelete,
    onConnect,
    addModel,
    syncNodePositions,
  } = useVisualLLMConfig({ config, status, onConfigChange });

  const [modelDraft, setModelDraft] = useState('');
  const [providerDraft, setProviderDraft] = useState('');
  const [showAddModel, setShowAddModel] = useState(false);

  const providers = useMemo(() => Object.entries(config?.providers || {}), [config]);

  useEffect(() => {
    if (!providerDraft && providers.length > 0) {
      setProviderDraft(providers[0][0]);
    }
  }, [providerDraft, providers]);

  const handleAddModel = () => {
    const modelName = modelDraft.trim();
    if (!modelName || !providerDraft) return;
    addModel(providerDraft, modelName);
    setModelDraft('');
  };

  const isValid = (connection: Connection) => isValidVisualConnection(connection, nodes);

  const nodeColor = (node: Node<VisualNodeData>) => {
    if (node.type === 'role') return '#22d3ee';
    if (node.type === 'provider') return '#f472b6';
    return '#34d399';
  };

  const handleNodesChange = (changes: NodeChange[]) => {
    onNodesChange(changes);
    // 当拖拽结束时，同步位置到 config
    const hasPositionChange = changes.some(
      (change) => change.type === 'position' && !change.dragging
    );
    if (hasPositionChange && config && onConfigChange) {
      syncNodePositions(config);
    }
  };

  if (!config) {
    return (
      <div className="rounded-xl border border-white/10 bg-black/30 p-6 text-xs text-text-dim">
        暂无 LLM 配置数据，无法渲染视觉编辑器。
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-black/40 p-4 shadow-[0_0_24px_rgba(34,211,238,0.12)]">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div>
          <div className="text-xs font-semibold text-text-main">LLM 视觉配置编辑器</div>
          <div className="text-[10px] text-text-dim">拖拽连线：Provider → Model → Role</div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowAddModel((prev) => !prev)}
            className="px-3 py-1.5 text-[10px] font-semibold bg-cyan-500/80 hover:bg-cyan-500 text-white rounded transition-colors"
          >
            添加模型
          </button>
          {onSave ? (
            <button
              type="button"
              onClick={() => {
                // 保存前同步位置
                if (config && onConfigChange) {
                  syncNodePositions(config);
                }
                onSave?.();
              }}
              className="px-3 py-1.5 text-[10px] font-semibold bg-emerald-500/80 hover:bg-emerald-500 text-white rounded transition-colors"
            >
              保存配置
            </button>
          ) : null}
        </div>
      </div>

      {showAddModel ? (
        <div className="mb-3 grid grid-cols-1 md:grid-cols-[180px_1fr_auto] gap-2 items-center">
          <select
            className="bg-black/40 border border-white/10 text-[10px] text-text-main rounded px-2 py-1.5"
            value={providerDraft}
            onChange={(event) => setProviderDraft(event.target.value)}
          >
            <option value="">选择提供商</option>
            {providers.map(([providerId, provider]) => {
              const label =
                typeof provider === 'object' && provider !== null && 'name' in provider
                  ? String((provider as Record<string, unknown>).name || providerId)
                  : providerId;
              return (
                <option key={providerId} value={providerId}>
                  {label}
                </option>
              );
            })}
          </select>
          <input
            className="bg-black/40 border border-white/10 text-[10px] text-text-main rounded px-2 py-1.5"
            placeholder="模型名称"
            value={modelDraft}
            onChange={(event) => setModelDraft(event.target.value)}
          />
          <button
            type="button"
            onClick={handleAddModel}
            className="px-3 py-1.5 text-[10px] font-semibold bg-fuchsia-500/80 hover:bg-fuchsia-500 text-white rounded"
          >
            添加
          </button>
        </div>
      ) : null}

      <div className="h-[60vh] min-h-[520px] rounded-xl border border-white/10 overflow-hidden">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={handleNodesChange}
          onEdgesChange={onEdgesChange}
          onEdgesDelete={onEdgesDelete}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          isValidConnection={isValid}
          className="bg-[radial-gradient(circle_at_top,_rgba(14,116,144,0.18),_transparent_60%)]"
        >
          <MiniMap
            nodeColor={nodeColor}
            maskColor="rgba(15,23,42,0.6)"
            className="bg-black/70"
          />
          <Controls className="bg-black/60" />
          <Background gap={24} size={1} color="rgba(148,163,184,0.35)" />
        </ReactFlow>
      </div>
    </div>
  );
}
