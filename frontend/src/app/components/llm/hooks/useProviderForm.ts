/**
 * useProviderForm Hook
 * 管理 Provider 编辑表单的本地状态
 * 解决复杂状态同步问题：防抖、脏值追踪、取消恢复
 */

import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import type { ProviderConfig } from '../types';

interface UseProviderFormOptions {
  provider: ProviderConfig;
  onUpdate: (updates: Partial<ProviderConfig>) => void;
  debounceMs?: number;
}

interface UseProviderFormReturn {
  formState: ProviderConfig;
  hasChanges: boolean;
  isDirty: boolean;
  fieldChanges: Partial<ProviderConfig>;
  isSaving: boolean;
  pendingUpdates: Partial<ProviderConfig>;
  setFieldValue: <K extends keyof ProviderConfig>(field: K, value: ProviderConfig[K]) => void;
  updateField: <K extends keyof ProviderConfig>(field: K, value: ProviderConfig[K]) => void;
  resetForm: () => void;
  commitChanges: () => void;
  discardChanges: () => void;
  clearPendingUpdates: () => void;
}

export function useProviderForm({
  provider,
  onUpdate,
  debounceMs = 300,
}: UseProviderFormOptions): UseProviderFormReturn {
  const [formState, setFormState] = useState<ProviderConfig>(provider);
  const [fieldChanges, setFieldChanges] = useState<Partial<ProviderConfig>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [pendingUpdates, setPendingUpdates] = useState<Partial<ProviderConfig>>({});

  const originalProvider = useRef(provider);
  const debounceTimer = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // 只有当provider ID发生变化时才重置表单（比如切换到不同的提供商）
    // 这避免了因为其他状态变化导致的意外重置
    if (provider.id !== originalProvider.current.id) {
      originalProvider.current = provider;
      setFormState(provider);
      setFieldChanges({});
      setPendingUpdates({});
      
      // 清除防抖定时器
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
        debounceTimer.current = null;
      }
    }
  }, [provider.id]);

  const hasChanges = useMemo(
    () => Object.keys(fieldChanges).length > 0,
    [fieldChanges]
  );

  const isDirty = useMemo(
    () => {
      const changedKeys = Object.keys(fieldChanges);
      if (changedKeys.length === 0) return false;

      return changedKeys.some(key => {
        const formValue = (formState as any)[key];
        const originalValue = (originalProvider.current as any)[key];
        return formValue !== originalValue;
      });
    },
    [formState, fieldChanges]
  );

  const setFieldValue = useCallback(<K extends keyof ProviderConfig>(
    field: K,
    value: ProviderConfig[K]
  ) => {
    
    // 立即更新本地状态
    setFormState(prev => ({ ...prev, [field]: value }));
    setFieldChanges(prev => ({ ...prev, [field]: value }));

    // 清除之前的防抖定时器
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    // 防抖更新父组件状态
    debounceTimer.current = setTimeout(() => {
      onUpdate({ [field]: value });
      setPendingUpdates(prev => ({ ...prev, [field]: value }));
    }, debounceMs);
  }, [debounceMs, onUpdate]);

  const updateField = useCallback(<K extends keyof ProviderConfig>(
    field: K,
    value: ProviderConfig[K]
  ) => {
    setFormState(prev => ({ ...prev, [field]: value }));
    setFieldChanges(prev => ({ ...prev, [field]: value }));
    onUpdate({ [field]: value });
    setPendingUpdates(prev => ({ ...prev, [field]: value }));
  }, [onUpdate]);

  const resetForm = useCallback(() => {
    setFormState(originalProvider.current);
    setFieldChanges({});
    setPendingUpdates({});

    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
      debounceTimer.current = null;
    }
  }, []);

  const commitChanges = useCallback(() => {
    setIsSaving(true);
    try {
      onUpdate(fieldChanges);
      originalProvider.current = { ...originalProvider.current, ...fieldChanges };
      setPendingUpdates(fieldChanges);
      setFieldChanges({});
    } finally {
      setIsSaving(false);
    }
  }, [fieldChanges, onUpdate]);

  const discardChanges = useCallback(() => {
    resetForm();
    onUpdate({});
  }, [resetForm, onUpdate]);

  const clearPendingUpdates = useCallback(() => {
    setPendingUpdates({});

    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
      debounceTimer.current = null;
    }
  }, []);

  return {
    formState,
    hasChanges,
    isDirty,
    fieldChanges,
    isSaving,
    pendingUpdates,
    setFieldValue,
    updateField,
    resetForm,
    commitChanges,
    discardChanges,
    clearPendingUpdates,
  };
}

/**
 * Debounced Callback Hook
 * 防抖回调，用于高频更新场景
 */
export function useDebouncedCallback<T extends (...args: any[]) => void>(
  callback: T,
  delay: number
): T {
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return useCallback((...args: Parameters<T>) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(() => {
      callback(...args);
    }, delay);
  }, [callback, delay]) as T;
}

/**
 * Field Validation Hook
 * 字段验证，支持实时验证和异步验证
 */
interface ValidationRule<T> {
  validate: (value: T) => boolean | Promise<boolean>;
  message: string;
}

interface UseFieldValidationReturn<T> {
  value: T;
  error: string | null;
  isValidating: boolean;
  isValid: boolean;
  setValue: (value: T) => void;
  validate: () => Promise<boolean>;
  reset: () => void;
}

export function useFieldValidation<T>(
  initialValue: T,
  rules: ValidationRule<T>[] = []
): UseFieldValidationReturn<T> {
  const [value, setValue] = useState<T>(initialValue);
  const [error, setError] = useState<string | null>(null);
  const [isValidating, setIsValidating] = useState(false);

  const validate = useCallback(async () => {
    setIsValidating(true);
    setError(null);

    for (const rule of rules) {
      const result = await rule.validate(value);
      if (!result) {
        setError(rule.message);
        setIsValidating(false);
        return false;
      }
    }

    setIsValidating(false);
    return true;
  }, [value, rules]);

  const isValid = error === null;

  const reset = useCallback(() => {
    setValue(initialValue);
    setError(null);
    setIsValidating(false);
  }, [initialValue]);

  return {
    value,
    error,
    isValidating,
    isValid,
    setValue,
    validate,
    reset,
  };
}

/**
 * Form Dirty Tracker
 * 追踪表单是否有未保存的更改
 */
export function useFormDirtyTracker(
  isDirty: boolean,
  onDirtyChange?: (isDirty: boolean) => void
) {
  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  return isDirty;
}
