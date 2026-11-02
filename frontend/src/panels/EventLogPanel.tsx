import React, { useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { Activity, Filter } from 'lucide-react';

export const EventLogPanel: React.FC = () => {
  const { events } = useAppStore();
  const [filterType, setFilterType] = useState<string>('all');
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);

  const filtered = filterType === 'all' ? events : events.filter((e) => e.type.startsWith(filterType));

  return (
    <div className="p-3 flex flex-col space-y-2 h-[calc(100vh-140px)] text-xs">
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <span className="font-semibold text-slate-300 flex items-center gap-1.5">
          <Activity size={14} className="text-sky-400" /> Monotonic Event Stream
        </span>

        {/* Filter */}
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-[11px] text-slate-300 focus:outline-none"
        >
          <option value="all">All Events</option>
          <option value="task.">Task Lifecycle</option>
          <option value="agent.">Agent Actions</option>
          <option value="artifact.">Artifacts</option>
          <option value="approval.">Approvals</option>
          <option value="system.">System/Quota</option>
        </select>
      </div>

      <div className="flex-1 overflow-y-auto space-y-1.5 font-mono text-[11px]">
        {filtered.map((evt) => {
          const isSelected = selectedEventId === evt.id;
          return (
            <div
              key={evt.id}
              onClick={() => setSelectedEventId(isSelected ? null : evt.id)}
              className={`p-2 rounded border cursor-pointer transition-all ${
                isSelected ? 'border-sky-500 bg-slate-900' : 'border-slate-800/80 bg-slate-950/60 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sky-400 font-semibold">{evt.type}</span>
                <span className="text-slate-500 text-[10px]">#{evt.id}</span>
              </div>
              <div className="text-[10px] text-slate-400 truncate mt-0.5">
                {evt.task_id && <span>Task: {evt.task_id} </span>}
                {evt.agent_id && <span>• Agent: {evt.agent_id}</span>}
              </div>

              {isSelected && (
                <pre className="mt-2 p-2 rounded bg-slate-900 text-slate-300 text-[10px] overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(evt.payload, null, 2)}
                </pre>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
