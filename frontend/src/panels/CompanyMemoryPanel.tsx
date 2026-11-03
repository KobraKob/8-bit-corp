import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { useAppStore } from '../state/useAppStore';
import { BookOpen, Search, Plus, RefreshCw } from 'lucide-react';

export const CompanyMemoryPanel: React.FC = () => {
  const { activeProjectId, projects, networkStatus } = useAppStore();
  const [query, setQuery] = useState('');
  const [notes, setNotes] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [tags, setTags] = useState('decision, research');
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true); setError(null);
    try { setNotes(await apiClient.getCompanyMemory(query, activeProjectId || undefined)); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not load company memory.'); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, [activeProjectId]);

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!title.trim() || !body.trim()) return;
    setSaving(true); setError(null);
    try {
      await apiClient.saveCompanyMemory({ title: title.trim(), body: body.trim(), tags, project_id: activeProjectId || undefined });
      setTitle(''); setBody(''); setShowForm(false); await load();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save memory.'); }
    finally { setSaving(false); }
  };

  return <section className="company-memory-panel app-panel">
    <header className="event-log-header"><div><h2><BookOpen size={16}/> Company memory</h2><p>Reusable client context, decisions and research</p></div>
      <button className="app-icon-button" type="button" onClick={() => void load()} disabled={networkStatus === 'offline'} aria-label="Refresh company memory"><RefreshCw size={14}/></button>
    </header>
    <div className="company-memory-tools">
      <form onSubmit={e => { e.preventDefault(); void load(); }}><label htmlFor="memory-query">Search knowledge</label><div className="company-memory-search"><input id="memory-query" value={query} onChange={e => setQuery(e.target.value)} placeholder="Client requirements, pricing, decisions…"/><button className="app-icon-button" type="submit" aria-label="Search memory"><Search size={14}/></button></div></form>
      <button className="app-button" type="button" onClick={() => setShowForm(v => !v)} disabled={networkStatus === 'offline'}><Plus size={13}/> Add memory</button>
    </div>
    {showForm && <form className="company-memory-form" onSubmit={save}>
      <label htmlFor="memory-title">Title</label><input id="memory-title" value={title} onChange={e => setTitle(e.target.value)} required maxLength={255} placeholder="Decision: use client-approved brand voice"/>
      <label htmlFor="memory-tags">Tags</label><input id="memory-tags" value={tags} onChange={e => setTags(e.target.value)} placeholder="decision, client, research"/>
      <label htmlFor="memory-body">Knowledge / decision / requirement</label><textarea id="memory-body" value={body} onChange={e => setBody(e.target.value)} rows={5} required placeholder="Record the source, rationale and constraints."/>
      <button className="app-button app-button-primary" type="submit" disabled={saving || networkStatus === 'offline'}>{saving ? 'Saving…' : 'Save to company memory'}</button>
    </form>}
    {error && <div className="task-stale-notice" role="alert">{error}</div>}
    {loading ? <p className="app-inline-note">Loading knowledge…</p> : notes.length === 0 ? <div className="app-empty"><BookOpen size={22}/><strong>No matching knowledge</strong><p>Project briefs are saved automatically. Managers and agents can add reusable decisions and research.</p></div> :
      <div className="company-memory-list">{notes.map(note => <article className="company-memory-item" key={note.id}><div><strong>{note.title}</strong><span>{note.project_id ? (projects.find(p => p.id === note.project_id)?.name || 'Project memory') : 'Company-wide'} · {note.tags || 'Uncategorized'}</span></div><p>{note.body}</p><time>{new Date(note.updated_at).toLocaleString()}</time></article>)}</div>}
  </section>;
};
