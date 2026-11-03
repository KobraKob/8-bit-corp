import React, { useEffect, useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { DollarSign, Cpu, Pause, Play, Key, Zap, WifiOff } from 'lucide-react';
import { TaskTreeNode } from '../api/types';

function countActiveTasks(nodes: TaskTreeNode[]): number {
  let count = 0;
  const walk = (items: TaskTreeNode[]) => items.forEach((item) => {
    if (['in_progress', 'integrating', 'reviewing', 'in_review'].includes(item.status)) count++;
    if (item.children) walk(item.children);
  });
  walk(nodes);
  return count;
}

export const BottomBar: React.FC = () => {
  const {
    usage, keyStatuses, taskTree, fetchKeys, setActiveDrawerTab,
    isPaused, togglePause, networkStatus, projects,
  } = useAppStore();
  const [isUpdatingPause, setIsUpdatingPause] = useState(false);

  useEffect(() => { void fetchKeys(); }, []);

  const cost = usage?.total_cost_estimate || 0;
  const tokens = (usage?.total_prompt_tokens || 0) + (usage?.total_completion_tokens || 0);
  const calls = usage?.total_calls || 0;
  const healthyKeys = keyStatuses.filter((key) => key.is_healthy).length;
  const activeCount = countActiveTasks(taskTree);
  const hasActiveProjects = projects.some((project) => project.status === 'active' || project.status === 'paused');

  const handlePause = async () => {
    setIsUpdatingPause(true);
    try {
      await togglePause();
    } finally {
      setIsUpdatingPause(false);
    }
  };

  return (
    <footer className="app-statusbar">
      <div className="app-statusbar-metrics">
        <span><DollarSign size={13} /><strong>${cost.toFixed(4)}</strong><span>Estimated cost</span></span>
        <span><Cpu size={13} /><strong>{calls.toLocaleString()}</strong><span>LLM calls</span></span>
        <span><strong>{tokens.toLocaleString()}</strong><span>Tokens used</span></span>
        <button type="button" onClick={() => setActiveDrawerTab('tree')} className="app-statusbar-link">
          <Zap size={13} /><strong>{activeCount}</strong><span>Active tasks</span>
        </button>
        <button type="button" onClick={() => setActiveDrawerTab('keys')} className="app-statusbar-link">
          <Key size={13} /><strong>{healthyKeys}/{keyStatuses.length}</strong><span>Healthy keys</span>
        </button>
      </div>
      <div className="app-statusbar-controls">
        <span className={'app-engine-state app-engine-' + networkStatus}>
          {networkStatus === 'offline' ? <WifiOff size={12} /> : <span className="app-engine-marker" />}
          {networkStatus === 'offline' ? 'Offline' : networkStatus === 'degraded' ? 'Sync unavailable' : activeCount > 0 ? 'Executing' : 'Ready'}
        </span>
        <button
          type="button"
          className="app-button app-button-quiet"
          onClick={() => void handlePause()}
          disabled={!hasActiveProjects || isUpdatingPause || networkStatus === 'offline'}
          title={isPaused ? 'Resume paused projects' : 'Pause active projects'}
        >
          {isPaused ? <Play size={12} /> : <Pause size={12} />}
          {isUpdatingPause ? 'Updating' : isPaused ? 'Resume projects' : 'Pause projects'}
        </button>
      </div>
    </footer>
  );
};
