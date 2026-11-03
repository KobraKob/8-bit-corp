import React, { useMemo, useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { Activity, RefreshCw, ChevronDown, Clock3 } from 'lucide-react';

const FILTERS = [
  { value: 'all', label: 'All events' },
  { value: 'task.', label: 'Task lifecycle' },
  { value: 'agent.', label: 'Agent actions' },
  { value: 'artifact.', label: 'Deliverables' },
  { value: 'approval.', label: 'Approvals' },
  { value: 'project.', label: 'Projects' },
  { value: 'system.', label: 'System' },
];

export const EventLogPanel: React.FC = () => {
  const { events, eventsLoading, eventsError, fetchEvents, networkStatus } = useAppStore();
  const [filterType, setFilterType] = useState('all');
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);

  const filtered = useMemo(
    () => filterType === 'all' ? events : events.filter((event) => event.type.startsWith(filterType)),
    [events, filterType]
  );

  return (
    <section className="event-log-panel app-panel">
      <header className="event-log-header">
        <div>
          <h2><Activity size={16} /> Activity log</h2>
          <p>Persisted events from the orchestration engine</p>
        </div>
        <button type="button" className="app-icon-button" onClick={() => void fetchEvents()} disabled={networkStatus === 'offline'} aria-label="Refresh activity log">
          <RefreshCw size={14} />
        </button>
      </header>

      <div className="event-log-toolbar">
        <label htmlFor="event-type-filter">Show</label>
        <select id="event-type-filter" value={filterType} onChange={(event) => setFilterType(event.target.value)}>
          {FILTERS.map((filter) => <option key={filter.value} value={filter.value}>{filter.label}</option>)}
        </select>
        <span className="app-measured">{filtered.length} events</span>
      </div>

      {eventsError && (
        <div className="task-stale-notice" role="alert">
          {networkStatus === 'offline' ? 'Offline. ' : 'Could not refresh. '}
          {events.length > 0 ? 'Showing the last event snapshot.' : eventsError}
        </div>
      )}

      {eventsLoading && events.length === 0 ? (
        <div className="task-tree-skeleton" aria-label="Loading activity">
          {[0, 1, 2, 3].map((item) => <div className="task-tree-skeleton-item" key={item}><div className="app-skeleton app-skeleton-line" /><div className="app-skeleton app-skeleton-wide" /></div>)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="app-empty">
          <Activity size={22} />
          <strong>No matching events</strong>
          <p>{events.length === 0 ? 'Events appear here when the backend records task, agent, project, or approval activity.' : 'Choose another filter to inspect more of the event history.'}</p>
          {eventsError && <button type="button" className="app-button" onClick={() => void fetchEvents()} disabled={networkStatus === 'offline'}>Retry</button>}
        </div>
      ) : (
        <div className="event-log-list">
          {filtered.map((event) => {
            const selected = selectedEventId === event.id;
            return (
              <article key={event.id} className={'event-record' + (selected ? ' event-record-selected' : '')}>
                <button
                  type="button"
                  className="event-record-toggle"
                  onClick={() => setSelectedEventId(selected ? null : event.id)}
                  aria-expanded={selected}
                >
                  <span className="event-record-marker" aria-hidden="true" />
                  <span className="event-record-copy">
                    <strong>{event.type.replaceAll('.', ' ')}</strong>
                    <span>{event.task_id ? 'Task ' + event.task_id : event.project_id ? 'Project ' + event.project_id : 'Company event'}</span>
                  </span>
                  <time dateTime={event.ts}><Clock3 size={11} />{new Date(event.ts).toLocaleString()}</time>
                  <ChevronDown size={14} className={selected ? 'event-record-chevron-open' : ''} />
                </button>
                {selected && (
                  <div className="event-record-details">
                    <dl>
                      <div><dt>Event ID</dt><dd className="app-measured">#{event.id}</dd></div>
                      {event.agent_id && <div><dt>Agent</dt><dd>{event.agent_id}</dd></div>}
                      {event.project_id && <div><dt>Project</dt><dd>{event.project_id}</dd></div>}
                      {event.task_id && <div><dt>Task</dt><dd>{event.task_id}</dd></div>}
                    </dl>
                    <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
};
