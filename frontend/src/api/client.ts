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
} from './types';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api').replace(/\/+$/, '');

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`API error (${res.status}): ${errorText}`);
  }
  return res.json();
}

export const apiClient = {
  // Projects
  getProjects: () => request<Project[]>('/projects'),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  createProject: (data: { name: string; client_name?: string; brief: string; due_at?: string }) =>
    request<Project>('/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getProjectTree: (id: string) => request<TaskTreeNode[]>(`/projects/${id}/tree`),
  submitTask: (projectId: string, data: { title: string; description: string; acceptance_criteria: string[] }) =>
    request<Task>(`/projects/${projectId}/tasks`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getProjectExportUrl: (projectId: string) => `${API_BASE}/projects/${projectId}/export`,

  // Tasks
  getTask: (taskId: string) => request<{ task: Task; messages: any[]; review_notes: string[] }>(`/tasks/${taskId}`),
  cancelTask: (taskId: string) => request<{ success: boolean }>(`/tasks/${taskId}/cancel`, { method: 'POST' }),
  pauseTask: (taskId: string) => request<{ success: boolean }>(`/tasks/${taskId}/pause`, { method: 'POST' }),
  resumeTask: (taskId: string) => request<{ success: boolean }>(`/tasks/${taskId}/resume`, { method: 'POST' }),
  retryTask: (taskId: string) => request<{ success: boolean }>(`/tasks/${taskId}/retry`, { method: 'POST' }),

  // Agents
  getAgents: () => request<Agent[]>('/agents'),
  getAgent: (id: string) => request<Agent>(`/agents/${id}`),
  hireAgent: (data: { title: string; department?: string; level?: number; model_tier?: string; system_prompt?: string; tools?: string[] }) =>
    request<Agent>('/agents', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateAgent: (id: string, data: Partial<Agent>) =>
    request<Agent>(`/agents/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  retireAgent: (id: string) => request<{ success: boolean }>(`/agents/${id}`, { method: 'DELETE' }),

  // Artifacts
  getArtifacts: (projectId: string) => request<Artifact[]>(`/artifacts?project_id=${encodeURIComponent(projectId)}`),
  getArtifact: (id: string) => request<Artifact>(`/artifacts/${id}`),
  getArtifactDownloadUrl: (id: string) => `${API_BASE}/artifacts/${id}/download`,

  // Approvals
  getApprovals: () => request<Approval[]>('/approvals'),
  decideApproval: (id: string, decision: 'approved' | 'rejected') =>
    request<Approval>(`/approvals/${id}/decide`, {
      method: 'POST',
      body: JSON.stringify({ decision }),
    }),

  // Usage
  getUsage: () => request<UsageSummary>('/usage'),

  // API Key Pool (5-10 Keys + Higher Managers)
  getKeys: () => request<KeyStatus[]>('/keys'),
  addKey: (data: { key: string; alias?: string; is_manager_dedicated?: boolean }) =>
    request<KeyStatus>('/keys', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  deleteKey: (alias: string) =>
    request<{ success: boolean; message: string }>(`/keys/${alias}`, {
      method: 'DELETE',
    }),

  // Events
  getEvents: (after = 0, projectId?: string) => {
    const params = new URLSearchParams({ after: String(after) });
    if (projectId) params.append('project_id', projectId);
    return request<EventPayload[]>(`/events?${params.toString()}`);
  },
};
