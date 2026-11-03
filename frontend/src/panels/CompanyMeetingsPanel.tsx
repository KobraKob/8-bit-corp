import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { CompanyMeeting } from '../api/types';
import { useAppStore } from '../state/useAppStore';
import { Users, RefreshCw, Video, CheckCircle2 } from 'lucide-react';

export const CompanyMeetingsPanel: React.FC = () => {
  const { activeProjectId, projects, networkStatus } = useAppStore();
  const [meetings, setMeetings] = useState<CompanyMeeting[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const load = async () => { setLoading(true); setError(null); try { setMeetings(await apiClient.getCompanyMeetings(activeProjectId || undefined)); } catch(e) { setError(e instanceof Error ? e.message : 'Could not load meetings.'); } finally { setLoading(false); } };
  useEffect(() => { void load(); }, [activeProjectId]);
  const convene = async () => { if (!activeProjectId) return; setCreating(true); setError(null); try { await apiClient.conveneCompanyMeeting(activeProjectId); await load(); } catch(e) { setError(e instanceof Error ? e.message : 'Could not convene meeting.'); } finally { setCreating(false); } };
  const projectName = projects.find(p => p.id === activeProjectId)?.name;
  return <section className="company-meetings-panel app-panel">
    <header className="event-log-header"><div><h2><Users size={16}/> Company meetings</h2><p>Manager coordination, blockers and decisions</p></div><button className="app-icon-button" type="button" onClick={() => void load()} aria-label="Refresh meetings"><RefreshCw size={14}/></button></header>
    {!activeProjectId && <p className="app-inline-note">Select a project to convene a coordination meeting.</p>}
    {activeProjectId && <div className="company-meeting-action"><span>{projectName || 'Active project'}</span><button className="app-button app-button-primary" type="button" onClick={() => void convene()} disabled={creating || networkStatus === 'offline'}><Video size={13}/>{creating ? 'Concluding…' : 'Convene managers'}</button></div>}
    {error && <div className="task-stale-notice" role="alert">{error}</div>}
    {loading ? <p className="app-inline-note">Loading meeting minutes…</p> : meetings.length === 0 ? <div className="app-empty"><Users size={22}/><strong>No meetings recorded</strong><p>Blocked tasks can trigger automatic coordination meetings. You can also convene managers manually.</p></div> :
      <div className="company-meeting-list">{meetings.map(meeting => <article className="company-meeting-card" key={meeting.id}>
        <header><div><strong>{meeting.title}</strong><span>{new Date(meeting.created_at).toLocaleString()} · {meeting.trigger}</span></div><small><CheckCircle2 size={12}/> {meeting.status}</small></header>
        <h4>Attendees</h4><p>{meeting.attendees.map(a => a.name+' · '+a.department).join(' / ') || 'No managers available'}</p>
        <h4>Department discussion</h4>{meeting.discussion.map((d,i) => <div className="company-meeting-discussion" key={i}><strong>{d.department}</strong><p>{d.position}</p></div>)}
        <h4>Decisions and actions</h4>{meeting.decisions.map((d,i) => <div className="company-meeting-decision" key={i}><strong>{d.decision}</strong><p>{d.action}</p><span>{d.owner_department} · {d.status}</span></div>)}
      </article>)}</div>}
  </section>;
};
