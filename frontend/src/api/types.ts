export interface Project {
  id: string;
  name: string;
  client_name?: string | null;
  brief: string;
  status: string;
  created_at: string;
  due_at?: string | null;
  settings_json: Record<string, any>;
}

export interface Task {
  id: string;
  project_id: string;
  parent_id?: string | null;
  root_id?: string | null;
  depth: number;
  title: string;
  description: string;
  original_goal: string;
  acceptance_criteria_json: string[];
  assignee_agent_id?: string | null;
  creator_agent_id?: string | null;
  reviewer_agent_id?: string | null;
  status: 'pending' | 'assigned' | 'in_progress' | 'blocked' | 'integrating' | 'in_review' | 'reviewing' | 'revision_requested' | 'done' | 'failed' | 'cancelled';
  attempt: number;
  max_attempts: number;
  depends_on_json: string[];
  deliverable_artifact_id?: string | null;
  review_notes_json: string[];
  token_budget: number;
  tokens_used: number;
  priority: number;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
}

export interface TaskTreeNode extends Task {
  children: TaskTreeNode[];
}

export interface Agent {
  id: string;
  role_key: string;
  display_name: string;
  department: string;
  level: number;
  reports_to_agent_id?: string | null;
  model_tier: string;
  system_prompt: string;
  tools_json: string[];
  status: 'active' | 'retired';
  sprite_json: {
    sprite_id?: string;
    skin_tone?: number;
    hair_style?: number;
    shirt_color?: string;
    pants_color?: string;
    accessory?: string;
    badge?: string;
  };
  api_key?: string | null;
  has_custom_api_key?: boolean;
  masked_api_key?: string | null;
  created_at: string;
}

export interface KeyStatus {
  alias: string;
  masked_key: string;
  is_manager_dedicated: boolean;
  is_healthy: boolean;
  total_calls: number;
  cooldown_remaining_sec: number;
}

export interface Artifact {
  id: string;
  project_id: string;
  task_id?: string | null;
  kind: 'text' | 'markdown' | 'code' | 'file' | 'json' | 'image_svg';
  path: string;
  summary: string;
  created_by_agent_id?: string | null;
  version: number;
  created_at: string;
  content?: string;
}

export interface Approval {
  id: string;
  project_id: string;
  task_id?: string | null;
  kind: string;
  request_json: Record<string, any>;
  status: 'pending' | 'approved' | 'rejected';
  decided_at?: string | null;
}

export interface EventPayload {
  id: number;
  ts: string;
  type: string;
  project_id?: string | null;
  task_id?: string | null;
  agent_id?: string | null;
  payload: Record<string, any>;
}

export interface CompanyMemory {
  id: string;
  project_id?: string | null;
  title: string;
  body: string;
  tags: string;
  updated_at: string;
}

export interface EmployeePerformance {
  agent_id: string;
  display_name: string;
  department: string;
  role_key: string;
  tasks_assigned: number;
  tasks_completed: number;
  tasks_failed: number;
  tasks_cancelled: number;
  revision_count: number;
  completion_rate: number | null;
  reliability_rate: number | null;
  average_completion_seconds: number | null;
  average_quality_score: number | null;
  quality_score_note: string;
}

export interface CompanyMeeting {
  id: string;
  project_id: string;
  title: string;
  trigger: string;
  status: string;
  attendees: Array<{ agent_id: string; name: string; department: string; role: string }>;
  agenda: string[];
  discussion: Array<Record<string, any>>;
  decisions: Array<Record<string, any>>;
  created_at: string;
  completed_at?: string | null;
}

export interface UsageSummary {
  total_calls: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_cost_estimate: number;
  models_daily_usage: Array<{
    model: string;
    day: string;
    requests_count: number;
    tokens_count: number;
  }>;
}
