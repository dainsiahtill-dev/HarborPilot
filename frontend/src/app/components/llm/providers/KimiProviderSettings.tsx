import React, { useState, useCallback } from 'react';
import { RefreshCw, AlertCircle, ExternalLink } from 'lucide-react';
import { BaseProviderSettings } from './BaseProviderSettings';
import { type ProviderConfig } from '../types';

interface KimiProviderSettingsProps {
  provider: ProviderConfig;
  onUpdate: (updates: Partial<ProviderConfig>) => void;
  onValidate: () => any;
}

interface ModelInfo {
  id: string;
  name?: string;
  description?: string;
  context?: string;
}

export function KimiProviderSettings({
  provider,
  onUpdate,
  onValidate
}: KimiProviderSettingsProps) {
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([
    { id: 'moonshot-v1-8k', name: 'moonshot-v1-8k', description: '标准模型', context: '8K' },
    { id: 'moonshot-v1-32k', name: 'moonshot-v1-32k', description: '长上下文模型', context: '32K' },
    { id: 'moonshot-v1-128k', name: 'moonshot-v1-128k', description: '超长上下文模型', context: '128K' }
  ]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const handleFieldChange = (field: string, value: any) => {
    onUpdate({ [field]: value });
  };

  const fetchModels = useCallback(async () => {
    setIsLoadingModels(true);
    setFetchError(null);

    try {
      const baseUrl = provider.base_url || 'https://api.moonshot.cn/v1';
      const modelsPath = provider.models_path || '/v1/models';
      const apiKey = provider.api_key;

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
      
      // Parse Moonshot API response (OpenAI compatible format)
      let models: ModelInfo[] = [];
      if (data.data && Array.isArray(data.data)) {
        models = data.data.map((item: any) => ({
          id: item.id || String(item),
          name: item.id || String(item),
          description: item.description || '',
          context: item.context_window ? `${item.context_window / 1000}K` : ''
        }));
      } else if (data.model_list && Array.isArray(data.model_list)) {
        models = data.model_list.map((item: any) => ({
          id: item.id || item.model_name || String(item),
          name: item.id || item.model_name || String(item),
          description: item.description || '',
          context: item.context_window ? `${item.context_window / 1000}K` : ''
        }));
      }

      // Fallback to default if no models returned
      if (models.length === 0) {
        models = [
          { id: 'moonshot-v1-8k', name: 'moonshot-v1-8k', description: '标准模型', context: '8K' },
          { id: 'moonshot-v1-32k', name: 'moonshot-v1-32k', description: '长上下文模型', context: '32K' },
          { id: 'moonshot-v1-128k', name: 'moonshot-v1-128k', description: '超长上下文模型', context: '128K' }
        ];
      }

      setAvailableModels(models);
      
      // If current model is not in the list, select the first one
      const currentModel = provider.model || provider.default_model || 'moonshot-v1-8k';
      if (!models.find(m => m.id === currentModel) && models.length > 0) {
        handleFieldChange('model', models[0].id);
      }
    } catch (error) {
      console.error('Failed to fetch models:', error);
      setFetchError(error instanceof Error ? error.message : '获取模型列表失败');
    } finally {
      setIsLoadingModels(false);
    }
  }, [provider.base_url, provider.models_path, provider.api_key, provider.model, provider.default_model]);

  return (
    <BaseProviderSettings provider={provider} onUpdate={onUpdate} onValidate={onValidate}>
      {/* Kimi API Configuration */}
      <div className="space-y-4">
        <h5 className="text-xs font-semibold text-text-main">Kimi API 配置</h5>
        
        {/* Base URL */}
        <div>
          <label className="block text-xs text-text-muted mb-1">API 基础URL</label>
          <input
            type="url"
            value={provider.base_url || "https://api.moonshot.cn/v1"}
            onChange={(e) => handleFieldChange('base_url', e.target.value)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
            placeholder="https://api.moonshot.cn/v1"
          />
          <p className="text-[9px] text-text-dim mt-1">
            Moonshot AI 官方 API 端点
          </p>
        </div>

        {/* API Path */}
        <div>
          <label className="block text-xs text-text-muted mb-1">API 路径</label>
          <input
            type="text"
            value={provider.api_path || "/v1/chat/completions"}
            onChange={(e) => handleFieldChange('api_path', e.target.value)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
            placeholder="/v1/chat/completions"
          />
          <p className="text-[9px] text-text-dim mt-1">
            对话补全 API 路径（OpenAI 兼容格式）
          </p>
        </div>

        {/* Models Path */}
        <div>
          <label className="block text-xs text-text-muted mb-1">模型列表路径</label>
          <input
            type="text"
            value={provider.models_path || "/v1/models"}
            onChange={(e) => handleFieldChange('models_path', e.target.value)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
            placeholder="/v1/models"
          />
          <p className="text-[9px] text-text-dim mt-1">
            获取可用模型列表的 API 路径
          </p>
        </div>

        {/* Model Selection with Fetch Button */}
        <div>
          <label className="block text-xs text-text-muted mb-1">模型</label>
          <div className="flex items-center gap-2">
            <select
              value={provider.model || provider.default_model || "moonshot-v1-8k"}
              onChange={(e) => handleFieldChange('model', e.target.value)}
              className="flex-1 bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
            >
              {availableModels.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name || model.id}{model.context ? ` (${model.context})` : ''}{model.description ? ` - ${model.description}` : ''}
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
            支持多轮对话、流式输出、多模态输入（文本、图片、视频）
          </p>
        </div>
      </div>

      {/* Model Parameters */}
      <div className="space-y-4">
        <h5 className="text-xs font-semibold text-text-main">模型参数</h5>
        
        {/* Temperature */}
        <div>
          <label className="block text-xs text-text-muted mb-1">
            Temperature (0-2)
          </label>
          <input
            type="number"
            value={provider.temperature ?? 0.7}
            onChange={(e) => handleFieldChange('temperature', parseFloat(e.target.value))}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
            min="0"
            max="2"
            step="0.1"
          />
          <p className="text-[9px] text-text-dim mt-1">
            影响输出随机性，值越高越随机，默认0.7
          </p>
        </div>

        {/* Top P */}
        <div>
          <label className="block text-xs text-text-muted mb-1">
            Top P (0-1)
          </label>
          <input
            type="number"
            value={provider.top_p ?? 1.0}
            onChange={(e) => handleFieldChange('top_p', parseFloat(e.target.value))}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
            min="0"
            max="1"
            step="0.1"
          />
          <p className="text-[9px] text-text-dim mt-1">
            采样策略，默认1.0
          </p>
        </div>

        {/* Max Tokens */}
        <div>
          <label className="block text-xs text-text-muted mb-1">
            Max Tokens
          </label>
          <input
            type="number"
            value={provider.max_tokens ?? 2048}
            onChange={(e) => handleFieldChange('max_tokens', parseInt(e.target.value))}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
            min="1"
          />
          <p className="text-[9px] text-text-dim mt-1">
            生成内容的最大 Token 数，默认2048
          </p>
        </div>

        {/* Stream */}
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="stream"
            checked={provider.streaming ?? false}
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
        <h5 className="text-xs font-semibold text-text-main">Kimi 模型信息</h5>
        <div className="bg-black/30 rounded-lg p-4 border border-white/10">
          <div className="space-y-3 text-xs">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-400"></div>
              <span className="text-text-main font-medium">moonshot-v1</span>
              <span className="text-text-dim">系列模型</span>
            </div>
            
            <div className="space-y-2 text-text-dim">
              <p>• moonshot-v1-8k: 标准模型，8K 上下文</p>
              <p>• moonshot-v1-32k: 长上下文模型，32K 上下文</p>
              <p>• moonshot-v1-128k: 超长上下文模型，128K 上下文</p>
              <p>• 支持多轮对话和流式输出</p>
              <p>• 支持多模态输入（文本、图片、视频）</p>
              <p>• OpenAI SDK 兼容</p>
            </div>
            
            <div className="pt-2 border-t border-white/10">
              <p className="text-[9px] text-text-dim">
                官方文档：
                <a 
                  href="https://platform.moonshot.ai/docs/api/chat"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-cyan-400 hover:text-cyan-300 ml-1 inline-flex items-center gap-0.5"
                >
                  Moonshot AI API 文档
                  <ExternalLink className="size-3" />
                </a>
              </p>
            </div>
          </div>
        </div>
      </div>
    </BaseProviderSettings>
  );
}
