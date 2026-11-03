import React, { useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { AgentAvatar } from '../components/AgentAvatar';
import { UserPlus, Users, Sparkles } from 'lucide-react';

export const OrgEditorPanel: React.FC = () => {
  const { agents, fetchAgents, setSelectedAgent } = useAppStore();

  const [title, setTitle] = useState('');
  const [department, setDepartment] = useState('Special Projects');
  const [level, setLevel] = useState(5);
  const [tier, setTier] = useState('fast');
  const [prompt, setPrompt] = useState('');
  const [isHiring, setIsHiring] = useState(false);
  const [hireError, setHireError] = useState<string | null>(null);

  // Group headcount by department
  const depts: Record<string, number> = {};
  for (const a of agents) {
    if (a.status === 'active') {
      depts[a.department] = (depts[a.department] || 0) + 1;
    }
  }

  const handleHire = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    setIsHiring(true);
    setHireError(null);
    try {
      await apiClient.hireAgent({
        title,
        department,
        level,
        model_tier: tier,
        system_prompt: prompt,
      });
      await fetchAgents();
      setTitle('');
      setPrompt('');
    } catch (err) {
      setHireError(err instanceof Error ? err.message : 'Could not hire this agent.');
      console.error('Failed to hire dynamic agent', err);
    } finally {
      setIsHiring(false);
    }
  };

  return (
    <div className="p-4 flex flex-col space-y-4 text-xs overflow-y-auto max-h-[calc(100vh-140px)]">
      {/* Department Headcount Summary */}
      <div className="flex flex-col gap-2">
        <span className="font-semibold text-slate-300 flex items-center gap-1.5">
          <Users size={14} className="text-sky-400" /> Company Roster ({agents.filter(a => a.status === 'active').length} Active Agents)
        </span>
        <div className="grid grid-cols-2 gap-1.5">
          {Object.entries(depts).map(([dept, count]) => (
            <div key={dept} className="flex justify-between p-2 rounded bg-slate-900 border border-slate-800 text-[11px]">
              <span className="text-slate-300">{dept}</span>
              <span className="font-mono text-sky-400 font-semibold">{count}</span>
            </div>
          ))}
        </div>
      </div>

      <section className="flex flex-col gap-2">
        <h3 className="text-xs font-medium text-slate-200">Team roster</h3>
        <div className="flex flex-col divide-y divide-slate-800 border-y border-slate-800">
          {agents.filter((agent) => agent.status === 'active').map((agent) => (
            <button
              type="button"
              key={agent.id}
              onClick={() => setSelectedAgent(agent.id)}
              className="flex items-center gap-3 py-2.5 text-left hover:bg-slate-900"
            >
              <AgentAvatar agent={agent} size={34} />
              <span className="flex min-w-0 flex-1 flex-col gap-1">
                <strong className="truncate text-xs font-medium text-slate-200">{agent.display_name}</strong>
                <span className="truncate text-[10px] text-slate-400">{agent.department}, {agent.role_key}</span>
              </span>
              <span className="text-[10px] text-slate-500">Level {agent.level}</span>
            </button>
          ))}
        </div>
      </section>

      {/* Dynamic Agent Hire Form */}
      {hireError && <p className='app-inline-error' role='alert'>{hireError}</p>}
      <form onSubmit={handleHire} className="p-3 rounded-lg border border-slate-800 bg-slate-900/60 flex flex-col space-y-3">
        <span className="font-semibold text-slate-200 flex items-center gap-1.5 pb-2 border-b border-slate-800">
          <UserPlus size={14} className="text-emerald-400" /> Hire New Dynamic Agent
        </span>

        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-slate-400">Role Title</label>
          <input
            type="text"
            required
            placeholder="e.g. Smart Contract Auditor"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="p-1.5 rounded bg-slate-950 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-sky-500"
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-slate-400">Department</label>
            <select
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              className="p-1.5 rounded bg-slate-950 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-sky-500"
            >
              <option value="Special Projects">Special Projects</option>
              <option value="Engineering">Engineering</option>
              <option value="Design">Design</option>
              <option value="Marketing">Marketing</option>
              <option value="Content">Content</option>
              <option value="Research">Research</option>
              <option value="Finance">Finance</option>
              <option value="Operations">Operations</option>
              <option value="Support">Support</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-slate-400">Model Tier</label>
            <select
              value={tier}
              onChange={(e) => setTier(e.target.value)}
              className="p-1.5 rounded bg-slate-950 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-sky-500"
            >
              <option value="fast">Fast</option>
              <option value="smart">Smart</option>
              <option value="premium">Premium</option>
            </select>
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-slate-400">System Directives</label>
          <textarea
            rows={3}
            placeholder="Describe specialized skills, authority, and output standards..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            className="p-1.5 rounded bg-slate-950 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-sky-500"
          />
        </div>

        <button
          type="submit"
          disabled={isHiring}
          className="mt-1 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium flex items-center justify-center gap-1.5 transition-colors text-xs"
        >
          <Sparkles size={13} />
          {isHiring ? 'Allocating Desk...' : 'Deploy to Office'}
        </button>
      </form>
    </div>
  );
};
