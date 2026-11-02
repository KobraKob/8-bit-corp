import React, { useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { Briefcase, Plus, Send, Building2, CheckCircle2 } from 'lucide-react';

export const LeftSidebar: React.FC<{ onOpenIntake: () => void }> = ({ onOpenIntake }) => {
  const { projects, activeProjectId, setActiveProject, fetchTaskTree } = useAppStore();
  const [quickTitle, setQuickTitle] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const activeProject = projects.find((p) => p.id === activeProjectId);

  const handleQuickSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickTitle.trim() || !activeProjectId) return;

    setIsSubmitting(true);
    try {
      await apiClient.submitTask(activeProjectId, {
        title: quickTitle,
        description: quickTitle,
        acceptance_criteria: ['Deliverable complete'],
      });
      setQuickTitle('');
      await fetchTaskTree();
    } catch (err) {
      console.error('Failed to submit task to CEO', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-72 bg-slate-950 border-r border-slate-800 flex flex-col justify-between h-screen text-xs select-none">
      {/* Brand Header */}
      <div className="p-3 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-sky-500/20 border border-sky-400/40 flex items-center justify-center">
            <Building2 size={14} className="text-sky-400" />
          </div>
          <span className="font-bold text-sm tracking-wide text-slate-100 font-mono">PIXEL CORP</span>
        </div>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-sky-950 border border-sky-800 text-sky-400 font-mono">
          v1.0
        </span>
      </div>

      {/* Projects List */}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Client Projects</span>
          <button
            onClick={onOpenIntake}
            className="p-1 rounded bg-sky-600/20 hover:bg-sky-600/30 text-sky-400 border border-sky-500/30 transition-all"
            title="New Project Brief"
          >
            <Plus size={13} />
          </button>
        </div>

        <div className="flex flex-col space-y-1">
          {projects.map((proj) => {
            const isActive = proj.id === activeProjectId;
            return (
              <div
                key={proj.id}
                onClick={() => setActiveProject(proj.id)}
                className={`p-2.5 rounded-lg border cursor-pointer transition-all ${
                  isActive
                    ? 'border-sky-500 bg-sky-950/40 shadow-sm'
                    : 'border-slate-800/80 bg-slate-900/40 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-200 truncate">{proj.name}</span>
                  {proj.status === 'completed' && <CheckCircle2 size={13} className="text-emerald-400" />}
                </div>
                {proj.client_name && (
                  <span className="text-[10px] text-slate-400 font-mono">Client: {proj.client_name}</span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Quick Task Intake to CEO */}
      <div className="p-3 border-t border-slate-800 bg-slate-900/40">
        <span className="text-[11px] font-semibold text-slate-300 block mb-1.5">Direct CEO Dispatch</span>
        <form onSubmit={handleQuickSubmit} className="flex gap-1.5">
          <input
            type="text"
            placeholder={activeProject ? 'Task for CEO...' : 'Select a project first'}
            disabled={!activeProject || isSubmitting}
            value={quickTitle}
            onChange={(e) => setQuickTitle(e.target.value)}
            className="flex-1 bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
          />
          <button
            type="submit"
            disabled={!activeProject || isSubmitting || !quickTitle.trim()}
            className="px-2.5 py-1.5 rounded bg-sky-600 hover:bg-sky-500 disabled:opacity-40 text-white font-medium transition-all"
          >
            <Send size={12} />
          </button>
        </form>
      </div>
    </div>
  );
};
