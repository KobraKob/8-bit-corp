import React from 'react';
import { useAppStore, ActiveDrawerTab } from '../state/useAppStore';
import { TaskTreePanel } from '../panels/TaskTreePanel';
import { KanbanPanel } from '../panels/KanbanPanel';
import { AgentInspectorPanel } from '../panels/AgentInspectorPanel';
import { ArtifactsPanel } from '../panels/ArtifactsPanel';
import { ApprovalsPanel } from '../panels/ApprovalsPanel';
import { OrgEditorPanel } from '../panels/OrgEditorPanel';
import { EventLogPanel } from '../panels/EventLogPanel';
import {
  Network,
  Kanban,
  UserCheck,
  FileText,
  ShieldAlert,
  Users,
  Activity,
} from 'lucide-react';

const TABS: { id: ActiveDrawerTab; label: string; icon: React.FC<{ size: number }> }[] = [
  { id: 'tree', label: 'Tree', icon: Network },
  { id: 'kanban', label: 'Kanban', icon: Kanban },
  { id: 'inspector', label: 'Inspector', icon: UserCheck },
  { id: 'artifacts', label: 'Artifacts', icon: FileText },
  { id: 'approvals', label: 'Approvals', icon: ShieldAlert },
  { id: 'org', label: 'Org', icon: Users },
  { id: 'events', label: 'Events', icon: Activity },
];

export const RightDrawer: React.FC = () => {
  const { activeDrawerTab, setActiveDrawerTab, approvals } = useAppStore();

  return (
    <div className="w-[420px] bg-slate-950 border-l border-slate-800 flex flex-col h-screen select-none">
      {/* Tab Navigation */}
      <div className="flex border-b border-slate-800 bg-slate-900/60 p-1 gap-1 overflow-x-auto">
        {TABS.map((tab) => {
          const isActive = activeDrawerTab === tab.id;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveDrawerTab(tab.id)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-[11px] font-medium transition-all relative ${
                isActive
                  ? 'bg-slate-800 text-sky-400 border border-slate-700 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
              }`}
            >
              <Icon size={12} />
              <span>{tab.label}</span>
              {tab.id === 'approvals' && approvals.filter((a) => a.status === 'pending').length > 0 && (
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 absolute top-1 right-1" />
              )}
            </button>
          );
        })}
      </div>

      {/* Panel Body */}
      <div className="flex-1 overflow-hidden">
        {activeDrawerTab === 'tree' && <TaskTreePanel />}
        {activeDrawerTab === 'kanban' && <KanbanPanel />}
        {activeDrawerTab === 'inspector' && <AgentInspectorPanel />}
        {activeDrawerTab === 'artifacts' && <ArtifactsPanel />}
        {activeDrawerTab === 'approvals' && <ApprovalsPanel />}
        {activeDrawerTab === 'org' && <OrgEditorPanel />}
        {activeDrawerTab === 'events' && <EventLogPanel />}
      </div>
    </div>
  );
};
