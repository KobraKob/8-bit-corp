import React, { useEffect, useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { TaskLogEntry, TaskTreeNode } from '../api/types';
import { apiClient } from '../api/client';
import {
  CheckCircle2,
  Clock,
  AlertTriangle,
  ArrowRight,
  CornerDownRight,
  Play,
  RefreshCw,
  Zap,
  Activity,
  Layers,
} from 'lucide-react';

const statusColors: Record<string, string> = {
  pending: 'text-slate-400 bg-slate-800 border-slate-700',
  assigned: 'text-blue-400 bg-blue-950/60 border-blue-800',
  in_progress: 'text-amber-300 bg-amber-950/80 border-amber-600 animate-pulse font-bold',
  integrating: 'text-purple-300 bg-purple-950/80 border-purple-600 animate-pulse font-bold',
  in_review: 'text-indigo-300 bg-indigo-950/80 border-indigo-600 font-bold',
  reviewing: 'text-violet-300 bg-violet-950/80 border-violet-600 font-bold animate-pulse',
  revision_requested: 'text-orange-400 bg-orange-950/60 border-orange-800',
  done: 'text-emerald-400 bg-emerald-950/60 border-emerald-800',
  blocked: 'text-rose-400 bg-rose-950/60 border-rose-800',
  failed: 'text-red-500 bg-red-950/60 border-red-800',
  cancelled: 'text-neutral-500 bg-neutral-900 border-neutral-800',
};

function TaskNodeItem({ node }: { node: TaskTreeNode }) {
  const { setSelectedTask, selectedTaskId, setSelectedAgent, agents } = useAppStore();
  const isSelected = selectedTaskId === node.id;
  const assignee = agents.find((a) => a.id === node.assignee_agent_id);

  const isInProgress = node.status === 'in_progress' || node.status === 'integrating' || node.status === 'reviewing';
  const isDone = node.status === 'done';

  return (
    <div className="flex flex-col ml-2.5 border-l-2 border-slate-800 pl-2.5 my-1.5">
      <div
        onClick={() => setSelectedTask(node.id)}
        className={`p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
          isSelected
            ? 'border-sky-500 bg-sky-950/50 shadow-md ring-1 ring-sky-500/50'
            : isInProgress
            ? 'border-amber-600/70 bg-amber-950/30 hover:border-amber-500'
            : 'border-slate-800/80 bg-slate-900/60 hover:border-slate-700'
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            {isInProgress ? (
              <RefreshCw size={12} className="text-amber-400 animate-spin shrink-0" />
            ) : isDone ? (
              <CheckCircle2 size={13} className="text-emerald-400 shrink-0" />
            ) : (
              <CornerDownRight size={12} className="text-slate-500 shrink-0" />
            )}
            <span className={`font-semibold truncate ${isInProgress ? 'text-amber-200' : 'text-slate-200'}`}>
              {node.title}
            </span>
          </div>
          <span
            className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase border shrink-0 ${
              statusColors[node.status] || 'text-slate-400'
            }`}
          >
            {node.status}
          </span>
        </div>

        <p className="text-slate-400 text-[11px] mt-1 line-clamp-2 leading-relaxed">
          {node.description}
        </p>

        <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-slate-800/60 text-[10px] text-slate-500 font-mono">
          <span>Depth: {node.depth}</span>
          <span>Attempt: {node.attempt}/{node.max_attempts}</span>
          {node.assignee_agent_id && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setSelectedAgent(node.assignee_agent_id!);
              }}
              className="text-sky-400 hover:underline truncate max-w-[130px]"
              title={assignee ? `${assignee.display_name} (${assignee.department})` : node.assignee_agent_id}
            >
              👤 {assignee ? assignee.display_name : node.assignee_agent_id.slice(0, 10)}
            </button>
          )}
          <span>Tokens: {node.tokens_used.toLocaleString()}</span>
        </div>
      </div>

      {node.children && node.children.length > 0 && (
        <div className="flex flex-col">
          {node.children.map((child) => (
            <TaskNodeItem key={child.id} node={child} />
          ))}
        </div>
      )}
    </div>
  );
}

function countTreeNodes(nodes: TaskTreeNode[]): { total: number; done: number; inProgress: number } {
  let total = 0;
  let done = 0;
  let inProgress = 0;
  function walk(items: TaskTreeNode[]) {
    for (const item of items) {
      total++;
      if (item.status === 'done') done++;
      if (item.status === 'in_progress' || item.status === 'integrating' || item.status === 'reviewing') inProgress++;
      if (item.children) walk(item.children);
    }
  }
  walk(nodes);
  return { total, done, inProgress };
}

export const TaskTreePanel: React.FC = () => {
  const { taskTree, fetchTaskTree, selectedTaskId } = useAppStore();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [taskLogs, setTaskLogs] = useState<TaskLogEntry[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsError, setLogsError] = useState<string | null>(null);

  const refreshTaskLogs = async () => {
    if (!selectedTaskId) return;
    setLogsLoading(true);
    setLogsError(null);
    try {
      setTaskLogs(await apiClient.getTaskLogs(selectedTaskId, 200));
    } catch (error) {
      setLogsError(error instanceof Error ? error.message : 'Unable to load task logs.');
    } finally {
      setLogsLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    setTaskLogs([]);
    setLogsError(null);
    if (!selectedTaskId) return () => { active = false; };
    setLogsLoading(true);
    apiClient.getTaskLogs(selectedTaskId, 200)
      .then((logs) => { if (active) setTaskLogs(logs); })
      .catch((error) => {
        if (active) setLogsError(error instanceof Error ? error.message : 'Unable to load task logs.');
      })
      .finally(() => { if (active) setLogsLoading(false); });
    return () => { active = false; };
  }, [selectedTaskId]);

  const { total, done, inProgress } = countTreeNodes(taskTree);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchTaskTree();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  if (taskTree.length === 0) {
    return (
      <div className="p-6 text-center text-slate-500 text-xs font-mono flex flex-col items-center gap-3">
        <Layers size={24} className="text-slate-700" />
        <p>No active tasks in this project yet.</p>
        <button
          onClick={handleRefresh}
          className="px-3 py-1 rounded bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 text-[11px]"
        >
          Check for Tasks
        </button>
      </div>
    );
  }

  return (
    <div className="p-3 flex flex-col space-y-2 overflow-y-auto max-h-[calc(100vh-140px)]">
      {/* Header with Stats & Live Refresh */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div>
          <div className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
            <Activity size={13} className="text-sky-400" />
            Hierarchy Execution Tree
          </div>
          <div className="text-[10px] text-slate-400 font-mono mt-0.5">
            {done}/{total} Done • {inProgress} In Progress
          </div>
        </div>

        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="p-1.5 rounded border border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-200 transition-colors"
          title="Refresh Execution Tree"
        >
          <RefreshCw size={12} className={isRefreshing ? 'animate-spin text-sky-400' : ''} />
        </button>
      </div>

      {/* Task Nodes */}
      {taskTree.map((root) => (
        <TaskNodeItem key={root.id} node={root} />
      ))}

      {selectedTaskId && (
        <section className="mt-3 rounded-lg border border-slate-800 bg-slate-950/80 overflow-hidden">
          <header className="flex items-center justify-between gap-2 px-3 py-2 border-b border-slate-800">
            <div className="min-w-0">
              <div className="text-[11px] font-bold text-slate-200">Task diagnostics</div>
              <div className="text-[9px] font-mono text-slate-500 truncate">{selectedTaskId}</div>
            </div>
            <button
              onClick={() => void refreshTaskLogs()}
              disabled={logsLoading}
              className="text-[10px] text-sky-400 hover:text-sky-300 disabled:opacity-50"
            >
              {logsLoading ? 'Loading…' : 'Refresh'}
            </button>
          </header>
          {logsError && <p className="px-3 py-2 text-[10px] text-rose-400">{logsError}</p>}
          {!logsLoading && !logsError && taskLogs.length === 0 && (
            <p className="px-3 py-3 text-[10px] text-slate-500">No execution logs recorded yet.</p>
          )}
          <div className="max-h-64 overflow-y-auto divide-y divide-slate-900">
            {taskLogs.map((log) => (
              <details key={log.id} className="px-3 py-2 group">
                <summary className="list-none cursor-pointer flex items-start gap-2">
                  <span className={`shrink-0 uppercase text-[9px] font-bold ${log.level === 'error' ? 'text-rose-400' : log.level === 'warning' ? 'text-amber-400' : log.level === 'info' ? 'text-sky-400' : 'text-slate-500'}`}>
                    {log.level}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-[10px] text-slate-200 break-words">{log.message}</span>
                    <span className="block text-[9px] text-slate-500 font-mono mt-0.5">
                      {log.event} · {new Date(log.created_at).toLocaleTimeString()}
                    </span>
                  </span>
                </summary>
                {Object.keys(log.metadata || {}).length > 0 && (
                  <pre className="mt-2 p-2 rounded bg-black/30 text-[9px] text-slate-400 whitespace-pre-wrap break-all overflow-x-auto">
                    {JSON.stringify(log.metadata, null, 2)}
                  </pre>
                )}
              </details>
            ))}
          </div>
        </section>
      )}
    </div>
  );
};
