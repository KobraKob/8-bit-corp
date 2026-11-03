import React from 'react';
import { useAppStore } from '../state/useAppStore';
import { TaskTreeNode } from '../api/types';
import {
  Activity,
  CheckCircle2,
  Clock,
  Layers,
  Play,
  Pause,
  RefreshCw,
  Sparkles,
  Zap,
  AlertCircle,
} from 'lucide-react';

function flattenTree(nodes: TaskTreeNode[]): TaskTreeNode[] {
  const list: TaskTreeNode[] = [];
  function walk(items: TaskTreeNode[]) {
    for (const item of items) {
      list.push(item);
      if (item.children && item.children.length > 0) {
        walk(item.children);
      }
    }
  }
  walk(nodes);
  return list;
}

export const LiveActivityHUD: React.FC = () => {
  const {
    projects,
    activeProjectId,
    taskTree,
    agents,
    events,
    fetchTaskTree,
    fetchProjects,
    setActiveDrawerTab,
    isPaused,
    togglePause,
  } = useAppStore();

  const [isRefreshing, setIsRefreshing] = React.useState(false);

  const activeProject = projects.find((p) => p.id === activeProjectId);
  const flatTasks = React.useMemo(() => flattenTree(taskTree), [taskTree]);

  const totalTasks = flatTasks.length;
  const doneTasks = flatTasks.filter((t) => t.status === 'done').length;
  const inProgressTasks = flatTasks.filter(
    (t) => t.status === 'in_progress' || t.status === 'integrating' || t.status === 'in_review' || t.status === 'reviewing'
  );
  const blockedTasks = flatTasks.filter((t) => t.status === 'blocked').length;

  const percent = totalTasks > 0 ? Math.round((doneTasks / totalTasks) * 100) : 0;

  // Active agents mapping
  const activeAgentNames = inProgressTasks
    .map((t) => {
      const agt = agents.find((a) => a.id === t.assignee_agent_id);
      return agt ? agt.display_name : t.assignee_agent_id?.slice(0, 10);
    })
    .filter(Boolean);

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await Promise.all([fetchTaskTree(), fetchProjects()]);
    setTimeout(() => setIsRefreshing(false), 500);
  };

  // Get latest live event description
  const latestEvent = events[0];

  return (
    <div className="absolute top-2 left-2 right-2 z-10 select-none pointer-events-auto">
      <div className="bg-slate-950/90 backdrop-blur-md border border-slate-800/90 rounded-lg p-2.5 shadow-xl flex flex-col gap-2">
        {/* Top Row: Project Title, Overall Progress, and Quick Actions */}
        <div className="flex items-center justify-between gap-3 text-xs">
          {/* Project & Status */}
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping shrink-0" />
            <div className="flex items-center gap-1.5 truncate">
              <span className="font-bold text-slate-100 font-mono text-sm truncate">
                {activeProject ? activeProject.name : 'No Project Active'}
              </span>
              <span
                className={`px-1.5 py-0.5 rounded text-[10px] font-mono uppercase font-semibold ${
                  inProgressTasks.length > 0
                    ? 'bg-amber-950/80 text-amber-300 border border-amber-800'
                    : doneTasks === totalTasks && totalTasks > 0
                    ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                    : 'bg-slate-900 text-slate-400 border border-slate-800'
                }`}
              >
                {inProgressTasks.length > 0
                  ? `${inProgressTasks.length} Working`
                  : doneTasks === totalTasks && totalTasks > 0
                  ? 'Completed'
                  : 'Ready'}
              </span>
            </div>
          </div>

          {/* Progress Indicator */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="flex flex-col items-end text-[10px] font-mono">
              <span className="text-slate-300 font-semibold">
                {doneTasks} of {totalTasks} Tasks ({percent}%)
              </span>
              <span className="text-slate-500 text-[9px]">
                {inProgressTasks.length} in progress • {blockedTasks} blocked
              </span>
            </div>

            {/* Visual Progress Bar */}
            <div className="w-28 h-2.5 bg-slate-900 border border-slate-800 rounded-full overflow-hidden relative">
              <div
                className="h-full bg-gradient-to-r from-sky-500 to-emerald-400 transition-all duration-500 rounded-full"
                style={{ width: `${percent}%` }}
              />
            </div>

            {/* Quick Refresh Button */}
            <button
              onClick={handleManualRefresh}
              disabled={isRefreshing}
              className="p-1.5 rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-slate-200 transition-all"
              title="Force Sync / Refresh"
            >
              <RefreshCw size={12} className={isRefreshing ? 'animate-spin text-sky-400' : ''} />
            </button>
          </div>
        </div>

        {/* Bottom Row: Real-Time Working Agent Status & Activity Ticker */}
        <div className="flex items-center justify-between gap-2 pt-1.5 border-t border-slate-800/60 text-[11px] font-mono">
          {/* Active Work Activity */}
          <div className="flex items-center gap-2 truncate">
            {inProgressTasks.length > 0 ? (
              <div className="flex items-center gap-1.5 text-amber-300 truncate">
                <Zap size={13} className="text-amber-400 animate-pulse shrink-0" />
                <span className="font-semibold text-slate-200">
                  [{activeAgentNames[0] || 'Autonomous Agent'}]:
                </span>
                <span className="truncate text-slate-300">
                  {inProgressTasks[0].title}
                </span>
                {inProgressTasks.length > 1 && (
                  <span className="text-slate-400 text-[10px]">
                    (+{inProgressTasks.length - 1} more active)
                  </span>
                )}
              </div>
            ) : latestEvent ? (
              <div className="flex items-center gap-1.5 text-slate-400 truncate">
                <Activity size={12} className="text-sky-400 shrink-0" />
                <span className="text-slate-500">Latest Event:</span>
                <span className="text-slate-300 truncate font-sans">
                  {latestEvent.type} {latestEvent.payload?.title || latestEvent.payload?.reason || ''}
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 text-slate-500">
                <Sparkles size={12} className="text-slate-600" />
                <span>All agents idle. Submit a client brief to dispatch the team.</span>
              </div>
            )}
          </div>

          {/* Quick Drawer Shortcuts */}
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              onClick={() => setActiveDrawerTab('tree')}
              className="px-2 py-0.5 rounded bg-slate-900 hover:bg-slate-800 text-sky-400 border border-slate-800 text-[10px] transition-colors"
            >
              View Tree
            </button>
            <button
              onClick={() => setActiveDrawerTab('kanban')}
              className="px-2 py-0.5 rounded bg-slate-900 hover:bg-slate-800 text-sky-400 border border-slate-800 text-[10px] transition-colors"
            >
              View Kanban
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
