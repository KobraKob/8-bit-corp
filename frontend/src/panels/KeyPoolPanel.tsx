import React, { useEffect, useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { Key, Plus, Trash2, RefreshCw, ShieldCheck, Zap, AlertTriangle, Clock } from 'lucide-react';

export const KeyPoolPanel: React.FC = () => {
  const { keyStatuses, fetchKeys, networkStatus } = useAppStore();
  const [newKey, setNewKey] = useState('');
  const [alias, setAlias] = useState('');
  const [isManagerDedicated, setIsManagerDedicated] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    void fetchKeys();
    const refreshWhenVisible = () => {
      if (navigator.onLine && document.visibilityState === 'visible') void fetchKeys();
    };
    const interval = window.setInterval(refreshWhenVisible, 30000);
    window.addEventListener('online', refreshWhenVisible);
    document.addEventListener('visibilitychange', refreshWhenVisible);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener('online', refreshWhenVisible);
      document.removeEventListener('visibilitychange', refreshWhenVisible);
    };
  }, []);

  const handleAddKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKey.trim()) return;
    setIsAdding(true);
    setErrorMsg(null);

    try {
      await apiClient.addKey({
        key: newKey.trim(),
        alias: alias.trim() ? alias.trim() : undefined,
        is_manager_dedicated: isManagerDedicated,
      });
      setNewKey('');
      setAlias('');
      setIsManagerDedicated(false);
      await fetchKeys();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to add key to pool');
    } finally {
      setIsAdding(false);
    }
  };

  const handleDeleteKey = async (targetAlias: string) => {
    if (confirm(`Remove API key '${targetAlias}' from active pool?`)) {
      try {
        await apiClient.deleteKey(targetAlias);
        await fetchKeys();
      } catch (err: any) {
        alert(`Failed to delete key: ${err.message}`);
      }
    }
  };

  const healthyCount = keyStatuses.filter((k) => k.is_healthy).length;
  const managerKeysCount = keyStatuses.filter((k) => k.is_manager_dedicated).length;

  return (
    <div className="p-4 flex flex-col space-y-4 text-xs overflow-y-auto max-h-[calc(100vh-140px)]">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div>
          <h3 className="font-bold text-sm text-slate-100 flex items-center gap-1.5">
            <Key size={16} className="text-amber-400" />
            API Key Pool Manager
          </h3>
          <p className="text-[11px] text-slate-400 font-mono">
            Multi-key rotation & higher manager reservation
          </p>
        </div>
        <button
          onClick={() => fetchKeys()}
          title="Refresh Key Status"
          className="p-1.5 rounded border border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <RefreshCw size={13} />
        </button>
      </div>

      {networkStatus === 'offline' && <p className='app-inline-note' role='status'>Offline. Showing the last available key status. Key changes require a server connection.</p>}

      {/* Pool Stats Card */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-slate-900/80 border border-slate-800 rounded p-2 text-center">
          <div className="text-[10px] text-slate-400 uppercase font-mono">Total Keys</div>
          <div className="text-base font-bold text-slate-100 font-mono mt-0.5">{keyStatuses.length}</div>
        </div>
        <div className="bg-slate-900/80 border border-slate-800 rounded p-2 text-center">
          <div className="text-[10px] text-emerald-400 uppercase font-mono">Healthy</div>
          <div className="text-base font-bold text-emerald-400 font-mono mt-0.5">{healthyCount}</div>
        </div>
        <div className="bg-slate-900/80 border border-slate-800 rounded p-2 text-center">
          <div className="text-[10px] text-purple-400 uppercase font-mono">Mgr Reserved</div>
          <div className="text-base font-bold text-purple-400 font-mono mt-0.5">{managerKeysCount}</div>
        </div>
      </div>

      {/* Key List */}
      <div className="flex flex-col gap-2">
        <label className="text-[11px] font-semibold text-slate-300">Active Keys in Rotation</label>
        {keyStatuses.length === 0 ? (
          <div className="p-4 rounded border border-dashed border-slate-800 text-center text-slate-500 font-mono text-[11px]">
            No pool keys loaded. Set GROQ_API_KEYS / GROQ_MANAGER_KEYS in .env or add below.
          </div>
        ) : (
          keyStatuses.map((k) => (
            <div
              key={k.alias}
              className={`p-2.5 rounded border transition-colors flex flex-col gap-1.5 ${
                k.is_healthy
                  ? 'bg-slate-900/70 border-slate-800'
                  : 'bg-amber-950/20 border-amber-900/50'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-semibold text-slate-200 text-xs">{k.alias}</span>
                  <span className="font-mono text-slate-400 text-[11px]">{k.masked_key}</span>
                </div>
                <button
                  onClick={() => handleDeleteKey(k.alias)}
                  className="text-slate-500 hover:text-rose-400 transition-colors p-1"
                  title="Remove Key"
                >
                  <Trash2 size={13} />
                </button>
              </div>

              <div className="flex items-center justify-between text-[10px] font-mono">
                <div className="flex items-center gap-1.5">
                  {k.is_manager_dedicated ? (
                    <span className="px-1.5 py-0.5 rounded bg-purple-950/80 border border-purple-800 text-purple-300 flex items-center gap-1">
                      <ShieldCheck size={10} /> Managers Only
                    </span>
                  ) : (
                    <span className="px-1.5 py-0.5 rounded bg-sky-950/80 border border-sky-800 text-sky-300 flex items-center gap-1">
                      <Zap size={10} /> General Pool
                    </span>
                  )}

                  {k.is_healthy ? (
                    <span className="px-1.5 py-0.5 rounded bg-emerald-950/80 border border-emerald-800 text-emerald-400">
                      Healthy
                    </span>
                  ) : (
                    <span className="px-1.5 py-0.5 rounded bg-amber-950/80 border border-amber-800 text-amber-300 flex items-center gap-1">
                      <AlertTriangle size={10} /> Cooldown ({k.cooldown_remaining_sec}s)
                    </span>
                  )}
                </div>

                <div className="text-slate-400 flex items-center gap-1">
                  <Clock size={10} />
                  <span>{k.total_calls} calls</span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Add New Key Form */}
      <form onSubmit={handleAddKey} className="flex flex-col gap-2 pt-2 border-t border-slate-800">
        <label className="text-[11px] font-semibold text-slate-300 flex items-center gap-1">
          <Plus size={13} className="text-sky-400" /> Add Key to Pool
        </label>

        {errorMsg && (
          <div className="p-2 rounded bg-rose-950/40 border border-rose-900 text-rose-300 text-[10px] font-mono">
            {errorMsg}
          </div>
        )}

        <input
          type="password"
          placeholder="API Key (e.g. gsk_...)"
          value={newKey}
          onChange={(e) => setNewKey(e.target.value)}
          className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 text-xs font-mono focus:outline-none focus:border-sky-500"
          required
        />

        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Alias (optional, e.g. mgr_key_2)"
            value={alias}
            onChange={(e) => setAlias(e.target.value)}
            className="flex-1 bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-slate-200 text-xs font-mono focus:outline-none focus:border-sky-500"
          />
        </div>

        <label className="flex items-center gap-2 cursor-pointer text-slate-300 text-[11px] mt-1 select-none">
          <input
            type="checkbox"
            checked={isManagerDedicated}
            onChange={(e) => setIsManagerDedicated(e.target.checked)}
            className="rounded border-slate-800 bg-slate-900 text-purple-600 focus:ring-0"
          />
          <span>Reserve for Higher Managers (Level &le; 3)</span>
        </label>

        <button
          type="submit"
          disabled={isAdding || !newKey.trim()}
          className="mt-1 w-full py-1.5 px-3 rounded bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-medium flex items-center justify-center gap-1.5 transition-all text-xs shadow-sm"
        >
          <Plus size={13} />
          {isAdding ? 'Registering Key...' : 'Register Key into Pool'}
        </button>
      </form>
    </div>
  );
};
