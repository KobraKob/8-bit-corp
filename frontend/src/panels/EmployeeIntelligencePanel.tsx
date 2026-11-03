import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { Activity, RefreshCw } from 'lucide-react';

export const EmployeeIntelligencePanel: React.FC = () => {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = async () => { setLoading(true); setError(null); try { setRows(await apiClient.getEmployeePerformance()); } catch(e) { setError(e instanceof Error ? e.message : 'Could not load performance history.'); } finally { setLoading(false); } };
  useEffect(() => { void load(); }, []);
  return <section className="employee-intelligence-panel app-panel">
    <header className="event-log-header"><div><h2><Activity size={16}/> Employee intelligence</h2><p>Evidence-based performance history by employee</p></div><button className="app-icon-button" type="button" onClick={() => void load()} aria-label="Refresh employee intelligence"><RefreshCw size={14}/></button></header>
    <p className="app-inline-note">Metrics are derived from assigned task history. Quality is a transparent proxy, not an automated judgment of an employee.</p>
    {error && <div className="task-stale-notice" role="alert">{error}</div>}
    {loading ? <p className="app-inline-note">Calculating performance history…</p> : rows.length === 0 ? <div className="app-empty"><Activity size={22}/><strong>No employee history yet</strong><p>Performance appears after employees receive and complete work.</p></div> :
      <div className="employee-intelligence-list">{rows.map(row => <article className="employee-intelligence-card" key={row.agent_id}>
        <header><div><strong>{row.display_name}</strong><span>{row.department} · {row.role_key}</span></div><small>{row.status}</small></header>
        <div className="employee-intelligence-metrics">
          <div><strong>{row.tasks_completed}/{row.tasks_assigned}</strong><span>Completed</span></div>
          <div><strong>{row.completion_rate == null ? '—' : Math.round(row.completion_rate*100)+'%'}</strong><span>Completion</span></div>
          <div><strong>{row.revision_count}</strong><span>Revisions</span></div>
          <div><strong>{row.reliability_rate == null ? '—' : Math.round(row.reliability_rate*100)+'%'}</strong><span>Reliability</span></div>
          <div><strong>{row.average_completion_seconds == null ? '—' : Math.round(row.average_completion_seconds/60)+'m'}</strong><span>Avg. time</span></div>
          <div><strong>{row.average_quality_score == null ? '—' : Math.round(row.average_quality_score*100)+'%'}</strong><span>Quality proxy</span></div>
        </div>
        <p>{row.quality_score_note}</p>
      </article>)}</div>}
  </section>;
};
