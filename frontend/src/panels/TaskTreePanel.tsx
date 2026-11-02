import React from 'react';
import { useAppStore } from '../state/useAppStore';
import { TaskTreeNode } from '../api/types';
import { CheckCircle2, Clock, AlertTriangle, ArrowRight, CornerDownRight, Play } from 'lucide-react';

const statusColors: Record<string, string> = {
  pending: 'text-slate-400 bg-slate-800 border-slate-700',
  assigned: 'text-blue-400 bg-blue-950/50 border-blue-800',
  in_progress: 'text-amber-400 bg-amber-950/50 border-amber-800 animate-pulse',
  integrating: 'text-purple-400 bg-purple-950/50 border-purple-800',
  in_review: 'text-indigo-400 bg-indigo-950/50 border-indigo-800',
  revision_requested: 'text-orange-400 bg-orange-950/50 border-orange-800',
  done: 'text-emerald-400 bg-emerald-950/50 border-emerald-800',
  blocked: 'text-rose-400 bg-rose-950/50 border-rose-800',
  failed: 'text-red-500 bg-red-950/50 border-red-800',
  cancelled: 'text-neutral-500 bg-neutral-900 border-neutral-800',
};

function TaskNodeItem({ node }: { node: TaskTreeNode }) {
  const { setSelectedTask, selectedTaskId, setSelectedAgent } = useAppStore();
  const isSelected = selectedTaskId === node.id;

  return (
    <div className="flex flex-col ml-3 border-l border-slate-800 pl-3 my-1.5">
      <div
        onClick={() => setSelectedTask(node.id)}
        className={`p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
          isSelected ? 'border-sky-500 bg-sky-950/40 shadow-sm' : 'border-slate-800/80 bg-slate-900/60 hover:border-slate-700'
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="font-semibold text-slate-200 truncate">{node.title}</span>
          <span className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase border ${statusColors[node.status] || 'text-slate-400'}`}>
            {node.status}
          </span>
        </div>

        <p className="text-slate-400 text-[11px] mt-1 line-clamp-2">{node.description}</p>

        <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-800/60 text-[10px] text-slate-500 font-mono">
          <span>Depth: {node.depth}</span>
          {node.assignee_agent_id && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setSelectedAgent(node.assignee_agent_id!);
              }}
              className="text-sky-400 hover:underline"
            >
              Assignee: {node.assignee_agent_id.slice(0, 10)}
            </button>
          )}
          <span>Tokens: {node.tokens_used}</span>
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

export const TaskTreePanel: React.FC = () => {
  const { taskTree } = useAppStore();

  if (taskTree.length === 0) {
    return (
      <div className="p-6 text-center text-slate-500 text-xs font-mono">
        No active tasks found. Submit a task from the sidebar to start the cascade.
      </div>
    );
  }

  return (
    <div className="p-3 flex flex-col space-y-1 overflow-y-auto max-h-[calc(100vh-140px)]">
      <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1 px-1">
        Hierarchy Execution Tree
      </div>
      {taskTree.map((root) => (
        <TaskNodeItem key={root.id} node={root} />
      ))}
    </div>
  );
};
