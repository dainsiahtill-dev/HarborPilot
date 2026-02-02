import { useState } from 'react';
import { FileJson, Terminal, Activity, Folder, TrendingUp, PieChart } from 'lucide-react';
import { LogViewer } from './LogViewer';
import { ArtifactsSidebar } from './ArtifactsSidebar';
import type { UsageStats } from './UsageHUD';

interface ProcessMonitorSidebarProps {
  onFileSelect: (file: any) => void;
  selectedFileId: string | null;
  onOpenWorkspace?: () => void;
  onOpenHistory?: () => void;
  fileStatusLines?: string[] | null;
  usageStats?: UsageStats | null;
}

type TabId = 'pm' | 'director' | 'files' | 'usage';

export function ProcessMonitorSidebar({
  onFileSelect,
  selectedFileId,
  onOpenWorkspace,
  onOpenHistory,
  fileStatusLines,
  usageStats,
}: ProcessMonitorSidebarProps) {
  const [activeTab, setActiveTab] = useState<TabId>('pm');

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] text-text-main">
      {/* Sidebar Header & Tabs */}
      <div className="flex flex-col border-b border-white/5 bg-[#252526]">
        <div className="px-3 py-2 flex items-center gap-2">
            <Activity className="size-4 text-accent" />
            <span className="text-xs font-bold tracking-wide text-gray-300">PROCESS MONITOR</span>
        </div>
        <div className="flex items-center px-1 pb-1 gap-1">
            <button
                onClick={() => setActiveTab('pm')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-[10px] uppercase font-bold tracking-wider rounded-t-mk transition-colors ${
                    activeTab === 'pm' 
                    ? 'bg-[#1e1e1e] text-blue-400 border-t-2 border-blue-400' 
                    : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
                }`}
            >
                <Terminal className="size-3" />
                PM Log
            </button>
            <button
                onClick={() => setActiveTab('director')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-[10px] uppercase font-bold tracking-wider rounded-t-mk transition-colors ${
                    activeTab === 'director' 
                    ? 'bg-[#1e1e1e] text-purple-400 border-t-2 border-purple-400' 
                    : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
                }`}
            >
                <Terminal className="size-3" />
                Director
            </button>
             <button
                onClick={() => setActiveTab('files')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-[10px] uppercase font-bold tracking-wider rounded-t-mk transition-colors ${
                    activeTab === 'files' 
                    ? 'bg-[#1e1e1e] text-emerald-400 border-t-2 border-emerald-400' 
                    : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
                }`}
            >
                <Folder className="size-3" />
                Files
            </button>
             <button
                onClick={() => setActiveTab('usage')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-[10px] uppercase font-bold tracking-wider rounded-t-mk transition-colors ${
                    activeTab === 'usage' 
                    ? 'bg-[#1e1e1e] text-yellow-400 border-t-2 border-yellow-400' 
                    : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
                }`}
            >
                <PieChart className="size-3" />
                Usage
            </button>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-hidden relative">
         <div className={`absolute inset-0 ${activeTab === 'pm' ? 'z-10' : 'z-0 invisible'}`}>
            <LogViewer sourceId="pm-subprocess" className="h-full" />
         </div>
         <div className={`absolute inset-0 ${activeTab === 'director' ? 'z-10' : 'z-0 invisible'}`}>
            <LogViewer sourceId="director" className="h-full" />
         </div>
         <div className={`absolute inset-0 overflow-hidden flex flex-col ${activeTab === 'files' ? 'z-10' : 'z-0 invisible'}`}>
             <ArtifactsSidebar 
                 onFileSelect={onFileSelect}
                 selectedFileId={selectedFileId}
                 onOpenWorkspace={onOpenWorkspace}
                 onOpenHistory={onOpenHistory}
                 fileStatusLines={fileStatusLines}
             />
         </div>
         <div className={`absolute inset-0 overflow-y-auto ${activeTab === 'usage' ? 'z-10' : 'z-0 invisible'}`}>
            <div className="p-4 space-y-6">
                <div className="space-y-2">
                   <h3 className="text-xs uppercase font-bold text-gray-500 tracking-wider">Total Usage</h3>
                   {usageStats ? (
                       <div className="grid grid-cols-2 gap-2">
                           <div className="bg-white/5 p-3 rounded border border-white/5">
                               <div className="text-2xl font-mono text-cyan-400">{usageStats.totals.total_tokens.toLocaleString()}</div>
                               <div className="text-[10px] text-gray-400 uppercase tracking-wider">Tokens Used</div>
                           </div>
                           <div className="bg-white/5 p-3 rounded border border-white/5">
                               <div className="text-2xl font-mono text-purple-400">{usageStats.calls.toLocaleString()}</div>
                               <div className="text-[10px] text-gray-400 uppercase tracking-wider">LLM Invocations</div>
                           </div>
                       </div>
                   ) : (
                       <div className="text-sm text-gray-500 italic">No usage data available</div>
                   )}
                </div>

                {usageStats?.by_mode && Object.keys(usageStats.by_mode).length > 0 && (
                     <div className="space-y-2">
                        <h3 className="text-xs uppercase font-bold text-gray-500 tracking-wider">Breakdown by Phase</h3>
                        <div className="space-y-1">
                            {Object.entries(usageStats.by_mode)
                                .sort(([, a], [, b]) => b.total_tokens - a.total_tokens)
                                .map(([mode, stats]) => (
                                <div key={mode} className="flex items-center justify-between text-xs bg-white/5 px-3 py-2 rounded">
                                    <div className="flex items-center gap-2">
                                        <div className="w-1.5 h-1.5 rounded-full bg-cyan-500/50"></div>
                                        <span className="font-medium text-gray-300 capitalize">{mode.replace('_', ' ')}</span>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <span className="text-gray-400 font-mono text-[10px]">{stats.calls} calls</span>
                                        <span className="text-cyan-400 font-mono">{stats.total_tokens.toLocaleString()} tks</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                     </div>
                )}
            </div>
         </div>
      </div>
    </div>
  );
}
