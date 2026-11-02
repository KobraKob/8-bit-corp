# Event Stream Contract & Protocol (`docs/events.md`)

Pixel Corp's frontend and orchestration engine are decoupled systems communicating over an append-only event log streamed via WebSocket (`/ws`) and queryable via `/api/events?after=<id>`.

## Event Payload Structure

```json
{
  "id": 42,
  "ts": "2026-11-02T22:30:00Z",
  "type": "task.created",
  "project_id": "proj_abc123",
  "task_id": "tsk_def456",
  "agent_id": "agt_ghi789",
  "payload": {
    "title": "Design UI Mockup & System",
    "depth": 1
  }
}
```

## Event Types Catalog

### Task Lifecycle
| Event Type | Emitted When | Payload Details |
|---|---|---|
| `task.created` | New task instantiated | `{ title, depth, assignee_agent_id, parent_id }` |
| `task.assigned` | Task routed to an agent | `{ assignee_agent_id, department }` |
| `task.started` | Task picked by worker | `{ title, depth }` |
| `task.delegated` | Manager breaks down task | `{ subtask_id, to_agent_id }` |
| `task.submitted` | Worker submits deliverable | `{ summary }` |
| `task.review_requested` | Sent to manager for audit | `{ reviewer_id, deliverable_artifact_id }` |
| `task.revision_requested` | Reviewer requests fixes | `{ revision_notes[], attempt }` |
| `task.approved` | Reviewer passes deliverable | `{ notes }` |
| `task.blocked` | Blocker reported | `{ reason }` |
| `task.failed` | Max attempts exceeded | `{ reason }` |
| `task.done` | Task terminal complete | `{ deliverable_artifact_id }` |

### Agent Actions & Animations
| Event Type | Animation in Phaser 3 Office |
|---|---|
| `agent.thinking` | Displays 3-dot thought bubble above agent sprite |
| `agent.tool_call` | Agent works at desk, typing animation at computer |
| `agent.tool_result` | Tool execution result completed |
| `agent.message` | Conversational output bubble |
| `agent.hired` | New desk spawns and agent walks in |
| `agent.retired` | Agent packs up and leaves office |

### Artifacts & Approvals
| Event Type | Emitted When |
|---|---|
| `artifact.created` | Deliverable file registered in workspace |
| `approval.requested` | High-stakes safety gate triggered |
| `approval.decided` | User approves or rejects gate |

### System & Quotas
| Event Type | Emitted When |
|---|---|
| `system.rate_limited` | Rate limiter throttled call to model |
| `system.quota_exhausted` | Daily quota reached; scheduler paused until reset |
| `system.resumed` | Scheduler resumed |
| `project.completed` | CEO integration completed; triggers confetti shower! |
