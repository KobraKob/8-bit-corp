import React, { useMemo, useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { AgentAvatar } from '../components/AgentAvatar';
import { UserPlus, Users, Sparkles, RefreshCw, ChevronRight } from 'lucide-react';

export const OrgEditorPanel: React.FC = () => {
  const { agents, agentsLoading, agentsError, fetchAgents, setSelectedAgent, networkStatus } = useAppStore();
  const [title, setTitle] = useState('');
  const [department, setDepartment] = useState('Special Projects');
  const [level, setLevel] = useState(5);
  const [tier, setTier] = useState('fast');
  const [prompt, setPrompt] = useState('');
  const [isHiring, setIsHiring] = useState(false);
  const [hireError, setHireError] = useState<string | null>(null);
  const [hireSuccess, setHireSuccess] = useState<string | null>(null);
  const activeAgents = agents.filter((agent) => agent.status === 'active');
  const departments = useMemo(() => {
    const result = new Map<string, number>();
    activeAgents.forEach((agent) => result.set(agent.department, (result.get(agent.department) || 0) + 1));
    return [...result.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [activeAgents]);

  const handleHire = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!title.trim() || networkStatus === 'offline') return;
    setIsHiring(true);
    setHireError(null);
    setHireSuccess(null);
    try {
      const agent = await apiClient.hireAgent({
        title: title.trim(),
        department,
        level,
        model_tier: tier,
        system_prompt: prompt,
      });
      await fetchAgents();
      setTitle('');
      setPrompt('');
      setHireSuccess(agent.display_name + ' joined the office.');
    } catch (error) {
      setHireError(error instanceof Error ? error.message : 'Could not create this agent.');
    } finally {
      setIsHiring(false);
    }
  };

  return (
    <section className="people-panel app-panel">
      <header className="people-header">
        <div>
          <h2><Users size={16} /> People</h2>
          <p>Team roster, roles and department capacity</p>
        </div>
        <button type="button" className="app-icon-button" onClick={() => void fetchAgents()} disabled={networkStatus === 'offline'} aria-label="Refresh team roster">
          <RefreshCw size={14} />
        </button>
      </header>

      {agentsError && (
        <div className="task-stale-notice" role="alert">
          {agents.length ? 'Showing the last available team roster. ' : ''}
          {agentsError}
        </div>
      )}
      {networkStatus === 'offline' && <p className="app-inline-note">Offline. Hiring and editing agents require a server connection.</p>}

      <div className="people-overview">
        <div><strong className="app-measured">{activeAgents.length}</strong><span>Active agents</span></div>
        <div><strong className="app-measured">{departments.length}</strong><span>Departments</span></div>
        <div><strong className="app-measured">{agents.filter((agent) => agent.status === 'retired').length}</strong><span>Retired</span></div>
      </div>

      <section className="people-roster">
        <header><h3>Team directory</h3><span>{activeAgents.length} people</span></header>
        {agentsLoading && agents.length === 0 ? (
          <div className="task-tree-skeleton" aria-label="Loading team roster">
            {[0, 1, 2, 3].map((item) => <div className="task-tree-skeleton-item" key={item}><div className="app-skeleton app-skeleton-line" /><div className="app-skeleton app-skeleton-short" /></div>)}
          </div>
        ) : activeAgents.length === 0 ? (
          <div className="app-empty"><Users size={22} /><strong>No team members loaded</strong><p>{agentsError || 'The configured company roster will appear when the backend is available.'}</p></div>
        ) : (
          <div className="people-list">
            {activeAgents.map((agent) => (
              <button type="button" key={agent.id} className="people-row" onClick={() => setSelectedAgent(agent.id)}>
                <AgentAvatar agent={agent} size={38} />
                <span className="people-row-copy">
                  <strong>{agent.display_name}</strong>
                  <span>{agent.department} · {agent.role_key}</span>
                </span>
                <span className="people-row-level">L{agent.level}</span>
                <ChevronRight size={14} />
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="department-list">
        <h3>Department capacity</h3>
        {departments.map(([name, count]) => (
          <div className="department-row" key={name}><span>{name}</span><strong className="app-measured">{count}</strong></div>
        ))}
      </section>

      <section className="people-hire">
        <header><h3><UserPlus size={15} /> Add an agent</h3><span>Creates a new role</span></header>
        {hireError && <p className="app-inline-error" role="alert">{hireError}</p>}
        {hireSuccess && <p className="app-inline-success" role="status">{hireSuccess}</p>}
        <form onSubmit={handleHire}>
          <label htmlFor="agent-role-title">Role title</label>
          <input id="agent-role-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="e.g. Security auditor" required />
          <div className="people-form-grid">
            <div>
              <label htmlFor="agent-department">Department</label>
              <select id="agent-department" value={department} onChange={(event) => setDepartment(event.target.value)}>
                {['Special Projects', 'Engineering', 'Design', 'Marketing', 'Content', 'Research', 'Finance', 'Operations', 'Support'].map((name) => <option key={name}>{name}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="agent-level">Seniority level</label>
              <select id="agent-level" value={level} onChange={(event) => setLevel(Number(event.target.value))}>
                {[4, 5, 6, 7, 8].map((value) => <option key={value} value={value}>Level {value}</option>)}
              </select>
            </div>
          </div>
          <label htmlFor="agent-model-tier">Model tier</label>
          <select id="agent-model-tier" value={tier} onChange={(event) => setTier(event.target.value)}>
            <option value="fast">Fast</option><option value="smart">Smart</option><option value="premium">Premium</option>
          </select>
          <label htmlFor="agent-system-prompt">Specialized instructions</label>
          <textarea id="agent-system-prompt" rows={4} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Define specialist skills, authority and expected outputs." />
          <button type="submit" className="app-button app-button-primary" disabled={isHiring || networkStatus === 'offline' || !title.trim()}>
            <Sparkles size={13} /> {isHiring ? 'Creating agent' : 'Add to company'}
          </button>
        </form>
      </section>
    </section>
  );
};
