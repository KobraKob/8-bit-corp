import React, { useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { TaskTreeNode } from '../api/types';
import { AgentAvatar } from '../components/AgentAvatar';
import {
  Activity, AlertCircle, CheckCircle2, ChevronDown, ChevronRight, Circle,
  Clock3, Layers, RefreshCw, ShieldAlert, UserRound, XCircle,
} from 'lucide-react';

const ACTIVE = new Set(['in_progress', 'integrating', 'reviewing']);
const REVIEW = new Set(['in_review', 'revision_requested']);
const DONE = new Set(['done']);
const BLOCKED = new Set(['blocked', 'failed']);

function flatten(nodes: TaskTreeNode[]): TaskTreeNode[] {
  const result: TaskTreeNode[] = [];
  const visit = (items: TaskTreeNode[]) => items.forEach((item) => {
    result.push(item);
    if (item.children?.length) visit(item.children);
  });
  visit(nodes);
  return result;
}

function elapsed(startedAt?: string | null, createdAt?: string): string | null {
  const value = startedAt || createdAt;
  if (!value) return null;
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60000));
  if (minutes < 1) return 'Started just now';
  if (minutes < 60) return 'Running for ' + minutes + 'm';
  const hours = Math.floor(minutes / 60);
  return 'Running for ' + hours + 'h ' + (minutes % 60) + 'm';
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: 'Pending',
    assigned: 'Queued',
    in_progress: 'Working',
    integrating: 'Integrating',
    in_review: 'Ready for review',
    reviewing: 'Reviewing',
    revision_requested: 'Changes requested',
    done: 'Complete',
    blocked: 'Blocked',
    failed: 'Failed',
    cancelled: 'Cancelled',
  };
  return labels[status] || status.replaceAll('_', ' ');
}

function statusIcon(status: string) {
  if (DONE.has(status)) return <CheckCircle2 size={14} />;
  if (BLOCKED.has(status)) return <AlertCircle size={14} />;
  if (REVIEW.has(status)) return <ShieldAlert size={14} />;
  if (ACTIVE.has(status)) return <Activity size={14} />;
  if (status === 'cancelled') return <XCircle size={14} />;
  return <Circle size={12} />;
}

function TaskNodeItem({ node }: { node: TaskTreeNode }) {
  const { setSelectedTask, selectedTaskId, setSelectedAgent, agents } = useAppStore();
  const [expanded, setExpanded] = useState(node.depth === 0);
  const assignee = agents.find((agent) => agent.id === node.assignee_agent_id);
  const selected = selectedTaskId === node.id;
  const hasChildren = Boolean(node.children?.length);
  const runningTime = elapsed(node.started_at, node.created_at);

  return (
    <div className="task-tree-node" style={{ marginLeft: Math.min(node.depth, 5) * 10 }}>
      <article className={'task-tree-card' + (selected ? ' task-tree-card-selected' : '')}>
        <div className="task-tree-main">
          <button type="button" className="task-tree-title" onClick={() => setSelectedTask(node.id)}>
            <span className={'task-status-icon task-status-' + node.status}>{statusIcon(node.status)}</span>
            <span className="task-tree-title-text">{node.title}</span>
          </button>
          {hasChildren && (
            <button
              type="button"
              className="task-tree-expand"
              onClick={() => setExpanded((value) => !value)}
              aria-label={expanded ? 'Collapse subtasks' : 'Expand subtasks'}
              aria-expanded={expanded}
            >
              {expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
            </button>
          )}
        </div>
        <div className="task-tree-description">{node.description}</div>
        <div className="task-tree-meta">
          <span className={'task-status-label task-status-' + node.status}>{statusLabel(node.status)}</span>
          {assignee ? (
            <button type="button" className="task-assignee" onClick={() => setSelectedAgent(assignee.id)}>
              <AgentAvatar agent={assignee} size={22} />
              <span>{assignee.display_name}</span>
            </button>
          ) : node.assignee_agent_id ? (
            <span className="task-assignee"><UserRound size={12} /> {node.assignee_agent_id.slice(0, 9)}</span>
          ) : null}
          <span className="task-tree-measured">Level {node.depth}</span>
          <span className="task-tree-measured">{node.tokens_used.toLocaleString()} tokens</span>
        </div>
        {ACTIVE.has(node.status) && runningTime && (
          <div className="task-tree-runtime"><Clock3 size={11} /> {runningTime}</div>
        )}
        {node.error && <div className="task-tree-error">{node.error}</div>}
      </article>
      {hasChildren && expanded && (
        <div className="task-tree-children">
          {node.children.map((child) => <TaskNodeItem key={child.id} node={child} />)}
        </div>
      )}
    </div>
  );
}

export const TaskTreePanel: React.FC = () => {
  const {
    taskTree, fetchTaskTree, activeProjectId, taskTreeLoading,
    taskTreeError, taskTreeUpdatedAt, projects, networkStatus,
  } = useAppStore();
  const nodes = flatten(taskTree);
  const done = nodes.filter((task) => task.status === 'done').length;
  const active = nodes.filter((task) => ACTIVE.has(task.status)).length;
  const review = nodes.filter((task) => REVIEW.has(task.status)).length;
  const blocked = nodes.filter((task) => BLOCKED.has(task.status)).length;
  const percent = nodes.length ? Math.round((done / nodes.length) * 100) : 0;
  const project = projects.find((item) => item.id === activeProjectId);

  return (
    <section className="task-panel app-panel app-scroll">
      <header className="task-panel-header">
        <div className="task-panel-heading">
          <div>
            <h2>Work hierarchy</h2>
            <p>{project?.name || 'Select a project to inspect its work.'}</p>
          </div>
          <button type="button" className="app-icon-button" onClick={() => void fetchTaskTree()} disabled={!activeProjectId || taskTreeLoading} aria-label="Refresh task hierarchy">
            <RefreshCw size={15} />
          </button>
        </div>
        {nodes.length > 0 && (
          <>
            <div className="task-progress-line">
              <span className="task-progress-value">{percent}%</span>
              <span className="task-progress-caption">{done} of {nodes.length} work packages complete</span>
            </div>
            <div className="app-progress" role="progressbar" aria-label="Project task completion" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
              <span style={{ transform: 'scaleX(' + (percent / 100) + ')' }} />
            </div>
            <div className="task-summary">
              <span><Activity size={12} /> {active} working</span>
              <span><ShieldAlert size={12} /> {review} in review</span>
              <span><AlertCircle size={12} /> {blocked} need attention</span>
            </div>
          </>
        )}
      </header>

      {taskTreeError && (
        <div className={nodes.length ? 'task-stale-notice' : 'app-error'} role="alert">
          <strong>{networkStatus === 'offline' ? 'You are offline.' : 'Could not refresh the work hierarchy.'}</strong>
          <span>{nodes.length ? ' Showing the last successful snapshot.' : ' ' + taskTreeError}</span>
          {nodes.length > 0 && taskTreeUpdatedAt && <span> Last synced {new Date(taskTreeUpdatedAt).toLocaleTimeString()}.</span>}
          <button type="button" onClick={() => void fetchTaskTree()} disabled={networkStatus === 'offline'}>Retry</button>
        </div>
      )}

      {!activeProjectId ? (
        <div className="app-empty"><Layers size={22} /><p>Select a project to see its task hierarchy.</p></div>
      ) : taskTreeLoading && nodes.length === 0 ? (
        <div className="task-tree-skeleton" aria-label="Loading work hierarchy">
          {[0, 1, 2].map((item) => (
            <div className="task-tree-skeleton-item" key={item}>
              <div className="app-skeleton app-skeleton-line" />
              <div className="app-skeleton app-skeleton-wide" />
              <div className="app-skeleton app-skeleton-short" />
            </div>
          ))}
        </div>
      ) : nodes.length === 0 ? (
        <div className="app-empty">
          <Layers size={24} />
          <strong>No work packages yet</strong>
          <p>Send a brief to the CEO from the project sidebar. The resulting work breakdown will appear here.</p>
          {taskTreeError && <button type="button" className="app-button" onClick={() => void fetchTaskTree()} disabled={networkStatus === 'offline'}>Try again</button>}
        </div>
      ) : (
        <div className="task-tree-list">
          {taskTree.map((root) => <TaskNodeItem key={root.id} node={root} />)}
        </div>
      )}
    </section>
  );
};
