import React, { useState, useCallback } from 'react';
import { RefreshCw, AlertCircle } from 'lucide-react';
import { BaseProviderSettings } from './BaseProviderSettings';
import { ApiKeyInput, UrlInput, TextInput, NumberInput } from './ProviderInput';
import { useProviderForm } from '../hooks';
import { type ProviderConfig } from '../types';

interface MaxminiProviderSettingsProps {
  provider: ProviderConfig;
  onUpdate: (updates: Partial<ProviderConfig>) => void;
  onValidate: () => any;
}

interface ModelInfo {
  id: string;
  name?: string;
  description?: string;
}

const cyberInputClasses = "flex h-9 w-full min-w-0 rounded-md border border-white/10 bg-black/40 px-3 py-1 text-sm text-slate-100 placeholder:text-slate-500 transition-all duration-200 outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 focus:bg-black/60 hover:border-violet-400/30 hover:bg-black/50 disabled:opacity-50 disabled:cursor-not-allowed";
const cyberSelectClasses = "flex h-9 w-full min-w-0 rounded-md border border-white/10 bg-black/40 px-3 py-1 text-sm text-slate-100 transition-all duration-200 outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 focus:bg-black/60 hover:border-violet-400/30 hover:bg-black/50 cursor-pointer appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2224%22%20height%3D%2224%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%2394a3b8%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpolyline%20points%3D%226%209%2012%2015%2018%209%22%3E%3C%2Fpolyline%3E%3C%2Fsvg%3E')] bg-[length:16px] bg-[right_8px_center] bg-no-repeat pr-10";

export function MaxminiProviderSettings({
  provider,
  onUpdate,
  onValidate
}: MaxminiProviderSettingsProps) {
  const {
    formState,
    hasChanges,
    isDirty,
    setFieldValue,
  } = useProviderForm({
    provider,
    onUpdate,
    debounceMs: 300,
  });

  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([
    { id: 'M2-her', name: 'M2-her', description: '最新对话模型' }
  ]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const handleFieldChange = useCallback((field: string, value: any) => {
    setFieldValue(field as keyof ProviderConfig, value);
  }, [setFieldValue]);

  const fetchModels = useCallback(async () => {
    setIsLoadingModels(true);
    setFetchError(null);

    try {
      const baseUrl = formState.base_url || 'https://api.minimaxi.com/v1';
      const modelsPath = formState.models_path || '/query/model_list';
      const apiKey = formState.api_key;

      if (!apiKey) {
        setFetchError('请先配置 API Key');
        return;
      }

      const response = await fetch(`${baseUrl}${modelsPath}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`API 请求失败: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      
      // Parse MiniMax API response
      let models: ModelInfo[] = [];
      if (data.model_list && Array.isArray(data.model_list)) {
        models = data.model_list.map((item: any) => ({
          id: item.model_name || item.id || String(item),
          name: item.model_name || item.name || String(item),
          description: item.description || ''
        }));
      } else if (data.data && Array.isArray(data.data)) {
        models = data.data.map((item: any) => ({
          id: item.model_name || item.id || String(item),
          name: item.model_name || item.name || String(item),
          description: item.description || ''
        }));
      }

      // Fallback to default if no models returned
      if (models.length === 0) {
        models = [{ id: 'M2-her', name: 'M2-her', description: '最新对话模型' }];
      }

      setAvailableModels(models);
      
      // If current model is not in the list, select the first one
      const currentModel = formState.model || 'M2-her';
      if (!models.find(m => m.id === currentModel) && models.length > 0) {
        handleFieldChange('model', models[0].id);
      }
    } catch (error) {
      console.error('Failed to fetch models:', error);
      setFetchError(error instanceof Error ? error.message : '获取模型列表失败');
    } finally {
      setIsLoadingModels(false);
    }
  }, [formState.base_url, formState.models_path, formState.api_key, formState.model, handleFieldChange]);

  return (
    <BaseProviderSettings provider={formState} onUpdate={onUpdate} onValidate={onValidate} hideApiKey hideBaseUrl>
      {/* MiniMax API Configuration */}
      <div className="space-y-4">
        <h5 className="text-xs font-semibold text-text-main">MiniMax API 配置</h5>
        
        {/* Base URL */}
        <UrlInput
          value={formState.base_url}
          onChange={(value) => setFieldValue('base_url', value)}
          placeholder="https://api.minimaxi.com/v1"
          label="API 基础URL"
          description="MiniMax官方API端点"
          debugLabel="maxmini_base_url"
        />

        {/* API Key */}
        <ApiKeyInput
          apiKey={formState.api_key}
          onChange={(value) => setFieldValue('api_key', value)}
          debugLabel="maxmini_api_key"
        />

        {/* API Path */}
        <TextInput
          value={formState.api_path}
          onChange={(value) => setFieldValue('api_path', value)}
          placeholder="/text/chatcompletion_v2"
          label="API 路径"
          description="文本对话API路径（v2版本）"
          debugLabel="maxmini_api_path"
        />

        {/* Model Selection with Fetch Button */}
        <div>
          <label className="block text-xs text-text-muted mb-1">模型</label>
          <div className="flex items-center gap-2">
            <select
              value={formState.model || "M2-her"}
              onChange={(e) => handleFieldChange('model', e.target.value)}
              className={cyberSelectClasses}
            >
              {availableModels.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name || model.id}{model.description ? ` - ${model.description}` : ''}
                </option>
              ))}
            </select>
            <button
              onClick={fetchModels}
              disabled={isLoadingModels}
              className="px-3 py-2 rounded border border-cyan-500/30 hover:border-cyan-500/60 text-cyan-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
              title="获取可用模型列表"
            >
              <RefreshCw className={`size-3.5 ${isLoadingModels ? 'animate-spin' : ''}`} />
              <span className="text-xs">获取</span>
            </button>
          </div>
          {fetchError && (
            <div className="mt-2 flex items-center gap-1.5 text-[10px] text-red-400">
              <AlertCircle className="size-3" />
              <span>{fetchError}</span>
            </div>
          )}
          <p className="text-[9px] text-text-dim mt-1">
            支持角色扮演、多轮对话等场景
          </p>
        </div>
      </div>

      {/* Model Parameters */}
      <div className="space-y-4">
        <h5 className="text-xs font-semibold text-text-main">模型参数</h5>
        
        {/* Temperature */}
        <NumberInput
          value={formState.temperature}
          onChange={(value) => setFieldValue('temperature', value)}
          placeholder="1.0"
          label="Temperature (0-1)"
          description="影响输出随机性，值越高越随机，默认1.0"
          min={0}
          max={1}
          step="0.1"
          debugLabel="maxmini_temperature"
        />

        {/* Top P */}
        <NumberInput
          value={formState.top_p}
          onChange={(value) => setFieldValue('top_p', value)}
          placeholder="1.0"
          label="Top P (0-1)"
          description="采样策略，默认1.0"
          min={0}
          max={1}
          step="0.1"
          debugLabel="maxmini_top_p"
        />

        {/* Max Tokens */}
        <NumberInput
          value={formState.max_tokens}
          onChange={(value) => setFieldValue('max_tokens', value)}
          placeholder="2048"
          label="Max Tokens"
          description="生成内容的最大Token数，默认2048"
          min={1}
          debugLabel="maxmini_max_tokens"
        />

        {/* Stream */}
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="stream"
            checked={formState.streaming ?? false}
            onChange={(e) => handleFieldChange('streaming', e.target.checked)}
            className="rounded border-white/10 bg-black/30"
          />
          <label htmlFor="stream" className="text-xs text-text-main">
            启用流式传输
          </label>
        </div>
        <p className="text-[9px] text-text-dim mt-1">
          开启后响应将分批返回，适合实时对话场景
        </p>
      </div>

      {/* Model Information */}
      <div className="space-y-4">
        <h5 className="text-xs font-semibold text-text-main">MiniMax 模型信息</h5>
        <div className="bg-black/30 rounded-lg p-4 border border-white/10">
          <div className="space-y-3 text-xs">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-400"></div>
              <span className="text-text-main font-medium">M2-her</span>
              <span className="text-text-dim">对话模型</span>
            </div>
            
            <div className="space-y-2 text-text-dim">
              <p>• M2-her: 最新对话模型，支持角色扮演</p>
              <p>• 支持多轮对话和上下文理解</p>
              <p>• 适用于创意写作、问答对话</p>
              <p>• 支持自定义角色和风格</p>
            </div>
            
            <div className="pt-2 border-t border-white/10">
              <p className="text-[9px] text-text-dim">
                官方文档：
                <a 
                  href="https://platform.minimaxi.com/docs/api-reference/text-chat"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-cyan-400 hover:text-cyan-300 ml-1"
                >
                  MiniMax API 文档
                </a>
              </p>
            </div>
          </div>
        </div>
      </div>
    </BaseProviderSettings>
  );
}
