/**
 * ProviderCard Component (Refactored)
 * 
 * 使用新的统一编辑状态管理 (useProviderForm)
 * 显示未保存更改指示器
 */

import React, { useCallback, useMemo } from 'react';
import { 
  Loader2, 
  Settings, 
  ChevronDown, 
  ChevronUp, 
  Zap, 
  Key, 
  Shield, 
  HelpCircle, 
  Clock, 
  UserCheck, 
  UserX, 
  PlayCircle,
  Save,
  X,
  AlertCircle
} from 'lucide-react';
import type { ProviderConfig } from '../types';
import type { ConnectivityStatus } from '../state';
import { 
  useProviderForm, 
  useProviderFormList,
  useIsProviderExpanded,
  useConnectivityStatus,
} from '../state';
import {
  formatConnectivityStatus,
  getConnectivityStatusDotColor,
  getConnectivityStatusBgColor,
} from '../utils/connectivity';

interface ProviderCardProps {
  providerId: string;
  provider: ProviderConfig;
  providerInfo: {
    name: string;
    type: string;
    supported_features: string[];
  } | null;
  ProviderComponent: React.ComponentType<{
    providerId?: string;
    provider: ProviderConfig;
    onUpdate: (updates: Partial<ProviderConfig>) => void;
    onValidate: () => { valid: boolean; errors: string[]; warnings: string[] };
  }> | null;
  connectivityStatus: ConnectivityStatus;
  costClass: string;
  isDeleting?: boolean;
  llmStatus?: {
    interviews?: {
      latest_by_provider?: Record<string, {
        status: 'passed' | 'failed';
        timestamp: string;
        role: string;
        model: string;
      }>;
    };
  } | null;
  onSave: (providerId: string, config: ProviderConfig) => Promise<void>;
  onDelete: (id: string) => void;
  onTest: (id: string) => void;
}

export function ProviderCardRefactored({
  providerId,
  provider,
  providerInfo,
  ProviderComponent,
  connectivityStatus,
  costClass,
  isDeleting,
  llmStatus,
  onSave,
  onDelete,
  onTest,
}: ProviderCardProps) {
  // 使用新的统一编辑状态 Hook
  const form = useProviderForm({
    providerId,
    initialConfig: provider,
    onSave,
  });

  // 全局未保存更改状态
  const globalFormList = useProviderFormList();
  
  // 展开状态
  const isExpanded = useIsProviderExpanded(providerId);
  
  // 面试状态
  const providerInterview = useMemo(() => {
    return llmStatus?.interviews?.latest_by_provider?.[providerId];
  }, [llmStatus, providerId]);

  // Provider 类型和认证方式
  const providerType = useMemo(() => {
    const type = provider.type?.toLowerCase() || '';
    return type.includes('cli') ? 'CLI' : 'HTTP';
  }, [provider.type]);

  const authType = useMemo(() => {
    return provider.api_key ? 'API Key' : 'None';
  }, [provider.api_key]);

  // 处理删除
  const handleDelete = useCallback(() => {
    // 如果有未保存的更改，先提示用户
    if (form.hasPendingChanges) {
      const confirmed = window.confirm(
        `Provider "${provider.name || providerId}" 有未保存的更改。\n\n确定要丢弃更改并删除吗？`
      );
      if (!confirmed) return;
    }
    onDelete(providerId);
  }, [form.hasPendingChanges, onDelete, provider.name, providerId]);

  // 处理测试
  const handleTest = useCallback(() => {
    onTest(providerId);
  }, [onTest, providerId]);

  // 切换编辑模式
  const handleToggleEdit = useCallback(() => {
    if (form.isEditing) {
      // 退出编辑模式
      if (form.hasPendingChanges) {
        const confirmed = window.confirm('有未保存的更改，确定要放弃吗？');
        if (!confirmed) return;
      }
      form.cancelEdit();
    } else {
      // 进入编辑模式
      form.startEdit();
    }
  }, [form]);

  // 处理保存
  const handleSave = useCallback(async () => {
    try {
      await form.saveForm();
    } catch (err) {
      // 错误已在 form 中处理
      console.error('Save failed:', err);
    }
  }, [form]);

  const actionsDisabled = form.isSaving || !!isDeleting;

  return (
    <div
      className={`rounded-xl p-4 border transition-all ${getConnectivityStatusBgColor(connectivityStatus)}`}
    >
      {/* Compact View */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`size-2 rounded-full ${getConnectivityStatusDotColor(connectivityStatus)}`} />
          <div>
            <h4 className="text-sm font-semibold text-text-main">
              {provider.name || providerInfo?.name || providerId}
              {/* 未保存更改指示器 */}
              {form.hasPendingChanges && (
                <span className="ml-2 px-1.5 py-0.5 text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded">
                  未保存
                </span>
              )}
            </h4>
            <div className="flex items-center gap-2 text-[10px] text-text-dim">
              <span className="font-mono">{provider.model || 'default'}</span>
              <span className={`${
                costClass.toLowerCase() === 'local' 
                  ? 'text-green-400' 
                  : costClass.toLowerCase() === 'fixed' 
                    ? 'text-blue-400' 
                    : 'text-purple-400'
              }`}>
                {costClass}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* 全局未保存更改指示器 - 只显示在其他卡片上 */}
          {!form.isEditing && globalFormList.hasAnyPendingChanges && (
            <div 
              className="px-2 py-1 rounded border border-amber-500/30 bg-amber-500/10 text-amber-300 text-[10px]"
              title={`${globalFormList.pendingChangesCount} 个 provider 有未保存的更改`}
            >
              <AlertCircle className="size-3 inline mr-1" />
              {globalFormList.pendingChangesCount} 未保存
            </div>
          )}

          {/* 面试状态 */}
          <div className="flex items-center gap-1.5 px-2 py-1 rounded border border-white/10 bg-white/5">
            {providerInterview ? (
              providerInterview.status === 'passed' ? (
                <UserCheck className="size-3 text-emerald-400" />
              ) : (
                <UserX className="size-3 text-rose-400" />
              )
            ) : (
              <HelpCircle className="size-3 text-gray-400" />
            )}
            <span className="text-[10px] text-text-main">
              {providerInterview 
                ? (providerInterview.status === 'passed' ? '面试通过' : '面试失败')
                : '未测试'}
            </span>
          </div>

          {/* 连通性状态 */}
          <div className={`flex items-center gap-1.5 px-2 py-1 rounded border border-white/10 bg-white/5`}>
            <span className={`size-1.5 rounded-full ${getConnectivityStatusDotColor(connectivityStatus)}`} />
            <span className="text-[10px] text-text-main">{formatConnectivityStatus(connectivityStatus)}</span>
          </div>

          {/* 操作按钮 */}
          <button
            onClick={handleTest}
            disabled={actionsDisabled}
            className="p-1.5 rounded border border-cyan-500/30 hover:border-cyan-500/60 text-cyan-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="测试连通性"
          >
            <PlayCircle className="size-3" />
          </button>

          {/* 编辑/保存按钮 */}
          {form.isEditing ? (
            <>
              <button
                onClick={handleSave}
                disabled={actionsDisabled || !form.hasPendingChanges}
                className="p-1.5 rounded border border-emerald-500/30 hover:border-emerald-500/60 text-emerald-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                title="保存更改"
              >
                {form.isSaving ? <Loader2 className="size-3 animate-spin" /> : <Save className="size-3" />}
              </button>
              <button
                onClick={handleToggleEdit}
                disabled={actionsDisabled}
                className="p-1.5 rounded border border-white/10 hover:border-white/30 text-slate-300 transition-colors"
                title="取消编辑"
              >
                <X className="size-3" />
              </button>
            </>
          ) : (
            <button
              onClick={handleToggleEdit}
              disabled={actionsDisabled}
              className={`p-1.5 rounded border transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                form.hasPendingChanges
                  ? 'border-amber-400/60 bg-amber-500/20 text-amber-200'
                  : 'border-white/10 hover:border-accent/40'
              }`}
              title={form.hasPendingChanges ? '有未保存的更改' : '编辑提供商'}
            >
              <Settings className="size-3" />
            </button>
          )}

          <button
            onClick={handleDelete}
            disabled={actionsDisabled}
            className="p-1.5 rounded border border-red-500/30 hover:border-red-500/40 text-red-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="删除提供商"
          >
            {isDeleting ? <Loader2 className="size-3 animate-spin" /> : '×'}
          </button>
        </div>
      </div>

      {/* Edit View */}
      {form.isEditing && ProviderComponent && (
        <div className="mt-4 pt-4 border-t border-white/10">
          {/* 未保存更改警告 */}
          {form.hasPendingChanges && (
            <div className="mb-4 px-3 py-2 rounded border border-amber-500/30 bg-amber-500/10 text-amber-200 text-xs flex items-center gap-2">
              <AlertCircle className="size-4" />
              <span>有未保存的更改。点击保存按钮提交更改，或点击取消放弃更改。</span>
            </div>
          )}
          
          {/* 错误显示 */}
          {form.error && (
            <div className="mb-4 px-3 py-2 rounded border border-red-500/30 bg-red-500/10 text-red-200 text-xs">
              {form.error}
            </div>
          )}

          <ProviderComponent
            providerId={providerId}
            provider={form.formState}
            onUpdate={form.updateFields}
            onValidate={() => ({ 
              valid: form.validationErrors.length === 0, 
              errors: form.validationErrors, 
              warnings: form.validationWarnings 
            })}
          />
        </div>
      )}
    </div>
  );
}

export default ProviderCardRefactored;
