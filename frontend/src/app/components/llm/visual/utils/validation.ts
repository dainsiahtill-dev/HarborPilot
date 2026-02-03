import type { Connection, Node } from '@xyflow/react';
import type { VisualNodeData } from '../types/visual';

export const isValidVisualConnection = (
  connection: Connection,
  nodes: Node<VisualNodeData>[]
): boolean => {
  if (!connection.source || !connection.target) return false;
  const source = nodes.find((node) => node.id === connection.source);
  const target = nodes.find((node) => node.id === connection.target);
  if (!source || !target) return false;

  if (source.type === 'model' && target.type === 'role') {
    return true;
  }

  if (source.type === 'provider' && target.type === 'model') {
    const sourceData = source.data;
    const targetData = target.data;
    const sourceProvider = sourceData.kind === 'provider' ? sourceData.providerId : undefined;
    const targetProvider = targetData.kind === 'model' ? targetData.providerId : undefined;
    return Boolean(sourceProvider && targetProvider && sourceProvider === targetProvider);
  }

  return false;
};
