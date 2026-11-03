import React, { useMemo, useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { TaskTreeNode } from '../api/types';
import { Activity, AlertCircle, RefreshCw, ShieldAlert } from 'lucide-react';

function flattenTree(nodes: TaskTreeNode[]): TaskTreeNode[] {
  const result: TaskTreeNode[] = [];
  const visit = (items: TaskTreeNode[]) => items.forEach((item) => {
    result.push(item);
    if (item.children?.length) visit(item.children);
  });
  visit(nodes);
  return result;
}

export const LiveActivityHUD: React.FC = () => {
  const {
    projects, activeProjectId, taskTree, agents, events,
    fetchTaskTree, fetchProjects, setActiveDrawerTab, networkStatus,
    taskTreeUpdatedAt, taskTreeError, taskTreeLoading,
  } = useAppStore();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const activeProject = projects.find((project) => project.id === activeProjectId);
  const flatTasks = useMemo(() => flattenTree(taskTree), [taskTree]);
  const total = flatTasks.length;
  const done = flatTasks.filter((task) => task.status === 'done').length;
  const working = flatTasks.filter((task) => ['in_progress', 'integrating'].includes(task.status));
  const review = flatTasks.filter((task) => ['in_review', 'reviewing', 'revision_requested'].includes(task.status)).length;
  const blocked = flatTasks.filter((task) => ['blocked', 'failed'].includes(task.status)).length;
  const hasProgressSnapshot = Boolean(taskTreeUpdatedAt) || taskTree.length > 0;
  const percent = total ? Math.round(done / total * 100) : 0;
  const firstTask = working[0];
  const firstAgent = firstTask ? agents.find((agent) => agent.id === firstTask.assignee_agent_id) : undefined;
  const latestEvent = events[0];

  const refresh = async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([fetchTaskTree(), fetchProjects()]);
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <section className="activity-strip" aria-label="Project activity">
      <div className="activity-project">
        <div className="activity-project-title">
          <strong>{activeProject?.name || 'No project selected'}</strong>
          <span className="activity-project-state">{activeProject?.status || 'Choose a workspace'}</span>
        </div>
        <div className="activity-project-progress">
          <div className="activity-progress-label">
            <span>{hasProgressSnapshot ? done + ' of ' + total + ' work packages complete' : taskTreeLoading ? 'Loading work packages' : 'Progress unavailable'}</span>
            <strong>{hasProgressSnapshot ? percent + '%' : '—'}</strong>
          </div>
          {hasProgressSnapshot ? (
            <div className="app-progress" role="progressbar" aria-label="Project completion" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
              <span style={{ transform: 'scaleX(' + (percent / 100) + ')' }} />
            </div>
          ) : <div className="app-progress app-progress-unknown" aria-label="Project progress unavailable" />}
        </div>
      </div>

      <div className="activity-metrics">
        <div><Activity size={13} /><strong>{working.length}</strong><span>Working</span></div>
        <div><ShieldAlert size={13} /><strong>{review}</strong><span>Review</span></div>
        <div><AlertCircle size={13} /><strong>{blocked}</strong><span>Blocked</span></div>
      </div>

      <div className="activity-latest">
        {firstTask ? (
          <span className="activity-current">
            {firstAgent?.display_name || 'Agent'} is working on <strong>{firstTask.title}</strong>
          </span>
        ) : latestEvent ? (
          <span className="activity-current"><span>Latest event</span> {latestEvent.type.replaceAll('_', ' ')}</span>
        ) : (
          <span className="activity-current">No recent activity recorded.</span>
        )}
        <span className={'activity-connection activity-connection-' + networkStatus}>
          {networkStatus === 'connected' ? 'Live updates' : networkStatus === 'offline' ? 'Offline snapshot' : networkStatus === 'degraded' ? 'Sync unavailable' : 'Connecting'}
        </span>
        <button type="button" className="activity-open-board" onClick={() => setActiveDrawerTab('kanban')}>Open board</button>
        <button type="button" className="activity-refresh" onClick={() => void refresh()} disabled={isRefreshing || networkStatus === 'offline'} aria-label="Refresh project activity">
          <RefreshCw size={14} />
          <span>{isRefreshing ? 'Syncing' : 'Refresh'}</span>
        </button>
      </div>
      {taskTreeError && (
        <div className="activity-warning" role="status">
          {networkStatus === 'offline' ? 'Connection unavailable. ' : 'Could not refresh. '}
          {taskTree.length > 0 || taskTreeUpdatedAt ? 'Showing the last saved snapshot' : 'No successful snapshot is available yet.'}
          {taskTreeUpdatedAt ? ' from ' + new Date(taskTreeUpdatedAt).toLocaleTimeString() : ''}.
        </div>
      )}
    </section>
  );
};
