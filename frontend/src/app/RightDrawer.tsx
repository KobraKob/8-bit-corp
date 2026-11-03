import React from 'react';
import { useAppStore, ActiveDrawerTab } from '../state/useAppStore';
import { TaskTreePanel } from '../panels/TaskTreePanel';
import { KanbanPanel } from '../panels/KanbanPanel';
import { AgentInspectorPanel } from '../panels/AgentInspectorPanel';
import { ArtifactsPanel } from '../panels/ArtifactsPanel';
import { ApprovalsPanel } from '../panels/ApprovalsPanel';
import { OrgEditorPanel } from '../panels/OrgEditorPanel';
import { EventLogPanel } from '../panels/EventLogPanel';
import { KeyPoolPanel } from '../panels/KeyPoolPanel';
import { ProjectsPanel } from '../panels/ProjectsPanel';
import { CompanyMemoryPanel } from '../panels/CompanyMemoryPanel';
import { EmployeeIntelligencePanel } from '../panels/EmployeeIntelligencePanel';
import { CompanyMeetingsPanel } from '../panels/CompanyMeetingsPanel';
import {
  Network, Kanban, UserRound, FileText, ShieldAlert, Users,
  Activity, KeyRound, BriefcaseBusiness, X, BookOpen, BarChart3, Video,
} from 'lucide-react';

type Tab = { id: ActiveDrawerTab; label: string; icon: React.FC<{ size?: number }> };

const WORK_TABS: Tab[] = [
  { id: 'kanban', label: 'Board', icon: Kanban },
  { id: 'tree', label: 'Hierarchy', icon: Network },
  { id: 'inspector', label: 'Agent', icon: UserRound },
  { id: 'artifacts', label: 'Deliverables', icon: FileText },
];
const COMPANY_TABS: Tab[] = [
  { id: 'approvals', label: 'Approvals', icon: ShieldAlert },
  { id: 'org', label: 'People', icon: Users },
  { id: 'events', label: 'Activity', icon: Activity },
  { id: 'keys', label: 'API keys', icon: KeyRound },
  { id: 'projects', label: 'Projects', icon: BriefcaseBusiness },
  { id: 'memory', label: 'Memory', icon: BookOpen },
  { id: 'intelligence', label: 'Intelligence', icon: BarChart3 },
  { id: 'meetings', label: 'Meetings', icon: Video },
];

function TabButton({ tab, active, count, onClick }: {
  tab: Tab; active: boolean; count?: number; onClick: () => void;
}) {
  const Icon = tab.icon;
  return (
    <button
      type="button"
      onClick={onClick}
      className={'app-drawer-tab' + (active ? ' app-drawer-tab-active' : '')}
      role="tab"
      id={'drawer-tab-' + tab.id}
      aria-selected={active}
      aria-controls="workspace-panel"
      tabIndex={active ? 0 : -1}
    >
      <Icon size={14} />
      <span>{tab.label}</span>
      {typeof count === 'number' && count > 0 && <span className="app-drawer-tab-count">{count}</span>}
    </button>
  );
}

export const RightDrawer: React.FC = () => {
  const { activeDrawerTab, setActiveDrawerTab, approvals, setDrawerOpen } = useAppStore();
  const pendingApprovals = approvals.filter((approval) => approval.status === 'pending').length;
  const allTabs = [...WORK_TABS, ...COMPANY_TABS];
  const handleTabKeys = (event: React.KeyboardEvent<HTMLElement>) => {
    const current = allTabs.findIndex((tab) => tab.id === activeDrawerTab);
    let next = current;
    if (event.key === 'ArrowRight') next = (current + 1) % allTabs.length;
    else if (event.key === 'ArrowLeft') next = (current - 1 + allTabs.length) % allTabs.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = allTabs.length - 1;
    else return;
    event.preventDefault();
    const nextTab = allTabs[next];
    setActiveDrawerTab(nextTab.id);
    window.requestAnimationFrame(() => document.getElementById('drawer-tab-' + nextTab.id)?.focus());
  };

  return (
    <aside className="app-drawer" aria-label="Workspace tools">
      <header className="app-drawer-header">
        <div>
          <h2>Workspace</h2>
          <p>Work, people and system records</p>
        </div>
        <button type="button" className="app-icon-button" onClick={() => setDrawerOpen(false)} aria-label="Close workspace panel">
          <X size={16} />
        </button>
      </header>

      <nav className="app-drawer-nav" role="tablist" aria-label="Workspace tools" onKeyDown={handleTabKeys}>
        <div className="app-drawer-group">
          <span className="app-drawer-group-title">Project work</span>
          <div className="app-drawer-tabs">
            {WORK_TABS.map((tab) => (
              <TabButton key={tab.id} tab={tab} active={activeDrawerTab === tab.id} onClick={() => setActiveDrawerTab(tab.id)} />
            ))}
          </div>
        </div>
        <div className="app-drawer-group">
          <span className="app-drawer-group-title">Company</span>
          <div className="app-drawer-tabs">
            {COMPANY_TABS.map((tab) => (
              <TabButton
                key={tab.id}
                tab={tab}
                active={activeDrawerTab === tab.id}
                count={tab.id === 'approvals' ? pendingApprovals : undefined}
                onClick={() => setActiveDrawerTab(tab.id)}
              />
            ))}
          </div>
        </div>
      </nav>

      <div className="app-drawer-content app-scroll" id="workspace-panel" role="tabpanel" aria-labelledby={"drawer-tab-" + activeDrawerTab} tabIndex={0}>
        {activeDrawerTab === 'tree' && <TaskTreePanel />}
        {activeDrawerTab === 'kanban' && <KanbanPanel />}
        {activeDrawerTab === 'inspector' && <AgentInspectorPanel />}
        {activeDrawerTab === 'keys' && <KeyPoolPanel />}
        {activeDrawerTab === 'projects' && <ProjectsPanel />}
        {activeDrawerTab === 'artifacts' && <ArtifactsPanel />}
        {activeDrawerTab === 'approvals' && <ApprovalsPanel />}
        {activeDrawerTab === 'org' && <OrgEditorPanel />}
        {activeDrawerTab === 'events' && <EventLogPanel />}
        {activeDrawerTab === 'memory' && <CompanyMemoryPanel />}
        {activeDrawerTab === 'intelligence' && <EmployeeIntelligencePanel />}
        {activeDrawerTab === 'meetings' && <CompanyMeetingsPanel />}
      </div>
    </aside>
  );
};
