import { X, Save } from 'lucide-react';
import { useEffect, useState } from 'react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: {
    pm_backend?: string;
    model?: string;
    prompt_profile?: string;
    interval?: number;
    timeout?: number;
    refresh_interval?: number;
    auto_refresh?: boolean;
    show_memory?: boolean;
    ramdisk_root?: string;
    json_log_path?: string;
    pm_show_output?: boolean;
    pm_runs_director?: boolean;
    pm_director_show_output?: boolean;
    pm_director_timeout?: number;
    pm_director_iterations?: number;
    pm_director_match_mode?: string;
    pm_max_failures?: number;
    pm_max_blocked?: number;
    pm_max_same?: number;
    director_iterations?: number;
    director_forever?: boolean;
    director_show_output?: boolean;
    qa_enabled?: boolean;
  } | null;
  onSave: (payload: {
    pm_backend?: string;
    model?: string;
    prompt_profile?: string;
    interval?: number;
    timeout?: number;
    refresh_interval?: number;
    auto_refresh?: boolean;
    show_memory?: boolean;
    ramdisk_root?: string;
    json_log_path?: string;
    pm_show_output?: boolean;
    pm_runs_director?: boolean;
    pm_director_show_output?: boolean;
    pm_director_timeout?: number;
    pm_director_iterations?: number;
    pm_director_match_mode?: string;
    pm_max_failures?: number;
    pm_max_blocked?: number;
    pm_max_same?: number;
    director_iterations?: number;
    director_forever?: boolean;
    director_show_output?: boolean;
    qa_enabled?: boolean;
  }) => Promise<void>;
}

export function SettingsModal({ isOpen, onClose, settings, onSave }: SettingsModalProps) {
  const defaultModel = 'modelscope.cn/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:latest';
  const defaultProfile = 'demo_ming_armada';
  const [pmBackend, setPmBackend] = useState('codex');
  const [ollamaModel, setOllamaModel] = useState(defaultModel);
  const [promptProfile, setPromptProfile] = useState(defaultProfile);
  const [refreshInterval, setRefreshInterval] = useState(3);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [pmInterval, setPmInterval] = useState(20);
  const [pmTimeout, setPmTimeout] = useState(0);
  const [pmRunsDirector, setPmRunsDirector] = useState(true);
  const [pmDirectorShowOutput, setPmDirectorShowOutput] = useState(true);
  const [pmDirectorTimeout, setPmDirectorTimeout] = useState(60);
  const [pmDirectorIterations, setPmDirectorIterations] = useState(1);
  const [pmDirectorMatchMode, setPmDirectorMatchMode] = useState('latest');
  const [pmShowOutput, setPmShowOutput] = useState(true);
  const [pmMaxFailures, setPmMaxFailures] = useState(5);
  const [pmMaxBlocked, setPmMaxBlocked] = useState(5);
  const [pmMaxSame, setPmMaxSame] = useState(3);
  const [directorIterations, setDirectorIterations] = useState(1);
  const [directorForever, setDirectorForever] = useState(false);
  const [directorShowOutput, setDirectorShowOutput] = useState(true);
  const [qaEnabled, setQaEnabled] = useState(true);
  const [ramdiskRoot, setRamdiskRoot] = useState('');
  const [jsonLogPath, setJsonLogPath] = useState('state/ollama/PM_LOG.jsonl');
  const [showMemory, setShowMemory] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!settings) return;
    setPmBackend(settings.pm_backend || 'codex');
    setOllamaModel(settings.model || defaultModel);
    setPromptProfile(settings.prompt_profile || defaultProfile);
    setRefreshInterval(settings.refresh_interval ?? 3);
    setAutoRefresh(settings.auto_refresh ?? true);
    setPmInterval(settings.interval ?? 20);
    setPmTimeout(settings.timeout ?? 0);
    setPmShowOutput(settings.pm_show_output ?? true);
    setPmRunsDirector(settings.pm_runs_director ?? true);
    setPmDirectorShowOutput(settings.pm_director_show_output ?? true);
    setPmDirectorTimeout(settings.pm_director_timeout ?? 60);
    setPmDirectorIterations(settings.pm_director_iterations ?? 1);
    setPmDirectorMatchMode(settings.pm_director_match_mode ?? 'latest');
    setPmMaxFailures(settings.pm_max_failures ?? 5);
    setPmMaxBlocked(settings.pm_max_blocked ?? 5);
    setPmMaxSame(settings.pm_max_same ?? 3);
    setDirectorIterations(settings.director_iterations ?? 1);
    setDirectorForever(settings.director_forever ?? false);
    setDirectorShowOutput(settings.director_show_output ?? true);
    setQaEnabled(settings.qa_enabled ?? true);
    setRamdiskRoot(settings.ramdisk_root ?? '');
    setJsonLogPath(settings.json_log_path ?? 'state/ollama/PM_LOG.jsonl');
    setShowMemory(settings.show_memory ?? false);
  }, [settings]);

  if (!isOpen) return null;

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave({
        pm_backend: pmBackend,
        model: ollamaModel,
        prompt_profile: promptProfile,
        refresh_interval: refreshInterval,
        auto_refresh: autoRefresh,
        interval: pmInterval,
        timeout: pmTimeout,
        pm_show_output: pmShowOutput,
        pm_runs_director: pmRunsDirector,
        pm_director_show_output: pmDirectorShowOutput,
        pm_director_timeout: pmDirectorTimeout,
        pm_director_iterations: pmDirectorIterations,
        pm_director_match_mode: pmDirectorMatchMode,
        pm_max_failures: pmMaxFailures,
        pm_max_blocked: pmMaxBlocked,
        pm_max_same: pmMaxSame,
        director_iterations: directorIterations,
        director_forever: directorForever,
        director_show_output: directorShowOutput,
        qa_enabled: qaEnabled,
        ramdisk_root: ramdiskRoot || '',
        json_log_path: jsonLogPath || 'state/ollama/PM_LOG.jsonl',
        show_memory: showMemory,
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[#252526] border border-gray-700 rounded-lg w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* 头部 */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-gray-200">系统配置</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-200 transition-colors"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* 内容 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {error ? (
            <div className="text-xs text-red-300 bg-red-950/40 border border-red-500/30 rounded p-2">
              {error}
            </div>
          ) : null}

          {/* Backend 配置 */}
          <div>
            <h3 className="text-sm font-semibold text-gray-300 mb-3">后端配置</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">PM Backend</label>
                <select
                  value={pmBackend}
                  onChange={(e) => setPmBackend(e.target.value)}
                  className="w-full bg-[#1e1e1e] text-gray-300 px-3 py-2 rounded border border-gray-700 text-sm focus:outline-none focus:border-blue-500"
                >
                  <option value="codex">Codex (推荐 - 更智能)</option>
                  <option value="ollama">Ollama (省成本)</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">PM 用于任务规划和决策，推荐使用 Codex</p>
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Model</label>
                <input
                  type="text"
                  value={ollamaModel}
                  onChange={(e) => setOllamaModel(e.target.value)}
                  className="w-full bg-[#1e1e1e] text-gray-300 px-3 py-2 rounded border border-gray-700 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          </div>

          {/* Prompt 模板 */}
          <div>
            <h3 className="text-sm font-semibold text-gray-300 mb-3">Prompt 模板</h3>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Profile</label>
              <select
                value={promptProfile}
                onChange={(e) => setPromptProfile(e.target.value)}
                className="w-full bg-[#1e1e1e] text-gray-300 px-3 py-2 rounded border border-gray-700 text-sm focus:outline-none focus:border-blue-500"
              >
                <option value="demo_ming_armada">demo_ming_armada (游戏开发团队)</option>
                <option value="generic">generic (通用)</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">
                定义多角色协作的提示词模板（Creative Director, Game Designer, etc.）
              </p>
            </div>
          </div>

          {/* 刷新设置 */}
          <div>
            <h3 className="text-sm font-semibold text-gray-300 mb-3">刷新设置</h3>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="auto-refresh"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="w-4 h-4 rounded bg-[#1e1e1e] border-gray-700"
                />
                <label htmlFor="auto-refresh" className="text-sm text-gray-300">
                  自动刷新
                </label>
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1.5">刷新间隔（秒）</label>
                <input
                  type="number"
                  min="1"
                  value={refreshInterval}
                  onChange={(e) => setRefreshInterval(Math.max(1, Number(e.target.value) || 1))}
                  disabled={!autoRefresh}
                  className="w-full bg-[#1e1e1e] text-gray-300 px-3 py-2 rounded border border-gray-700 text-sm focus:outline-none focus:border-blue-500 disabled:text-gray-500"
                />
                <p className="text-xs text-gray-500 mt-1">建议 1-10 秒。</p>
              </div>
            </div>
          </div>

          {/* PM 运行设置 */}
          <div>
            <h3 className="text-sm font-semibold text-gray-300 mb-3">PM 运行设置</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">循环间隔（秒）</label>
                <input
                  type="number"
                  min="1"
                  value={pmInterval}
                  onChange={(e) => setPmInterval(Math.max(1, Number(e.target.value) || 1))}
                  className="w-full bg-[#1e1e1e] text-gray-300 px-3 py-2 rounded border border-gray-700 text-sm focus:outline-none focus:border-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">PM 循环模式下每轮的等待间隔。</p>
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1.5">单次超时（秒，0=不限）</label>
                <input
                  type="number"
                  min="0"
                  value={pmTimeout}
                  onChange={(e) => setPmTimeout(Math.max(0, Number(e.target.value) || 0))}
                  className="w-full bg-[#1e1e1e] text-gray-300 px-3 py-2 rounded border border-gray-700 text-sm focus:outline-none focus:border-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">0 表示不限制。</p>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="pm-show-output"
                  checked={pmShowOutput}
                  onChange={(e) => setPmShowOutput(e.target.checked)}
                  className="w-4 h-4 rounded bg-[#1e1e1e] border-gray-700"
                />
                <label htmlFor="pm-show-output" className="text-sm text-gray-300">
                  鏄剧ず PM 杈撳嚭
                </label>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="pm-runs-director"
                  checked={pmRunsDirector}
                  onChange={(e) => setPmRunsDirector(e.target.checked)}
                  className="w-4 h-4 rounded bg-[#1e1e1e] border-gray-700"
                />
                <label htmlFor="pm-runs-director" className="text-sm text-gray-300">
                  PM 触发 Director
                </label>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="pm-director-output"
                  checked={pmDirectorShowOutput}
                  onChange={(e) => setPmDirectorShowOutput(e.target.checked)}
                  disabled={!pmRunsDirector}
                  className="w-4 h-4 rounded bg-[#1e1e1e] border-gray-700"
                />
                <label htmlFor="pm-director-output" className="text-sm text-gray-300">
                  显示 Director 输出
                </label>
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Director 结果超时（秒）</label>
                <input
                  type="number"
                  min="1"
                  value={pmDirectorTimeout}
                  onChange={(e) => setPmDirectorTimeout(Math.max(1, Number(e.target.value) || 1))}
                  disabled={!pmRunsDirector}
                  className="w-full bg-[#1e1e1e] text-gray-300 px-3 py-2 rounded border border-gray-700 text-sm focus:outline-none focus:border-blue-500 disabled:text-gray-500"
                />
                <p className="text-xs text-gray-500 mt-1">仅在 PM 触发 Director 时生效。</p>
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Director 尝试次数</label>
                <input
                  type="number"
                  min="1"
                  value={pmDirectorIterations}
                  onChange={(e) => setPmDirectorIterations(Math.max(1, Number(e.target.value) || 1))}
                  disabled={!pmRunsDirector}
                  className="w-full bg-[#1e1e1e] text-gray-300 px-3 py-2 rounded border border-gray-700 text-sm focus:outline-none focus:border-blue-500 disabled:text-gray-500"
                />
                <p className="text-xs text-gray-500 mt-1">同一任务允许 Director 重试次数。</p>
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Director 结果匹配模式</label>
                <select
                  value={pmDirectorMatchMode}
                  onChange={(e) => setPmDirectorMatchMode(e.target.value)}
                  disabled={!pmRunsDirector}
                  className="w-full bg-[#1e1e1e] text-gray-300 px-3 py-2 rounded border border-gray-700 text-sm focus:outline-none focus:border-blue-500 disabled:text-gray-500"
                >
                  <option value="latest">latest（推荐）</option>
                  <option value="run_id">run_id</option>
                  <option value="any">any</option>
                  <option value="strict">strict</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">控制 PM 如何确认 Director 结果。</p>
              </div>
            </div>
          </div>

          {/* PM 限制 */}
          <div>
            <h3 className="text-sm font-semibold text-gray-300 mb-3">PM 限制</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">最大失败次数</label>
                <input
                  type="number"
                  min="1"
                  value={pmMaxFailures}
                  onChange={(e) => setPmMaxFailures(Math.max(1, Number(e.target.value) || 1))}
                  className="w-full bg-[#1e1e1e] text-gray-300 px-3 py-2 rounded border border-gray-700 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">最大阻塞次数</label>
                <input
                  type="number"
                  min="1"
                  value={pmMaxBlocked}
                  onChange={(e) => setPmMaxBlocked(Math.max(1, Number(e.target.value) || 1))}
                  className="w-full bg-[#1e1e1e] text-gray-300 px-3 py-2 rounded border border-gray-700 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-xs text-gray-400 mb-1.5">最大连续重复次数</label>
                <input
                  type="number"
                  min="1"
                  value={pmMaxSame}
                  onChange={(e) => setPmMaxSame(Math.max(1, Number(e.target.value) || 1))}
                  className="w-full bg-[#1e1e1e] text-gray-300 px-3 py-2 rounded border border-gray-700 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          </div>

          {/* Director 设置 */}
          <div>
            <h3 className="text-sm font-semibold text-gray-300 mb-3">Director 设置</h3>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="director-qa"
                  checked={qaEnabled}
                  onChange={(e) => setQaEnabled(e.target.checked)}
                  className="w-4 h-4 rounded bg-[#1e1e1e] border-gray-700"
                />
                <label htmlFor="director-qa" className="text-sm text-gray-300">
                  启用 QA 审核
                </label>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="director-forever"
                  checked={directorForever}
                  onChange={(e) => setDirectorForever(e.target.checked)}
                  className="w-4 h-4 rounded bg-[#1e1e1e] border-gray-700"
                />
                <label htmlFor="director-forever" className="text-sm text-gray-300">
                  持续运行（忽略迭代次数）
                </label>
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1.5">迭代次数</label>
                <input
                  type="number"
                  min="1"
                  value={directorIterations}
                  onChange={(e) => setDirectorIterations(Math.max(1, Number(e.target.value) || 1))}
                  disabled={directorForever}
                  className="w-full bg-[#1e1e1e] text-gray-300 px-3 py-2 rounded border border-gray-700 text-sm focus:outline-none focus:border-blue-500 disabled:text-gray-500"
                />
                <p className="text-xs text-gray-500 mt-1">关闭“持续运行”后生效。</p>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="director-output"
                  checked={directorShowOutput}
                  onChange={(e) => setDirectorShowOutput(e.target.checked)}
                  className="w-4 h-4 rounded bg-[#1e1e1e] border-gray-700"
                />
                <label htmlFor="director-output" className="text-sm text-gray-300">
                  显示 Director 输出
                </label>
              </div>
            </div>
          </div>

          {/* 存储与日志 */}
          <div>
            <h3 className="text-sm font-semibold text-gray-300 mb-3">存储与日志</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">RAMDisk 根目录（可选）</label>
                <input
                  type="text"
                  value={ramdiskRoot}
                  onChange={(e) => setRamdiskRoot(e.target.value)}
                  placeholder="X:\\"
                  className="w-full bg-[#1e1e1e] text-gray-300 px-3 py-2 rounded border border-gray-700 text-sm focus:outline-none focus:border-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">留空禁用；示例：X:\</p>
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1.5">JSON 日志路径</label>
                <input
                  type="text"
                  value={jsonLogPath}
                  onChange={(e) => setJsonLogPath(e.target.value)}
                  className="w-full bg-[#1e1e1e] text-gray-300 px-3 py-2 rounded border border-gray-700 text-sm focus:outline-none focus:border-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">相对 Workspace 的路径。</p>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="show-memory"
                  checked={showMemory}
                  onChange={(e) => setShowMemory(e.target.checked)}
                  className="w-4 h-4 rounded bg-[#1e1e1e] border-gray-700"
                />
                <label htmlFor="show-memory" className="text-sm text-gray-300">
                  显示 Memory 面板
                </label>
              </div>
              <p className="text-xs text-gray-500">开启后右侧显示 memory 视图。</p>
            </div>
          </div>
        </div>

        {/* 底部按钮 */}
        <div className="flex items-center justify-end gap-2 p-4 border-t border-gray-700">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
            disabled={saving}
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors flex items-center gap-2 disabled:opacity-60"
          >
            <Save className="size-4" />
            {saving ? '保存中...' : '保存配置'}
          </button>
        </div>
      </div>
    </div>
  );
}
