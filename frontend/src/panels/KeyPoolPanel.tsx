import React, { useEffect, useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { Key, Plus, Trash2, RefreshCw, ShieldCheck, AlertTriangle } from 'lucide-react';

export const KeyPoolPanel: React.FC = () => {
  const { keyStatuses, keysLoading, keysError, fetchKeys, networkStatus } = useAppStore();
  const [newKey, setNewKey] = useState('');
  const [alias, setAlias] = useState('');
  const [isManagerDedicated, setIsManagerDedicated] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [busyAlias, setBusyAlias] = useState<string | null>(null);

  useEffect(() => {
    void fetchKeys();
    const refreshWhenVisible = () => {
      if (document.visibilityState === 'visible') void fetchKeys();
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

  const handleAddKey = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!newKey.trim() || networkStatus === 'offline') return;
    setIsAdding(true);
    setErrorMsg(null);
    try {
      await apiClient.addKey({
        key: newKey.trim(),
        alias: alias.trim() || undefined,
        is_manager_dedicated: isManagerDedicated,
      });
      setNewKey('');
      setAlias('');
      setIsManagerDedicated(false);
      await fetchKeys();
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : 'Could not add this key.');
    } finally {
      setIsAdding(false);
    }
  };

  const handleDeleteKey = async (targetAlias: string) => {
    if (networkStatus === 'offline' || !window.confirm('Remove API key "' + targetAlias + '" from rotation?')) return;
    setBusyAlias(targetAlias);
    setErrorMsg(null);
    try {
      await apiClient.deleteKey(targetAlias);
      await fetchKeys();
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : 'Could not remove this key.');
    } finally {
      setBusyAlias(null);
    }
  };

  const healthyCount = keyStatuses.filter((key) => key.is_healthy).length;
  const managerKeysCount = keyStatuses.filter((key) => key.is_manager_dedicated).length;

  return (
    <section className="key-pool-panel app-panel">
      <header className="key-pool-header">
        <div>
          <h2><Key size={16} /> API key pool</h2>
          <p>Rotation health and manager reservations</p>
        </div>
        <button type="button" className="app-icon-button" onClick={() => void fetchKeys()} disabled={networkStatus === 'offline'} aria-label="Refresh API key status">
          <RefreshCw size={14} />
        </button>
      </header>

      {keysError && <div className="task-stale-notice" role="alert">{keyStatuses.length ? 'Showing the last key status snapshot. ' : ''}{keysError}</div>}
      {networkStatus === 'offline' && <p className="app-inline-note">Offline. Key status is a snapshot. Adding and removing keys is disabled.</p>}
      {errorMsg && <div className="app-error" role="alert">{errorMsg}</div>}

      <div className="key-pool-metrics">
        <div><strong className="app-measured">{keyStatuses.length || (keysLoading ? '—' : '0')}</strong><span>Total keys</span></div>
        <div><strong className="app-measured">{keysLoading && keyStatuses.length === 0 ? '—' : healthyCount}</strong><span>Healthy</span></div>
        <div><strong className="app-measured">{keysLoading && keyStatuses.length === 0 ? '—' : managerKeysCount}</strong><span>Reserved</span></div>
      </div>

      <section className="key-pool-list">
        <h3>Keys in rotation</h3>
        {keysLoading && keyStatuses.length === 0 ? (
          <div className="task-tree-skeleton" aria-label="Loading API key status">
            {[0, 1, 2].map((item) => <div className="task-tree-skeleton-item" key={item}><div className="app-skeleton app-skeleton-line" /><div className="app-skeleton app-skeleton-short" /></div>)}
          </div>
        ) : keyStatuses.length === 0 ? (
          <div className="app-empty">
            <Key size={22} />
            <strong>No keys loaded</strong>
            <p>{keysError || 'Set GROQ_API_KEYS and GROQ_MANAGER_KEYS in the backend environment, or add a key below.'}</p>
          </div>
        ) : keyStatuses.map((key) => (
          <article className="key-record" key={key.alias}>
            <div className="key-record-main">
              <div>
                <strong>{key.alias}</strong>
                <span className="app-measured">{key.masked_key}</span>
              </div>
              <span className={key.is_healthy ? 'key-health key-health-ok' : 'key-health key-health-warn'}>
                {key.is_healthy ? <ShieldCheck size={12} /> : <AlertTriangle size={12} />}
                {key.is_healthy ? 'Healthy' : 'Cooling down'}
              </span>
            </div>
            <div className="key-record-meta">
              <span>{key.is_manager_dedicated ? 'Manager reserved' : 'Shared pool'}</span>
              <span className="app-measured">{key.total_calls.toLocaleString()} calls</span>
              {key.cooldown_remaining_sec > 0 && <span>{key.cooldown_remaining_sec}s cooldown</span>}
              <button type="button" onClick={() => void handleDeleteKey(key.alias)} disabled={busyAlias === key.alias || networkStatus === 'offline'} aria-label={'Remove key ' + key.alias}>
                <Trash2 size={13} /> {busyAlias === key.alias ? 'Removing' : 'Remove'}
              </button>
            </div>
          </article>
        ))}
      </section>

      <section className="key-add">
        <h3><Plus size={15} /> Register a key</h3>
        <form onSubmit={handleAddKey}>
          <label htmlFor="pool-api-key">API key</label>
          <input id="pool-api-key" type="password" autoComplete="off" value={newKey} onChange={(event) => setNewKey(event.target.value)} placeholder="Paste provider key" required />
          <label htmlFor="pool-key-alias">Alias <span>(optional)</span></label>
          <input id="pool-key-alias" value={alias} onChange={(event) => setAlias(event.target.value)} placeholder="e.g. research-key-2" />
          <label className="key-manager-toggle">
            <input type="checkbox" checked={isManagerDedicated} onChange={(event) => setIsManagerDedicated(event.target.checked)} />
            Reserve for higher managers (levels 1–3)
          </label>
          <button type="submit" className="app-button app-button-primary" disabled={isAdding || !newKey.trim() || networkStatus === 'offline'}>
            <Plus size={13} /> {isAdding ? 'Registering' : 'Add key to pool'}
          </button>
        </form>
      </section>
    </section>
  );
};
