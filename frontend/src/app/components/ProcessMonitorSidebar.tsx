import { useState } from 'react';
import { FileJson, Terminal, Activity, Folder } from 'lucide-react';
import { LogViewer } from './LogViewer';
import { ArtifactsSidebar } from './ArtifactsSidebar';

interface ProcessMonitorSidebarProps {
  onFileSelect: (file: any) => void;
  selectedFileId: string | null;
  onOpenWorkspace?: () => void;
  onOpenHistory?: () => void;
  fileStatusLines?: string[] | null;
}

type TabId = 'pm' | 'director' | 'files';

export function ProcessMonitorSidebar({
  onFileSelect,
  selectedFileId,
  onOpenWorkspace,
  onOpenHistory,
  fileStatusLines,
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
      </div>
    </div>
  );
}
