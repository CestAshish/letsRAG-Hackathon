import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import axios from 'axios';
import { X, Activity, Terminal } from 'lucide-react';

export function TelemetryModal({ messageId, onClose }: { messageId: string, onClose: () => void }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'analytics' | 'logs'>('analytics');

  useEffect(() => {
    axios.get(`http://localhost:8000/api/analytics/${messageId}`)
      .then(res => { setData(res.data); setLoading(false); })
      .catch(e => { console.error(e); setLoading(false); });
  }, [messageId]);

  return createPortal(
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999] p-4">
      <div className="bg-[var(--bg-secondary)] text-[var(--text-primary)] rounded-xl shadow-2xl w-full max-w-3xl overflow-hidden flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between p-4 border-b border-[var(--border-color)]">
          <h2 className="font-semibold text-lg flex items-center gap-2"><Activity size={20} className="text-[var(--accent-color)]"/> Telemetry & Observability</h2>
          <button onClick={onClose} className="p-1 hover:bg-[var(--bg-tertiary)] rounded-full text-[var(--text-secondary)] bg-transparent border-none cursor-pointer"><X size={20}/></button>
        </div>
        
        <div className="flex border-b border-[var(--border-color)] bg-[var(--bg-tertiary)]">
          <button onClick={() => setTab('analytics')} className={`px-4 py-3 font-medium text-sm flex items-center gap-2 bg-transparent border-none cursor-pointer ${tab === 'analytics' ? 'border-b-2 border-[var(--accent-color)] text-[var(--accent-color)] bg-[var(--bg-secondary)]' : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]'}`}>
            <Activity size={16}/> Analytics Dashboard
          </button>
          <button onClick={() => setTab('logs')} className={`px-4 py-3 font-medium text-sm flex items-center gap-2 bg-transparent border-none cursor-pointer ${tab === 'logs' ? 'border-b-2 border-[var(--accent-color)] text-[var(--accent-color)] bg-[var(--bg-secondary)]' : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]'}`}>
            <Terminal size={16}/> Raw Logs
          </button>
        </div>
        
        <div className="p-6 overflow-y-auto flex-1 bg-[var(--bg-tertiary)]">
          {loading ? (
            <div className="animate-pulse space-y-4">
              <div className="h-4 bg-[var(--border-color)] rounded w-1/4"></div>
              <div className="h-32 bg-[var(--border-color)] rounded w-full"></div>
              <div className="h-32 bg-[var(--border-color)] rounded w-full"></div>
            </div>
          ) : !data ? (
            <div className="text-red-500 bg-red-50 p-4 rounded-lg border border-red-200">Failed to load telemetry data for message ID: {messageId}</div>
          ) : tab === 'analytics' ? (
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-[var(--bg-secondary)] p-5 rounded-xl border border-[var(--border-color)] shadow-sm">
                <h3 className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Agent Iterations</h3>
                <div className="text-3xl font-black text-[var(--text-primary)]">{data.analytics.total_agent_loops} <span className="text-sm font-medium text-[var(--text-secondary)]">Loops</span></div>
              </div>
              
              <div className="bg-[var(--bg-secondary)] p-5 rounded-xl border border-[var(--border-color)] shadow-sm">
                <h3 className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Service Calls</h3>
                <div className="space-y-2 mt-3">
                  <div className="flex justify-between items-center"><span className="text-[var(--text-secondary)] text-sm">LLM Generations</span><span className="font-bold text-[var(--text-primary)] bg-[var(--bg-tertiary)] px-2 py-0.5 rounded border border-[var(--border-color)]">{data.analytics.llm_calls}</span></div>
                  <div className="flex justify-between items-center"><span className="text-[var(--text-secondary)] text-sm">Vector/Embedding Models</span><span className="font-bold text-[var(--text-primary)] bg-[var(--bg-tertiary)] px-2 py-0.5 rounded border border-[var(--border-color)]">{data.analytics.hf_calls}</span></div>
                </div>
              </div>
              
              <div className="col-span-2 bg-[var(--bg-secondary)] p-5 rounded-xl border border-[var(--border-color)] shadow-sm">
                <h3 className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-wider mb-4">Token Usage Breakdown</h3>
                <div className="flex items-center gap-6">
                  <div className="flex-1 bg-[var(--bg-tertiary)] p-3 rounded-lg border border-[var(--border-color)]">
                    <div className="text-xs text-[var(--text-secondary)] mb-1 uppercase font-semibold tracking-wide">Input Tokens</div>
                    <div className="text-2xl font-mono text-[var(--text-primary)]">{data.analytics.total_prompt_tokens.toLocaleString()}</div>
                  </div>
                  <div className="flex-1 bg-[var(--bg-tertiary)] p-3 rounded-lg border border-[var(--border-color)]">
                    <div className="text-xs text-[var(--text-secondary)] mb-1 uppercase font-semibold tracking-wide">Output Tokens</div>
                    <div className="text-2xl font-mono text-[var(--text-primary)]">{data.analytics.total_completion_tokens.toLocaleString()}</div>
                  </div>
                  <div className="flex-1 bg-blue-50/10 p-3 rounded-lg border border-[var(--accent-color)]">
                    <div className="text-xs text-[var(--accent-color)] mb-1 uppercase font-semibold tracking-wide">Total Tokens Used</div>
                    <div className="text-2xl font-mono text-[var(--accent-color)] font-bold">{data.analytics.total_tokens.toLocaleString()}</div>
                  </div>
                </div>
              </div>
              
              {data.analytics.tools_used.length > 0 && (
                <div className="col-span-2 bg-[var(--bg-secondary)] p-5 rounded-xl border border-[var(--border-color)] shadow-sm">
                  <h3 className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-wider mb-3">Tools Invoked</h3>
                  <div className="flex flex-wrap gap-2">
                    {data.analytics.tools_used.map((t: string, i: number) => (
                      <span key={i} className="px-2.5 py-1 bg-[var(--bg-tertiary)] text-[var(--text-primary)] border border-[var(--border-color)] rounded-md text-sm font-mono">{t}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-[#000000] rounded-xl p-5 font-mono text-xs text-green-400 overflow-x-auto shadow-inner leading-relaxed">
              {data.logs.map((log: string, i: number) => <div key={i} className="mb-2 whitespace-pre-wrap">{log}</div>)}
              {data.logs.length === 0 && <div className="text-gray-500 italic">No telemetry logs captured for this message.</div>}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
