import React, { useState } from 'react';
import { Button } from '@/app/components/ui/button';
import { Card } from '@/app/components/ui/card';
import { Activity, Eye, Server, Zap } from 'lucide-react';

interface TestResult {
  status: string;
  response?: any;
  error?: string;
}

export function TurboTestBench() {
  const [daskStatus, setDaskStatus] = useState<any>(null);
  const [visionResult, setVisionResult] = useState<TestResult | null>(null);
  const [loading, setLoading] = useState<string | null>(null);

  const apiCall = async (endpoint: string, method: string = 'POST', body?: any) => {
    try {
        const token = localStorage.getItem('token');
        const headers: Record<string, string> = {
            'Content-Type': 'application/json'
        };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const res = await fetch(`http://localhost:8000${endpoint}`, {
            method,
            headers,
            body: body ? JSON.stringify(body) : undefined
        });
        const data = await res.json();
        return data;
    } catch (e: any) {
        return { error: e.message };
    }
  };

  const checkDask = async () => {
    setLoading('dask');
    const res = await apiCall('/arsenal/scheduler/status', 'GET');
    setDaskStatus(res);
    setLoading(null);
  };

  const startDask = async () => {
    setLoading('dask');
    const res = await apiCall('/arsenal/scheduler/start', 'POST');
    setDaskStatus(res);
    setLoading(null);
  };

  const stopDask = async () => {
    setLoading('dask');
    const res = await apiCall('/arsenal/scheduler/stop', 'POST');
    setDaskStatus(res);
    setLoading(null);
  };

  const testVision = async () => {
    setLoading('vision');
    // Send a 1x1 pixel base64 for testing mock
    const mockImage = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";
    const res = await apiCall('/arsenal/vision/analyze', 'POST', { image: mockImage, task: '<OD>' });
    setVisionResult({ status: 'done', response: res });
    setLoading(null);
  };

  return (
    <div className="space-y-6">
      {/* Dask Control */}
      <Card className="p-4 bg-black/20 border-white/5">
        <h3 className="text-sm font-semibold text-cyan-400 flex items-center gap-2 mb-4">
            <Server className="w-4 h-4" /> Dask-CUDA Scheduler
        </h3>
        <div className="flex gap-2 mb-4">
            <Button size="sm" variant="outline" onClick={checkDask} disabled={loading === 'dask'}>Check Status</Button>
            <Button size="sm" className="bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30" onClick={startDask} disabled={loading === 'dask'}>Start Cluster</Button>
            <Button size="sm" className="bg-red-500/20 text-red-300 hover:bg-red-500/30" onClick={stopDask} disabled={loading === 'dask'}>Stop Cluster</Button>
        </div>
        {daskStatus && (
            <pre className="text-xs bg-black/50 p-2 rounded text-emerald-400/80 overflow-auto">
                {JSON.stringify(daskStatus, null, 2)}
            </pre>
        )}
      </Card>

      {/* Vision Control */}
      <Card className="p-4 bg-black/20 border-white/5">
        <h3 className="text-sm font-semibold text-purple-400 flex items-center gap-2 mb-4">
            <Eye className="w-4 h-4" /> Vision Service (Florence-2)
        </h3>
        <div className="flex gap-2 mb-4">
            <Button size="sm" variant="outline" onClick={testVision} disabled={loading === 'vision'}>Test Inference (Mock)</Button>
        </div>
        {visionResult && (
            <div className="text-xs bg-black/50 p-2 rounded text-purple-400/80 overflow-auto">
                <div className="mb-2 font-bold">Analysis Result:</div>
                <pre>{JSON.stringify(visionResult.response, null, 2)}</pre>
            </div>
        )}
      </Card>
    </div>
  );
}
