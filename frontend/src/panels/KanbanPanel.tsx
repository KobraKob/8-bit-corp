import React from 'react';
import { useAppStore } from '../state/useAppStore';
import { TaskTreeNode } from '../api/types';

export const KanbanPanel: React.FC = () => {
  const { taskTree, setSelectedTask, selectedTaskId } = useAppStore();

  // Flatten task tree into flat list
  const allTasks: TaskTreeNode[] = [];
  function collect(node: TaskTreeNode) {
    allTasks.push(node);
    if (node.children) {
      for (const c of node.children) collect(c);
    }
  }
  taskTree.forEach(collect);

  const columns = [
    { key: 'assigned', label: 'Assigned', color: 'border-blue-700 bg-blue-950/20' },
    { key: 'in_progress', label: 'In Progress', color: 'border-amber-700 bg-amber-950/20' },
    { key: 'in_review', label: 'In Review', color: 'border-indigo-700 bg-indigo-950/20' },
    { key: 'reviewing', label: 'Reviewing', color: 'border-violet-700 bg-violet-950/20' },
    { key: 'done', label: 'Done', color: 'border-emerald-700 bg-emerald-950/20' },
    { key: 'blocked', label: 'Blocked', color: 'border-rose-700 bg-rose-950/20' },
  ];

  return (
    <div className="flex gap-2.5 p-3 overflow-x-auto h-[calc(100vh-140px)]">
      {columns.map((col) => {
        const tasksInCol = allTasks.filter((t) => t.status === col.key);
        return (
          <div
            key={col.key}
            className={`flex-1 min-w-[210px] max-w-[260px] rounded-lg border p-2 flex flex-col ${col.color}`}
          >
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-800 text-xs font-semibold text-slate-300">
              <span>{col.label}</span>
              <span className="px-1.5 py-0.5 rounded-full bg-slate-800 text-[10px] text-slate-400">
                {tasksInCol.length}
              </span>
            </div>

            <div className="flex flex-col gap-2 overflow-y-auto">
              {tasksInCol.map((task) => (
                <div
                  key={task.id}
                  onClick={() => setSelectedTask(task.id)}
                  className={`p-2 rounded border text-xs cursor-pointer transition-all ${
                    selectedTaskId === task.id
                      ? 'border-sky-500 bg-sky-950/60'
                      : 'border-slate-800 bg-slate-900/80 hover:border-slate-700'
                  }`}
                >
                  <div className="font-medium text-slate-200">{task.title}</div>
                  <div className="text-[11px] text-slate-400 mt-1 line-clamp-2">{task.description}</div>
                  <div className="mt-2 text-[10px] text-slate-500 flex justify-between font-mono">
                    <span>Depth {task.depth}</span>
                    <span>{task.tokens_used} tok</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};
