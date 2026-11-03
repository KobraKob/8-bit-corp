import React, { useMemo } from 'react';
import { useAppStore } from '../state/useAppStore';
import { TaskTreeNode } from '../api/types';
import { AgentAvatar } from '../components/AgentAvatar';
import {
  AlertCircle, CheckCircle2, Clock3, Layers, RefreshCw, ShieldAlert, XCircle,
} from 'lucide-react';

type Column = {
  key: string;
  title: string;
  statuses: string[];
  icon: React.ReactNode;
};

const COLUMNS: Column[] = [
  { key: 'queue', title: 'Queue', statuses: ['pending', 'assigned'], icon: <Clock3 size={14} /> },
  { key: 'working', title: 'Working', statuses: ['in_progress', 'integrating'], icon: <RefreshCw size={14} /> },
  { key: 'review', title: 'Review', statuses: ['in_review', 'reviewing', 'revision_requested'], icon: <ShieldAlert size={14} /> },
  { key: 'attention', title: 'Attention', statuses: ['blocked', 'failed'], icon: <AlertCircle size={14} /> },
  { key: 'closed', title: 'Closed', statuses: ['done', 'cancelled'], icon: <CheckCircle2 size={14} /> },
];

function flattenTree(nodes: TaskTreeNode[]): TaskTreeNode[] {
  const result: TaskTreeNode[] = [];
  const visit = (items: TaskTreeNode[]) => items.forEach((item) => {
    result.push(item);
    if (item.children?.length) visit(item.children);
  });
  visit(nodes);
  return result;
}

function labelFor(status: string): string {
  const labels: Record<string, string> = {
    pending: 'Pending', assigned: 'Queued', in_progress: 'Working',
    integrating: 'Integrating', in_review: 'Ready for review',
    reviewing: 'Reviewing', revision_requested: 'Changes requested',
    blocked: 'Blocked', failed: 'Failed', done: 'Complete', cancelled: 'Cancelled',
  };
  return labels[status] || status.replaceAll('_', ' ');
}

export const KanbanPanel: React.FC = () => {
  const {
    taskTree, setSelectedTask, selectedTaskId, agents,
    taskTreeLoading, taskTreeError, taskTreeUpdatedAt, fetchTaskTree,
    activeProjectId, networkStatus, projects,
  } = useAppStore();

  const allTasks = useMemo(() => flattenTree(taskTree), [taskTree]);
  const doneCount = allTasks.filter((task) => task.status === 'done').length;
  const progress = allTasks.length ? Math.round(doneCount / allTasks.length * 100) : 0;
  const project = projects.find((item) => item.id === activeProjectId);

  if (!activeProjectId) {
    return <div className="app-empty"><Layers size={24} /><strong>Choose a project</strong><p>Select a project to see its work board.</p></div>;
  }

  if (taskTreeLoading && allTasks.length === 0) {
    return (
      <div className="kanban-loading" aria-label="Loading task board">
        {COLUMNS.slice(0, 3).map((column) => (
          <div className="kanban-skeleton-column" key={column.key}>
            <div className="app-skeleton app-skeleton-line" />
            {[0, 1, 2].map((item) => <div className="kanban-skeleton-card" key={item}><div className="app-skeleton app-skeleton-wide" /><div className="app-skeleton app-skeleton-short" /></div>)}
          </div>
        ))}
      </div>
    );
  }

  if (allTasks.length === 0) {
    return (
      <div className="app-empty">
        <Layers size={24} />
        <strong>No tasks on this board</strong>
        <p>Submit a project brief to the CEO. Delegated work will appear in its status column.</p>
        {taskTreeError && <button className="app-button" type="button" onClick={() => void fetchTaskTree()} disabled={networkStatus === 'offline'}>Retry</button>}
      </div>
    );
  }

  return (
    <section className="kanban-panel app-panel">
      <header className="kanban-header">
        <div className="kanban-heading">
          <div>
            <h2>Work board</h2>
            <p>{project?.name || 'Project tasks'}</p>
          </div>
          <button type="button" className="app-icon-button" onClick={() => void fetchTaskTree()} disabled={taskTreeLoading} aria-label="Refresh work board">
            <RefreshCw size={15} />
          </button>
        </div>
        <div className="kanban-progress-copy">
          <strong>{progress}% complete</strong>
          <span>{doneCount} of {allTasks.length} work packages</span>
        </div>
        <div className="app-progress" role="progressbar" aria-label="Project completion" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}>
          <span style={{ transform: 'scaleX(' + (progress / 100) + ')' }} />
        </div>
        {taskTreeError && (
          <div className="task-stale-notice" role="status">
            {networkStatus === 'offline' ? 'Offline. ' : 'Refresh failed. '}
            Showing the last successful board snapshot
            {taskTreeUpdatedAt ? ' from ' + new Date(taskTreeUpdatedAt).toLocaleTimeString() : ''}.
          </div>
        )}
      </header>

      <div className="kanban-board" aria-label="Project task status columns">
        {COLUMNS.map((column) => {
          const tasks = allTasks.filter((task) => column.statuses.includes(task.status));
          return (
            <section className="kanban-column" key={column.key} aria-labelledby={'kanban-' + column.key}>
              <header className="kanban-column-header">
                <span className="kanban-column-icon">{column.icon}</span>
                <h3 id={'kanban-' + column.key}>{column.title}</h3>
                <span className="kanban-count">{tasks.length}</span>
              </header>
              <div className="kanban-column-content">
                {tasks.length === 0 ? (
                  <p className="kanban-column-empty">Nothing here</p>
                ) : tasks.map((task) => {
                  const agent = agents.find((item) => item.id === task.assignee_agent_id);
                  const selected = selectedTaskId === task.id;
                  return (
                    <button
                      type="button"
                      key={task.id}
                      className={'kanban-task' + (selected ? ' kanban-task-selected' : '')}
                      onClick={() => setSelectedTask(task.id)}
                      aria-pressed={selected}
                    >
                      <span className="kanban-task-top">
                        <span className={'kanban-task-status kanban-task-status-' + task.status}>{labelFor(task.status)}</span>
                        {task.priority <= 2 && <span className="kanban-priority">Priority {task.priority}</span>}
                      </span>
                      <strong className="kanban-task-title">{task.title}</strong>
                      <span className="kanban-task-description">{task.description}</span>
                      <span className="kanban-task-footer">
                        {agent ? <><AgentAvatar agent={agent} size={22} /><span>{agent.display_name}</span></> : <span>Unassigned</span>}
                        <span className="kanban-task-depth">Level {task.depth}</span>
                      </span>
                      {task.error && <span className="kanban-task-error"><XCircle size={12} /> {task.error}</span>}
                    </button>
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>
    </section>
  );
};
