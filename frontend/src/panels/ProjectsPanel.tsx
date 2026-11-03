import React, { useMemo, useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { Project } from '../api/types';
import { Archive, Clock3, Pause, Play, Search, Square, Trash2, FolderOpen, RefreshCw } from 'lucide-react';

type Filter = 'all' | 'active' | 'paused' | 'completed' | 'stopped';
const filters: { id: Filter; label: string }[] = [
  { id: 'all', label: 'All' }, { id: 'active', label: 'Active' },
  { id: 'paused', label: 'Paused' }, { id: 'completed', label: 'Completed' },
  { id: 'stopped', label: 'Stopped' },
];
const statusStyles: Record<string, string> = {
  active: 'project-status-active', paused: 'project-status-paused',
  completed: 'project-status-completed', stopped: 'project-status-stopped',
};

export const ProjectsPanel: React.FC = () => {
  const {
    projects, activeProjectId, fetchProjects, setActiveProject, clearActiveProject,
    setActiveDrawerTab, networkStatus, projectsError, projectsLoading,
  } = useAppStore();
  const [filter, setFilter] = useState<Filter>('all');
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState('');

  const counts = useMemo(() => ({
    all: projects.length,
    active: projects.filter((project) => project.status === 'active').length,
    paused: projects.filter((project) => project.status === 'paused').length,
    completed: projects.filter((project) => project.status === 'completed').length,
    stopped: projects.filter((project) => project.status === 'stopped').length,
  }), [projects]);
  const visible = useMemo(() => projects.filter((project) =>
    (filter === 'all' || project.status === filter) &&
    (project.name + ' ' + (project.client_name || '') + ' ' + project.brief).toLowerCase().includes(query.toLowerCase())
  ), [projects, filter, query]);

  const action = async (project: Project, kind: 'pause' | 'resume' | 'stop' | 'delete') => {
    if (networkStatus === 'offline') return;
    if (kind === 'stop' && !window.confirm('Stop "' + project.name + '"? Queued tasks and active workers will be cancelled.')) return;
    if (kind === 'delete' && !window.confirm('Permanently delete "' + project.name + '" and its deliverables? This cannot be undone.')) return;
    setBusy(project.id);
    setError('');
    try {
      if (kind === 'pause') await apiClient.pauseProject(project.id);
      if (kind === 'resume') await apiClient.resumeProject(project.id);
      if (kind === 'stop') await apiClient.stopProject(project.id);
      if (kind === 'delete') {
        await apiClient.deleteProject(project.id);
        if (activeProjectId === project.id) clearActiveProject();
      }
      await fetchProjects();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Project action failed.');
    } finally {
      setBusy(null);
    }
  };

  const open = async (project: Project, tab: 'tree' | 'artifacts' = 'tree') => {
    await setActiveProject(project.id);
    setActiveDrawerTab(tab);
  };

  return (
    <section className="projects-panel app-panel">
      <header className="projects-header">
        <div className="projects-title-row">
          <div>
            <h2>Project portfolio</h2>
            <p>Track work from intake through delivery.</p>
          </div>
          <button type="button" className="app-icon-button" onClick={() => void fetchProjects()} disabled={networkStatus === 'offline'} aria-label="Refresh project portfolio">
            <RefreshCw size={14} />
          </button>
        </div>
        <label className="projects-search">
          <Search size={14} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search projects or clients" />
        </label>
        <p className="projects-pause-note">Pause holds queued work. Active agent steps may finish before the pause takes full effect.</p>
        <div className="projects-filters" aria-label="Filter projects">
          {filters.map((item) => (
            <button key={item.id} type="button" onClick={() => setFilter(item.id)} aria-pressed={filter === item.id} className={filter === item.id ? 'projects-filter projects-filter-active' : 'projects-filter'}>
              {item.label}<span>{counts[item.id]}</span>
            </button>
          ))}
        </div>
      </header>

      {projectsError && <div className="task-stale-notice" role="alert">{networkStatus === 'offline' ? 'Offline. ' : 'Project refresh failed. '}Showing the last successful project list.</div>}
      {error && <div className="app-error mx-3 mt-3" role="alert">{error}</div>}

      <div className="projects-list app-scroll">
        {projectsLoading && projects.length === 0 ? (
          <div className="task-tree-skeleton" aria-label="Loading projects">
            {[0, 1, 2].map((item) => <div className="task-tree-skeleton-item" key={item}><div className="app-skeleton app-skeleton-line" /><div className="app-skeleton app-skeleton-wide" /><div className="app-skeleton app-skeleton-short" /></div>)}
          </div>
        ) : visible.length === 0 ? (
          <div className="app-empty">
            <Archive size={22} />
            <strong>{query ? 'No matching projects' : filter === 'completed' ? 'No completed projects yet' : 'No projects in this view'}</strong>
            <p>{networkStatus === 'offline' && projects.length === 0 ? 'No saved project list is available in this session.' : filter === 'completed' ? 'Projects move here after their final work package is approved.' : 'Try another status filter or clear your search.'}</p>
          </div>
        ) : visible.map((project) => {
          const status = project.status || 'active';
          const loading = busy === project.id;
          return (
            <article key={project.id} className={'project-record' + (activeProjectId === project.id ? ' project-record-selected' : '')}>
              <div className="project-record-heading">
                <div>
                  <h3>{project.name}</h3>
                  <p>{project.client_name || 'No client assigned'}</p>
                </div>
                <span className={'project-status ' + (statusStyles[status] || '')}>{status}</span>
              </div>
              <p className="project-record-brief">{project.brief}</p>
              <div className="project-record-meta">
                <span><Clock3 size={12} /> Created {new Date(project.created_at).toLocaleDateString()}</span>
                {project.due_at && <span>Due {new Date(project.due_at).toLocaleDateString()}</span>}
              </div>
              <div className="project-record-actions">
                <button type="button" className="app-button app-button-primary" onClick={() => void open(project)}><FolderOpen size={12} /> Open workspace</button>
                <button type="button" className="app-button" onClick={() => void open(project, 'artifacts')}><Archive size={12} /> Deliverables</button>
                {status === 'active' && <button type="button" className="app-button" disabled={loading || networkStatus === 'offline'} onClick={() => void action(project, 'pause')}><Pause size={12} /> Pause</button>}
                {status === 'paused' && <button type="button" className="app-button" disabled={loading || networkStatus === 'offline'} onClick={() => void action(project, 'resume')}><Play size={12} /> Resume</button>}
                {(status === 'active' || status === 'paused') && <button type="button" className="app-button" disabled={loading || networkStatus === 'offline'} onClick={() => void action(project, 'stop')}><Square size={11} /> Stop</button>}
                {(status === 'completed' || status === 'stopped') && <button type="button" className="app-button project-delete" disabled={loading || networkStatus === 'offline'} onClick={() => void action(project, 'delete')}><Trash2 size={12} /> Delete</button>}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
};
