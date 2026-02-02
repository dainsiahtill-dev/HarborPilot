import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { apiFetch } from '@/api';
import {
  History,
  Calendar,
  Target,
  CheckCircle,
  XCircle,
  Clock,
  FileText,
  Search,
  Filter,
  Download,
  ChevronDown,
  ChevronRight,
  Activity,
  AlertTriangle,
  Users,
  ListChecks,
  ArrowRight,
  RefreshCw
} from 'lucide-react';
import { Button } from '@/app/components/ui/button';
import { Input } from '@/app/components/ui/input';
import { ScrollArea } from '@/app/components/ui/scroll-area';
import { Badge } from '@/app/components/ui/badge';
import { Separator } from '@/app/components/ui/separator';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/app/components/ui/collapsible';

// 防抖hook
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

interface TaskHistoryRound {
  round_id: string;
  timestamp: string;
  pm_iteration: number;
  focus: string;
  overall_goal: string;
  tasks: TaskItem[];
  execution_summary: {
    total_tasks: number;
    completed_tasks: number;
    failed_tasks: number;
    success_rate: number;
  };
  director_results: {
    run_id: string;
    status: string;
    start_time: string;
    end_time: string;
    successes: number;
    total: number;
  };
  artifacts: {
    pm_tasks_path: string;
    director_result_path: string;
    events_path: string;
    dialogue_path: string;
  };
}

interface TaskItem {
  id: string;
  title: string;
  goal: string;
  acceptance?: string[];
  target_files?: string[];
  constraints?: string[];
}

interface WorkspaceHistoryPanelProps {
  className?: string;
}

export function WorkspaceHistoryPanel({ className }: WorkspaceHistoryPanelProps) {
  const [rounds, setRounds] = useState<TaskHistoryRound[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRound, setSelectedRound] = useState<TaskHistoryRound | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'success' | 'fail' | 'unknown'>('all');
  const [expandedRounds, setExpandedRounds] = useState<Set<string>>(new Set());
  const [selectedTask, setSelectedTask] = useState<TaskItem | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const autoRefreshInterval = useRef<NodeJS.Timeout | null>(null);

  // 防抖搜索
  const debouncedSearchQuery = useDebounce(searchQuery, 300);

  // 加载历史数据
  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiFetch('/history/rounds?limit=100');
      if (!response.ok) {
        throw new Error('Failed to load history');
      }
      const data = await response.json();
      setRounds(data.rounds || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load history');
    } finally {
      setLoading(false);
    }
  }, []);

  // 自动刷新
  useEffect(() => {
    if (autoRefresh) {
      autoRefreshInterval.current = setInterval(loadHistory, 30000); // 30秒刷新一次
    } else {
      if (autoRefreshInterval.current) {
        clearInterval(autoRefreshInterval.current);
        autoRefreshInterval.current = null;
      }
    }

    return () => {
      if (autoRefreshInterval.current) {
        clearInterval(autoRefreshInterval.current);
      }
    };
  }, [autoRefresh, loadHistory]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // 过滤和搜索
  const filteredRounds = useMemo(() => {
    return rounds.filter(round => {
      // 状态过滤
      if (statusFilter !== 'all') {
        const directorStatus = round.director_results?.status?.toLowerCase() || 'unknown';
        if (statusFilter === 'success' && !directorStatus.includes('success')) return false;
        if (statusFilter === 'fail' && !directorStatus.includes('fail')) return false;
        if (statusFilter === 'unknown' && directorStatus !== 'unknown') return false;
      }

      // 搜索过滤（使用防抖后的查询）
      if (debouncedSearchQuery) {
        const query = debouncedSearchQuery.toLowerCase();
        const searchFields = [
          round.focus,
          round.overall_goal,
          round.round_id,
          ...(round.tasks?.map(task => task.title) || []),
          ...(round.tasks?.map(task => task.goal) || [])
        ].join(' ').toLowerCase();
        
        if (!searchFields.includes(query)) return false;
      }

      return true;
    });
  }, [rounds, debouncedSearchQuery, statusFilter]);

  // 切换轮次展开状态
  const toggleRoundExpansion = (roundId: string) => {
    setExpandedRounds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(roundId)) {
        newSet.delete(roundId);
      } else {
        newSet.add(roundId);
      }
      return newSet;
    });
  };

  // 获取状态图标和颜色
  const getStatusIcon = (status: string) => {
    const statusLower = status.toLowerCase();
    if (statusLower.includes('success')) {
      return <CheckCircle className="h-4 w-4 text-emerald-400" />;
    } else if (statusLower.includes('fail')) {
      return <XCircle className="h-4 w-4 text-red-400" />;
    } else if (statusLower.includes('blocked')) {
      return <AlertTriangle className="h-4 w-4 text-amber-400" />;
    } else {
      return <Activity className="h-4 w-4 text-gray-400" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const statusLower = status.toLowerCase();
    if (statusLower.includes('success')) {
      return <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20">成功</Badge>;
    } else if (statusLower.includes('fail')) {
      return <Badge className="bg-red-500/10 text-red-400 border-red-500/20">失败</Badge>;
    } else if (statusLower.includes('blocked')) {
      return <Badge className="bg-amber-500/10 text-amber-400 border-amber-500/20">阻塞</Badge>;
    } else {
      return <Badge className="bg-gray-500/10 text-gray-400 border-gray-500/20">未知</Badge>;
    }
  };

  // 格式化时间
  const formatTime = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return timestamp;
    }
  };

  // 导出历史数据
  const exportHistory = () => {
    const dataStr = JSON.stringify(filteredRounds, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `task-history-${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className={`flex flex-col h-full bg-[#1e1e1e] border-gray-800 ${className || ''}`}>
      {/* 头部 */}
      <div className="flex items-center justify-between p-4 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <History className="h-5 w-5 text-blue-400" />
          <h2 className="text-lg font-semibold text-gray-200">任务历史</h2>
          <Badge variant="outline" className="text-xs">
            {filteredRounds.length} 轮
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant={autoRefresh ? "default" : "ghost"}
            size="sm"
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`text-xs ${autoRefresh ? "bg-blue-600 hover:bg-blue-500" : "text-gray-400 hover:text-white"}`}
          >
            {autoRefresh ? "自动刷新中" : "自动刷新"}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={loadHistory}
            disabled={loading}
            className="text-gray-400 hover:text-white"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={exportHistory}
            className="text-gray-400 hover:text-white"
          >
            <Download className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* 搜索和过滤 */}
      <div className="p-4 border-b border-gray-800 space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="搜索轮次、任务..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 bg-[#2a2a2a] border-gray-700 text-gray-200 placeholder-gray-500"
          />
        </div>
        <div className="flex gap-2">
          <Button
            variant={statusFilter === 'all' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setStatusFilter('all')}
            className="text-xs"
          >
            全部
          </Button>
          <Button
            variant={statusFilter === 'success' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setStatusFilter('success')}
            className="text-xs text-emerald-400 hover:text-emerald-300"
          >
            成功
          </Button>
          <Button
            variant={statusFilter === 'fail' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setStatusFilter('fail')}
            className="text-xs text-red-400 hover:text-red-300"
          >
            失败
          </Button>
          <Button
            variant={statusFilter === 'unknown' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setStatusFilter('unknown')}
            className="text-xs text-gray-400 hover:text-gray-300"
          >
            未知
          </Button>
        </div>
      </div>

      {/* 历史列表 */}
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-3">
          {loading ? (
            <div className="text-center text-gray-500 py-8">加载中...</div>
          ) : error ? (
            <div className="text-center text-red-400 py-8">错误: {error}</div>
          ) : filteredRounds.length === 0 ? (
            <div className="text-center text-gray-500 py-8">暂无历史记录</div>
          ) : (
            filteredRounds.map((round) => (
              <Collapsible
                key={round.round_id}
                open={expandedRounds.has(round.round_id)}
                onOpenChange={() => toggleRoundExpansion(round.round_id)}
              >
                <CollapsibleTrigger className="w-full">
                  <div className="bg-[#2a2a2a] rounded-lg p-4 border border-gray-700 hover:border-gray-600 transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {expandedRounds.has(round.round_id) ? (
                          <ChevronDown className="h-4 w-4 text-gray-400" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-gray-400" />
                        )}
                        <div className="flex items-center gap-2">
                          {getStatusIcon(round.director_results?.status || 'unknown')}
                          <span className="font-mono text-sm text-blue-300">{round.round_id}</span>
                          {getStatusBadge(round.director_results?.status || 'unknown')}
                        </div>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-gray-400">
                        <span className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {formatTime(round.timestamp)}
                        </span>
                        <span className="flex items-center gap-1">
                          <ListChecks className="h-3 w-3" />
                          {round.execution_summary?.total_tasks || 0} 任务
                        </span>
                        {round.execution_summary?.success_rate !== undefined && (
                          <span className="flex items-center gap-1">
                            <Target className="h-3 w-3" />
                            {Math.round((round.execution_summary.success_rate || 0) * 100)}%
                          </span>
                        )}
                      </div>
                    </div>
                    
                    {/* 轮次摘要 */}
                    <div className="mt-3 text-sm">
                      {round.focus && (
                        <div className="text-gray-300 mb-1">
                          聚焦: <span className="text-blue-300">{round.focus}</span>
                        </div>
                      )}
                      {round.overall_goal && (
                        <div className="text-gray-400 text-xs line-clamp-2">
                          {round.overall_goal}
                        </div>
                      )}
                    </div>
                  </div>
                </CollapsibleTrigger>
                
                <CollapsibleContent className="mt-2">
                  <div className="bg-[#252525] rounded-lg p-4 border border-gray-700">
                    {/* 任务列表 */}
                    <div className="space-y-2">
                      <h4 className="text-sm font-medium text-gray-300 flex items-center gap-2">
                        <ListChecks className="h-4 w-4" />
                        任务列表 ({round.tasks?.length || 0})
                      </h4>
                      {round.tasks?.map((task, index) => (
                        <div
                          key={task.id || index}
                          className="bg-[#2a2a2a] rounded p-3 border border-gray-700 cursor-pointer hover:border-gray-600 transition-colors"
                          onClick={() => setSelectedTask(task)}
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1 min-w-0">
                              <div className="text-sm font-medium text-gray-200 truncate">
                                {task.title || `任务 ${index + 1}`}
                              </div>
                              {task.goal && (
                                <div className="text-xs text-gray-400 mt-1 line-clamp-2">
                                  {task.goal}
                                </div>
                              )}
                              {task.acceptance && task.acceptance.length > 0 && (
                                <div className="mt-2">
                                  <div className="text-xs text-gray-500 mb-1">验收标准:</div>
                                  <ul className="text-xs text-gray-400 space-y-1">
                                    {task.acceptance.slice(0, 2).map((criteria, idx) => (
                                      <li key={idx} className="flex items-start gap-1">
                                        <ArrowRight className="h-3 w-3 flex-shrink-0 mt-0.5" />
                                        <span>{criteria}</span>
                                      </li>
                                    ))}
                                    {task.acceptance.length > 2 && (
                                      <li className="text-gray-500">
                                        ...还有 {task.acceptance.length - 2} 项
                                      </li>
                                    )}
                                  </ul>
                                </div>
                              )}
                            </div>
                            {task.target_files && task.target_files.length > 0 && (
                              <Badge className="text-xs ml-2">
                                {task.target_files.length} 文件
                              </Badge>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                    
                    {/* 执行结果 */}
                    {round.director_results && (
                      <div className="mt-4 pt-4 border-t border-gray-700">
                        <h4 className="text-sm font-medium text-gray-300 flex items-center gap-2 mb-3">
                          <Activity className="h-4 w-4" />
                          执行结果
                        </h4>
                        <div className="grid grid-cols-2 gap-3 text-xs">
                          <div className="bg-[#2a2a2a] rounded p-2">
                            <div className="text-gray-500">状态</div>
                            <div className="flex items-center gap-1 mt-1">
                              {getStatusIcon(round.director_results.status)}
                              <span className="text-gray-200">{round.director_results.status}</span>
                            </div>
                          </div>
                          <div className="bg-[#2a2a2a] rounded p-2">
                            <div className="text-gray-500">成功率</div>
                            <div className="text-gray-200 mt-1">
                              {round.director_results.successes}/{round.director_results.total}
                            </div>
                          </div>
                          {round.director_results.start_time && (
                            <div className="bg-[#2a2a2a] rounded p-2">
                              <div className="text-gray-500">开始时间</div>
                              <div className="text-gray-200 mt-1">
                                {formatTime(round.director_results.start_time)}
                              </div>
                            </div>
                          )}
                          {round.director_results.end_time && (
                            <div className="bg-[#2a2a2a] rounded p-2">
                              <div className="text-gray-500">结束时间</div>
                              <div className="text-gray-200 mt-1">
                                {formatTime(round.director_results.end_time)}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </CollapsibleContent>
              </Collapsible>
            ))
          )}
        </div>
      </ScrollArea>

      {/* 任务详情模态框 */}
      {selectedTask && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-[#1e1e1e] rounded-lg max-w-2xl w-full max-h-[80vh] overflow-hidden border border-gray-800">
            <div className="flex items-center justify-between p-4 border-b border-gray-800">
              <h3 className="text-lg font-semibold text-gray-200">任务详情</h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedTask(null)}
                className="text-gray-400 hover:text-white"
              >
                ✕
              </Button>
            </div>
            <ScrollArea className="p-4">
              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-medium text-gray-300 mb-2">标题</h4>
                  <div className="text-gray-200">{selectedTask.title}</div>
                </div>
                <div>
                  <h4 className="text-sm font-medium text-gray-300 mb-2">目标</h4>
                  <div className="text-gray-200">{selectedTask.goal}</div>
                </div>
                {selectedTask.acceptance && selectedTask.acceptance.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-300 mb-2">验收标准</h4>
                    <ul className="list-disc list-inside text-gray-200 space-y-1">
                      {selectedTask.acceptance.map((criteria, index) => (
                        <li key={index}>{criteria}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {selectedTask.target_files && selectedTask.target_files.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-300 mb-2">目标文件</h4>
                    <div className="space-y-1">
                      {selectedTask.target_files.map((file, index) => (
                        <div key={index} className="text-gray-200 font-mono text-sm bg-[#2a2a2a] p-2 rounded">
                          {file}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {selectedTask.constraints && selectedTask.constraints.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-300 mb-2">约束条件</h4>
                    <ul className="list-disc list-inside text-gray-200 space-y-1">
                      {selectedTask.constraints.map((constraint, index) => (
                        <li key={index}>{constraint}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>
        </div>
      )}
    </div>
  );
}
