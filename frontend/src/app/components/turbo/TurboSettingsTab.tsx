import { useEffect, useState } from 'react';
import { Activity, Cpu, Zap, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { Switch } from '@/app/components/ui/switch';
import { apiFetch } from '@/api';

interface GPUDevice {
  index: number;
  name: string;
  memory_total_mb: number;
  driver_version: string;
  compute_cap: string;
}

interface TurboStatusResponse {
  enabled: boolean;
  auto_detect: boolean;
  memory_limit: number;
  active: boolean;
  detection: {
    available: boolean;
    count: number;
    devices: GPUDevice[];
    driver_version: string;
    rapids_available: boolean;
    error: string | null;
  };
}

export function TurboSettingsTab() {
  const [status, setStatus] = useState<TurboStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState(false);

  const fetchStatus = async () => {
    try {
      setLoading(true);
      const res = await apiFetch('/turbo/status');
      if (!res.ok) throw new Error('Failed to fetch turbo status');
      const data = await res.json();
      setStatus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleToggle = async (enabled: boolean) => {
    if (!status) return;
    setToggling(true);
    try {
      const res = await apiFetch('/turbo/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          enabled,
          auto_detect: status.auto_detect,
          memory_limit: status.memory_limit
        })
      });
      if (!res.ok) throw new Error('Failed to update turbo config');
      const data = await res.json();
      setStatus((prev) => prev ? { ...prev, ...data } : data);
    } catch (err) {
      // Revert optimization? Or just show error?
      console.error(err);
    } finally {
      setToggling(false);
    }
  };

  if (loading && !status) {
    return <div className="p-8 text-center text-text-dim">Loading GPU Status...</div>;
  }

  if (error) {
    return <div className="p-8 text-center text-red-400">Error: {error}</div>;
  }

  if (!status) return null;

  const { detection, enabled, active } = status;

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header / Hero */}
      <div className={`rounded-xl p-6 border ${active ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-white/5 border-white/10'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={`p-3 rounded-lg ${active ? 'bg-emerald-500/20 text-emerald-400' : 'bg-white/5 text-text-dim'}`}>
              <Zap className="size-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-text-main flex items-center gap-2">
                Turbo Mode
                {active && <span className="text-[10px] bg-emerald-500 text-black px-2 py-0.5 rounded font-bold uppercase tracking-wider">Active</span>}
              </h3>
              <p className="text-sm text-text-dim">
                Hardware acceleration for text processing and context engineering
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <Switch 
              checked={enabled} 
              onCheckedChange={handleToggle}
              disabled={toggling || (!detection.available && status.auto_detect)}
            />
          </div>
        </div>
      </div>

      {/* GPU Arsenal Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Detection Card */}
        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <h4 className="text-sm font-semibold text-text-main mb-4 flex items-center gap-2">
            <Cpu className="size-4" />
            GPU Arsenal
          </h4>
          
          {detection.available ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">Driver Version</span>
                <span className="text-text-main font-mono">{detection.driver_version}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">RAPIDS Stack</span>
                {detection.rapids_available ? (
                  <span className="text-emerald-400 flex items-center gap-1"><CheckCircle2 className="size-3" /> Installed</span>
                ) : (
                  <span className="text-amber-400 flex items-center gap-1"><AlertTriangle className="size-3" /> Missing</span>
                )}
              </div>
              <div className="space-y-2 mt-4">
                {detection.devices.map((gpu) => (
                  <div key={gpu.index} className="bg-black/20 rounded p-2 text-xs border border-white/5">
                    <div className="flex justify-between mb-1">
                      <span className="font-semibold text-text-main">{gpu.name}</span>
                      <span className="text-text-dim">ID: {gpu.index}</span>
                    </div>
                    <div className="flex justify-between text-text-muted">
                      <span>VRAM: {gpu.memory_total_mb} MB</span>
                      <span>CC: {gpu.compute_cap}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-text-dim text-sm">
              <AlertTriangle className="size-8 mx-auto mb-2 opacity-50" />
              <p>No compatible NVIDIA GPUs detected.</p>
              {detection.error && <p className="text-xs text-red-400 mt-2">{detection.error}</p>}
            </div>
          )}
        </div>

        {/* Performance Impact Card */}
        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <h4 className="text-sm font-semibold text-text-main mb-4 flex items-center gap-2">
            <Activity className="size-4" />
            Performance Impact
          </h4>
          
          <div className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-xs text-text-muted">
                <span>Regex Operations</span>
                <span className="text-emerald-400">~100x Faster</span>
              </div>
              <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 w-[95%]" />
              </div>
            </div>
            
            <div className="space-y-2">
              <div className="flex justify-between text-xs text-text-muted">
                <span>Context Indexing</span>
                <span className="text-emerald-400">Real-time</span>
              </div>
              <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 w-[80%]" />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs text-text-muted">
                <span>Memory Overhead</span>
                <span className="text-blue-400">+2GB VRAM</span>
              </div>
              <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-blue-500 w-[20%]" />
              </div>
            </div>
          </div>
          
          <div className="mt-6 p-3 bg-accent/10 rounded-lg border border-accent/20 text-xs text-text-dim">
            <p className="font-semibold text-accent mb-1">Note:</p>
            When enabled, text processing tasks are offloaded to the GPU. 
            This consumes VRAM but significantly reduces CPU load and latency.
          </div>
        </div>
      </div>
    </div>
  );
}
