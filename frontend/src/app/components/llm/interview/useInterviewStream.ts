import { useCallback, useRef, useState } from 'react';
import { getBackendInfo } from '@/api';
import type { TestEvent } from '../test/types';

export interface StreamEvent {
  type: string;
  data: Record<string, unknown>;
}

export interface InterviewStreamResult {
  sessionId: string;
  answer: string;
  output?: string;
  thinking?: string;
  latencyMs?: number;
  ok?: boolean;
  error?: string | null;
}

export interface UseInterviewStreamOptions {
  onEvent?: (event: TestEvent) => void;
  onStart?: (sessionId: string) => void;
  onComplete?: (result: InterviewStreamResult) => void;
  onError?: (error: string) => void;
}

export function useInterviewStream(options: UseInterviewStreamOptions = {}) {
  const { onEvent, onStart, onComplete, onError } = options;
  const [isStreaming, setIsStreaming] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const activeSessionIdRef = useRef<string | null>(null);

  const requestCancel = useCallback(async (sessionId: string) => {
    try {
      const backendInfo = await getBackendInfo();
      if (!backendInfo.baseUrl) return;

      await fetch(`${backendInfo.baseUrl}/llm/interview/cancel`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(backendInfo.token ? { Authorization: `Bearer ${backendInfo.token}` } : {}),
        },
        body: JSON.stringify({ session_id: sessionId }),
      });
    } catch {
      // ignore
    }
  }, []);

  const startStream = useCallback(async (payload: {
    roleId: string;
    providerId: string;
    model: string;
    question: string;
    expectedCriteria?: string[];
    expectsThinking?: boolean;
    sessionId?: string | null;
    context?: Array<{ question: string; answer: string }>;
  }) => {
    if (isStreaming) return;
    
    setIsStreaming(true);
    activeSessionIdRef.current = payload.sessionId ? String(payload.sessionId) : null;
    
    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    
    // Use fetch with ReadableStream for POST request
    // EventSource doesn't support POST, so we use fetch + ReadableStream
    abortControllerRef.current = new AbortController();
    
    try {
      const backendInfo = await getBackendInfo();
      if (!backendInfo.baseUrl) {
        throw new Error('Backend baseUrl missing.');
      }
      const response = await fetch(`${backendInfo.baseUrl}/llm/interview/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(backendInfo.token ? { Authorization: `Bearer ${backendInfo.token}` } : {}),
        },
        body: JSON.stringify({
          role: payload.roleId,
          provider_id: payload.providerId,
          model: payload.model,
          question: payload.question,
          criteria: payload.expectedCriteria,
          expects_thinking: payload.expectsThinking,
          session_id: payload.sessionId,
          context: payload.context,
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
      let finalResult: InterviewStreamResult | null = null;
      
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        // Process SSE messages
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer
        
        let currentEvent: string | null = null;
        let currentData = '';
        
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7);
          } else if (line.startsWith('data: ')) {
            currentData = line.slice(6);
          } else if (line === '' && currentEvent) {
            // End of event, process it
            try {
              const data = JSON.parse(currentData);
              
              switch (currentEvent) {
                case 'start':
                  if (typeof data.session_id === 'string' && data.session_id) {
                    activeSessionIdRef.current = data.session_id;
                    onStart?.(data.session_id);
                  }
                  onEvent?.({
                    type: 'stdout',
                    timestamp: new Date().toISOString(),
                    content: `Stream started: ${data.session_id}`,
                    details: { kind: 'start', ...data },
                  });
                  break;
                  
                case 'command':
                  onEvent?.({
                    type: 'command',
                    timestamp: new Date().toISOString(),
                    content: `${data.command} ${data.args?.join(' ') || ''}`,
                    details: data,
                  });
                  break;
                  
                case 'stdout':
                  onEvent?.({
                    type: 'stdout',
                    timestamp: new Date().toISOString(),
                    content: data.line || '',
                  });
                  break;
                  
                case 'stderr':
                  onEvent?.({
                    type: 'stderr',
                    timestamp: new Date().toISOString(),
                    content: data.line || '',
                  });
                  break;
                  
                case 'complete':
                  finalResult = data as InterviewStreamResult;
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
                  // Heartbeat, ignore
                  break;
                  
                default:
                  onEvent?.({
                    type: 'stdout',
                    timestamp: new Date().toISOString(),
                    content: `[${currentEvent}] ${JSON.stringify(data)}`,
                  });
              }
            } catch (e) {
              // Invalid JSON, ignore
            }
            
            currentEvent = null;
            currentData = '';
          }
        }
      }
      
      if (finalResult) {
        onComplete?.(finalResult);
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
      eventSourceRef.current = null;
      activeSessionIdRef.current = null;
    }
  }, [isStreaming, onEvent, onStart, onComplete, onError]);

  const stopStream = useCallback((sessionIdOverride?: string | null) => {
    abortControllerRef.current?.abort();
    const sessionId = sessionIdOverride ?? activeSessionIdRef.current;
    activeSessionIdRef.current = null;
    if (sessionId) {
      void requestCancel(sessionId);
    }
    setIsStreaming(false);
  }, [requestCancel]);

  return {
    isStreaming,
    startStream,
    stopStream,
  };
}
