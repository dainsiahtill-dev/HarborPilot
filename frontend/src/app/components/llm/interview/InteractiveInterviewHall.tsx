import { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, AlertTriangle, Loader2, Send, RefreshCw, Check, XCircle, Eraser } from 'lucide-react';
import type { InterviewProviderSummary, InterviewRoleSummary } from './InterviewHall';
import { TerminalOutput } from '../test/TerminalOutput';
import { useTestEvents } from '../test/hooks/useTestEvents';
import type { TestEvent } from '../test/types';
import { RealtimeThinkingDisplay } from './RealtimeThinkingDisplay';
import { useInterviewStream, type RealtimeThinkingEvent } from './useInterviewStream';

type RoleId = 'pm' | 'director' | 'qa' | 'docs';

export interface QuestionTemplate {
  id: string;
  category: string;
  title: string;
  question: string;
  expectedCriteria: string[];
  difficulty: 'basic' | 'intermediate' | 'advanced';
  role: RoleId;
}

export interface InterviewMessage {
  id: string;
  type: 'question' | 'answer' | 'system';
  content: string;
  timestamp: string;
  sender: 'user' | 'model';
  questionId?: string;
  question?: string;
  expectedCriteria?: string[];
  thinking?: string;
  evaluation?: {
    userRating: 'pass' | 'fail' | 'pending';
    notes?: string;
    criteriaAssessment?: Record<string, boolean>;
  };
}

export interface InteractiveInterviewReport {
  id: string;
  role: RoleId;
  provider: {
    id: string;
    name: string;
    model: string;
  };
  startTime: string;
  endTime: string;
  overallStatus: 'passed' | 'failed';
  questions: Array<{
    question: string;
    answer: string;
    evaluation?: InterviewMessage['evaluation'];
    expectedCriteria?: string[];
  }>;
  summary: {
    totalQuestions: number;
    passedQuestions: number;
    averageRating: number;
    strengths: string[];
    weaknesses: string[];
    recommendation: string;
  };
  userNotes: string;
}

export interface InteractiveInterviewAnswer {
  sessionId: string;
  answer: string;
  output?: string;
  thinking?: string;
  latencyMs?: number;
  ok?: boolean;
  error?: string | null;
  debug?: {
    prompt?: string;
    cli_args?: string[] | null;
    cli_send_prompt?: boolean | null;
    stdin_prompt?: string | null;
    cli_command?: string | null;
    debug_steps?: string[];
    debug_stream_output?: string[];
  };
}

interface InteractiveInterviewHallProps {
  roles: InterviewRoleSummary[];
  providers: InterviewProviderSummary[];
  selectedRole: RoleId | null;
  selectedProvider: string | null;
  selectedModel: string | null;
  onSelectRole: (role: RoleId) => void;
  onSelectProvider: (providerId: string) => void;
  onAskQuestion: (payload: {
    roleId: RoleId;
    providerId: string;
    question: string;
    expectedCriteria?: string[];
    expectsThinking?: boolean;
    sessionId?: string | null;
    context?: Array<{ question: string; answer: string }>;
    debug?: boolean;
  }) => Promise<InteractiveInterviewAnswer | null>;
  onSaveReport: (payload: {
    roleId: RoleId;
    providerId: string;
    report: InteractiveInterviewReport;
  }) => Promise<{ saved: boolean; report_path?: string } | null>;
  resolveEnvOverrides?: (providerId: string) => Promise<Record<string, string> | null>;
}

const ROLE_BADGES: Record<string, string> = {
  pm: 'bg-cyan-500/20 text-cyan-200 border-cyan-500/30',
  director: 'bg-emerald-500/20 text-emerald-200 border-emerald-500/30',
  qa: 'bg-blue-500/20 text-blue-200 border-blue-500/30',
  docs: 'bg-amber-500/20 text-amber-200 border-amber-500/30'
};

const STATUS_STYLES: Record<string, { border: string; bg: string; dot: string; text: string }> = {
  ready: {
    border: 'border-emerald-500/40',
    bg: 'bg-emerald-500/10',
    dot: 'bg-emerald-400',
    text: 'text-emerald-300'
  },
  failed: {
    border: 'border-rose-500/40',
    bg: 'bg-rose-500/10',
    dot: 'bg-rose-400',
    text: 'text-rose-300'
  },
  testing: {
    border: 'border-cyan-500/40',
    bg: 'bg-cyan-500/10',
    dot: 'bg-cyan-300',
    text: 'text-cyan-200'
  },
  untested: {
    border: 'border-white/10',
    bg: 'bg-white/5',
    dot: 'bg-white/40',
    text: 'text-text-dim'
  }
};

const STATUS_LABELS: Record<string, string> = {
  ready: '连通通过',
  failed: '连通失败',
  testing: '测试中',
  untested: '未测试'
};

const SESSION_STATUS: Record<'idle' | 'running' | 'success' | 'failed', { label: string; badge: string }> = {
  idle: { label: '待命', badge: 'bg-gray-500/20 text-gray-300 border-gray-500/30' },
  running: { label: '进行中', badge: 'bg-cyan-500/20 text-cyan-200 border-cyan-500/30' },
  success: { label: '完成', badge: 'bg-emerald-500/20 text-emerald-200 border-emerald-500/30' },
  failed: { label: '失败', badge: 'bg-red-500/20 text-red-200 border-red-500/30' }
};

const QUESTION_TEMPLATES: QuestionTemplate[] = [
  {
    id: 'pm-project-analysis',
    category: '项目规划类',
    title: '项目需求分析',
    question: '请分析这个项目需求并制定实施计划，包括时间安排、资源分配和风险评估。',
    expectedCriteria: ['分析深度', '计划完整性', '风险评估'],
    difficulty: 'intermediate',
    role: 'pm'
  },
  {
    id: 'pm-conflict-resolution',
    category: '冲突协调类',
    title: '技术分歧协调',
    question: '开发团队在前端技术选型上出现分歧，作为PM你如何协调解决？请说明具体步骤和考虑因素。',
    expectedCriteria: ['思考过程', '解决方案', '沟通策略'],
    difficulty: 'advanced',
    role: 'pm'
  },
  {
    id: 'director-architecture',
    category: '架构决策类',
    title: '架构方案选择',
    question: '如果需要在稳定性和交付速度之间权衡，你会如何做架构决策？请给出判断依据。',
    expectedCriteria: ['技术分析', '权衡取舍', '风险评估'],
    difficulty: 'advanced',
    role: 'director'
  },
  {
    id: 'director-code-review',
    category: '代码审查类',
    title: '代码质量改进',
    question: '请说明你在代码审查中如何发现高风险问题，并提出改进建议。',
    expectedCriteria: ['问题识别', '改进方案', '质量标准'],
    difficulty: 'intermediate',
    role: 'director'
  },
  {
    id: 'qa-test-strategy',
    category: '测试策略类',
    title: '测试计划制定',
    question: '面对一个迭代频繁的项目，你会如何制定测试策略以确保质量？',
    expectedCriteria: ['测试覆盖', '风险识别', '执行策略'],
    difficulty: 'intermediate',
    role: 'qa'
  },
  {
    id: 'qa-defect-analysis',
    category: '缺陷分析类',
    title: '线上故障复盘',
    question: '线上出现严重缺陷时，你会如何定位原因并推动修复？',
    expectedCriteria: ['问题定位', '根因分析', '协作推进'],
    difficulty: 'advanced',
    role: 'qa'
  },
  {
    id: 'docs-guide',
    category: '文档编写类',
    title: '功能说明文档',
    question: '请为一个新功能编写简明的使用说明，包含前置条件与操作步骤。',
    expectedCriteria: ['文档完整性', '表达清晰度', '可操作性'],
    difficulty: 'basic',
    role: 'docs'
  },
  {
    id: 'docs-onboarding',
    category: '用户引导类',
    title: '快速上手指南',
    question: '你会如何设计一个新用户的快速上手指南？请说明结构与重点。',
    expectedCriteria: ['结构设计', '用户视角', '示例准确性'],
    difficulty: 'intermediate',
    role: 'docs'
  }
];

const createMessageId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const normalizeCriteriaAssessment = (
  criteria: string[],
  current?: Record<string, boolean>
) => {
  const next: Record<string, boolean> = { ...(current || {}) };
  criteria.forEach((item) => {
    if (typeof next[item] !== 'boolean') {
      next[item] = false;
    }
  });
  return next;
};

export function InteractiveInterviewHall({
  roles,
  providers,
  selectedRole,
  selectedProvider,
  selectedModel,
  onSelectRole,
  onSelectProvider,
  onAskQuestion,
  onSaveReport,
  resolveEnvOverrides
}: InteractiveInterviewHallProps) {
  const [messages, setMessages] = useState<InterviewMessage[]>([]);
  const [customQuestion, setCustomQuestion] = useState('');
  const [quickQuestion, setQuickQuestion] = useState('');
  const [responding, setResponding] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [view, setView] = useState<'interview' | 'report'>('interview');
  const [report, setReport] = useState<InteractiveInterviewReport | null>(null);
  const [reportSavedPath, setReportSavedPath] = useState<string | null>(null);
  const [userNotes, setUserNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [sessionStatus, setSessionStatus] = useState<'idle' | 'running' | 'success' | 'failed'>('idle');
  const { events: sessionEvents, addEvent: addSessionEvent, resetEvents: resetSessionEvents } = useTestEvents();
  const [thinkingEvents, setThinkingEvents] = useState<RealtimeThinkingEvent[]>([]);
  const [debugMode, setDebugMode] = useState(false);
  const [useStreamingMode, setUseStreamingMode] = useState(true); // Enable streaming by default
  const handleThinkingEvent = useCallback((event: RealtimeThinkingEvent) => {
    setThinkingEvents((prev) => {
      const next = [...prev];
      const existingIndex = next.findIndex(
        (item) => item.id === event.id && item.kind === event.kind
      );
      if (existingIndex >= 0) {
        next[existingIndex] = { ...next[existingIndex], ...event };
        return next;
      }
      next.push(event);
      const maxEvents = 200;
      if (next.length <= maxEvents) return next;
      return next.slice(next.length - maxEvents);
    });
  }, []);
  const clearThinkingEvents = useCallback(() => setThinkingEvents([]), []);

  const { isStreaming: isStreamConnecting, startStream, stopStream } = useInterviewStream({
    onEvent: (event) => {
      pushSessionEvent(event);
    },
    onThinkingEvent: handleThinkingEvent,
    onStart: (streamSessionId) => {
      if (!sessionId) {
        setSessionId(streamSessionId);
      }
    },
    onComplete: (result) => {
      if (result.sessionId && !sessionId) {
        setSessionId(result.sessionId);
      }
      
      const answerMessage: InterviewMessage = {
        id: createMessageId(),
        type: 'answer',
        content: result.answer || result.output || '',
        timestamp: new Date().toISOString(),
        sender: 'model',
        thinking: result.thinking,
        evaluation: {
          userRating: 'pending',
          notes: '',
          criteriaAssessment: {}
        }
      };
      setMessages((prev) => [...prev, answerMessage]);
      
      if (result.ok === false) {
        setError(result.error || '模型返回失败');
        setSessionStatus('failed');
      } else {
        setSessionStatus('success');
        pushSessionEvent({
          type: 'result',
          timestamp: new Date().toISOString(),
          content: '已收到模型响应'
        });
      }
      setResponding(false);
    },
    onError: (error) => {
      setError(error);
      setSessionStatus('failed');
      setResponding(false);
    }
  });

  const activeRole = roles.find((role) => role.id === selectedRole);
  const activeProvider = providers.find((provider) => provider.id === selectedProvider);

  const templatesByCategory = useMemo(() => {
    const scoped = QUESTION_TEMPLATES.filter(
      (template) => !selectedRole || template.role === selectedRole
    );
    const grouped = new Map<string, QuestionTemplate[]>();
    scoped.forEach((template) => {
      const list = grouped.get(template.category) || [];
      list.push(template);
      grouped.set(template.category, list);
    });
    return Array.from(grouped.entries());
  }, [selectedRole]);

  const answerMessages = useMemo(
    () => messages.filter((message) => message.type === 'answer'),
    [messages]
  );
  const qaPairs = useMemo(() => {
    const pairs: Array<{ question: InterviewMessage | null; answer: InterviewMessage | null }> = [];
    let pendingQuestion: InterviewMessage | null = null;
    messages.forEach((message) => {
      if (message.type === 'question') {
        if (pendingQuestion) {
          pairs.push({ question: pendingQuestion, answer: null });
        }
        pendingQuestion = message;
        return;
      }
      if (message.type === 'answer') {
        if (pendingQuestion) {
          pairs.push({ question: pendingQuestion, answer: message });
          pendingQuestion = null;
          return;
        }
        pairs.push({ question: null, answer: message });
        return;
      }
      pairs.push({ question: null, answer: message });
    });
    if (pendingQuestion) {
      pairs.push({ question: pendingQuestion, answer: null });
    }
    return pairs;
  }, [messages]);
  const thinkingEnabled = debugMode && useStreamingMode;
  const showThinkingPanel = thinkingEnabled || thinkingEvents.length > 0;
  const hasPendingEvaluation = answerMessages.some(
    (message) => !message.evaluation || message.evaluation.userRating === 'pending'
  );
  const passedAnswers = answerMessages.filter(
    (message) => message.evaluation?.userRating === 'pass'
  ).length;
  const canFinalize = answerMessages.length > 0 && !hasPendingEvaluation && !responding;

  useEffect(() => {
    void stopStream();
    setResponding(false);
    setMessages([]);
    setSessionId(null);
    setReport(null);
    setReportSavedPath(null);
    setView('interview');
    setError(null);
    setCustomQuestion('');
    setQuickQuestion('');
    setUserNotes('');
    setSessionStatus('idle');
    resetSessionEvents();
    clearThinkingEvents();
    setDebugMode(false);
    setUseStreamingMode(true);
  }, [clearThinkingEvents, resetSessionEvents, selectedRole, selectedProvider, stopStream]);

  useEffect(() => {
    return () => {
      void stopStream();
    };
  }, [stopStream]);

  const buildContext = (): Array<{ question: string; answer: string }> => {
    return answerMessages.slice(-3).map((message) => ({
      question: message.question || '',
      answer: message.content
    }));
  };

  const stringifyEventPayload = (payload: unknown, limit = 4000) => {
    try {
      const text = typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2);
      if (text.length <= limit) return text;
      return `${text.slice(0, limit)}...`;
    } catch {
      return String(payload);
    }
  };

  const pushSessionEvent = (event: TestEvent) => {
    addSessionEvent(event);
  };

  const clearSessionEvents = () => {
    resetSessionEvents();
    setSessionStatus('idle');
  };

  const handleSendQuestion = async (template?: QuestionTemplate, directQuestion?: string) => {
    if (!selectedRole || !selectedProvider) {
      setError('请先选择岗位与模型');
      return;
    }
    const question = (template?.question || directQuestion || customQuestion).trim();
    if (!question) return;

    setError(null);
    setSessionStatus('running');
    pushSessionEvent({
      type: 'command',
      timestamp: new Date().toISOString(),
      content: `POST /llm/interview/ask ${stringifyEventPayload({
        role: selectedRole,
        provider_id: selectedProvider,
        model: selectedModel,
        question
      })}`
    });
    pushSessionEvent({
      type: 'stdout',
      timestamp: new Date().toISOString(),
      content: '发送面试问题...'
    });
    const questionMessage: InterviewMessage = {
      id: createMessageId(),
      type: 'question',
      content: question,
      timestamp: new Date().toISOString(),
      sender: 'user',
      questionId: template?.id,
      expectedCriteria: template?.expectedCriteria
    };
    setMessages((prev) => [...prev, questionMessage]);
    if (!template && !directQuestion) {
      setCustomQuestion('');
    }
    if (directQuestion) {
      setQuickQuestion('');
    }

    setResponding(true);
    
    // Use streaming mode if enabled (for real-time output)
    if (useStreamingMode && debugMode) {
      pushSessionEvent({
        type: 'stdout',
        timestamp: new Date().toISOString(),
        content: 'Using streaming mode for real-time output...'
      });
      
      const streamSessionId = sessionId || `interactive-${createMessageId()}`;
      if (!sessionId) {
        setSessionId(streamSessionId);
      }

      let envOverrides: Record<string, string> | null = null;
      if (resolveEnvOverrides) {
        try {
          envOverrides = await resolveEnvOverrides(selectedProvider);
        } catch {
          envOverrides = null;
        }
      }

      await startStream({
        roleId: selectedRole,
        providerId: selectedProvider,
        model: selectedModel || '',
        question,
        expectedCriteria: template?.expectedCriteria,
        expectsThinking: template ? template.difficulty !== 'basic' : undefined,
        sessionId: streamSessionId,
        context: buildContext(),
        envOverrides: envOverrides || undefined,
      });
      return;
    }
    
    // Standard non-streaming mode
    try {
      const response = await onAskQuestion({
        roleId: selectedRole,
        providerId: selectedProvider,
        question,
        expectedCriteria: template?.expectedCriteria,
        expectsThinking: template ? template.difficulty !== 'basic' : undefined,
        sessionId,
        context: buildContext(),
        debug: debugMode
      });
      if (!response) {
        setResponding(false);
        setSessionStatus('failed');
        pushSessionEvent({
          type: 'error',
          timestamp: new Date().toISOString(),
          content: '未收到模型响应'
        });
        return;
      }
      if (response.sessionId && !sessionId) {
        setSessionId(response.sessionId);
      }
      pushSessionEvent({
        type: 'response',
        timestamp: new Date().toISOString(),
        content: stringifyEventPayload(response)
      });
      const debugPayload = response.debug;
      if (debugMode && debugPayload?.prompt) {
        pushSessionEvent({
          type: 'stdout',
          timestamp: new Date().toISOString(),
          content: `PROMPT\\n${debugPayload.prompt}`
        });
      }
      if (debugMode && typeof debugPayload?.cli_send_prompt === 'boolean') {
        pushSessionEvent({
          type: 'stdout',
          timestamp: new Date().toISOString(),
          content: `PROMPT MODE\\n${debugPayload.cli_send_prompt ? 'stdin' : 'argv'}`
        });
      }
      if (debugMode && debugPayload?.cli_command) {
        pushSessionEvent({
          type: 'stdout',
          timestamp: new Date().toISOString(),
          content: `CLI COMMAND\\n${debugPayload.cli_command}`
        });
      }
      if (debugMode && debugPayload?.cli_args && debugPayload.cli_args.length > 0) {
        pushSessionEvent({
          type: 'stdout',
          timestamp: new Date().toISOString(),
          content: `CLI ARGS\\n${JSON.stringify(debugPayload.cli_args)}`
        });
      }
      if (debugMode && debugPayload?.stdin_prompt) {
        pushSessionEvent({
          type: 'stdout',
          timestamp: new Date().toISOString(),
          content: `STDIN PROMPT\\n${debugPayload.stdin_prompt}`
        });
      }
      // Show detailed execution steps
      if (debugMode && debugPayload?.debug_steps && Array.isArray(debugPayload.debug_steps)) {
        debugPayload.debug_steps.forEach((step: string) => {
          pushSessionEvent({
            type: 'stdout',
            timestamp: new Date().toISOString(),
            content: `STEP: ${step}`
          });
        });
      }
      // Show streaming output (real-time CLI output)
      if (debugMode && debugPayload?.debug_stream_output && Array.isArray(debugPayload.debug_stream_output)) {
        pushSessionEvent({
          type: 'stdout',
          timestamp: new Date().toISOString(),
          content: '--- STREAM OUTPUT START ---'
        });
        debugPayload.debug_stream_output.forEach((line: string) => {
          pushSessionEvent({
            type: 'stdout',
            timestamp: new Date().toISOString(),
            content: line
          });
        });
        pushSessionEvent({
          type: 'stdout',
          timestamp: new Date().toISOString(),
          content: '--- STREAM OUTPUT END ---'
        });
      }
      const answerMessage: InterviewMessage = {
        id: createMessageId(),
        type: 'answer',
        content: response.answer || response.output || '',
        timestamp: new Date().toISOString(),
        sender: 'model',
        questionId: template?.id,
        question,
        expectedCriteria: template?.expectedCriteria,
        thinking: response.thinking,
        evaluation: {
          userRating: 'pending',
          notes: '',
          criteriaAssessment: normalizeCriteriaAssessment(template?.expectedCriteria || [])
        }
      };
      setMessages((prev) => [...prev, answerMessage]);
      if (response.ok === false) {
        setError(response.error || '模型返回失败');
        setSessionStatus('failed');
        pushSessionEvent({
          type: 'error',
          timestamp: new Date().toISOString(),
          content: response.error || '模型返回失败'
        });
      } else {
        setSessionStatus('success');
        pushSessionEvent({
          type: 'result',
          timestamp: new Date().toISOString(),
          content: '已收到模型响应'
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '发送问题失败');
      setSessionStatus('failed');
      pushSessionEvent({
        type: 'error',
        timestamp: new Date().toISOString(),
        content: err instanceof Error ? err.message : '发送问题失败'
      });
    } finally {
      setResponding(false);
    }
  };

  const updateEvaluation = (messageId: string, updates: Partial<InterviewMessage['evaluation']>) => {
    setMessages((prev) =>
      prev.map((message) => {
        if (message.id !== messageId || message.type !== 'answer') {
          return message;
        }
        return {
          ...message,
          evaluation: {
            userRating: 'pending',
            notes: '',
            criteriaAssessment: normalizeCriteriaAssessment(message.expectedCriteria || []),
            ...(message.evaluation || {}),
            ...updates
          }
        };
      })
    );
  };

  const analyzePerformance = (answers: InterviewMessage[]) => {
    const stats = new Map<string, { pass: number; total: number }>();
    answers.forEach((message) => {
      const criteria = message.expectedCriteria || [];
      const assessment = message.evaluation?.criteriaAssessment || {};
      criteria.forEach((item) => {
        const entry = stats.get(item) || { pass: 0, total: 0 };
        entry.total += 1;
        if (assessment[item]) {
          entry.pass += 1;
        }
        stats.set(item, entry);
      });
    });
    const scored = Array.from(stats.entries()).map(([key, value]) => ({
      key,
      rate: value.total ? value.pass / value.total : 0
    }));
    scored.sort((a, b) => b.rate - a.rate);
    const strengths = scored.slice(0, 3).map((item) => item.key);
    const weaknesses = scored.slice(-3).map((item) => item.key).filter(Boolean);
    return { strengths, weaknesses };
  };

  const buildReport = (overallStatus: 'passed' | 'failed'): InteractiveInterviewReport => {
    const startTime = messages[0]?.timestamp || new Date().toISOString();
    const endTime = new Date().toISOString();
    const questions = answerMessages.map((message) => ({
      question: message.question || '',
      answer: message.content,
      evaluation: message.evaluation,
      expectedCriteria: message.expectedCriteria
    }));
    const passedQuestions = answerMessages.filter(
      (message) => message.evaluation?.userRating === 'pass'
    ).length;
    const totalQuestions = answerMessages.length || 1;
    const { strengths, weaknesses } = analyzePerformance(answerMessages);
    return {
      id: sessionId || createMessageId(),
      role: selectedRole || 'pm',
      provider: {
        id: selectedProvider || '',
        name: activeProvider?.name || selectedProvider || 'Unknown',
        model: selectedModel || activeProvider?.model || 'unknown'
      },
      startTime,
      endTime,
      overallStatus,
      questions,
      summary: {
        totalQuestions,
        passedQuestions,
        averageRating: passedQuestions / totalQuestions,
        strengths,
        weaknesses,
        recommendation: overallStatus === 'passed' ? '建议通过面试' : '建议进一步提升后重试'
      },
      userNotes
    };
  };

  const finalizeInterview = async (status: 'passed' | 'failed') => {
    if (!selectedRole || !selectedProvider) return;
    const nextReport = buildReport(status);
    setReport(nextReport);
    setView('report');
    setSaving(true);
    pushSessionEvent({
      type: 'command',
      timestamp: new Date().toISOString(),
      content: `POST /llm/interview/save ${stringifyEventPayload({
        role: selectedRole,
        provider_id: selectedProvider,
        model: selectedModel,
        status
      })}`
    });
    pushSessionEvent({
      type: 'stdout',
      timestamp: new Date().toISOString(),
      content: '保存面试报告...'
    });
    try {
      const result = await onSaveReport({
        roleId: selectedRole,
        providerId: selectedProvider,
        report: nextReport
      });
      if (result?.report_path) {
        setReportSavedPath(result.report_path);
        pushSessionEvent({
          type: 'result',
          timestamp: new Date().toISOString(),
          content: `报告已保存: ${result.report_path}`
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存面试报告失败');
      pushSessionEvent({
        type: 'error',
        timestamp: new Date().toISOString(),
        content: err instanceof Error ? err.message : '保存面试报告失败'
      });
    } finally {
      setSaving(false);
    }
  };

  const resetInterview = () => {
    const runId = sessionId;
    void stopStream(runId);
    setMessages([]);
    setResponding(false);
    setSessionId(null);
    setReport(null);
    setReportSavedPath(null);
    setView('interview');
    setError(null);
    setCustomQuestion('');
    setQuickQuestion('');
    setUserNotes('');
    setSessionStatus('idle');
    setDebugMode(false);
    setUseStreamingMode(true);
    resetSessionEvents();
    clearThinkingEvents();
  };

  if (view === 'report' && report) {
    return (
      <div className="rounded-2xl border border-emerald-500/20 bg-black/30 p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-wide text-text-dim">Interactive Interview Report</div>
            <h3 className="text-lg font-semibold text-text-main">面试报告 · {activeRole?.label || report.role}</h3>
            <div className="text-[11px] text-text-dim">
              模型：{report.provider.name} • {report.provider.model}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {report.overallStatus === 'passed' ? (
              <span className="px-2 py-1 text-[10px] uppercase font-semibold rounded border bg-emerald-500/20 text-emerald-200 border-emerald-500/30">
                Passed
              </span>
            ) : (
              <span className="px-2 py-1 text-[10px] uppercase font-semibold rounded border bg-amber-500/20 text-amber-200 border-amber-500/30">
                Failed
              </span>
            )}
            <button
              onClick={resetInterview}
              className="px-3 py-1.5 text-[10px] border border-white/10 rounded hover:border-white/30 flex items-center gap-1"
            >
              <RefreshCw className="size-3" />
              重新开始
            </button>
          </div>
        </div>

        {saving ? (
          <div className="text-[11px] text-text-dim flex items-center gap-2">
            <Loader2 className="size-3 animate-spin" />
            正在保存面试报告...
          </div>
        ) : reportSavedPath ? (
          <div className="text-[11px] text-emerald-300">报告已保存：{reportSavedPath}</div>
        ) : null}
        {error ? (
          <div className="text-[11px] text-red-200 bg-red-500/10 border border-red-500/20 rounded p-2">
            {error}
          </div>
        ) : null}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div className="rounded-lg border border-white/10 bg-black/20 p-3">
            <div className="text-[10px] uppercase tracking-wide text-text-dim mb-1">总问题数</div>
            <div className="text-text-main font-semibold">{report.summary.totalQuestions}</div>
          </div>
          <div className="rounded-lg border border-white/10 bg-black/20 p-3">
            <div className="text-[10px] uppercase tracking-wide text-text-dim mb-1">通过问题</div>
            <div className="text-text-main font-semibold">{report.summary.passedQuestions}</div>
          </div>
          <div className="rounded-lg border border-white/10 bg-black/20 p-3">
            <div className="text-[10px] uppercase tracking-wide text-text-dim mb-1">平均评分</div>
            <div className="text-text-main font-semibold">
              {Math.round(report.summary.averageRating * 100)}%
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-white/10 bg-black/20 p-4 text-xs space-y-2">
          <div className="text-[10px] uppercase tracking-wide text-text-dim">总结</div>
          <div className="text-text-main">推荐：{report.summary.recommendation}</div>
          {report.summary.strengths.length > 0 ? (
            <div className="text-text-dim">优势：{report.summary.strengths.join('、')}</div>
          ) : null}
          {report.summary.weaknesses.length > 0 ? (
            <div className="text-text-dim">待提升：{report.summary.weaknesses.join('、')}</div>
          ) : null}
          {report.userNotes ? (
            <div className="text-text-dim">备注：{report.userNotes}</div>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 h-full min-h-0">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs text-text-dim uppercase tracking-wide">Interactive Interview</div>
          <h3 className="text-lg font-semibold text-text-main">交互式面试大厅</h3>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-text-dim">
          <CheckCircle2 className="size-4 text-emerald-300" />
          用户主导提问与评估
        </div>
      </div>

      {/* Main content area - 响应式布局 */}
      <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_1.2fr_1.5fr_1fr] gap-6 flex-1 min-h-0">
        {/* Left Panel - Role Selection */}
        <div className="grid grid-rows-[auto_1fr_auto_1fr] gap-4 min-h-0">
          <div className="text-xs font-semibold text-text-main uppercase tracking-wide">🎯 面试岗位</div>
          <div className="space-y-2 min-h-0 overflow-auto pr-1">
            {roles.map((role) => {
              const isActive = role.id === selectedRole;
              const badge = ROLE_BADGES[role.id] || 'bg-white/10 text-text-main border-white/20';
              return (
                <button
                  key={role.id}
                  onClick={() => onSelectRole(role.id)}
                  className={`w-full text-left rounded-xl border p-4 transition-all ${
                    isActive
                      ? 'border-cyan-400/60 bg-cyan-500/10'
                      : 'border-white/10 bg-white/5 hover:border-white/20'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-1 text-[10px] uppercase font-semibold rounded border ${badge}`}>
                        {role.label}
                      </span>
                      {role.readiness?.ready ? (
                        <CheckCircle2 className="size-4 text-emerald-400" />
                      ) : (
                        <AlertTriangle className="size-4 text-amber-300" />
                      )}
                    </div>
                    <div className="text-[10px] text-text-dim uppercase tracking-wide">
                      {role.requiresThinking ? 'Thinking Required' : 'Thinking Optional'}
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-text-dim">{role.description}</div>
                </button>
              );
            })}
          </div>

          <div className="text-xs font-semibold text-text-main uppercase tracking-wide">🤖 模型选择</div>
          <div className="space-y-2 min-h-0 overflow-auto pr-1">
            {providers.map((provider) => {
              const isActive = provider.id === selectedProvider;
              const styles = STATUS_STYLES[provider.status] || STATUS_STYLES.untested;
              return (
                <button
                  key={provider.id}
                  onClick={() => onSelectProvider(provider.id)}
                  className={`w-full text-left rounded-xl border p-3 transition-all ${
                    isActive
                      ? 'border-emerald-400/50 bg-emerald-500/10'
                      : `${styles.border} ${styles.bg} hover:border-white/20`
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs text-text-main font-semibold">{provider.name}</div>
                      <div className="text-[10px] text-text-dim">{provider.model || '未设置模型'}</div>
                    </div>
                    <span className={`text-[9px] uppercase px-2 py-0.5 rounded border ${styles.border} ${styles.text}`}>
                      {STATUS_LABELS[provider.status]}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Second Panel - Question Templates */}
        <div className="flex flex-col gap-4 min-h-0">
          <div className="text-xs font-semibold text-text-main uppercase tracking-wide">📋 问题模板库</div>
          <div className="space-y-3 flex-1 min-h-0 overflow-auto pr-1">
            {templatesByCategory.length === 0 ? (
              <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-xs text-text-dim">
                请选择岗位以显示对应问题模板。
              </div>
            ) : (
              templatesByCategory.map(([category, templates]) => (
                <div key={category} className="rounded-xl border border-white/10 bg-white/5 p-3 space-y-2">
                  <div className="text-[11px] font-semibold text-text-main">{category}</div>
                  <div className="space-y-2">
                    {templates.map((template) => (
                      <button
                        key={template.id}
                        onClick={() => handleSendQuestion(template)}
                        disabled={responding}
                        className="w-full text-left text-[11px] px-3 py-2 rounded border border-white/10 bg-black/40 hover:border-cyan-400/40 disabled:opacity-60"
                      >
                        <div className="text-text-main font-semibold">{template.title}</div>
                        <div className="text-text-dim mt-1">{template.question}</div>
                      </button>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="rounded-xl border border-white/10 bg-black/30 p-4 space-y-3">
            <div className="text-xs font-semibold text-text-main uppercase tracking-wide">➕ 自定义问题</div>
            <textarea
              value={customQuestion}
              onChange={(event) => setCustomQuestion(event.target.value)}
              placeholder="输入自定义面试问题..."
              rows={3}
              className="w-full rounded-lg border border-white/10 bg-black/40 p-2 text-xs text-text-main"
            />
            <button
              onClick={() => handleSendQuestion()}
              disabled={responding || !customQuestion.trim()}
              className="w-full px-3 py-2 text-[11px] font-semibold bg-cyan-500/80 hover:bg-cyan-500 text-white rounded transition-colors disabled:opacity-60 flex items-center justify-center gap-1"
            >
              <Send className="size-3" />
              {responding ? '发送中...' : '发送问题'}
            </button>
          </div>
        </div>

        {/* Center Panel - Real-time Conversation */}
        <div className="flex flex-col gap-4 min-h-0">
          <div className="text-xs font-semibold text-text-main uppercase tracking-wide">💬 实时对话区</div>
          <div className="rounded-xl border border-white/10 bg-black/30 p-4 space-y-3 flex-1 min-h-0 flex flex-col">
            <div className="text-[11px] text-text-dim flex-shrink-0">
              当前组合：{activeRole?.label || '未选择'} / {activeProvider?.name || '未选择'}{' '}
              {selectedModel ? `• ${selectedModel}` : ''}
            </div>

            {showThinkingPanel ? (
              <RealtimeThinkingDisplay
                events={thinkingEvents}
                enabled={thinkingEnabled}
                isStreaming={responding && thinkingEnabled}
                onClear={clearThinkingEvents}
                className="flex-shrink-0"
              />
            ) : null}

            {messages.length === 0 ? (
              <div className="text-xs text-text-dim flex-1 flex items-center justify-center">暂无对话记录，请从左侧选择问题。</div>
            ) : (
              <div className="space-y-3 flex-1 min-h-0 overflow-auto pr-2">
                {qaPairs.map((pair, index) => {
                  const question = pair.question;
                  const answer = pair.answer;
                  const criteria = answer?.expectedCriteria || question?.expectedCriteria || [];
                  return (
                  <div
                    key={question?.id || answer?.id || `qa-${index}`}
                    className="rounded-lg border border-white/10 bg-white/5 p-3 text-xs flex-shrink-0 space-y-3"
                  >
                    <div className="text-[10px] uppercase tracking-wide text-text-dim">
                      问答 {index + 1}
                    </div>

                    {question ? (
                      <div className="rounded-md border border-cyan-500/20 bg-cyan-500/5 p-3">
                        <div className="text-[10px] uppercase tracking-wide text-text-dim mb-1">Question</div>
                        <div className="text-text-main whitespace-pre-wrap">{question.content}</div>
                      </div>
                    ) : null}

                    {answer ? (
                      <div className="rounded-md border border-emerald-500/20 bg-emerald-500/5 p-3 space-y-2">
                        <div className="text-[10px] uppercase tracking-wide text-text-dim mb-1">Answer</div>
                        <div className="text-text-main whitespace-pre-wrap">{answer.content}</div>
                        {answer.thinking ? (
                          <div className="text-[11px] text-text-dim whitespace-pre-wrap">
                            <span className="text-[10px] uppercase tracking-wide">Thinking</span>
                            <div>{answer.thinking}</div>
                          </div>
                        ) : null}

                        <div className="space-y-2">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => updateEvaluation(answer.id, { userRating: 'pass' })}
                              className={`px-2 py-1 text-[10px] rounded border ${
                                answer.evaluation?.userRating === 'pass'
                                  ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200'
                                  : 'border-white/10 text-text-dim'
                              }`}
                            >
                              <Check className="size-3 inline-block mr-1" />
                              通过
                            </button>
                            <button
                              onClick={() => updateEvaluation(answer.id, { userRating: 'fail' })}
                              className={`px-2 py-1 text-[10px] rounded border ${
                                answer.evaluation?.userRating === 'fail'
                                  ? 'border-rose-500/40 bg-rose-500/10 text-rose-200'
                                  : 'border-white/10 text-text-dim'
                              }`}
                            >
                              <XCircle className="size-3 inline-block mr-1" />
                              失败
                            </button>
                          </div>

                          {criteria.length > 0 ? (
                            <div className="space-y-1 text-[10px] text-text-dim">
                              <div className="uppercase tracking-wide">评估指标</div>
                              <div className="flex flex-wrap gap-2">
                                {criteria.map((item) => (
                                  <label key={item} className="flex items-center gap-1">
                                    <input
                                      type="checkbox"
                                      checked={Boolean(answer.evaluation?.criteriaAssessment?.[item])}
                                      onChange={(event) => {
                                        updateEvaluation(answer.id, {
                                          criteriaAssessment: {
                                            ...(answer.evaluation?.criteriaAssessment || {}),
                                            [item]: event.target.checked
                                          }
                                        });
                                      }}
                                    />
                                    {item}
                                  </label>
                                ))}
                              </div>
                            </div>
                          ) : null}

                          <input
                            value={answer.evaluation?.notes || ''}
                            onChange={(event) => updateEvaluation(answer.id, { notes: event.target.value })}
                            placeholder="备注（可选）"
                            className="w-full rounded border border-white/10 bg-black/40 px-2 py-1 text-[10px]"
                          />
                        </div>
                      </div>
                    ) : (
                      <div className="text-[11px] text-text-dim">
                        {responding ? '等待回答中...' : '暂无回答'}
                      </div>
                    )}
                  </div>
                );
                })}
              </div>
            )}

            {error ? (
              <div className="text-[11px] text-red-200 bg-red-500/10 border border-red-500/20 rounded p-2 flex-shrink-0">
                {error}
              </div>
            ) : null}

            <div className="rounded-lg border border-white/10 bg-black/40 p-3 space-y-2 flex-shrink-0">
              <div className="text-[10px] uppercase tracking-wide text-text-dim">继续追问</div>
              <textarea
                value={quickQuestion}
                onChange={(event) => setQuickQuestion(event.target.value)}
                placeholder="在这里输入追问问题..."
                rows={2}
                className="w-full rounded border border-white/10 bg-black/30 px-2 py-1 text-[10px] text-text-main"
              />
              <button
                onClick={() => handleSendQuestion(undefined, quickQuestion)}
                disabled={responding || !quickQuestion.trim()}
                className="w-full px-3 py-1.5 text-[10px] font-semibold bg-cyan-500/80 hover:bg-cyan-500 text-white rounded transition-colors disabled:opacity-60 flex items-center justify-center gap-1"
              >
                <Send className="size-3" />
                {responding ? '发送中...' : '发送追问'}
              </button>
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-black/30 p-4 space-y-3 flex-shrink-0">
            <div className="text-xs font-semibold text-text-main uppercase tracking-wide">面试控制</div>
            <textarea
              value={userNotes}
              onChange={(event) => setUserNotes(event.target.value)}
              placeholder="面试官备注（可选）"
              rows={2}
              className="w-full rounded-lg border border-white/10 bg-black/40 p-2 text-xs text-text-main"
            />
            <div className="flex flex-col gap-2">
              <button
                onClick={() => finalizeInterview('passed')}
                disabled={!canFinalize || passedAnswers === 0}
                className="px-3 py-2 text-[11px] font-semibold bg-emerald-500/80 hover:bg-emerald-500 text-white rounded transition-colors disabled:opacity-60 flex items-center justify-center gap-1"
              >
                <CheckCircle2 className="size-3" />
                通过
              </button>
              <button
                onClick={() => finalizeInterview('failed')}
                disabled={answerMessages.length === 0 || responding}
                className="px-3 py-2 text-[11px] font-semibold bg-rose-500/80 hover:bg-rose-500 text-white rounded transition-colors disabled:opacity-60 flex items-center justify-center gap-1"
              >
                <XCircle className="size-3" />
                失败
              </button>
              <button
                onClick={resetInterview}
                className="px-3 py-2 text-[11px] border border-white/10 rounded hover:border-white/30 flex items-center justify-center gap-1"
              >
                <RefreshCw className="size-3" />
                重置会话
              </button>
            </div>
          </div>
        </div>

        {/* Right Panel - Testing Panel */}
        <div className="flex flex-col gap-4 min-h-0">
          <div className="text-xs font-semibold text-text-main uppercase tracking-wide">🖥️ 测试面板</div>
          <div className="relative bg-black/30 bg-gradient-to-br from-cyan-500/10 via-purple-500/10 to-pink-500/10 rounded-xl border border-cyan-400/30 shadow-[0_0_20px_rgba(34,211,238,0.18),0_0_40px_rgba(168,85,247,0.12)] backdrop-blur-xl overflow-hidden flex-1 min-h-0 flex flex-col">
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/60 via-fuchsia-400/50 to-pink-400/60" />
            <div className="flex items-start justify-between gap-3 p-4 border-b border-cyan-500/20 bg-black/40 flex-shrink-0">
              <div>
                <div className="text-sm font-semibold text-text-main flex items-center gap-2">
                  🖥️ Testing: Interactive Interview
                  <span className={`text-[9px] uppercase tracking-wider px-2 py-0.5 rounded border ${SESSION_STATUS[sessionStatus].badge}`}>
                    {SESSION_STATUS[sessionStatus].label}
                  </span>
                </div>
                <div className="text-[10px] text-text-dim mt-1">
                  Provider: {activeProvider?.name || '未选择'} · Model: {selectedModel || activeProvider?.model || 'default'}
                </div>
                {sessionId ? (
                  <div className="text-[10px] text-text-dim mt-1">Session: {sessionId}</div>
                ) : null}
              </div>
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-1 text-[10px] text-text-dim">
                  <input
                    type="checkbox"
                    checked={debugMode}
                    onChange={(event) => setDebugMode(event.target.checked)}
                    className="h-3 w-3 rounded border-white/10 bg-black/40"
                  />
                  Debug 模式
                </label>
                <label className="flex items-center gap-1 text-[10px] text-text-dim">
                  <input
                    type="checkbox"
                    checked={useStreamingMode}
                    onChange={(event) => setUseStreamingMode(event.target.checked)}
                    className="h-3 w-3 rounded border-white/10 bg-black/40"
                  />
                  实时流式
                </label>
                <button
                  type="button"
                  onClick={clearSessionEvents}
                  className="p-1.5 rounded border border-white/10 hover:border-accent/40 text-text-dim"
                  title="清空日志"
                >
                  <Eraser className="size-3" />
                </button>
              </div>
            </div>
            <div className="p-4 space-y-3 flex-1 overflow-auto">
              <TerminalOutput
                events={sessionEvents}
                placeholder='$ 尚未发送面试问题...'
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
