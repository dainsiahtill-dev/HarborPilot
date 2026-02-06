import React, { useState, useCallback } from 'react';
import { RefreshCw, AlertCircle, Key } from 'lucide-react';
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

const cyberInputClasses = "flex h-9 w-full min-w-0 rounded-md border border-white/10 bg-black/40 px-3 py-1 text-sm text-slate-100 placeholder:text-slate-500 transition-all duration-200 outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 focus:bg-black/60 hover:border-violet-400/30 hover:bg-black/50 disabled:opacity-50 disabled:cursor-not-allowed";

const cyberSelectClasses = "flex h-9 w-full min-w-0 rounded-md border border-white/10 bg-black/40 px-3 py-1 text-sm text-slate-100 transition-all duration-200 outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 focus:bg-black/60 hover:border-violet-400/30 hover:bg-black/50 cursor-pointer appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2224%22%20height%3D%2224%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%2394a3b8%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpolyline%20points%3D%226%209%2012%2015%2018%209%22%3E%3C%2Fpolyline%3E%3C%2Fsvg%3E')] bg-[length:16px] bg-[right_8px_center] bg-no-repeat pr-10";

function KimiApiKeyInput({ 
  value, 
  onChange, 
  placeholder 
}: { 
  value?: string; 
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value);
  }, [onChange]);

  return (
    <div>
      <label className="block text-xs text-text-muted mb-1 flex items-center gap-1">
        <Key className="size-3" />
        API Key
      </label>
      <input
        type="text"
        value={value ?? ''}
        onChange={handleChange}
        placeholder={placeholder || 'sk-...'}
        className={`${cyberInputClasses} font-mono`}
        autoComplete="off"
        spellCheck={false}
      />
      <p className="text-[9px] text-text-dim mt-1">
        API Key用于身份验证，请妥善保管
      </p>
    </div>
  );
}

export function KimiProviderSettings({
  provider,
  onUpdate,
  onValidate
}: KimiProviderSettingsProps) {
  const setFieldValue = useCallback(
    <K extends keyof ProviderConfig>(field: K, value: ProviderConfig[K]) => {
      onUpdate({ [field]: value });
    },
    [onUpdate]
  );

  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([
    { id: 'moonshot-v1-8k', name: 'moonshot-v1-8k', description: '标准模型', context: '8K' },
    { id: 'moonshot-v1-32k', name: 'moonshot-v1-32k', description: '长上下文模型', context: '32K' },
    { id: 'moonshot-v1-128k', name: 'moonshot-v1-128k', description: '超长上下文模型', context: '128K' }
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

      if (models.length === 0) {
        models = [
          { id: 'moonshot-v1-8k', name: 'moonshot-v1-8k', description: '标准模型', context: '8K' },
          { id: 'moonshot-v1-32k', name: 'moonshot-v1-32k', description: '长上下文模型', context: '32K' },
          { id: 'moonshot-v1-128k', name: 'moonshot-v1-128k', description: '超长上下文模型', context: '128K' }
        ];
      }

      setAvailableModels(models);
      
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
  }, [provider.base_url, provider.models_path, provider.api_key, provider.model, provider.default_model, handleFieldChange]);

  return (
    <BaseProviderSettings provider={provider} onUpdate={onUpdate} onValidate={onValidate} hideApiKey hideBaseUrl>
      {/* Kimi API Configuration */}
      <div className="space-y-4">
        <h5 className="text-xs font-semibold text-text-main">Kimi API 配置</h5>
        
        {/* Base URL */}
        <div>
          <label className="block text-xs text-text-muted mb-1">API 基础URL</label>
          <input
            type="text"
            value={provider.base_url || ''}
            onChange={(e) => setFieldValue('base_url', e.target.value)}
            placeholder="https://api.moonshot.cn/v1"
            className={`${cyberInputClasses} font-mono`}
          />
          <p className="text-[9px] text-text-dim mt-1">Moonshot AI 官方 API 端点</p>
        </div>

        {/* API Key */}
        <KimiApiKeyInput
          value={provider.api_key}
          onChange={(value) => setFieldValue('api_key', value)}
          placeholder="sk-..."
        />

        {/* API Path */}
        <div>
          <label className="block text-xs text-text-muted mb-1">API 路径</label>
          <input
            type="text"
            value={provider.api_path || ''}
            onChange={(e) => setFieldValue('api_path', e.target.value)}
            placeholder="/v1/chat/completions"
            className={`${cyberInputClasses} font-mono`}
          />
          <p className="text-[9px] text-text-dim mt-1">对话补全 API 路径（OpenAI 兼容格式）</p>
        </div>

        {/* Models Path */}
        <div>
          <label className="block text-xs text-text-muted mb-1">模型列表路径</label>
          <input
            type="text"
            value={provider.models_path || ''}
            onChange={(e) => setFieldValue('models_path', e.target.value)}
            placeholder="/v1/models"
            className={`${cyberInputClasses} font-mono`}
          />
          <p className="text-[9px] text-text-dim mt-1">获取可用模型列表的 API 路径</p>
        </div>

        {/* Model Selection with Fetch Button */}
        <div>
          <label className="block text-xs text-text-muted mb-1">模型</label>
          <div className="flex items-center gap-2">
            <select
              value={provider.model || provider.default_model || "moonshot-v1-8k"}
              onChange={(e) => handleFieldChange('model', e.target.value)}
              className={cyberSelectClasses}
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
              className="px-3 py-2 rounded border border-cyan-500/30 hover:border-cyan-500/60 text-cyan-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5 bg-black/40"
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
          <label className="block text-xs text-text-muted mb-1">Temperature (0-1)</label>
          <input
            type="number"
            value={provider.temperature ?? ''}
            onChange={(e) => setFieldValue('temperature', e.target.value === '' ? undefined : parseFloat(e.target.value))}
            placeholder="1.0"
            className={cyberInputClasses}
            min={0}
            max={1}
            step="0.1"
          />
          <p className="text-[9px] text-text-dim mt-1">影响输出随机性，值越高越随机，默认1.0</p>
        </div>

        {/* Top P */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Top P (0-1)</label>
          <input
            type="number"
            value={provider.top_p ?? ''}
            onChange={(e) => setFieldValue('top_p', e.target.value === '' ? undefined : parseFloat(e.target.value))}
            placeholder="0.95"
            className={cyberInputClasses}
            min={0}
            max={1}
            step="0.01"
          />
          <p className="text-[9px] text-text-dim mt-1">核采样阈值，默认0.95</p>
        </div>

        {/* Max Tokens */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Max Tokens</label>
          <input
            type="number"
            value={provider.max_tokens ?? ''}
            onChange={(e) => setFieldValue('max_tokens', e.target.value === '' ? undefined : parseInt(e.target.value))}
            placeholder="2048"
            className={cyberInputClasses}
            min={1}
          />
          <p className="text-[9px] text-text-dim mt-1">生成内容的最大Token数，默认2048</p>
        </div>

        {/* Stream */}
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="kimi-stream"
            checked={provider.streaming ?? false}
            onChange={(e) => handleFieldChange('streaming', e.target.checked)}
            className="rounded border-white/10 bg-black/30"
          />
          <label htmlFor="kimi-stream" className="text-xs text-text-main">
            启用流式传输
          </label>
        </div>
        <p className="text-[9px] text-text-dim mt-1">
          开启后响应将分批返回，适合实时对话场景
        </p>
      </div>

      {/* Kimi Model Information */}
      <div className="space-y-4">
        <h5 className="text-xs font-semibold text-text-main">Kimi 模型信息</h5>
        <div className="bg-black/30 rounded-lg p-4 border border-white/10">
          <div className="space-y-3 text-xs">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-violet-400"></div>
              <span className="text-text-main font-medium">Moonshot AI (Kimi)</span>
              <span className="text-text-dim">官方大语言模型</span>
            </div>
            
            <div className="space-y-2 text-text-dim">
              <p>• moonshot-v1-8k：标准模型，支持8K上下文窗口</p>
              <p>• moonshot-v1-32k：长上下文模型，支持32K上下文窗口</p>
              <p>• moonshot-v1-128k：超长上下文模型，支持128K上下文窗口</p>
              <p>• 支持多轮对话、流式输出、多模态输入</p>
            </div>
            
            <div className="pt-2 border-t border-white/10">
              <p className="text-[9px] text-text-dim">
                官方文档：
                <a 
                  href="https://platform.moonshot.cn/docs/api/chat"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-cyan-400 hover:text-cyan-300 ml-1"
                >
                  Kimi API 文档
                </a>
              </p>
            </div>
          </div>
        </div>
      </div>
    </BaseProviderSettings>
  );
}
