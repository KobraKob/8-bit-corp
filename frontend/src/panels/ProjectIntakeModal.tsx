import React, { useEffect, useRef, useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { X, Briefcase, Sparkles, BookOpen } from 'lucide-react';

const PLAYBOOKS = [
  {
    name: 'Landing page',
    brief: 'Design and build a responsive landing page. Include brand direction, accessible layouts, production-ready components, and a concise handoff.',
  },
  {
    name: 'Full-stack application',
    brief: 'Plan and build a full-stack application with clear requirements, API contracts, data models, accessible user interface, and tests.',
  },
  {
    name: 'Research and proposal',
    brief: 'Research the market, compare credible alternatives, document assumptions and evidence, and prepare a decision-ready proposal.',
  },
];

export const ProjectIntakeModal: React.FC<{ isOpen: boolean; onClose: () => void }> = ({ isOpen, onClose }) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  const { fetchProjects, setActiveProject, networkStatus } = useAppStore();
  const [name, setName] = useState('');
  const [clientName, setClientName] = useState('');
  const [brief, setBrief] = useState('');
  const [createdProjectId, setCreatedProjectId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const dialog = dialogRef.current;
    const focusable = () => dialog?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    window.requestAnimationFrame(() => focusable()?.[0]?.focus());

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      }
      if (event.key !== 'Tab') return;
      const items = Array.from(focusable() || []);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      previousFocus?.focus();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const resetAndClose = () => {
    setName('');
    setClientName('');
    setBrief('');
    setCreatedProjectId(null);
    setSubmitError(null);
    onClose();
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim() || !brief.trim() || networkStatus === 'offline') return;
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      let projectId = createdProjectId;
      if (!projectId) {
        const project = await apiClient.createProject({
          name: name.trim(),
          client_name: clientName.trim() || undefined,
          brief: brief.trim(),
        });
        projectId = project.id;
        setCreatedProjectId(project.id);
        await fetchProjects();
        await setActiveProject(project.id);
      }

      try {
        await apiClient.submitTask(projectId, {
          title: 'Deliver: ' + name.trim(),
          description: brief.trim(),
          acceptance_criteria: ['Complete the project deliverable to the agreed requirements.'],
        });
      } catch (error) {
        await fetchProjects();
        await setActiveProject(projectId);
        setSubmitError('Project created successfully, but the CEO task was not dispatched. Retry here; the project will not be duplicated. Details: ' +
          (error instanceof Error ? error.message : 'Request failed.'));
        return;
      }

      await fetchProjects();
      await setActiveProject(projectId);
      resetAndClose();
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Could not create this project.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="project-modal-backdrop">
      <div ref={dialogRef} className="project-modal" role="dialog" aria-modal="true" aria-labelledby="project-intake-title" aria-describedby="project-intake-description">
        <header className="project-modal-header">
          <div>
            <span className="project-modal-icon"><Briefcase size={17} /></span>
            <div>
              <h2 id="project-intake-title">Create project</h2>
              <p id="project-intake-description">A separate workspace for each client engagement.</p>
            </div>
          </div>
          <button type="button" className="app-icon-button" onClick={resetAndClose} aria-label="Close project intake">
            <X size={16} />
          </button>
        </header>

        <section className="project-playbooks">
          <label><BookOpen size={13} /> Start from a brief</label>
          <div>
            {PLAYBOOKS.map((playbook) => (
              <button key={playbook.name} type="button" onClick={() => { setName(playbook.name); setBrief(playbook.brief); }}>
                {playbook.name}
              </button>
            ))}
          </div>
        </section>

        {submitError && <div className="app-error" role="alert">{submitError}</div>}
        {createdProjectId && <p className="app-inline-note">Project already exists. Retrying will only dispatch its initial task.</p>}

        <form className="project-modal-form" onSubmit={handleSubmit}>
          <div>
            <label htmlFor="project-name">Project name</label>
            <input id="project-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Customer portal redesign" required disabled={Boolean(createdProjectId)} />
          </div>
          <div>
            <label htmlFor="project-client">Client or organisation <span>Optional</span></label>
            <input id="project-client" value={clientName} onChange={(event) => setClientName(event.target.value)} placeholder="Client name" disabled={Boolean(createdProjectId)} />
          </div>
          <div>
            <label htmlFor="project-brief">Project brief</label>
            <textarea id="project-brief" rows={6} value={brief} onChange={(event) => setBrief(event.target.value)} placeholder="Describe the outcome, requirements, constraints, and acceptance criteria." required disabled={Boolean(createdProjectId)} />
          </div>
          <footer>
            <button type="button" className="app-button" onClick={resetAndClose}>Cancel</button>
            <button type="submit" className="app-button app-button-primary" disabled={isSubmitting || networkStatus === 'offline' || !name.trim() || !brief.trim()}>
              <Sparkles size={13} />
              {networkStatus === 'offline' ? 'Offline' : isSubmitting ? 'Sending' : createdProjectId ? 'Retry CEO dispatch' : 'Create and dispatch'}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
};
