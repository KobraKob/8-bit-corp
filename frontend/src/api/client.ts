import {
  Agent, Approval, Artifact, EventPayload, Project, Task, TaskTreeNode, UsageSummary, KeyStatus, CompanyMemory, EmployeePerformance, CompanyMeeting,
} from './types';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api').replace(/\/+$/, '');
const REQUEST_TIMEOUT_MS = 8000;
const inFlightRequests = new Set<AbortController>();

if (typeof window !== 'undefined') {
  window.addEventListener('offline', () => {
    inFlightRequests.forEach((controller) => controller.abort());
  });
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    throw new Error('You are offline. The last available data is still shown.');
  }

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  inFlightRequests.add(controller);
  const url = API_BASE + endpoint;
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };

  try {
    const res = await fetch(url, { ...options, headers, signal: controller.signal });
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error('API error (' + res.status + '): ' + (errorText || res.statusText));
    }
    if (res.status === 204) return undefined as T;
    return await res.json() as T;
  } catch (error) {
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      throw new Error('Connection lost. Showing the last successful data.');
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('The server did not respond within 8 seconds. Retry when it is reachable.');
    }
    if (error instanceof TypeError) {
      throw new Error('Cannot reach the Pixel Corp server. Check that the backend is running.');
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
    inFlightRequests.delete(controller);
  }
}

export const apiClient = {
  getProjects: () => request<Project[]>('/projects'),
  getProject: (id: string) => request<Project>('/projects/' + id),
  pauseProject: (id: string) => request<Project>('/projects/' + id + '/pause', { method: 'POST' }),
  resumeProject: (id: string) => request<Project>('/projects/' + id + '/resume', { method: 'POST' }),
  stopProject: (id: string) => request<Project>('/projects/' + id + '/stop', { method: 'POST' }),
  deleteProject: (id: string) => request<void>('/projects/' + id, { method: 'DELETE' }),
  createProject: (data: { name: string; client_name?: string; brief: string; due_at?: string }) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify(data) }),
  getProjectTree: (id: string) => request<TaskTreeNode[]>('/projects/' + id + '/tree'),
  submitTask: (projectId: string, data: { title: string; description: string; acceptance_criteria: string[] }) =>
    request<Task>('/projects/' + projectId + '/tasks', { method: 'POST', body: JSON.stringify(data) }),
  getProjectExportUrl: (projectId: string) => API_BASE + '/projects/' + projectId + '/export',

  getTask: (taskId: string) => request<{ task: Task; messages: any[]; review_notes: string[] }>('/tasks/' + taskId),
  cancelTask: (taskId: string) => request<{ success: boolean }>('/tasks/' + taskId + '/cancel', { method: 'POST' }),
  pauseTask: (taskId: string) => request<{ success: boolean }>('/tasks/' + taskId + '/pause', { method: 'POST' }),
  resumeTask: (taskId: string) => request<{ success: boolean }>('/tasks/' + taskId + '/resume', { method: 'POST' }),
  retryTask: (taskId: string) => request<{ success: boolean }>('/tasks/' + taskId + '/retry', { method: 'POST' }),

  getAgents: () => request<Agent[]>('/agents'),
  getAgent: (id: string) => request<Agent>('/agents/' + id),
  hireAgent: (data: { title: string; department?: string; level?: number; model_tier?: string; system_prompt?: string; tools?: string[] }) =>
    request<Agent>('/agents', { method: 'POST', body: JSON.stringify(data) }),
  updateAgent: (id: string, data: Partial<Agent>) =>
    request<Agent>('/agents/' + id, { method: 'PATCH', body: JSON.stringify(data) }),
  retireAgent: (id: string) => request<{ success: boolean }>('/agents/' + id, { method: 'DELETE' }),

  getArtifacts: (projectId: string) => request<Artifact[]>('/artifacts?project_id=' + encodeURIComponent(projectId)),
  getArtifact: (id: string) => request<Artifact>('/artifacts/' + id),
  getArtifactDownloadUrl: (id: string) => API_BASE + '/artifacts/' + id + '/download',

  getApprovals: () => request<Approval[]>('/approvals'),
  decideApproval: (id: string, decision: 'approved' | 'rejected') =>
    request<Approval>('/approvals/' + id + '/decide', { method: 'POST', body: JSON.stringify({ decision }) }),

  getUsage: () => request<UsageSummary>('/usage'),
  getKeys: () => request<KeyStatus[]>('/keys'),
  addKey: (data: { key: string; alias?: string; is_manager_dedicated?: boolean }) =>
    request<KeyStatus>('/keys', { method: 'POST', body: JSON.stringify(data) }),
  deleteKey: (alias: string) =>
    request<{ success: boolean; message: string }>('/keys/' + alias, { method: 'DELETE' }),

  getCompanyMemory: (query = '', projectId?: string) => {
    const params = new URLSearchParams({ q: query });
    if (projectId) params.append('project_id', projectId);
    return request<CompanyMemory[]>('/company/memory?' + params.toString());
  },
  saveCompanyMemory: (data: { title: string; body: string; tags?: string; project_id?: string }) =>
    request<CompanyMemory>('/company/memory', { method: 'POST', body: JSON.stringify(data) }),
  getEmployeePerformance: () => request<EmployeePerformance[]>('/company/employees/performance'),
  getCompanyMeetings: (projectId?: string) => request<CompanyMeeting[]>('/company/meetings' + (projectId ? '?project_id=' + encodeURIComponent(projectId) : '')),
  conveneCompanyMeeting: (projectId: string) =>
    request<CompanyMeeting>('/company/meetings', { method: 'POST', body: JSON.stringify({ project_id: projectId, reason: 'manual' }) }),

  getEvents: (after = 0, projectId?: string) => {
    const params = new URLSearchParams({ after: String(after) });
    if (projectId) params.append('project_id', projectId);
    return request<EventPayload[]>('/events?' + params.toString());
  },
};
