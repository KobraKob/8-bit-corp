import React, { useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { DollarSign, Cpu, Pause, Play, Key, Zap, WifiOff } from 'lucide-react';
import { TaskTreeNode } from '../api/types';

function countActiveTasks(nodes: TaskTreeNode[]): number {
  let count = 0;
  const visit = (items: TaskTreeNode[]) => {
    items.forEach((item) => {
      if (['in_progress', 'integrating', 'reviewing', 'in_review'].includes(item.status)) count += 1;
      if (item.children?.length) visit(item.children);
    });
  };
  visit(nodes);
  return count;
}

export const BottomBar: React.FC = () => {
  const {
    usage, usageError, keyStatuses, keysLoading, taskTree, taskTreeError,
    setActiveDrawerTab, isPaused, togglePause, networkStatus, projects,
  } = useAppStore();
  const [isUpdatingPause, setIsUpdatingPause] = useState(false);

  const activeCount = countActiveTasks(taskTree);
  const costLabel = usage ? '$' + usage.total_cost_estimate.toFixed(4) : '—';
  const callsLabel = usage ? usage.total_calls.toLocaleString() : '—';
  const tokensLabel = usage
    ? (usage.total_prompt_tokens + usage.total_completion_tokens).toLocaleString()
    : '—';
  const healthyKeys = keyStatuses.filter((key) => key.is_healthy).length;
  const keyHealthLabel = keysLoading && keyStatuses.length === 0
    ? '—'
    : keyStatuses.length > 0 ? healthyKeys + '/' + keyStatuses.length : '—';
  const activeTaskLabel = taskTreeError && taskTree.length === 0 ? '—' : String(activeCount);
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
        <span title={usageError || 'Last reported API usage'}>
          <DollarSign size={13} /><strong>{costLabel}</strong><span>Estimated cost</span>
        </span>
        <span title={usageError || 'Last reported LLM calls'}>
          <Cpu size={13} /><strong>{callsLabel}</strong><span>LLM calls</span>
        </span>
        <span title={usageError || 'Last reported token usage'}>
          <strong>{tokensLabel}</strong><span>Tokens used</span>
        </span>
        <button type="button" onClick={() => setActiveDrawerTab('tree')} className="app-statusbar-link">
          <Zap size={13} /><strong>{activeTaskLabel}</strong><span>Active tasks</span>
        </button>
        <button type="button" onClick={() => setActiveDrawerTab('keys')} className="app-statusbar-link">
          <Key size={13} /><strong>{keyHealthLabel}</strong><span>Healthy keys</span>
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
