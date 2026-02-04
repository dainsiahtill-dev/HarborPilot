import React, { useEffect, useState } from 'react';
import { CodeMap3D } from './CodeMap3D';
import { Card } from '@/app/components/ui/card';
import { Button } from '@/app/components/ui/button';
import { Loader2, RefreshCcw, Box } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/app/components/ui/alert';

interface MapData {
  points: { path: string; x: number; y: number; z: number; cluster: number }[];
  mode: string;
  engine_active: boolean;
}

export function ArsenalPanel() {
  const [data, setData] = useState<MapData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem('token'); // Simplistic auth
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`; 
      // Assuming 'token' is stored. If using AuthContext, we might need to hook into it. 
      // For now, let's try direct fetch assuming browser cookie or standard header.
      // Actually SettingsModal uses props for config, but fetching fresh map data might need auth.
      // We'll trust the global fetch interceptor if it exists, or try basic retrieval.
      
      const res = await fetch('http://localhost:8000/arsenal/code_map', {
          headers: {
              'Authorization': localStorage.getItem('auth_token') || ''
          }
      });
      
      if (!res.ok) throw new Error('Failed to fetch arsenal data');
      const json = await res.json();
      setData(json);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <div className="space-y-4 text-text-main h-full">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2">
             <Box className="w-5 h-5 text-cyan-400" />
             HarborPilot Arsenal
          </h2>
          <p className="text-sm text-text-dim">Advanced Visualization & Heavy Compute</p>
        </div>
        <Button 
            variant="outline" 
            size="sm" 
            onClick={fetchData} 
            disabled={loading}
            className="border-white/10 hover:bg-white/5"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <RefreshCcw className="w-4 h-4 mr-2" />}
          Re-Scan
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card className="p-4 bg-black/20 border-white/5">
        <div className="mb-4 flex items-center justify-between text-xs text-text-dim">
           <span>VISUALIZATION: 3D CODE MAP</span>
           <span>MODE: {data?.mode?.toUpperCase() || 'UNKNOWN'}</span>
        </div>
        
        {loading && !data ? (
            <div className="h-[500px] flex items-center justify-center border border-white/5 rounded bg-black/40">
                <div className="flex flex-col items-center gap-2">
                    <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
                    <span className="text-sm text-cyan-400/80">Analysing Codebase Structure...</span>
                </div>
            </div>
        ) : (
            data?.points && <CodeMap3D points={data.points} />
        )}
        
        <div className="mt-4 text-xs text-text-muted">
            {data?.points?.length || 0} Files indexed using {data?.engine_active ? 'Turbo Engine' : 'Standard Engine'}.
        </div>
      </Card>
    </div>
  );
}
