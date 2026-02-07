/**
 * StrictViewAdapter
 * 
 * Phase 4.2: Type Safety Enhancement
 * - Strict type constraints for view adapters
 * - Type-safe update operations
 * - Discriminated unions for operation types
 */

import type { UnifiedLlmConfig } from '../types';
import type { ViewAdapter } from './types';

// ============================================================================
// Operation Type Definitions
// ============================================================================

// List View Operations
export type ListUpdateOperation =
  | { type: 'update_provider'; payload: { providerId: string; config: any } }
  | { type: 'update_role'; payload: { roleId: string; config: any } }
  | { type: 'update_assignment'; payload: { roleId: string; providerId: string; model: string } }
  | { type: 'add_provider'; payload: { providerId: string; config: any } }
  | { type: 'remove_provider'; payload: { providerId: string } }
  | { type: 'reorder_providers'; payload: { order: string[] } };

// Visual View Operations
export type VisualUpdateOperation =
  | { type: 'update_node_position'; payload: { nodeId: string; x: number; y: number } }
  | { type: 'update_node_style'; payload: { nodeId: string; style: Record<string, any> } }
  | { type: 'update_layout'; payload: { layout: string; options?: any } }
  | { type: 'add_connection'; payload: { from: string; to: string; type: string } }
  | { type: 'remove_connection'; payload: { from: string; to: string } }
  | { type: 'set_viewport'; payload: { x: number; y: number; zoom: number } };

// Deep Test View Operations
export type TestUpdateOperation =
  | { type: 'update_test_result'; payload: { testId: string; result: any } }
  | { type: 'update_connectivity'; payload: { providerId: string; status: any } }
  | { type: 'update_interview'; payload: { interviewId: string; status: any } }
  | { type: 'start_test'; payload: { testId: string; config: any } }
  | { type: 'cancel_test'; payload: { testId: string } }
  | { type: 'set_test_filter'; payload: { filter: string; value: any } };

// Union of all operations
export type ViewUpdateOperation = 
  | (ListUpdateOperation & { viewType: 'list' })
  | (VisualUpdateOperation & { viewType: 'visual' })
  | (TestUpdateOperation & { viewType: 'deepTest' });

// ============================================================================
// Extract Operation Parameters Utility Type
// ============================================================================

export type ExtractOperationParams<
  TOperation extends { type: string; payload?: any },
  TType extends TOperation['type']
> = TOperation extends { type: TType; payload: infer P } ? P : never;

// ============================================================================
// Strict View Adapter Interface
// ============================================================================

export interface StrictViewAdapter<
  TViewData,
  TViewState,
  TOperation extends { type: string; payload?: any }
> extends ViewAdapter<TViewData, TViewState> {
  /**
   * Get list of supported operation types
   */
  getSupportedOperations(): TOperation['type'][];

  /**
   * Type-safe update operation
   */
  executeOperation(
    operation: TOperation['type'],
    params: any
  ): Partial<UnifiedLlmConfig>;

  /**
   * Validate operation parameters
   */
  validateOperation(
    operation: TOperation['type'],
    params: any
  ): { valid: boolean; errors: string[] };

  /**
   * Check if operation is supported
   */
  isOperationSupported(operation: string): operation is TOperation['type'];
}

// ============================================================================
// Strict List View Adapter Implementation
// ============================================================================

export interface ListViewData {
  providers: Array<{
    id: string;
    name: string;
    type: string;
    status: string;
  }>;
  roles: Array<{
    id: string;
    name: string;
    assignment?: {
      provider_id: string;
      model: string;
    };
  }>;
  assignments: Array<{
    roleId: string;
    providerId: string;
    model: string;
  }>;
}

export interface ListViewState {
  selectedProviderId: string | null;
  selectedRoleId: string | null;
  filter: string;
  sortBy: 'name' | 'type' | 'status';
  sortOrder: 'asc' | 'desc';
  expandedProviders: Set<string>;
}

export class StrictListViewAdapter implements StrictViewAdapter<
  ListViewData,
  ListViewState,
  ListUpdateOperation
> {
  adaptToView(unifiedData: UnifiedLlmConfig): ListViewData {
    const providers = Object.entries(unifiedData.providers || {}).map(([id, config]) => ({
      id,
      name: config.name || id,
      type: config.type || 'unknown',
      status: 'unknown',
    }));

    const roles = Object.entries(unifiedData.roles || {}).map(([id, config]) => ({
      id,
      name: id,
      assignment: config.assignment,
    }));

    const assignments = Object.entries(unifiedData.roles || {})
      .filter(([, config]) => config.assignment)
      .map(([roleId, config]) => ({
        roleId,
        providerId: config.assignment!.provider_id,
        model: config.assignment!.model || 'default',
      }));

    return { providers, roles, assignments };
  }

  adaptFromView(viewData: ListViewData, unifiedData: UnifiedLlmConfig): Partial<UnifiedLlmConfig> {
    // Convert view data back to unified format
    const providers: UnifiedLlmConfig['providers'] = {};
    viewData.providers.forEach((p) => {
      providers[p.id] = {
        ...unifiedData.providers?.[p.id],
        name: p.name,
        type: p.type,
      };
    });

    const roles: UnifiedLlmConfig['roles'] = {};
    viewData.roles.forEach((r) => {
      if (r.assignment) {
        roles[r.id] = {
          ...unifiedData.roles?.[r.id],
          assignment: {
            provider_id: r.assignment.provider_id,
            model: r.assignment.model,
            assigned_at: new Date().toISOString(),
            confidence: 0.8,
          },
        };
      }
    });

    return { providers, roles };
  }

  createViewState(): ListViewState {
    return {
      selectedProviderId: null,
      selectedRoleId: null,
      filter: '',
      sortBy: 'name',
      sortOrder: 'asc',
      expandedProviders: new Set(),
    };
  }

  updateViewState(state: ListViewState, changes: Partial<ListViewState>): ListViewState {
    return { ...state, ...changes };
  }

  getSupportedOperations(): ListUpdateOperation['type'][] {
    return [
      'update_provider',
      'update_role',
      'update_assignment',
      'add_provider',
      'remove_provider',
      'reorder_providers',
    ];
  }

  isOperationSupported(operation: string): operation is ListUpdateOperation['type'] {
    return this.getSupportedOperations().includes(operation as ListUpdateOperation['type']);
  }

  validateOperation(
    operation: ListUpdateOperation['type'],
    params: any
  ): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    switch (operation) {
      case 'update_provider':
        if (!params?.providerId) errors.push('providerId is required');
        if (!params?.config) errors.push('config is required');
        break;
      case 'update_role':
        if (!params?.roleId) errors.push('roleId is required');
        break;
      case 'update_assignment':
        if (!params?.roleId) errors.push('roleId is required');
        if (!params?.providerId) errors.push('providerId is required');
        break;
      case 'add_provider':
        if (!params?.providerId) errors.push('providerId is required');
        if (!params?.config) errors.push('config is required');
        break;
      case 'remove_provider':
        if (!params?.providerId) errors.push('providerId is required');
        break;
      case 'reorder_providers':
        if (!params?.order || !Array.isArray(params.order)) {
          errors.push('order must be an array');
        }
        break;
    }

    return { valid: errors.length === 0, errors };
  }

  executeOperation(
    operation: ListUpdateOperation['type'],
    params: any
  ): Partial<UnifiedLlmConfig> {
    // Validate first
    const validation = this.validateOperation(operation, params);
    if (!validation.valid) {
      throw new Error(`Invalid operation: ${validation.errors.join(', ')}`);
    }

    switch (operation) {
      case 'update_provider':
        return {
          providers: {
            [params.providerId]: params.config,
          },
        };

      case 'update_role':
        return {
          roles: {
            [params.roleId]: params.config,
          },
        };

      case 'update_assignment':
        return {
          roles: {
            [params.roleId]: {
              assignment: {
                provider_id: params.providerId,
                model: params.model,
                assigned_at: new Date().toISOString(),
                confidence: 0.8,
              },
            } as any,
          },
        };

      case 'add_provider':
        return {
          providers: {
            [params.providerId]: params.config,
          },
        };

      case 'remove_provider':
        // Return marker for removal
        return {
          providers: {
            [params.providerId]: undefined as any,
          },
        };

      case 'reorder_providers':
        // Reordering doesn't change unified data, only view state
        return {};

      default:
        throw new Error(`Unsupported operation: ${operation}`);
    }
  }
}

// ============================================================================
// Type Guard Functions
// ============================================================================

export function isListOperation(
  operation: ViewUpdateOperation
): operation is ListUpdateOperation & { viewType: 'list' } {
  return operation.viewType === 'list';
}

export function isVisualOperation(
  operation: ViewUpdateOperation
): operation is VisualUpdateOperation & { viewType: 'visual' } {
  return operation.viewType === 'visual';
}

export function isTestOperation(
  operation: ViewUpdateOperation
): operation is TestUpdateOperation & { viewType: 'deepTest' } {
  return operation.viewType === 'deepTest';
}

// ============================================================================
// Operation Factory Functions
// ============================================================================

export const ListOperations = {
  updateProvider: (
    providerId: string,
    config: any
  ): ListUpdateOperation & { viewType: 'list' } => ({
    viewType: 'list',
    type: 'update_provider',
    payload: { providerId, config },
  }),

  updateRole: (roleId: string, config: any): ListUpdateOperation & { viewType: 'list' } => ({
    viewType: 'list',
    type: 'update_role',
    payload: { roleId, config },
  }),

  updateAssignment: (
    roleId: string,
    providerId: string,
    model: string
  ): ListUpdateOperation & { viewType: 'list' } => ({
    viewType: 'list',
    type: 'update_assignment',
    payload: { roleId, providerId, model },
  }),

  addProvider: (
    providerId: string,
    config: any
  ): ListUpdateOperation & { viewType: 'list' } => ({
    viewType: 'list',
    type: 'add_provider',
    payload: { providerId, config },
  }),

  removeProvider: (providerId: string): ListUpdateOperation & { viewType: 'list' } => ({
    viewType: 'list',
    type: 'remove_provider',
    payload: { providerId },
  }),

  reorderProviders: (order: string[]): ListUpdateOperation & { viewType: 'list' } => ({
    viewType: 'list',
    type: 'reorder_providers',
    payload: { order },
  }),
};

// ============================================================================
// Type-safe Operation Executor
// ============================================================================

export class TypedOperationExecutor {
  constructor(private adapter: StrictViewAdapter<any, any, any>) {}

  execute(operation: ViewUpdateOperation): Partial<UnifiedLlmConfig> {
    if (!this.adapter.isOperationSupported(operation.type)) {
      throw new Error(`Operation ${operation.type} is not supported by this adapter`);
    }

    return this.adapter.executeOperation(operation.type, operation.payload);
  }

  validate(operation: ViewUpdateOperation): { valid: boolean; errors: string[] } {
    if (!this.adapter.isOperationSupported(operation.type)) {
      return { valid: false, errors: [`Operation ${operation.type} is not supported`] };
    }

    return this.adapter.validateOperation(operation.type, operation.payload);
  }
}
