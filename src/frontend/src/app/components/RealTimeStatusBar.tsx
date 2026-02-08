import { Activity, CheckCircle, AlertTriangle, Clock, Zap, Target, PlayCircle, Square, Cpu, Database, Wifi } from 'lucide-react';
import { useState, useEffect } from 'react';

interface RealTimeStatusBarProps {
  pmRunning: boolean;
  directorRunning: boolean;
  pmStartedAt: number | null;
  directorStartedAt: number | null;
  pmIteration: number | null;
  currentTask?: string;
  successRate?: number;
  queueCount?: number;
  llmStatus?: string;
  lancedbOk?: boolean;
}

function formatDuration(startedAt: number | null) {
  if (!startedAt) return '';
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - startedAt));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h${minutes % 60}m`;
}

function clampText(text: string, maxLen: number) {
  if (!text) return '';
  return text.length <= maxLen ? text : text.slice(0, maxLen - 1) + '…';
}

export function RealTimeStatusBar({
  pmRunning,
  directorRunning,
  pmStartedAt,
  directorStartedAt,
  pmIteration,
  currentTask,
  successRate,
  queueCount,
  llmStatus,
  lancedbOk,
}: RealTimeStatusBarProps) {
  const [currentTime, setCurrentTime] = useState(new Date());

  // 更新时间显示
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const pmDuration = formatDuration(pmStartedAt);
  const directorDuration = formatDuration(directorStartedAt);
  const successRateText = successRate !== undefined ? `${Math.round(successRate * 100)}%` : '--';
  const currentTaskText = currentTask ? clampText(currentTask, 35) : '';
  const queueText = queueCount !== undefined ? `${queueCount}` : '';

  return (
    <div className="h-11 bg-black/90 backdrop-blur-xl border-b border-cyan-500/30 flex items-center px-5 relative overflow-hidden">
      {/* 赛博朋克背景效果 */}
      <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/5 via-purple-500/5 to-blue-500/5"></div>
      <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PGxpbmVhckdyYWRpZW50IGlkPSJhIiB4MT0iMCUiIHkxPSIwJSIgeDI9IjEwMCUiIHkyPSIwJSI+PHN0b3Agb2Zmc2V0PSIwJSIgc3RvcC1jb2xvcj0iI2N5YW41MDAiLz48c3RvcCBvZmZzZXQ9IjEwMCUiIHN0b3AtY29sb3I9IiNjeWFuNTAwIi8+PC9saW5lYXJHcmFkaWVudD48bGluZWFyR3JhZGllbnQgaWQ9ImIiIHgxPSIwJSIgeTE9IjAlIiB4Mj0iMTAwJSIgeTI9IjEwMCUiPjxzdG9wIG9mZnNldD0iMCUiIHN0b3AtY29sb3I9IiNweWFuNTAwIi8+PHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9yPSIjcHlhbjUwMCIvPjwvbGluZWFyR3JhZGllbnQ+PC9kZWZzPjxyZWN0IHdpZHRoPSIyMDAiIGhlaWdodD0iNCIgZmlsbD0idXJsKCNhKSIgb3BhY2l0eT0iMC4zIi8+PHJlY3Qgd2lkdGg9IjIwMCIgaGVpZ2h0PSI0IiBmaWxsPSJ1cmwoI2IpIiBvcGFjaXR5PSIwLjMiLz48L3N2Zz4=')] opacity-20"></div>
      
      {/* 左侧：系统状态 - iOS风格小组件 */}
      <div className="flex items-center gap-3 flex-1 relative z-10">
        {/* PM状态 - iOS小组件风格 */}
        <div className="relative group">
          <div className="absolute inset-0 bg-cyan-500/20 blur-xl rounded-xl group-hover:blur-2xl transition-all duration-300"></div>
          <div className="relative bg-black/60 backdrop-blur-md rounded-xl border border-cyan-500/30 px-3 py-1.5 flex items-center gap-2.5">
            <div className="relative">
              {pmRunning ? (
                <>
                  <div className="absolute inset-0 bg-cyan-500 blur-md animate-pulse"></div>
                  <PlayCircle className="w-4 h-4 text-cyan-400 relative" />
                </>
              ) : (
                <Square className="w-4 h-4 text-gray-500" />
              )}
            </div>
            <div className="flex flex-col">
              <div className="text-[10px] font-semibold text-cyan-300 tracking-wide">PM</div>
              <div className="text-[9px] text-gray-400 font-mono">
                {pmRunning ? `ACTIVE ${pmDuration}` : 'IDLE'}
              </div>
            </div>
          </div>
        </div>

        {/* Director状态 */}
        <div className="relative group">
          <div className="absolute inset-0 bg-purple-500/20 blur-xl rounded-xl group-hover:blur-2xl transition-all duration-300"></div>
          <div className="relative bg-black/60 backdrop-blur-md rounded-xl border border-purple-500/30 px-3 py-1.5 flex items-center gap-2.5">
            <div className="relative">
              {directorRunning ? (
                <>
                  <div className="absolute inset-0 bg-purple-500 blur-md animate-pulse"></div>
                  <Cpu className="w-4 h-4 text-purple-400 relative" />
                </>
              ) : (
                <Square className="w-4 h-4 text-gray-500" />
              )}
            </div>
            <div className="flex flex-col">
              <div className="text-[10px] font-semibold text-purple-300 tracking-wide">DIRECTOR</div>
              <div className="text-[9px] text-gray-400 font-mono">
                {directorRunning ? `ACTIVE ${directorDuration}` : 'IDLE'}
              </div>
            </div>
          </div>
        </div>

        {/* 轮次信息 - 赛博朋克风格 */}
        {pmIteration !== null && (
          <div className="relative group">
            <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/30 to-purple-500/30 blur-xl rounded-xl group-hover:blur-2xl transition-all duration-300"></div>
            <div className="relative bg-black/60 backdrop-blur-md rounded-xl border border-cyan-500/50 px-3 py-1.5 flex items-center gap-2.5">
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-cyan-500 to-purple-500 blur-md animate-pulse"></div>
                <Zap className="w-4 h-4 text-white relative" />
              </div>
              <div className="flex flex-col">
                <div className="text-[10px] font-bold text-white tracking-wider">ROUND</div>
                <div className="text-[9px] text-cyan-300 font-mono font-bold">
                  #{pmIteration.toString().padStart(3, '0')}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 中间：任务信息 - 赛博朋克数据面板 */}
      <div className="flex items-center gap-5 px-5 border-x border-cyan-500/20 relative z-10">
        {/* 成功率 - 赛博朋克仪表盘风格 */}
        {successRate !== undefined && (
          <div className="relative group">
            <div className="absolute inset-0 bg-emerald-500/10 blur-lg rounded-lg"></div>
            <div className="relative bg-black/40 backdrop-blur-sm rounded-lg px-2.5 py-1.5 flex items-center gap-1.5 border border-emerald-500/30">
              <div className="relative">
                <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                <div className="absolute -inset-1 bg-emerald-400/20 blur-sm"></div>
              </div>
              <div className="flex flex-col">
                <div className="text-[8px] text-emerald-300 font-mono tracking-wider">SUCCESS</div>
                <div className="text-[10px] font-bold text-emerald-400 font-mono">{successRateText}</div>
              </div>
            </div>
          </div>
        )}

        {/* 当前任务 - 赛博朋克终端风格 */}
        {currentTaskText && (
          <div className="relative group max-w-xs">
            <div className="absolute inset-0 bg-blue-500/10 blur-lg rounded-lg"></div>
            <div className="relative bg-black/40 backdrop-blur-sm rounded-lg px-2.5 py-1.5 flex items-center gap-1.5 border border-blue-500/30">
              <div className="relative">
                <Target className="w-3.5 h-3.5 text-blue-400" />
                <div className="absolute -inset-1 bg-blue-400/20 blur-sm"></div>
              </div>
              <div className="flex flex-col">
                <div className="text-[8px] text-blue-300 font-mono tracking-wider">MISSION</div>
                <div className="text-[10px] font-mono text-blue-400 truncate">{currentTaskText}</div>
              </div>
            </div>
          </div>
        )}

        {/* 队列数量 - iOS徽章风格 */}
        {queueText && (
          <div className="relative">
            <div className="absolute inset-0 bg-orange-500/20 blur-lg rounded-full"></div>
            <div className="relative bg-orange-500/20 backdrop-blur-sm rounded-full px-2.5 py-1 border border-orange-500/40">
              <div className="text-[10px] font-bold text-orange-300 font-mono">
                QUEUE: {queueText}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 右侧：系统监控 - 赛博朋克HUD风格 */}
      <div className="flex items-center gap-3 flex-1 justify-end relative z-10">
        {/* LLM状态 */}
        {llmStatus && (
          <div className="relative group">
            <div className="absolute inset-0 bg-cyan-500/10 blur-lg rounded-lg"></div>
            <div className="relative bg-black/40 backdrop-blur-sm rounded-lg px-2.5 py-1.5 flex items-center gap-1.5 border border-cyan-500/30">
              <div className="relative">
                <Wifi className="w-3.5 h-3.5 text-cyan-400" />
                <div className={`absolute -inset-1 ${
                  llmStatus === 'ready' ? 'bg-emerald-400/20' : 'bg-yellow-400/20'
                } blur-sm`}></div>
              </div>
              <div className="flex flex-col">
                <div className="text-[8px] text-cyan-300 font-mono tracking-wider">LLM</div>
                <div className={`text-[10px] font-mono font-bold ${
                  llmStatus === 'ready' ? 'text-emerald-400' : 'text-yellow-400'
                }`}>
                  {llmStatus.toUpperCase()}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 数据库状态 */}
        {lancedbOk !== undefined && (
          <div className="relative group">
            <div className="absolute inset-0 bg-purple-500/10 blur-lg rounded-lg"></div>
            <div className="relative bg-black/40 backdrop-blur-sm rounded-lg px-2.5 py-1.5 flex items-center gap-1.5 border border-purple-500/30">
              <div className="relative">
                <Database className="w-3.5 h-3.5 text-purple-400" />
                <div className={`absolute -inset-1 ${
                  lancedbOk ? 'bg-emerald-400/20' : 'bg-red-400/20'
                } blur-sm`}></div>
              </div>
              <div className="flex flex-col">
                <div className="text-[8px] text-purple-300 font-mono tracking-wider">DATABASE</div>
                <div className={`text-[10px] font-mono font-bold ${
                  lancedbOk ? 'text-emerald-400' : 'text-red-400'
                }`}>
                  {lancedbOk ? 'ONLINE' : 'OFFLINE'}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 时间显示 - 赛博朋克终端时钟 */}
        <div className="relative group">
          <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 to-purple-500/10 blur-lg rounded-lg"></div>
          <div className="relative bg-black/40 backdrop-blur-sm rounded-lg px-2.5 py-1.5 flex items-center gap-1.5 border border-cyan-500/30">
            <div className="relative">
              <Clock className="w-3.5 h-3.5 text-cyan-400" />
              <div className="absolute -inset-1 bg-cyan-400/20 blur-sm animate-pulse"></div>
            </div>
            <div className="flex flex-col">
              <div className="text-[8px] text-cyan-300 font-mono tracking-wider">SYSTEM TIME</div>
              <div className="text-[10px] font-mono text-cyan-400 font-bold">
                {currentTime.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 扫描线效果 */}
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-cyan-500/10 to-transparent h-px animate-pulse"></div>
    </div>
  );
}
