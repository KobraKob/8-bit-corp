import React, { useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { X, Briefcase, Sparkles, BookOpen } from 'lucide-react';

const PLAYBOOKS = [
  {
    name: 'Landing Page & Brand Kit',
    brief: 'Design and build a responsive retro landing page with SVG logo, typography specs, and clean HTML/CSS components.',
  },
  {
    name: 'Full-Stack Web App',
    brief: 'Develop full-stack web application with REST API endpoints, relational database models, and interactive client UI.',
  },
  {
    name: 'Investor Pitch & Proposal',
    brief: 'Draft comprehensive corporate client proposal, milestone breakdown quote, market research slides, and agreement outline.',
  },
];

export const ProjectIntakeModal: React.FC<{ isOpen: boolean; onClose: () => void }> = ({
  isOpen,
  onClose,
}) => {
  const { fetchProjects, setActiveProject, networkStatus } = useAppStore();

  const [name, setName] = useState('');
  const [clientName, setClientName] = useState('');
  const [brief, setBrief] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !brief.trim()) return;

    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const proj = await apiClient.createProject({
        name,
        client_name: clientName || undefined,
        brief,
      });

      // Submit root task to CEO
      await apiClient.submitTask(proj.id, {
        title: `Deliver: ${proj.name}`,
        description: proj.brief,
        acceptance_criteria: ['Complete project deliverable meeting all client specifications'],
      });

      await fetchProjects();
      await setActiveProject(proj.id);
      onClose();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Could not create this project.');
      console.error('Failed to create project', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const applyPlaybook = (p: typeof PLAYBOOKS[0]) => {
    setName(p.name);
    setBrief(p.brief);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/90 p-4">
      <div role="dialog" aria-modal="true" aria-labelledby="project-intake-title" className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full p-5 flex flex-col space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Briefcase size={18} className="text-sky-400" />
            <h2 id="project-intake-title" className="text-sm font-medium text-slate-100">New project</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white" aria-label="Close project intake">
            <X size={16} />
          </button>
        </div>

        {/* Reusable Playbooks */}
        <div className="flex flex-col gap-1.5">
          <label className="text-[11px] font-semibold text-slate-400 flex items-center gap-1">
            <BookOpen size={12} /> Fast-Start Playbooks
          </label>
          <div className="flex flex-wrap gap-1.5">
            {PLAYBOOKS.map((p) => (
              <button
                key={p.name}
                type="button"
                onClick={() => applyPlaybook(p)}
                className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[11px] text-slate-200 transition-colors"
              >
                {p.name}
              </button>
            ))}
          </div>
        </div>

        {submitError && <p className="app-inline-error" role="alert">{submitError}</p>}
      <form onSubmit={handleSubmit} className="flex flex-col space-y-3">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-slate-300">Project Name</label>
            <input
              type="text"
              required
              placeholder="e.g. Pixel Cyberpunk Landing Page"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="p-2 rounded bg-slate-950 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-sky-500"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-slate-300">Client / Organization Name (Optional)</label>
            <input
              type="text"
              placeholder="e.g. Acme Corp"
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
              className="p-2 rounded bg-slate-950 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-sky-500"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-slate-300">Comprehensive Brief & Requirements</label>
            <textarea
              rows={4}
              required
              placeholder="Specify requirements, constraints, deliverable expectations..."
              value={brief}
              onChange={(e) => setBrief(e.target.value)}
              className="p-2 rounded bg-slate-950 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-sky-500 leading-relaxed font-mono"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 rounded border border-slate-700 text-slate-300 hover:bg-slate-800 text-xs"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || networkStatus === 'offline'}
              className="px-4 py-1.5 rounded bg-sky-600 hover:bg-sky-500 text-white font-medium text-xs flex items-center gap-1.5 transition-all"
            >
              <Sparkles size={13} />
              {networkStatus === 'offline' ? 'Offline' : isSubmitting ? 'Sending to CEO...' : 'Submit to CEO'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
