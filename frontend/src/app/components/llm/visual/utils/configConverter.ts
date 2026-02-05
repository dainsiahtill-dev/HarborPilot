import type { Edge, Node } from '@xyflow/react';
import type {
  VisualEdgeData,
  VisualGraphConfig,
  VisualGraphStatus,
  VisualModelNodeData,
  VisualNodeData,
  VisualNodePosition,
  VisualProviderNodeData,
  VisualRoleId,
  VisualRoleNodeData,
} from '../types/visual';

const ROLE_ORDER: VisualRoleId[] = ['pm', 'director', 'qa', 'docs'];

const ROLE_META: Record<VisualRoleId, { label: string; description: string }> = {
  pm: { label: 'PM', description: '项目规划与任务协调' },
  director: { label: 'Director', description: '代码执行与技术实现' },
  qa: { label: 'QA', description: '质量检查与测试验证' },
  docs: { label: 'Docs', description: '文档输出与规范整理' },
};

const normalizeId = (value: string) => value.replace(/[^a-zA-Z0-9_-]/g, '_');

export const roleNodeId = (roleId: VisualRoleId) => `role:${roleId}`;
export const providerNodeId = (providerId: string) => `provider:${normalizeId(providerId)}`;
export const modelNodeId = (providerId: string, model: string) =>
  `model:${normalizeId(providerId)}:${normalizeId(model)}`;

const coerceManualModels = (config: Record<string, unknown>) => {
  const manual = config.manual_models;
  if (Array.isArray(manual)) {
    return manual.map((item) => String(item)).filter(Boolean);
  }
  return [];
};

export const buildVisualGraph = (
  config: VisualGraphConfig,
  status?: VisualGraphStatus | null
): { nodes: Node<VisualNodeData>[]; edges: Edge<VisualEdgeData>[] } => {
  const providers = Object.entries(config.providers || {});
  const roleReqs = config.policies?.role_requirements || {};
  const savedLayout = config.visual_layout || {};

  // Helper to safely restore position
  const restorePosition = (nodeId: string, defaultPosition: VisualNodePosition): VisualNodePosition => {
    const saved = savedLayout[nodeId];
    if (saved && typeof saved.x === 'number' && typeof saved.y === 'number') {
      return saved;
    }
    return defaultPosition;
  };

  const providerModels = new Map<string, Set<string>>();
  const addModel = (providerId: string, model: string) => {
    if (!providerId || !model) return;
    if (!providerModels.has(providerId)) {
      providerModels.set(providerId, new Set());
    }
    providerModels.get(providerId)?.add(model);
  };

  Object.entries(config.roles || {}).forEach(([roleId, roleCfg]) => {
    const providerId = roleCfg?.provider_id || '';
    const model = roleCfg?.model || '';
    if (providerId && model) {
      addModel(providerId, model);
    }
  });

  providers.forEach(([providerId, providerCfgRaw]) => {
    const providerCfg =
      typeof providerCfgRaw === 'object' && providerCfgRaw !== null
        ? (providerCfgRaw as Record<string, unknown>)
        : {};
    const manualModels = coerceManualModels(providerCfg);
    manualModels.forEach((model) => addModel(providerId, model));
  });

  const nodes: Node<VisualNodeData>[] = [];
  const edges: Edge<VisualEdgeData>[] = [];

  providers.forEach(([providerId, providerCfgRaw], providerIndex) => {
    const providerCfg = typeof providerCfgRaw === 'object' && providerCfgRaw !== null
      ? (providerCfgRaw as Record<string, unknown>)
      : {};
    const providerType = typeof providerCfg.type === 'string' ? providerCfg.type : undefined;
    const providerLabel =
      typeof providerCfg.name === 'string' && providerCfg.name.trim()
        ? providerCfg.name.trim()
        : providerId;
    const modelList = Array.from(providerModels.get(providerId) || []);
    
    const providerNode: Node<VisualProviderNodeData> = {
      id: providerNodeId(providerId),
      type: 'provider',
      position: restorePosition(providerNodeId(providerId), { x: 40, y: providerIndex * 180 + 40 }),
      data: {
        kind: 'provider',
        providerId,
        label: providerLabel,
        providerType,
        modelCount: modelList.length,
      },
    };
    nodes.push(providerNode);

    modelList.forEach((model, modelIndex) => {
      const modelNode: Node<VisualModelNodeData> = {
        id: modelNodeId(providerId, model),
        type: 'model',
        position: restorePosition(modelNodeId(providerId, model), { x: 340, y: providerIndex * 180 + modelIndex * 120 + 40 }),
        data: {
          kind: 'model',
          providerId,
          model,
          label: model,
          assignedRoles: [],
        },
      };
      nodes.push(modelNode);
      edges.push({
        id: `edge:${providerNode.id}:${modelNode.id}`,
        source: providerNode.id,
        target: modelNode.id,
        type: 'custom',
        data: { kind: 'provider-to-model' },
      });
    });
  });

  ROLE_ORDER.forEach((roleId, index) => {
    const requirement = roleReqs[roleId] || {};
    const readiness = status?.roles?.[roleId];
    const meta = ROLE_META[roleId];
    
    nodes.push({
      id: roleNodeId(roleId),
      type: 'role',
      position: restorePosition(roleNodeId(roleId), { x: 700, y: index * 180 + 40 }),
      data: {
        kind: 'role',
        roleId,
        label: meta.label,
        description: meta.description,
        requiresThinking: Boolean(requirement.requires_thinking),
        minConfidence: typeof requirement.min_confidence === 'number' ? requirement.min_confidence : undefined,
        readiness: readiness
          ? {
              ready: readiness.ready,
              grade: readiness.grade,
            }
          : undefined,
      },
    });
  });

  Object.entries(config.roles || {}).forEach(([roleId, roleCfg]) => {
    const providerId = roleCfg?.provider_id || '';
    const model = roleCfg?.model || '';
    if (!providerId || !model) return;
    const modelId = modelNodeId(providerId, model);
    const roleIdNormalized = roleId as VisualRoleId;
    const modelNode = nodes.find((node) => node.id === modelId);
    if (modelNode && modelNode.type === 'model') {
      const data = modelNode.data as VisualModelNodeData;
      data.assignedRoles = Array.from(new Set([...(data.assignedRoles || []), roleIdNormalized]));
    }
    edges.push({
      id: `edge:${modelId}:${roleNodeId(roleIdNormalized)}`,
      source: modelId,
      target: roleNodeId(roleIdNormalized),
      type: 'custom',
      data: { kind: 'model-to-role' },
    });
  });

  return { nodes, edges };
};

export const mergeNodePositions = (
  previous: Node<VisualNodeData>[],
  next: Node<VisualNodeData>[]
): Node<VisualNodeData>[] => {
  const positions = new Map(previous.map((node) => [node.id, node.position]));
  return next.map((node) => {
    const position = positions.get(node.id);
    return position ? { ...node, position } : node;
  });
};

export const updateRoleAssignment = (
  config: VisualGraphConfig,
  roleId: VisualRoleId,
  providerId: string,
  model: string
): VisualGraphConfig => {
  return {
    ...config,
    roles: {
      ...config.roles,
      [roleId]: {
        ...(config.roles?.[roleId] || {}),
        provider_id: providerId,
        model,
      },
    },
  };
};

export const clearRoleAssignment = (config: VisualGraphConfig, roleId: VisualRoleId): VisualGraphConfig => {
  const nextRole = { ...(config.roles?.[roleId] || {}) } as Record<string, unknown>;
  delete nextRole.provider_id;
  delete nextRole.model;
  return {
    ...config,
    roles: {
      ...config.roles,
      [roleId]: nextRole,
    },
  };
};

export const addManualModel = (
  config: VisualGraphConfig,
  providerId: string,
  model: string
): VisualGraphConfig => {
  const raw = config.providers?.[providerId];
  const providerCfg =
    typeof raw === 'object' && raw !== null ? ({ ...(raw as Record<string, unknown>) } as Record<string, unknown>) : {};
  const manualModels = coerceManualModels(providerCfg);
  if (!manualModels.includes(model)) {
    manualModels.push(model);
  }
  providerCfg.manual_models = manualModels;
  return {
    ...config,
    providers: {
      ...config.providers,
      [providerId]: providerCfg,
    },
  };
};

export const extractNodePositions = (nodes: Node<VisualNodeData>[]): Record<string, VisualNodePosition> => {
  const layout: Record<string, VisualNodePosition> = {};
  nodes.forEach((node) => {
    if (node.position && typeof node.position.x === 'number' && typeof node.position.y === 'number') {
      layout[node.id] = { x: node.position.x, y: node.position.y };
    }
  });
  return layout;
};

export const updateVisualLayout = (
  config: VisualGraphConfig,
  nodes: Node<VisualNodeData>[]
): VisualGraphConfig => {
  const layout = extractNodePositions(nodes);
  return {
    ...config,
    visual_layout: layout,
  };
};
