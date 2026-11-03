import { create } from 'zustand';
import {
  Agent,
  Approval,
  Artifact,
  EventPayload,
  Project,
  Task,
  TaskTreeNode,
  UsageSummary,
  KeyStatus,
} from '../api/types';
import { apiClient } from '../api/client';

export type ActiveDrawerTab =
  | 'tree'
  | 'kanban'
  | 'inspector'
  | 'artifacts'
  | 'approvals'
  | 'org'
  | 'events'
  | 'keys';

interface AppState {
  projects: Project[];
  activeProjectId: string | null;
  taskTree: TaskTreeNode[];
  agents: Agent[];
  selectedAgentId: string | null;
  selectedTaskId: string | null;
  selectedArtifact: Artifact | null;
  approvals: Approval[];
  events: EventPayload[];
  usage: UsageSummary | null;
  keyStatuses: KeyStatus[];
  activeDrawerTab: ActiveDrawerTab;
  isPaused: boolean;
  isLoading: boolean;
  lastEventId: number;
  selectedRoom: string | null;
  replayEventId: number | null;

  // Actions
  fetchProjects: () => Promise<void>;
  setActiveProject: (id: string) => Promise<void>;
  fetchTaskTree: () => Promise<void>;
  fetchAgents: () => Promise<void>;
  fetchApprovals: () => Promise<void>;
  fetchUsage: () => Promise<void>;
  fetchKeys: () => Promise<void>;
  setSelectedAgent: (id: string | null) => void;
  setSelectedTask: (id: string | null) => void;
  setSelectedArtifact: (art: Artifact | null) => void;
  setActiveDrawerTab: (tab: ActiveDrawerTab) => void;
  togglePause: () => void;
  setSelectedRoom: (room: string | null) => void;
  setReplayEvent: (eventId: number | null) => void;
  handleIncomingEvent: (evt: EventPayload) => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  projects: [],
  activeProjectId: null,
  taskTree: [],
  agents: [],
  selectedAgentId: null,
  selectedTaskId: null,
  selectedArtifact: null,
  approvals: [],
  events: [],
  usage: null,
  keyStatuses: [],
  activeDrawerTab: 'tree',
  isPaused: false,
  isLoading: false,
  lastEventId: 0,
  selectedRoom: null,
  replayEventId: null,

  fetchProjects: async () => {
    try {
      const projects = await apiClient.getProjects();
      set({ projects });
      if (!get().activeProjectId && projects.length > 0) {
        get().setActiveProject(projects[0].id);
      }
    } catch (e) {
      console.error('Failed to load projects', e);
    }
  },

  setActiveProject: async (id: string) => {
    set({ activeProjectId: id });
    await get().fetchTaskTree();
  },

  fetchTaskTree: async () => {
    const { activeProjectId } = get();
    if (!activeProjectId) return;
    try {
      const tree = await apiClient.getProjectTree(activeProjectId);
      set({ taskTree: tree });
    } catch (e) {
      console.error('Failed to load task tree', e);
    }
  },

  fetchAgents: async () => {
    try {
      const agents = await apiClient.getAgents();
      set({ agents });
    } catch (e) {
      console.error('Failed to load agents', e);
    }
  },

  fetchApprovals: async () => {
    try {
      const approvals = await apiClient.getApprovals();
      set({ approvals });
    } catch (e) {
      console.error('Failed to load approvals', e);
    }
  },

  fetchUsage: async () => {
    try {
      const usage = await apiClient.getUsage();
      set({ usage });
    } catch (e) {
      console.error('Failed to load usage', e);
    }
  },

  fetchKeys: async () => {
    try {
      const keyStatuses = await apiClient.getKeys();
      set({ keyStatuses });
    } catch (e) {
      console.error('Failed to load key statuses', e);
    }
  },

  setSelectedAgent: (id) => set({ selectedAgentId: id, activeDrawerTab: id ? 'inspector' : get().activeDrawerTab }),
  setSelectedTask: (id) => set({ selectedTaskId: id }),
  setSelectedArtifact: (art) => set({ selectedArtifact: art, activeDrawerTab: art ? 'artifacts' : get().activeDrawerTab }),
  setActiveDrawerTab: (tab) => set({ activeDrawerTab: tab }),
  togglePause: () => set((state) => ({ isPaused: !state.isPaused })),
  setSelectedRoom: (room) => set({ selectedRoom: room }),
  setReplayEvent: (eventId) => set({ replayEventId: eventId }),

  handleIncomingEvent: (evt: EventPayload) => {
    set((state) => {
      // Catch-up replay and the live socket can deliver the same event.
      if (state.events.some((existing) => existing.id === evt.id)) return state;
      const newEvents = [evt, ...state.events].slice(0, 500);
      const nextLastId = Math.max(state.lastEventId, evt.id || 0);
      return { events: newEvents, lastEventId: nextLastId };
    });

    // Auto-refresh task tree on task lifecycle events
    if (evt.type.startsWith('task.') || evt.type === 'project.completed') {
      get().fetchTaskTree();
    }
    // Auto-refresh approvals
    if (evt.type.startsWith('approval.')) {
      get().fetchApprovals();
    }
    // Auto-refresh agents
    if (evt.type.startsWith('agent.hired') || evt.type.startsWith('agent.retired')) {
      get().fetchAgents();
    }
    // Auto-refresh usage on tool calls or completions
    if (evt.type === 'agent.tool_call' || evt.type === 'task.done') {
      get().fetchUsage();
      get().fetchKeys();
    }
  },
}));
