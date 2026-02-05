import { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from '@xyflow/react';
import type { VisualEdgeData, VisualGraphConfig, VisualGraphStatus, VisualNodeData, VisualRoleId } from '../types/visual';
import {
  addManualModel,
  buildVisualGraph,
  clearRoleAssignment,
  extractNodePositions,
  mergeNodePositions,
  modelNodeId,
  updateRoleAssignment,
} from '../utils/configConverter';

interface UseVisualLLMConfigOptions {
  config: VisualGraphConfig | null;
  status?: VisualGraphStatus | null;
  onConfigChange?: (config: VisualGraphConfig) => void;
}

export function useVisualLLMConfig({ config, status, onConfigChange }: UseVisualLLMConfigOptions) {
  const graph = useMemo(() => {
    if (!config) return { nodes: [], edges: [] };
    return buildVisualGraph(config, status || undefined);
  }, [config, status]);

  const [nodes, setNodes] = useState<Node<VisualNodeData>[]>(graph.nodes);
  const [edges, setEdges] = useState<Edge<VisualEdgeData>[]>(graph.edges);

  useEffect(() => {
    setNodes((prev) => mergeNodePositions(prev, graph.nodes));
    setEdges(graph.edges);
  }, [graph.nodes, graph.edges]);

  const nodeMap = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);



  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((current) => applyEdgeChanges(changes, current));
  }, []);

  const syncTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // 同步节点位置到配置
  const syncNodePositions = useCallback(
    (currentConfig: VisualGraphConfig, currentNodes: Node<VisualNodeData>[]) => {
      if (!onConfigChange) return;
      const layout = extractNodePositions(currentNodes);
      const nextConfig = {
        ...currentConfig,
        visual_layout: layout,
      };
      onConfigChange(nextConfig);
    },
    [onConfigChange]
  );

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setNodes((current) => {
        const nextNodes = applyNodeChanges(changes, current);
        
        // 实时同步位置变化 (避免依赖 stale 的 nodesRef)
        const hasPositionChange = changes.some((c) => c.type === 'position');
        if (hasPositionChange && config && onConfigChange) {
          if (syncTimeoutRef.current) {
            clearTimeout(syncTimeoutRef.current);
          }
          syncTimeoutRef.current = setTimeout(() => {
            const layout = extractNodePositions(nextNodes);
            if (onConfigChange && config) {
              const nextConfig = {
                ...config,
                visual_layout: layout,
              };
              onConfigChange(nextConfig);
            }
          }, 500);
          
          // 修正：我们在这个回调里只做 setNodes。
          // sync 逻辑应该放在 useEffect 或者使用 stable ref for config?
          // 或者，我们让 `onNodesChange` 依赖 `config`。
          // React Flow 可以在 onNodesChange 变动时处理。
        }
        return nextNodes;
      });
    },
    [config, onConfigChange] // 依赖 config, 这会导致 onNodesChange 在 config 变动时更新
  );
  
  // 使用 Effect 处理 debounced sync 更好？
  // 不，Effect 会在每次 render 都跑。
  // 我们只希望在 drag 时跑。
  
  // 回到 Plan A: 显式传递 nodes 给 syncNodePositions 在 handleSave 中。
  // 对于自动 sync，我们使用 updated nodes。
  
  // 让我们简化:
  // onNodesChange 只负责 setNodes 和 trigger effect?
  
  // 重写 onNodesChange:
  // 我们使用一个 ref 来存 latestConfig，这样 timeout 里可以拿到最新的 config。

  const updateConfigRole = useCallback(
    (roleId: VisualRoleId, providerId: string, model: string) => {
      if (!config || !onConfigChange) return;
      onConfigChange(updateRoleAssignment(config, roleId, providerId, model));
    },
    [config, onConfigChange]
  );

  const clearConfigRole = useCallback(
    (roleId: VisualRoleId) => {
      if (!config || !onConfigChange) return;
      onConfigChange(clearRoleAssignment(config, roleId));
    },
    [config, onConfigChange]
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      const sourceNode = nodeMap.get(connection.source);
      const targetNode = nodeMap.get(connection.target);
      if (!sourceNode || !targetNode) return;

      if (sourceNode.type === 'model' && targetNode.type === 'role') {
        const modelData = sourceNode.data;
        const roleData = targetNode.data;
        if (modelData.kind !== 'model' || roleData.kind !== 'role') return;
        updateConfigRole(roleData.roleId, modelData.providerId, modelData.model);
        setEdges((current) => {
          const filtered = current.filter(
            (edge) => !(edge.data?.kind === 'model-to-role' && edge.target === targetNode.id)
          );
          const exists = filtered.some(
            (edge) => edge.source === connection.source && edge.target === connection.target
          );
          if (exists) return filtered;
          return addEdge(
            {
              ...connection,
              type: 'custom',
              data: { kind: 'model-to-role' },
            },
            filtered
          );
        });
      } else if (sourceNode.type === 'provider' && targetNode.type === 'model') {
        setEdges((current) => {
          const exists = current.some(
            (edge) => edge.source === connection.source && edge.target === connection.target
          );
          if (exists) return current;
          return addEdge(
            {
              ...connection,
              type: 'custom',
              data: { kind: 'provider-to-model' },
            },
            current
          );
        });
      }
    },
    [nodeMap, updateConfigRole]
  );

  const onEdgesDelete = useCallback(
    (deleted: Edge<VisualEdgeData>[]) => {
      deleted.forEach((edge) => {
        if (edge.data?.kind !== 'model-to-role') return;
        const targetNode = nodeMap.get(edge.target);
        if (!targetNode || targetNode.type !== 'role') return;
        const roleData = targetNode.data;
        if (roleData.kind === 'role') {
          clearConfigRole(roleData.roleId);
        }
      });
    },
    [clearConfigRole, nodeMap]
  );

  const addModel = useCallback(
    (providerId: string, model: string) => {
      if (!providerId || !model) return;
      const existing = nodes.find(
        (node) => node.type === 'model' && node.data.kind === 'model' && node.data.providerId === providerId && node.data.model === model
      );
      if (existing) return;
      const providerNode = nodes.find(
        (node) =>
          node.type === 'provider' &&
          node.data.kind === 'provider' &&
          node.data.providerId === providerId
      );
      if (!providerNode) return;
      const nextNode: Node<VisualNodeData> = {
        id: modelNodeId(providerId, model),
        type: 'model',
        position: { x: providerNode.position.x + 300, y: providerNode.position.y + 140 },
        data: {
          kind: 'model',
          providerId,
          model,
          label: model,
          assignedRoles: [],
        },
      };
      setNodes((current) => [...current, nextNode]);
      setEdges((current) => [
        ...current,
        {
          id: `edge:${providerNode.id}:${nextNode.id}`,
          source: providerNode.id,
          target: nextNode.id,
          type: 'custom',
          data: { kind: 'provider-to-model' },
        },
      ]);
      if (config && onConfigChange) {
        const providerCfg = config.providers?.[providerId] as Record<string, unknown> | undefined;
        const providerType = typeof providerCfg?.type === 'string' ? providerCfg.type : '';
        if (providerType === 'codex_cli' || providerType === 'gemini_cli' || providerType === 'cli') {
          onConfigChange(addManualModel(config, providerId, model));
        }
      }
    },
    [config, nodes, onConfigChange]
  );

  return {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onConnect,
    onEdgesDelete,
    addModel,
    setNodes,
    setEdges,
    syncNodePositions,
  };
}

