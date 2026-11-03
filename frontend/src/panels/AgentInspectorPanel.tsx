import React, { useEffect, useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { AgentAvatar } from '../components/AgentAvatar';
import { Save, Check, KeyRound, ShieldCheck, Trash2, UserX, RefreshCw } from 'lucide-react';

export const AgentInspectorPanel: React.FC = () => {
  const {
    selectedAgentId, agents, agentsLoading, agentsError, fetchAgents,
    setSelectedAgent, networkStatus,
  } = useAppStore();
  const agent = agents.find((item) => item.id === selectedAgentId);
  const [prompt, setPrompt] = useState('');
  const [modelTier, setModelTier] = useState('fast');
  const [customKeyInput, setCustomKeyInput] = useState('');
  const [isSaved, setIsSaved] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (!agent) return;
    setPrompt(agent.system_prompt || '');
    setModelTier(agent.model_tier || 'fast');
    setCustomKeyInput('');
    setIsSaved(false);
    setSaveError(null);
  }, [agent?.id]);

  if (!agent) {
    return (
      <div className="app-empty">
        <UserX size={22} />
        <strong>No agent selected</strong>
        <p>Select a person in the office, team directory, or task board to inspect their role and instructions.</p>
        {agentsError && <p role="alert">{agentsError}</p>}
        {agentsLoading && <span>Loading team roster…</span>}
        <button type="button" className="app-button" onClick={() => void fetchAgents()} disabled={networkStatus === 'offline'}>
          <RefreshCw size={13} /> Refresh roster
        </button>
      </div>
    );
  }

  const isHigherManager = agent.level <= 3;

  const handleSave = async () => {
    if (networkStatus === 'offline') return;
    setIsSaving(true);
    setSaveError(null);
    setIsSaved(false);
    try {
      const payload: Partial<typeof agent> = { system_prompt: prompt, model_tier: modelTier };
      if (customKeyInput.trim()) payload.api_key = customKeyInput.trim();
      await apiClient.updateAgent(agent.id, payload);
      await fetchAgents();
      setCustomKeyInput('');
      setIsSaved(true);
      window.setTimeout(() => setIsSaved(false), 2500);
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Could not save agent settings.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleClearCustomKey = async () => {
    if (networkStatus === 'offline') return;
    setIsSaving(true);
    setSaveError(null);
    try {
      await apiClient.updateAgent(agent.id, { api_key: '' });
      await fetchAgents();
      setCustomKeyInput('');
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Could not clear this API key.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleRetire = async () => {
    if (networkStatus === 'offline' || !window.confirm('Retire ' + agent.display_name + '? They will leave the active office roster.')) return;
    setIsSaving(true);
    setSaveError(null);
    try {
      await apiClient.retireAgent(agent.id);
      setSelectedAgent(null);
      await fetchAgents();
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Could not retire this agent.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section className="agent-inspector app-panel">
      <header className="agent-inspector-header">
        <AgentAvatar agent={agent} size={64} />
        <div>
          <h2>{agent.display_name}</h2>
          <p>{agent.department} · Level {agent.level} · {agent.role_key}</p>
          <span className={'agent-status-label agent-status-' + agent.status}>{agent.status}</span>
        </div>
      </header>

      {isHigherManager && (
        <div className="agent-executive-note">
          <ShieldCheck size={15} />
          <span><strong>Executive priority.</strong> This role uses the dedicated manager key pool when configured.</span>
        </div>
      )}

      <section className="agent-inspector-section">
        <header><h3>Model configuration</h3><span>Execution tier</span></header>
        <div className="agent-model-options">
          {['fast', 'smart', 'premium'].map((tier) => (
            <button key={tier} type="button" onClick={() => setModelTier(tier)} aria-pressed={modelTier === tier} className={modelTier === tier ? 'agent-model-option agent-model-option-selected' : 'agent-model-option'}>
              {tier}
            </button>
          ))}
        </div>
      </section>

      <section className="agent-inspector-section">
        <header><h3><KeyRound size={14} /> Dedicated API key</h3><span>{agent.has_custom_api_key ? 'Override set' : 'Using pool'}</span></header>
        {agent.has_custom_api_key ? (
          <div className="agent-key-current">
            <span><strong>Active override</strong><code>{agent.masked_api_key || '••••••••••••'}</code></span>
            <button type="button" onClick={() => void handleClearCustomKey()} disabled={isSaving || networkStatus === 'offline'}>
              <Trash2 size={12} /> Clear
            </button>
          </div>
        ) : (
          <>
            <p className="agent-field-help">Optional private provider key. It is never shown again after saving.</p>
            <label htmlFor="agent-custom-key">API key</label>
            <input id="agent-custom-key" type="password" autoComplete="new-password" value={customKeyInput} onChange={(event) => setCustomKeyInput(event.target.value)} placeholder="Paste provider key" />
          </>
        )}
      </section>

      <section className="agent-inspector-section">
        <header><h3>Granted tools</h3><span>{agent.tools_json.length} permissions</span></header>
        <div className="agent-tool-list">
          {agent.tools_json.length ? agent.tools_json.map((tool) => <span key={tool}>{tool}</span>) : <p className="app-muted">No tools assigned.</p>}
        </div>
      </section>

      <section className="agent-inspector-section">
        <header><h3>System instructions</h3><span>Agent authority and behaviour</span></header>
        <label htmlFor="agent-system-prompt">Prompt</label>
        <textarea id="agent-system-prompt" rows={10} value={prompt} onChange={(event) => setPrompt(event.target.value)} />
      </section>

      {saveError && <p className="app-inline-error" role="alert">{saveError}</p>}
      {isSaved && <p className="app-inline-success" role="status"><Check size={13} /> Agent settings saved.</p>}
      {networkStatus === 'offline' && <p className="app-inline-note">Offline. Changes are unavailable until the backend reconnects.</p>}

      <footer className="agent-inspector-actions">
        <button type="button" className="app-button agent-retire-button" onClick={() => void handleRetire()} disabled={isSaving || networkStatus === 'offline' || agent.status === 'retired'}>
          <UserX size={13} /> Retire
        </button>
        <button type="button" className="app-button app-button-primary" onClick={() => void handleSave()} disabled={isSaving || networkStatus === 'offline'}>
          {isSaved ? <Check size={13} /> : <Save size={13} />}
          {isSaving ? 'Saving' : isSaved ? 'Saved' : 'Save changes'}
        </button>
      </footer>
    </section>
  );
};
