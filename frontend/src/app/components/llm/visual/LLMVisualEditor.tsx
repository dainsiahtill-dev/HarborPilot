import { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Connection,
  type Node,
  type NodeChange,
  type Edge,
  type ReactFlowInstance,
} from '@xyflow/react';
import { Trash2, Unplug, Play, CheckCircle, Activity, ExternalLink, LayoutGrid, Maximize } from 'lucide-react';
import '@xyflow/react/dist/style.css';
import { useVisualLLMConfig } from './hooks/useVisualLLMConfig';
import { nodeTypes, edgeTypes } from './utils/nodeTypes';
import { isValidVisualConnection } from './utils/validation';
import { extractNodePositions, extractNodeStates } from './utils/configConverter';
import { ContextMenu, type ContextMenuItem } from './components/ContextMenu';
import type { VisualGraphConfig, VisualGraphStatus, VisualNodeData, VisualProviderNodeData, VisualModelNodeData, VisualRoleNodeData } from './types/visual';

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
    syncNodeStates,
    deleteNode,
    deleteEdge,
    setNodes,
  } = useVisualLLMConfig({ config, status, onConfigChange });

  const [rfInstance, setRfInstance] = useState<ReactFlowInstance<VisualNodeData, Edge> | null>(null);
  const [modelDraft, setModelDraft] = useState('');
  const [providerDraft, setProviderDraft] = useState('');
  const [showAddModel, setShowAddModel] = useState(false);
  const [contextMenu, setContextMenu] = useState<{
    visible: boolean;
    x: number;
    y: number;
    type: 'node' | 'edge';
    data: any;
  } | null>(null);

  const providers = useMemo(() => Object.entries(config?.providers || {}), [config]);

  const onNodeContextMenu = useCallback(
    (event: React.MouseEvent, node: Node) => {
      event.preventDefault();
      setContextMenu({
        visible: true,
        x: event.clientX,
        y: event.clientY,
        type: 'node',
        data: node,
      });
    },
    []
  );

  const onEdgeContextMenu = useCallback(
    (event: React.MouseEvent, edge: Edge) => {
      event.preventDefault();
      setContextMenu({
        visible: true,
        x: event.clientX,
        y: event.clientY,
        type: 'edge',
        data: edge,
      });
    },
    []
  );

  const onPaneClick = useCallback(() => {
    setContextMenu(null);
  }, []);

  const closeContextMenu = useCallback(() => {
    setContextMenu(null);
  }, []);

  const handleAutoLayout = useCallback(() => {
    const updates: Node<VisualNodeData>[] = [];
    
    // Group nodes by type
    const providers = nodes.filter(n => n.type === 'provider');
    const models = nodes.filter(n => n.type === 'model');
    const roles = nodes.filter(n => n.type === 'role');
    const others = nodes.filter(n => !['provider', 'model', 'role'].includes(n.type || ''));

    providers.forEach((node, index) => {
      updates.push({ ...node, position: { x: 40, y: index * 180 + 40 } });
    });

    // Group models by provider for better association
    const modelsByProvider: Record<string, Node<VisualNodeData>[]> = {};
    models.forEach(m => {
      const data = m.data as VisualModelNodeData;
      const pid = data.providerId || 'unknown';
      if (!modelsByProvider[pid]) modelsByProvider[pid] = [];
      modelsByProvider[pid].push(m);
    });

    // Helper to find provider index
    const getProviderY = (pid: string) => {
      const idx = providers.findIndex(p => (p.data as VisualProviderNodeData).providerId === pid);
      return idx >= 0 ? idx * 180 + 40 : 0;
    };

    let flatModelIndex = 0;
    // Iterate models by provider if possible, or just flat
    // To minimize crossing lines, we should try to align with provider
    // But simplistic approach: just use flat index, maybe sorted by provider?
    
    // Let's stick to flat layout in column 2 for now, simple and predictable
    models.forEach((node, index) => {
       updates.push({ ...node, position: { x: 340, y: index * 120 + 40 } });
    });

    roles.forEach((node, index) => {
      updates.push({ ...node, position: { x: 700, y: index * 180 + 40 } });
    });
    
    others.forEach((node, index) => {
       updates.push({ ...node, position: { x: 1000, y: index * 180 + 40 } });
    });

    setNodes(updates);
    
    // Fit view after layout with a slight delay
    setTimeout(() => {
      rfInstance?.fitView({ duration: 800 });
    }, 50);
  }, [nodes, setNodes, rfInstance]);

  // Generate menu items based on context
  const getContextMenuItems = useCallback((): { items: ContextMenuItem[]; title?: string } => {
    if (!contextMenu) return { items: [] };

    if (contextMenu.type === 'node') {
      const node = contextMenu.data as Node<VisualNodeData>;
      const items: ContextMenuItem[] = [];
      let title = '';

      if (node.type === 'provider') {
        const data = node.data as VisualProviderNodeData;
        title = `Provider: ${data.label}`;
        items.push({
          label: '测试连接',
          icon: Activity,
          action: () => {
             console.log('Test provider', data.providerId);
          },
        });
        items.push({
          label: '删除 Provider',
          icon: Trash2,
          variant: 'danger',
          action: () => deleteNode(node.id),
        });
      } else if (node.type === 'model') {
         const data = node.data as VisualModelNodeData;
         title = `Model: ${data.model}`;
         items.push({
          label: '删除模型',
          icon: Trash2,
          variant: 'danger',
          action: () => deleteNode(node.id),
        });
      } else if (node.type === 'role') {
         const data = node.data as VisualRoleNodeData;
         title = `Role: ${data.label}`;
         items.push({
           label: '清除分配',
           icon: Unplug,
           variant: 'warning',
           action: () => {
             console.warn('Clear assignment not fully wired via node menu yet');
           }
         });
      }
      return { items, title };
    } else if (contextMenu.type === 'edge') {

      const edge = contextMenu.data as Edge;
      return {
        title: '连接操作',
        items: [
          {
            label: '删除连接',
            icon: Unplug,
            variant: 'danger',
            action: () => deleteEdge(edge.id),
          },
        ],
      };
    }
    return { items: [] };
  }, [contextMenu, deleteNode, deleteEdge]);

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

  const isValid = (connection: Connection | Edge) => {
    if ('sourceHandle' in connection) {
      return isValidVisualConnection(connection as Connection, nodes);
    }
    return false;
  };

  const nodeColor = (node: Node<VisualNodeData>) => {
    if (node.type === 'role') return '#22d3ee';
    if (node.type === 'provider') return '#f472b6';
    return '#34d399';
  };

  const handleNodesChange = (changes: NodeChange[]) => {
    onNodesChange(changes);
  };

  if (!config) {
    return (
      <div className="rounded-xl border border-white/10 bg-black/30 p-6 text-xs text-text-dim">
        暂无 LLM 配置数据，无法渲染视觉编辑器。
      </div>
    );
  }

  const handleSave = () => {
    if (!config || !onConfigChange) return;
    
    // 先同步状态到配置中
    const updatedConfig = { ...config };
    
    // 手动提取位置和状态
    const layout = extractNodePositions(nodes);
    const states = extractNodeStates(nodes, edges);
    
    // 直接更新配置
    const finalConfig = {
      ...updatedConfig,
      visual_layout: layout,
      visual_node_states: states,
    };
    
    // 调用配置更新
    onConfigChange(finalConfig);
    
    // 等待状态更新完成后再保存
    setTimeout(() => {
      onSave?.();
    }, 300);
  };

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
            onClick={handleAutoLayout}
            className="p-1.5 text-text-dim hover:text-cyan-400 transition-colors"
            title="自动布局"
          >
            <LayoutGrid size={14} />
          </button>
          <button
            type="button"
            onClick={() => rfInstance?.fitView({ duration: 400 })}
            className="p-1.5 text-text-dim hover:text-cyan-400 transition-colors"
            title="适应视图"
          >
            <Maximize size={14} />
          </button>
          <div className="w-px h-3 bg-white/10 mx-1" />
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
              onClick={handleSave}
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
          onNodeContextMenu={onNodeContextMenu}
          onEdgeContextMenu={onEdgeContextMenu}
          onPaneClick={onPaneClick}
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

      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          items={getContextMenuItems().items}
          title={getContextMenuItems().title}
          onClose={closeContextMenu}
        />
      )}
    </div>
  );
}
