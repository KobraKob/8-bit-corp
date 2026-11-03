import { create } from 'zustand';
import {
  Agent, Approval, Artifact, EventPayload, Project, TaskTreeNode, UsageSummary, KeyStatus,
} from '../api/types';
import { apiClient } from '../api/client';

export type ActiveDrawerTab =
  | 'tree' | 'kanban' | 'inspector' | 'artifacts' | 'approvals'
  | 'org' | 'events' | 'keys' | 'projects' | 'memory' | 'intelligence' | 'meetings';

export type NetworkStatus = 'online' | 'connected' | 'degraded' | 'offline';

interface AppState {
  projects: Project[];
  activeProjectId: string | null;
  taskTree: TaskTreeNode[];
  taskTreeCache: Record<string, TaskTreeNode[]>;
  taskTreeSyncedAt: Record<string, string>;
  agents: Agent[];
  agentsLoading: boolean;
  agentsError: string | null;
  agentsRequestInFlight: boolean;
  selectedAgentId: string | null;
  selectedTaskId: string | null;
  selectedArtifact: Artifact | null;
  approvals: Approval[];
  approvalsLoading: boolean;
  approvalsError: string | null;
  approvalsRequestInFlight: boolean;
  events: EventPayload[];
  eventsLoading: boolean;
  eventsError: string | null;
  eventsRequestInFlight: boolean;
  usage: UsageSummary | null;
  usageError: string | null;
  usageRequestInFlight: boolean;
  keyStatuses: KeyStatus[];
  keysLoading: boolean;
  keysError: string | null;
  keysRequestInFlight: boolean;
  activeDrawerTab: ActiveDrawerTab;
  isDrawerOpen: boolean;
  isPaused: boolean;
  projectsLoading: boolean;
  projectsError: string | null;
  taskTreeLoading: boolean;
  taskTreeError: string | null;
  taskTreeUpdatedAt: string | null;
  taskTreeRequestProjectId: string | null;
  projectsRequestInFlight: boolean;
  networkStatus: NetworkStatus;
  lastEventId: number;

  fetchProjects: () => Promise<void>;
  setActiveProject: (id: string) => Promise<void>;
  clearActiveProject: () => void;
  fetchTaskTree: () => Promise<void>;
  fetchAgents: () => Promise<void>;
  fetchEvents: () => Promise<void>;
  fetchApprovals: () => Promise<void>;
  fetchUsage: () => Promise<void>;
  fetchKeys: () => Promise<void>;
  setSelectedAgent: (id: string | null) => void;
  setSelectedTask: (id: string | null) => void;
  setSelectedArtifact: (art: Artifact | null) => void;
  setActiveDrawerTab: (tab: ActiveDrawerTab) => void;
  setDrawerOpen: (open: boolean) => void;
  setNetworkStatus: (status: NetworkStatus) => void;
  togglePause: () => Promise<void>;
  handleIncomingEvent: (evt: EventPayload) => void;
}

const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : 'The request failed. Retry when the server is reachable.';

function derivePaused(projects: Project[]): boolean {
  const pausable = projects.filter((project) => project.status === 'active' || project.status === 'paused');
  return pausable.length > 0 && pausable.every((project) => project.status === 'paused');
}

export const useAppStore = create<AppState>((set, get) => ({
  projects: [],
  activeProjectId: null,
  taskTree: [],
  taskTreeCache: {},
  taskTreeSyncedAt: {},
  agents: [],
  agentsLoading: false,
  agentsError: null,
  agentsRequestInFlight: false,
  selectedAgentId: null,
  selectedTaskId: null,
  selectedArtifact: null,
  approvals: [],
  approvalsLoading: false,
  approvalsError: null,
  approvalsRequestInFlight: false,
  events: [],
  eventsLoading: false,
  eventsError: null,
  eventsRequestInFlight: false,
  usage: null,
  usageError: null,
  usageRequestInFlight: false,
  keyStatuses: [],
  keysLoading: false,
  keysError: null,
  keysRequestInFlight: false,
  activeDrawerTab: 'tree',
  isDrawerOpen: true,
  isPaused: false,
  projectsLoading: false,
  projectsError: null,
  taskTreeLoading: false,
  taskTreeError: null,
  taskTreeUpdatedAt: null,
  taskTreeRequestProjectId: null,
  projectsRequestInFlight: false,
  networkStatus: typeof navigator !== 'undefined' && !navigator.onLine ? 'offline' : 'online',
  lastEventId: 0,

  fetchProjects: async () => {
    if (get().projectsRequestInFlight) return;
    set({ projectsRequestInFlight: true });
    const hasProjects = get().projects.length > 0;
    set({ projectsLoading: !hasProjects, projectsError: null });
    try {
      const projects = await apiClient.getProjects();
      set({
        projects,
        projectsLoading: false,
        projectsRequestInFlight: false,
        projectsError: null,
        isPaused: derivePaused(projects),
        networkStatus: 'online',
      });
      const activeId = get().activeProjectId;
      if (!activeId && projects.length > 0) {
        await get().setActiveProject(projects[0].id);
      } else if (activeId && !projects.some((project) => project.id === activeId)) {
        get().clearActiveProject();
      }
    } catch (error) {
      set({
        projectsLoading: false,
        projectsRequestInFlight: false,
        projectsError: errorMessage(error),
        networkStatus: typeof navigator !== 'undefined' && !navigator.onLine ? 'offline' : 'degraded',
      });
    }
  },

  clearActiveProject: () => set({
    activeProjectId: null,
    taskTree: [],
    selectedTaskId: null,
    selectedArtifact: null,
    taskTreeLoading: false,
    taskTreeError: null,
    taskTreeUpdatedAt: null,
    taskTreeRequestProjectId: null,
  }),

  setActiveProject: async (id: string) => {
    if (get().activeProjectId === id && get().taskTreeUpdatedAt) {
      set({ isDrawerOpen: true });
      return;
    }
    const cachedTree = get().taskTreeCache[id] || [];
    set({
      activeProjectId: id,
      taskTree: cachedTree,
      taskTreeLoading: cachedTree.length === 0 && !get().taskTreeSyncedAt[id],
      taskTreeError: null,
      taskTreeUpdatedAt: get().taskTreeSyncedAt[id] || null,
      selectedTaskId: null,
      selectedArtifact: null,
      isDrawerOpen: true,
    });
    await get().fetchTaskTree();
  },

  fetchTaskTree: async () => {
    const projectId = get().activeProjectId;
    if (!projectId) {
      set({ taskTree: [], taskTreeLoading: false, taskTreeError: null, taskTreeRequestProjectId: null });
      return;
    }
    if (get().taskTreeRequestProjectId === projectId) return;
    set({ taskTreeRequestProjectId: projectId });
    const hasSnapshot = get().taskTree.length > 0 || Boolean(get().taskTreeSyncedAt[projectId]);
    set({ taskTreeLoading: !hasSnapshot, taskTreeError: null });
    try {
      const tree = await apiClient.getProjectTree(projectId);
      const syncedAt = new Date().toISOString();
      set((state) => ({
        taskTreeCache: { ...state.taskTreeCache, [projectId]: tree },
        taskTreeSyncedAt: { ...state.taskTreeSyncedAt, [projectId]: syncedAt },
        ...(state.taskTreeRequestProjectId === projectId ? { taskTreeRequestProjectId: null } : {}),
        ...(state.activeProjectId === projectId ? {
          taskTree: tree,
          taskTreeLoading: false,
          taskTreeError: null,
          taskTreeUpdatedAt: syncedAt,
          networkStatus: 'online' as const,
        } : {}),
      }));
    } catch (error) {
      if (get().activeProjectId !== projectId) return;
      set({
        taskTreeLoading: false,
        taskTreeRequestProjectId: null,
        taskTreeError: errorMessage(error),
        networkStatus: typeof navigator !== 'undefined' && !navigator.onLine ? 'offline' : 'degraded',
      });
    }
  },

  fetchEvents: async () => {
    if (get().eventsRequestInFlight) return;
    set({ eventsRequestInFlight: true, eventsLoading: get().events.length === 0, eventsError: null });
    try {
      const latestId = get().lastEventId;
      const incoming = await apiClient.getEvents(latestId);
      set((state) => {
        const known = new Set(state.events.map((event) => event.id));
        const fresh = incoming.filter((event) => !known.has(event.id));
        return {
          events: [...fresh.reverse(), ...state.events].slice(0, 500),
          lastEventId: Math.max(state.lastEventId, ...incoming.map((event) => event.id), 0),
          eventsLoading: false,
          eventsRequestInFlight: false,
          eventsError: null,
        };
      });
    } catch (error) {
      set({
        eventsLoading: false,
        eventsRequestInFlight: false,
        eventsError: errorMessage(error),
        networkStatus: typeof navigator !== 'undefined' && !navigator.onLine ? 'offline' : 'degraded',
      });
    }
  },

  fetchAgents: async () => {
    if (get().agentsRequestInFlight) return;
    set({ agentsRequestInFlight: true, agentsLoading: get().agents.length === 0, agentsError: null });
    try {
      set({
        agents: await apiClient.getAgents(),
        agentsLoading: false,
        agentsRequestInFlight: false,
        agentsError: null,
      });
    } catch (error) {
      set({
        agentsLoading: false,
        agentsRequestInFlight: false,
        agentsError: errorMessage(error),
        networkStatus: typeof navigator !== 'undefined' && !navigator.onLine ? 'offline' : 'degraded',
      });
    }
  },

  fetchApprovals: async () => {
    if (get().approvalsRequestInFlight) return;
    set({ approvalsRequestInFlight: true, approvalsLoading: get().approvals.length === 0, approvalsError: null });
    try {
      set({
        approvals: await apiClient.getApprovals(),
        approvalsLoading: false,
        approvalsRequestInFlight: false,
        approvalsError: null,
      });
    } catch (error) {
      set({
        approvalsLoading: false,
        approvalsRequestInFlight: false,
        approvalsError: errorMessage(error),
        networkStatus: typeof navigator !== 'undefined' && !navigator.onLine ? 'offline' : 'degraded',
      });
    }
  },

  fetchUsage: async () => {
    if (get().usageRequestInFlight) return;
    set({ usageRequestInFlight: true, usageError: null });
    try {
      set({ usage: await apiClient.getUsage(), usageRequestInFlight: false, usageError: null });
    } catch (error) {
      set({
        usageRequestInFlight: false,
        usageError: errorMessage(error),
        networkStatus: typeof navigator !== 'undefined' && !navigator.onLine ? 'offline' : 'degraded',
      });
    }
  },

  fetchKeys: async () => {
    if (get().keysRequestInFlight) return;
    set({ keysRequestInFlight: true, keysLoading: get().keyStatuses.length === 0, keysError: null });
    try {
      set({
        keyStatuses: await apiClient.getKeys(),
        keysLoading: false,
        keysRequestInFlight: false,
        keysError: null,
      });
    } catch (error) {
      set({
        keysLoading: false,
        keysRequestInFlight: false,
        keysError: errorMessage(error),
        networkStatus: typeof navigator !== 'undefined' && !navigator.onLine ? 'offline' : 'degraded',
      });
    }
  },

  setSelectedAgent: (id) => set({
    selectedAgentId: id,
    activeDrawerTab: id ? 'inspector' : get().activeDrawerTab,
    isDrawerOpen: id ? true : get().isDrawerOpen,
  }),
  setSelectedTask: (id) => set({ selectedTaskId: id }),
  setSelectedArtifact: (art) => set({
    selectedArtifact: art,
    activeDrawerTab: art ? 'artifacts' : get().activeDrawerTab,
    isDrawerOpen: art ? true : get().isDrawerOpen,
  }),
  setActiveDrawerTab: (tab) => set({ activeDrawerTab: tab, isDrawerOpen: true }),
  setDrawerOpen: (open) => set({ isDrawerOpen: open }),
  setNetworkStatus: (status) => set({ networkStatus: status }),

  togglePause: async () => {
    const projects = get().projects;
    const shouldResume = get().isPaused;
    const targets = projects.filter((project) =>
      shouldResume ? project.status === 'paused' : project.status === 'active'
    );
    if (targets.length === 0) return;
    const results = await Promise.allSettled(targets.map((project) =>
      shouldResume ? apiClient.resumeProject(project.id) : apiClient.pauseProject(project.id)
    ));
    await get().fetchProjects();
    const failed = results.filter((result) => result.status === 'rejected').length;
    if (failed > 0) {
      set({ projectsError: failed + ' project action(s) failed. Review project statuses and retry.' });
    }
  },

  handleIncomingEvent: (evt: EventPayload) => {
    set((state) => {
      if (state.events.some((existing) => existing.id === evt.id)) return state;
      return {
        events: [evt, ...state.events].slice(0, 500),
        lastEventId: Math.max(state.lastEventId, evt.id || 0),
      };
    });

    if (evt.type.startsWith('task.') || evt.type === 'project.completed') {
      void get().fetchTaskTree();
      if (evt.type === 'project.completed') void get().fetchProjects();
    }
    if (evt.type.startsWith('approval.')) void get().fetchApprovals();
    if (evt.type.startsWith('agent.hired') || evt.type.startsWith('agent.retired')) void get().fetchAgents();
    if (evt.type === 'agent.tool_call' || evt.type === 'task.done') {
      void get().fetchUsage();
      void get().fetchKeys();
    }
  },
}));
