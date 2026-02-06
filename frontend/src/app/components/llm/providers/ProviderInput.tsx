import React, { useState, useCallback, useRef } from 'react';
import { Key } from 'lucide-react';

// Cyberpunk style input classes
const cyberInputClasses = "flex h-9 w-full min-w-0 rounded-md border border-white/10 bg-black/40 px-3 py-1 text-sm text-slate-100 placeholder:text-slate-500 transition-all duration-200 outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 focus:bg-black/60 hover:border-violet-400/30 hover:bg-black/50 disabled:opacity-50 disabled:cursor-not-allowed";

interface ProviderInputProps {
  value?: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: 'text' | 'password' | 'url' | 'number';
  className?: string;
  disabled?: boolean;
  autoComplete?: string;
  spellCheck?: boolean;
  min?: number;
  max?: number;
  step?: string;
  // 防抖延迟（毫秒）
  debounceMs?: number;
  // 调试标签
  debugLabel?: string;
}

/**
 * 简化的提供商输入组件，专注于防止API KEY清空问题
 */
export function ProviderInput({
  value,
  onChange,
  placeholder,
  type = 'text',
  className = '',
  disabled = false,
  autoComplete = 'off',
  spellCheck = false,
  min,
  max,
  step,
  debounceMs = 300,
  debugLabel
}: ProviderInputProps) {
  // 本地状态，只用于显示，不参与复杂的同步逻辑
  const [localValue, setLocalValue] = useState(value || '');
  
  // 防抖更新定时器
  const updateTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  // 跟踪是否正在防抖中
  const isDebouncingRef = useRef(false);

  // 当父组件值变化且不在防抖中时，更新本地值
  React.useEffect(() => {
    if (!isDebouncingRef.current && value !== localValue) {
      setLocalValue(value || '');
    }
  }, [value]);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    
    // 立即更新本地状态，确保输入框响应
    setLocalValue(newValue);
    
    // 标记正在防抖
    isDebouncingRef.current = true;
    
    // 防抖更新父组件状态
    if (updateTimeoutRef.current) {
      clearTimeout(updateTimeoutRef.current);
    }
    
    updateTimeoutRef.current = setTimeout(() => {
      if (debugLabel) {
        console.log(`ProviderInput[${debugLabel}]: Updating to:`, newValue);
      }
      onChange(newValue);
      // 防抖结束，重置标志
      isDebouncingRef.current = false;
    }, debounceMs);
  }, [onChange, debounceMs, debugLabel]);

  // 处理数字类型的输入
  const handleNumberChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    
    // 立即更新本地状态
    setLocalValue(newValue);
    
    // 标记正在防抖
    isDebouncingRef.current = true;
    
    // 防抖更新父组件状态
    if (updateTimeoutRef.current) {
      clearTimeout(updateTimeoutRef.current);
    }
    
    updateTimeoutRef.current = setTimeout(() => {
      const parsedValue = newValue === '' ? undefined : parseFloat(newValue);
      if (debugLabel) {
        console.log(`ProviderInput[${debugLabel}]: Updating number to:`, parsedValue);
      }
      onChange(parsedValue as any);
      // 防抖结束，重置标志
      isDebouncingRef.current = false;
    }, debounceMs);
  }, [onChange, debounceMs, debugLabel]);

  // 清理定时器
  React.useEffect(() => {
    return () => {
      if (updateTimeoutRef.current) {
        clearTimeout(updateTimeoutRef.current);
      }
    };
  }, []);

  // 使用本地值作为显示值
  const displayValue = localValue;

  return (
    <input
      type={type}
      value={displayValue}
      onChange={type === 'number' ? handleNumberChange : handleChange}
      className={`${cyberInputClasses} ${className}`}
      placeholder={placeholder}
      disabled={disabled}
      autoComplete={autoComplete}
      spellCheck={spellCheck}
      min={min}
      max={max}
      step={step}
    />
  );
}

/**
 * 专用的API Key输入组件
 */
interface ApiKeyInputProps {
  apiKey?: string;
  onChange: (value: string) => void;
  placeholder?: string;
  debugLabel?: string;
}

export function ApiKeyInput({ 
  apiKey, 
  onChange, 
  placeholder = "sk-...",
  debugLabel = 'api_key'
}: ApiKeyInputProps) {
  return (
    <div>
      <label className="block text-xs text-text-muted mb-1 flex items-center gap-1">
        <Key className="size-3" />
        API Key
      </label>
      <ProviderInput
        value={apiKey}
        onChange={onChange}
        type="text"
        placeholder={placeholder}
        className="font-mono"
        debugLabel={debugLabel}
      />
      <p className="text-[9px] text-text-dim mt-1">
        API Key用于身份验证，请妥善保管
      </p>
    </div>
  );
}

/**
 * 通用URL输入组件
 */
interface UrlInputProps {
  value?: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
  description?: string;
  debugLabel?: string;
}

export function UrlInput({ 
  value, 
  onChange, 
  placeholder,
  label = "URL",
  description,
  debugLabel = 'url'
}: UrlInputProps) {
  return (
    <div>
      <label className="block text-xs text-text-muted mb-1">{label}</label>
      <ProviderInput
        value={value}
        onChange={onChange}
        type="url"
        placeholder={placeholder}
        className="font-mono"
        debugLabel={debugLabel}
      />
      {description && (
        <p className="text-[9px] text-text-dim mt-1">{description}</p>
      )}
    </div>
  );
}

/**
 * 通用文本输入组件
 */
interface TextInputProps {
  value?: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
  description?: string;
  debugLabel?: string;
}

export function TextInput({ 
  value, 
  onChange, 
  placeholder,
  label,
  description,
  debugLabel = 'text'
}: TextInputProps) {
  return (
    <div>
      {label && (
        <label className="block text-xs text-text-muted mb-1">{label}</label>
      )}
      <ProviderInput
        value={value}
        onChange={onChange}
        type="text"
        placeholder={placeholder}
        className="font-mono"
        debugLabel={debugLabel}
      />
      {description && (
        <p className="text-[9px] text-text-dim mt-1">{description}</p>
      )}
    </div>
  );
}

/**
 * 通用数字输入组件
 */
interface NumberInputProps {
  value?: number;
  onChange: (value: number | undefined) => void;
  placeholder?: string;
  label?: string;
  description?: string;
  min?: number;
  max?: number;
  step?: string;
  debugLabel?: string;
}

export function NumberInput({ 
  value, 
  onChange, 
  placeholder,
  label,
  description,
  min,
  max,
  step,
  debugLabel = 'number'
}: NumberInputProps) {
  return (
    <div>
      {label && (
        <label className="block text-xs text-text-muted mb-1">{label}</label>
      )}
      <ProviderInput
        value={value?.toString() || ''}
        onChange={(val) => onChange(val === '' ? undefined : parseFloat(val))}
        type="number"
        placeholder={placeholder}
        min={min}
        max={max}
        step={step}
        debugLabel={debugLabel}
      />
      {description && (
        <p className="text-[9px] text-text-dim mt-1">{description}</p>
      )}
    </div>
  );
}
