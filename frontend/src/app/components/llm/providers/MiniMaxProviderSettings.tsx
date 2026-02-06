import React, { useCallback } from 'react';
import { BaseProviderSettings } from './BaseProviderSettings';
import { ApiKeyInput, UrlInput, TextInput, NumberInput } from './ProviderInput';
import { type ProviderConfig } from '../types';

interface MiniMaxProviderSettingsProps {
  provider: ProviderConfig;
  onUpdate: (updates: Partial<ProviderConfig>) => void;
  onValidate: () => any;
}

export function MiniMaxProviderSettings({
  provider,
  onUpdate,
  onValidate
}: MiniMaxProviderSettingsProps) {
  const setFieldValue = useCallback(
    <K extends keyof ProviderConfig>(field: K, value: ProviderConfig[K]) => {
      onUpdate({ [field]: value });
    },
    [onUpdate]
  );

  const handleFieldChange = useCallback((field: string, value: any) => {
    setFieldValue(field as keyof ProviderConfig, value);
  }, [setFieldValue]);

  return (
    <BaseProviderSettings provider={provider} onUpdate={onUpdate} onValidate={onValidate} hideApiKey hideBaseUrl>
      {/* MiniMax API Configuration */}
      <div className="space-y-4">
        <h5 className="text-xs font-semibold text-text-main">MiniMax API 配置</h5>
        
        {/* Base URL */}
        <UrlInput
          value={provider.base_url}
          onChange={(value) => setFieldValue('base_url', value)}
          placeholder="https://api.minimaxi.com/v1"
          label="API 基础URL"
          description="MiniMax官方API端点"
          debugLabel="minimax_base_url"
        />

        {/* API Key */}
        <ApiKeyInput
          value={provider.api_key}
          onChange={(value) => setFieldValue('api_key', value)}
          placeholder="sk-..."
          label="API Key"
          description="MiniMax API密钥"
          debugLabel="minimax_api_key"
        />

        {/* API Path */}
        <TextInput
          value={provider.api_path}
          onChange={(value) => setFieldValue('api_path', value)}
          placeholder="/text/chatcompletion_v2"
          label="API 路径"
          description="文本对话API路径（v2版本）"
          debugLabel="minimax_api_path"
        />

        {/* Model Input */}
        <TextInput
          value={provider.model || ''}
          onChange={(value) => setFieldValue('model', value)}
          placeholder="MiniMax-M2.1"
          label="模型名称"
          description="输入 MiniMax 模型名称，如 MiniMax-M2.1、MiniMax-M2.1-lightning、MiniMax-M2"
          debugLabel="minimax_model"
        />
      </div>

      {/* Model Parameters */}
      <div className="space-y-4">
        <h5 className="text-xs font-semibold text-text-main">模型参数</h5>
        
        {/* Temperature */}
        <NumberInput
          value={provider.temperature}
          onChange={(value) => setFieldValue('temperature', value)}
          placeholder="1.0"
          label="Temperature (0-1)"
          description="影响输出随机性，值越高越随机，默认1.0"
          min={0}
          max={1}
          step="0.1"
          debugLabel="minimax_temperature"
        />

        {/* Top P */}
        <NumberInput
          value={provider.top_p}
          onChange={(value) => setFieldValue('top_p', value)}
          placeholder="0.95"
          label="Top P (0-1)"
          description="核采样阈值，默认0.95"
          min={0}
          max={1}
          step="0.01"
          debugLabel="minimax_top_p"
        />

        {/* Max Tokens */}
        <NumberInput
          value={provider.max_tokens}
          onChange={(value) => setFieldValue('max_tokens', value)}
          placeholder="2048"
          label="Max Tokens"
          description="生成内容的最大Token数，默认2048"
          min={1}
          debugLabel="minimax_max_tokens"
        />

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
        <h5 className="text-xs font-semibold text-text-main">MiniMax 模型信息</h5>
        <div className="bg-black/30 rounded-lg p-4 border border-white/10">
          <div className="space-y-3 text-xs">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-400"></div>
              <span className="text-text-main font-medium">MiniMax-M2 系列</span>
              <span className="text-text-dim">官方文本生成模型</span>
            </div>
            
            <div className="space-y-2 text-text-dim">
              <p>• 请访问 MiniMax 官方文档查看可用模型列表</p>
              <p>• 常用模型：MiniMax-M2.1、MiniMax-M2.1-lightning、MiniMax-M2</p>
              <p>• 支持多轮对话和上下文理解</p>
              <p>• 适用于创意写作、问答对话</p>
            </div>
            
            <div className="pt-2 border-t border-white/10">
              <p className="text-[9px] text-text-dim">
                官方文档：
                <a 
                  href="https://platform.minimax.io/docs/api-reference/api-overview"
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
