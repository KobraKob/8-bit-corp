# Pixel Corp 🏢✨

> **An AI Company Simulator in a Pixel-Art Open Office.**
> 
> A live visualization of a multi-agent orchestration engine. Submit any freelance client brief or project goal to the **CEO**, watch the corporate hierarchy triage, delegate down the org chart, execute work at pixel desks, conduct acceptance criteria reviews, and synthesize bottom-up deliverables with confetti celebrations.

---

## 🏛️ System Architecture

```
+------------------------------------------------------------------------------+
|                             USER / FOUNDER                                   |
|       (Project Brief Intake • CEO Dispatch • Live Office • Approvals)        |
+------------------------------------------------------------------------------+
                                      │  REST API / WebSockets
                                      ▼
+------------------------------------------------------------------------------+
|                         FASTAPI BACKEND & REALTIME                           |
|   /api/projects   /api/tasks   /api/agents   /api/artifacts   /api/usage     |
|   WebSocket (/ws): Live Event Streaming with 'last_event_id' Reconnect      |
+------------------------------------------------------------------------------+
                                      │
                                      ▼
+------------------------------------------------------------------------------+
|                         MULTI-AGENT ORCHESTRATOR                             |
|  • CEO Triage & DAG Delegation (Topological cycle detection)                 |
|  • Depth-First Async Scheduler & Crash Recovery                              |
|  • Review Loops: Acceptance Criteria Audits (Approve / Revise / Escalate)   |
|  • Bottom-Up Synthesis: Child Deliverable Aggregation & Final Project Bundle |
+------------------------------------------------------------------------------+
          │                                                  │
          ▼                                                  ▼
+----------------------------+            +------------------------------------+
|     LLM ROUTER & LIMITER   |            |      PERSISTENCE & ISOLATION       |
| • Groq / OpenAI / Mock     |            | • SQLite (WAL Mode, Postgres-ready)|
| • Token-Bucket (RPM/TPM)   |            | • Workspaces (Path Traversal Guard)|
| • Daily Counters (RPD/TPD) |            | • Sandbox (Subprocess Execution)   |
| • 1-Turn Schema Repair     |            | • Append-Only Monotonic Event Bus  |
+----------------------------+            +------------------------------------+
```

---

## 🚀 Quickstart (< 5 minutes)

### Prerequisites
- **Python 3.11+**
- **Node.js 20.19+** & **pnpm** (or npm)

### 1. Backend Setup
```bash
# In project root
python -m venv backend/.venv
# Windows:
backend\.venv\Scripts\activate
# Linux/macOS:
# source backend/.venv/bin/activate

python -m pip install -e "backend[dev]"
```

Copy the environment template:
```bash
cp .env.example .env
```
The template starts in offline mock mode. Set `LLM_PROVIDER=groq` and add your `GROQ_API_KEY` to `.env` when you want live model calls.

### 2. Frontend Setup
```bash
cd frontend
pnpm install
```

### 3. Run Development Servers
In terminal 1 (Backend):
```bash
# From backend directory or using python module
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```
API Documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

In terminal 2 (Frontend):
```bash
cd frontend
pnpm dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🧪 Running Tests (100% Offline)

The backend test suite runs offline without API keys using `MockProvider`:

```bash
# Run the full backend test suite
python -m pytest backend/tests
```

Frontend build & typecheck:
```bash
cd frontend
pnpm build
```

---

## Runtime reliability and debugging

### Provider adapters
Provider selection is explicit in `config/models.yaml`:
- `groq`: Groq chat-completions adapter with pooled API keys.
- `openai_compatible`: OpenAI-compatible gateways and self-hosted endpoints.
- `ollama`: Ollama's local OpenAI-compatible `/v1` endpoint.
- `mock`: deterministic offline testing.

Set `LLM_PROVIDER` in `.env`. For Ollama, set `LLM_PROVIDER=ollama`, start Ollama, and set the tier model IDs in `config/models.yaml` to models installed locally. The OpenAI-compatible adapter uses a 60-second request timeout and leaves retries to the router. Retryable timeouts, connection failures, 408/409/425, 429, and 5xx responses use bounded exponential backoff; `Retry-After` is respected when supplied. Non-retryable errors move directly to the next configured model fallback.

### Durable execution
Each task stores a JSON checkpoint, worker lease token, lease expiry, retry time, and delegation count. The runtime persists its conversation, tool-call state, token usage, and execution phase after each model/tool step. A worker must own the current lease to write checkpoints. Expired leases are recovered by the scheduler without deleting the last checkpoint.

Tool calls are recorded as started before execution and completed after their result is saved. If a process dies between those writes, the tool is not blindly replayed: the model receives an interruption marker and must inspect the current workspace before deciding what to do next. This avoids automatic duplicate side effects, but external tools should still be designed to be idempotent.

### Task diagnostics
Select a task in the execution tree to view its structured diagnostics. The same records are available from `GET /api/tasks/{task_id}/logs`. Logs include claims, checkpoints, tool execution, recovery, and errors. They intentionally exclude provider secrets.

### Retry and delegation limits
Task failures use bounded exponential retry delays and stop at the task's `max_attempts`. Provider retries are separately bounded by `llm_max_retries`. A task can delegate only once; the project task-count and hierarchy-depth limits prevent recursive fan-out from growing without bound. Repeated identical tool calls are intercepted by the runtime.

## Security and deployment boundary

The built-in `run_code` tool uses a restricted subprocess, not a hardened container boundary. Do not expose this development server to untrusted users or execute untrusted agent code on a production host. Before public deployment, isolate code execution in disposable containers with CPU, memory, filesystem, and network limits, and add authentication to the API.

## 🎮 Office Controls & Visuals

- **Canvas Interaction**:
  - **Click on any Agent**: Opens the **Agent Inspector** in the right drawer to modify their system prompt, change model tier (`fast` / `smart` / `premium`), or retire them.
  - **Drag (left/right/middle click)**: Smooth pan across all 4 office floors.
  - **Mouse Wheel**: Smooth zoom (1.0x to 3.5x).
- **Agent Animations (Driven by Event Stream)**:
  - 💭 **3-Dot Thought Bubble**: Agent is thinking / calling LLM.
  - ⚠️ **Red '!' Bubble**: Task blocked or escalating.
  - 🚶‍♂️ **Walking Animation**: Delegator walks over to deliver tickets to assignee's desk.
  - 🎉 **Confetti Shower**: Whole building celebrates when CEO delivers the completed project deliverable!

---

## ⚙️ Upgrading & Changing Models

No code changes are required to switch LLM models or providers. Edit `config/models.yaml`:
```yaml
default_provider: groq
tiers:
  fast:    { provider: groq, model: llama-3.1-8b-instant }
  smart:   { provider: groq, model: llama-3.3-70b-versatile }
  premium: { provider: groq, model: llama-3.3-70b-versatile }
```
See [`docs/upgrading-models.md`](docs/upgrading-models.md) for detailed instructions.

---

## 📁 Repository Layout

```
pixel-corp/
  config/
    models.yaml           # Model providers, tiers, rate limits
    org.yaml              # Default 46-agent corporate hierarchy
    settings.yaml         # Concurrency, budgets, safety gates
  backend/
    app/
      api/                # FastAPI REST & WebSocket endpoints
      core/               # Logging, config loader, security errors
      db/                 # SQLAlchemy 2 models, async session, WAL mode
      domain/             # Pure task FSM, DAG cycle detection, org model
      events/             # Monotonic event bus with catch-up resume
      llm/                # Provider adapters, retries, rate limiter, JSON repair
      agents/             # Context builder, agent runtime tool loop
      tools/              # Tool registry, subprocess sandbox, SSRF guard
      orchestrator/       # Triage, checkpoints, delegation, reviews, scheduler
      workspace/          # Isolated project workspaces with path traversal guards
    tests/                # Backend unit & integration tests
  frontend/
    src/
      api/                # Typed REST client
      state/              # Zustand store & WebSocket auto-reconnect client
      office/             # Phaser scene, EasyStar pathfinding, procedural pixel-art
      panels/             # Task tree, Kanban, Inspector, Artifacts, Approvals, Org, Events
      app/                # App shell, left sidebar, right drawer, bottom usage meter
  docs/
    events.md             # Event stream contract
    org.md                # Org hierarchy and floor layout
    upgrading-models.md   # Model configuration guide
  DECISIONS.md            # Engineering decisions log
  build.md                # Project mission & architecture blueprint
```


## Virtual office controls

The office view now streams employee activity from the event bus and animates working, thinking, reviewing, blocked, meeting, walking, and idle states. Department rooms use distinct floor and accent palettes. Select a room on the map or in the Rooms panel to focus the camera.

The Virtual Office panel provides:
- Department filters and employee activity status.
- Meeting start, join, leave, and end events.
- Persistent employee-to-employee messages.
- Queued-task handoff with an atomic assignment update. Tasks already held by a worker lease cannot be transferred.
- A chronological event timeline with single-event replay.

Office actions are exposed at `POST /api/office/actions`. The existing WebSocket event stream delivers meeting, conversation, and handoff activity to connected clients. On narrow screens, open **Control panels** to access the task drawer without squeezing the office canvas.
