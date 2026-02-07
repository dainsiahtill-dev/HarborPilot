import { useCallback, useEffect, useRef, useState } from 'react';
import { getBackendInfo } from '../../../../api';
import type { TestEvent } from '../../test/types';

export interface TestStreamEvent {
  type: string;
  data: Record<string, unknown>;
}

export interface TestSuiteStartEvent {
  suite: string;
}

export interface TestSuiteCompleteEvent {
  suite: string;
  result: {
    ok: boolean;
    details?: Record<string, unknown>;
  };
}

export interface TestCompleteEvent {
  schema_version: number;
  test_run_id: string;
  timestamp: string;
  target: {
    role: string;
    provider_id: string;
    model: string;
  };
  suites: Record<string, unknown>;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    estimated: boolean;
  };
  final: {
    ready: boolean;
    grade: string;
    next_action: string;
  };
}

export interface UseTestStreamOptions {
  onEvent?: (event: TestEvent) => void;
  onSuiteStart?: (suite: string) => void;
  onSuiteComplete?: (suite: string, result: { ok: boolean }) => void;
  onComplete?: (report: TestCompleteEvent) => void;
  onError?: (error: string) => void;
}

export function useTestStream(options: UseTestStreamOptions = {}) {
  const { onEvent, onSuiteStart, onSuiteComplete, onComplete, onError } = options;
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const startStream = useCallback(async (payload: {
    role: string;
    providerId: string;
    model: string;
    suites?: string[];
    testLevel?: string;
    evaluationMode?: string;
    apiKey?: string | null;
    envOverrides?: Record<string, string>;
  }) => {
    if (isStreaming) return;

    setIsStreaming(true);

    abortControllerRef.current = new AbortController();

    try {
      const backendInfo = await getBackendInfo();
      if (!backendInfo.baseUrl) {
        throw new Error('Backend baseUrl missing');
      }

      const response = await fetch(`${backendInfo.baseUrl}/llm/test/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(backendInfo.token ? { Authorization: `Bearer ${backendInfo.token}` } : {}),
        },
        body: JSON.stringify({
          role: payload.role,
          provider_id: payload.providerId,
          model: payload.model,
          suites: payload.suites || ['connectivity', 'response', 'qualification'],
          test_level: payload.testLevel || 'quick',
          evaluation_mode: payload.evaluationMode || 'provider',
          api_key: payload.apiKey,
          env_overrides: payload.envOverrides,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || `HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let currentEvent: string | null = null;
        let currentData = '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7);
          } else if (line.startsWith('data: ')) {
            currentData = line.slice(6);
          } else if (line === '' && currentEvent) {
            try {
              const data = JSON.parse(currentData);

              switch (currentEvent) {
                case 'start':
                  onEvent?.({
                    type: 'stdout',
                    timestamp: new Date().toISOString(),
                    content: `Test started: ${data.test_run_id || data.run_id}`,
                    details: data,
                  });
                  break;

                case 'suite_start':
                  if (data.suite) {
                    onSuiteStart?.(data.suite);
                    onEvent?.({
                      type: 'command',
                      timestamp: new Date().toISOString(),
                      content: `Starting suite: ${data.suite}`,
                      details: data,
                    });
                  }
                  break;

                case 'suite_complete':
                  if (data.suite && data.result) {
                    onSuiteComplete?.(data.suite, data.result);
                    onEvent?.({
                      type: data.result.ok ? 'result' : 'error',
                      timestamp: new Date().toISOString(),
                      content: `Suite ${data.suite}: ${data.result.ok ? 'PASS' : 'FAIL'}`,
                      details: data,
                    });
                  }
                  break;

                case 'suite_error':
                  onEvent?.({
                    type: 'error',
                    timestamp: new Date().toISOString(),
                    content: `Suite error: ${data.error || 'Unknown error'}`,
                    details: data,
                  });
                  break;

                case 'complete':
                  onComplete?.(data as TestCompleteEvent);
                  onEvent?.({
                    type: 'result',
                    timestamp: new Date().toISOString(),
                    content: `Test completed: ${data.final?.grade || 'UNKNOWN'}`,
                    details: data,
                  });
                  break;

                case 'error':
                  onEvent?.({
                    type: 'error',
                    timestamp: new Date().toISOString(),
                    content: data.error || 'Unknown error',
                  });
                  onError?.(data.error || 'Unknown error');
                  break;

                case 'ping':
                  break;

                default:
                  onEvent?.({
                    type: 'stdout',
                    timestamp: new Date().toISOString(),
                    content: `[${currentEvent}] ${JSON.stringify(data)}`,
                  });
              }
            } catch {
              // Invalid JSON, ignore
            }

            currentEvent = null;
            currentData = '';
          }
        }
      }
    } catch (error) {
      if (error instanceof Error && error.name !== 'AbortError') {
        onEvent?.({
          type: 'error',
          timestamp: new Date().toISOString(),
          content: error.message,
        });
        onError?.(error.message);
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }, [isStreaming, onEvent, onSuiteStart, onSuiteComplete, onComplete, onError]);

  const stopStream = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setIsStreaming(false);
  }, []);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  return {
    isStreaming,
    startStream,
    stopStream,
  };
}
