import React, { useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { Shield, Sparkles, Terminal, UserX, Save, Check } from 'lucide-react';

export const AgentInspectorPanel: React.FC = () => {
  const { selectedAgentId, agents, fetchAgents } = useAppStore();
  const agent = agents.find((a) => a.id === selectedAgentId);

  const [prompt, setPrompt] = useState(agent?.system_prompt || '');
  const [modelTier, setModelTier] = useState(agent?.model_tier || 'fast');
  const [isSaved, setIsSaved] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Sync state when selection changes
  React.useEffect(() => {
    if (agent) {
      setPrompt(agent.system_prompt);
      setModelTier(agent.model_tier);
      setIsSaved(false);
    }
  }, [agent?.id]);

  if (!agent) {
    return (
      <div className="p-8 text-center text-slate-500 text-xs font-mono">
        Click on any agent sprite in the office or from a task to inspect their role, prompt, and tier.
      </div>
    );
  }

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await apiClient.updateAgent(agent.id, {
        system_prompt: prompt,
        model_tier: modelTier,
      });
      await fetchAgents();
      setIsSaved(true);
      setTimeout(() => setIsSaved(false), 2500);
    } catch (e) {
      console.error('Failed to update agent', e);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRetire = async () => {
    if (confirm(`Are you sure you want to retire ${agent.display_name}?`)) {
      await apiClient.retireAgent(agent.id);
      await fetchAgents();
    }
  };

  return (
    <div className="p-4 flex flex-col space-y-4 text-xs overflow-y-auto max-h-[calc(100vh-140px)]">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div>
          <h3 className="font-bold text-sm text-slate-100">{agent.display_name}</h3>
          <p className="text-[11px] text-slate-400 font-mono">
            {agent.department} • Level {agent.level} • {agent.role_key}
          </p>
        </div>
        <span
          className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase ${
            agent.status === 'active' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-slate-800 text-slate-400'
          }`}
        >
          {agent.status}
        </span>
      </div>

      {/* Model Tier Selector */}
      <div className="flex flex-col gap-1.5">
        <label className="text-[11px] font-semibold text-slate-300">Model Tier</label>
        <div className="grid grid-cols-3 gap-2">
          {['fast', 'smart', 'premium'].map((tier) => (
            <button
              key={tier}
              onClick={() => setModelTier(tier)}
              className={`py-1.5 px-2 rounded border font-mono text-center text-[11px] capitalize transition-all ${
                modelTier === tier
                  ? 'border-sky-500 bg-sky-950 text-sky-200 shadow-sm'
                  : 'border-slate-800 bg-slate-900 text-slate-400 hover:border-slate-700'
              }`}
            >
              {tier}
            </button>
          ))}
        </div>
      </div>

      {/* Tools Granted */}
      <div className="flex flex-col gap-1.5">
        <label className="text-[11px] font-semibold text-slate-300">Active Permissions & Tools</label>
        <div className="flex flex-wrap gap-1">
          {agent.tools_json.map((tool) => (
            <span
              key={tool}
              className="px-2 py-0.5 rounded bg-slate-800/80 border border-slate-700 text-slate-300 font-mono text-[10px]"
            >
              {tool}
            </span>
          ))}
        </div>
      </div>

      {/* System Prompt Live Editor */}
      <div className="flex flex-col gap-1.5">
        <label className="text-[11px] font-semibold text-slate-300">System Directives & Authority Prompt</label>
        <textarea
          rows={7}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          className="w-full bg-slate-900/90 border border-slate-800 rounded p-2 text-slate-200 text-[11px] font-mono leading-relaxed focus:outline-none focus:border-sky-500"
        />
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-between pt-2">
        <button
          onClick={handleRetire}
          disabled={agent.status === 'retired'}
          className="px-3 py-1.5 rounded border border-rose-900/50 text-rose-400 hover:bg-rose-950/30 flex items-center gap-1.5 transition-all text-xs"
        >
          <UserX size={13} /> Retire
        </button>

        <button
          onClick={handleSave}
          disabled={isSaving}
          className="px-4 py-1.5 rounded bg-sky-600 hover:bg-sky-500 text-white font-medium flex items-center gap-1.5 transition-all text-xs shadow-sm"
        >
          {isSaved ? <Check size={13} className="text-emerald-300" /> : <Save size={13} />}
          {isSaved ? 'Saved' : isSaving ? 'Saving...' : 'Apply Changes'}
        </button>
      </div>
    </div>
  );
};
