import React, { useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { AgentAvatar } from '../components/AgentAvatar';
import { Briefcase, Plus, Send, Building2, CheckCircle2, CirclePause, CircleStop, AlertCircle } from 'lucide-react';

const statusLabel: Record<string, string> = {
  active: 'Active', paused: 'Paused', completed: 'Completed', stopped: 'Stopped',
};

export const LeftSidebar: React.FC<{ onOpenIntake: () => void }> = ({ onOpenIntake }) => {
  const {
    projects, activeProjectId, setActiveProject, fetchTaskTree,
    setActiveDrawerTab, agents, networkStatus,
  } = useAppStore();
  const [quickTitle, setQuickTitle] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const ceo = agents.find((agent) => agent.role_key === 'ceo');
  const activeProject = projects.find((project) => project.id === activeProjectId);

  const handleQuickSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!quickTitle.trim() || !activeProjectId) return;
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      await apiClient.submitTask(activeProjectId, {
        title: quickTitle.trim(),
        description: quickTitle.trim(),
        acceptance_criteria: ['Deliverable complete'],
      });
      setQuickTitle('');
      await fetchTaskTree();
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Could not send this task.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <aside className="app-sidebar">
      <div className="app-sidebar-heading">
        <div className="app-sidebar-section-title">Projects</div>
        <div className="app-sidebar-heading-actions">
          <button type="button" className="app-sidebar-manage" onClick={() => setActiveDrawerTab('projects')}>
            Manage
          </button>
          <button type="button" className="app-icon-button" onClick={onOpenIntake} title="Create project" aria-label="Create project">
            <Plus size={15} />
          </button>
        </div>
      </div>

      <div className="app-sidebar-projects app-scroll">
        {projects.length === 0 ? (
          <div className="app-sidebar-empty">
            <Briefcase size={19} />
            <strong>No projects yet</strong>
            <p>Create a workspace to start assigning work to the team.</p>
            <button type="button" className="app-button app-button-primary" onClick={onOpenIntake}>Create project</button>
          </div>
        ) : projects.map((project) => {
          const selected = project.id === activeProjectId;
          return (
            <button
              type="button"
              key={project.id}
              onClick={() => void setActiveProject(project.id)}
              className={'app-project-link' + (selected ? ' app-project-link-selected' : '')}
              aria-current={selected ? 'page' : undefined}
            >
              <span className="app-project-link-icon"><Building2 size={15} /></span>
              <span className="app-project-link-copy">
                <strong>{project.name}</strong>
                {project.client_name && <span>{project.client_name}</span>}
                <span className={'app-project-state app-project-state-' + project.status}>
                  {project.status === 'completed' ? <CheckCircle2 size={11} /> : project.status === 'paused' ? <CirclePause size={11} /> : project.status === 'stopped' ? <CircleStop size={11} /> : <span className="app-project-state-marker" />}
                  {statusLabel[project.status] || project.status}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      <div className="app-dispatch">
        <div className="app-dispatch-heading">
          {ceo ? <AgentAvatar agent={ceo} size={36} /> : <span className="app-brand-mark"><Building2 size={17} /></span>}
          <div>
            <strong>Send work to the CEO</strong>
            <span>{activeProject ? activeProject.name : 'Select a project first'}</span>
          </div>
        </div>
        <form onSubmit={handleQuickSubmit} className="app-dispatch-form">
          <label htmlFor="quick-ceo-task">New task</label>
          <textarea
            id="quick-ceo-task"
            placeholder={activeProject ? 'Describe the work to delegate…' : 'Choose a project above'}
            disabled={!activeProject || isSubmitting || networkStatus === 'offline'}
            value={quickTitle}
            onChange={(event) => setQuickTitle(event.target.value)}
            rows={3}
          />
          <button type="submit" className="app-button app-button-primary" disabled={!activeProject || isSubmitting || !quickTitle.trim() || networkStatus === 'offline'}>
            <Send size={13} /> {isSubmitting ? 'Sending' : 'Dispatch task'}
          </button>
        </form>
        {submitError && <p className="app-inline-error" role="alert"><AlertCircle size={12} /> {submitError}</p>}
        {networkStatus === 'offline' && <p className="app-inline-note">Dispatch is unavailable while offline.</p>}
      </div>
    </aside>
  );
};
