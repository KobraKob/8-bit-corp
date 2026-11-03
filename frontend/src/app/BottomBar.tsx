import React, { useEffect } from 'react';
import { useAppStore } from '../state/useAppStore';
import { DollarSign, Cpu, Play, Pause, Key, Zap } from 'lucide-react';
import { TaskTreeNode } from '../api/types';

function countActiveTasks(nodes: TaskTreeNode[]): number {
  let count = 0;
  function walk(items: TaskTreeNode[]) {
    for (const item of items) {
      if (item.status === 'in_progress' || item.status === 'integrating' || item.status === 'reviewing') {
        count++;
      }
      if (item.children) walk(item.children);
    }
  }
  walk(nodes);
  return count;
}

export const BottomBar: React.FC = () => {
  const { usage, keyStatuses, taskTree, fetchKeys, setActiveDrawerTab, isPaused, togglePause } = useAppStore();

  useEffect(() => {
    fetchKeys();
  }, []);

  const cost = usage?.total_cost_estimate || 0.0;
  const tokens = (usage?.total_prompt_tokens || 0) + (usage?.total_completion_tokens || 0);
  const calls = usage?.total_calls || 0;
  const healthyKeys = keyStatuses.filter((k) => k.is_healthy).length;
  const activeCount = countActiveTasks(taskTree);

  return (
    <div className="h-9 bg-slate-950 border-t border-slate-800 flex items-center justify-between px-3 text-[11px] font-mono text-slate-400 select-none z-20">
      {/* Payroll & Usage Metrics */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1 text-slate-300">
          <DollarSign size={13} className="text-emerald-400" />
          <span>Payroll: </span>
          <span className="font-semibold text-emerald-400">${cost.toFixed(4)}</span>
        </div>

        <div className="flex items-center gap-1">
          <Cpu size={13} className="text-sky-400" />
          <span>LLM Calls: </span>
          <span className="font-semibold text-slate-200">{calls}</span>
        </div>

        <div>
          <span>Total Tokens: </span>
          <span className="font-semibold text-slate-200">{tokens.toLocaleString()}</span>
        </div>

        {/* Live Active Execution Indicator */}
        <button
          onClick={() => setActiveDrawerTab('tree')}
          className={`flex items-center gap-1.5 px-2 py-0.5 rounded border transition-colors cursor-pointer ${
            activeCount > 0
              ? 'bg-amber-950/60 border-amber-800 text-amber-300'
              : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-300'
          }`}
          title="Click to view execution tree"
        >
          <Zap size={12} className={activeCount > 0 ? 'text-amber-400 animate-pulse' : 'text-slate-500'} />
          <span>Tasks: </span>
          <span className="font-semibold">
            {activeCount > 0 ? `${activeCount} Running` : 'Idle'}
          </span>
        </button>

        {/* Key Pool Status Badge */}
        <button
          onClick={() => setActiveDrawerTab('keys')}
          className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-900 border border-slate-800 hover:border-amber-700/60 text-slate-300 transition-colors cursor-pointer"
          title="Open API Key Pool"
        >
          <Key size={12} className="text-amber-400" />
          <span>Keys: </span>
          <span className="font-semibold text-amber-300">
            {healthyKeys}/{keyStatuses.length || 1} Active
          </span>
        </button>
      </div>

      {/* Quota & Pause Controls */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-[10px]">
          <span className={`w-1.5 h-1.5 rounded-full ${activeCount > 0 ? 'bg-amber-400 animate-ping' : 'bg-emerald-400 animate-pulse'}`} />
          <span>Engine: {activeCount > 0 ? 'Executing' : 'Healthy'}</span>
        </div>

        <button
          onClick={togglePause}
          className={`flex items-center gap-1 px-2.5 py-0.5 rounded text-[11px] font-medium border transition-all ${
            isPaused
              ? 'bg-amber-950 border-amber-800 text-amber-300 hover:bg-amber-900'
              : 'bg-slate-900 border-slate-800 text-slate-300 hover:bg-slate-800'
          }`}
        >
          {isPaused ? <Play size={11} /> : <Pause size={11} />}
          <span>{isPaused ? 'Resume All' : 'Pause All'}</span>
        </button>
      </div>
    </div>
  );
};
