export type VisualRoleId = 'pm' | 'director' | 'qa' | 'docs';

export type VisualNodeKind = 'role' | 'provider' | 'model';

export interface VisualRoleNodeData {
  kind: 'role';
  roleId: VisualRoleId;
  label: string;
  description?: string;
  requiresThinking?: boolean;
  minConfidence?: number;
  readiness?: {
    ready?: boolean;
    grade?: string;
  };
}

export interface VisualProviderNodeData {
  kind: 'provider';
  providerId: string;
  label: string;
  providerType?: string;
  costClass?: string;
  status?: string;
  modelCount?: number;
}

export interface VisualModelNodeData {
  kind: 'model';
  providerId: string;
  model: string;
  label: string;
  assignedRoles?: VisualRoleId[];
}

export type VisualNodeData = VisualRoleNodeData | VisualProviderNodeData | VisualModelNodeData;

export type VisualEdgeKind = 'provider-to-model' | 'model-to-role';

export interface VisualEdgeData {
  kind: VisualEdgeKind;
}

export interface VisualGraphConfig {
  providers: Record<string, unknown>;
  roles: Record<string, { provider_id?: string; model?: string; profile?: string }>;
  policies?: {
    role_requirements?: Record<string, { requires_thinking?: boolean; min_confidence?: number; error_message?: string }>;
  };
}

export interface VisualGraphStatus {
  roles?: Record<string, { ready?: boolean; grade?: string } | undefined>;
}
