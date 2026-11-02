# BUILD.md — "Pixel Corp": An AI Company Simulator in a Pixel-Art Office

> Hand this file to the coding agent. Read it fully before writing any code.
> Build in the phases below, in order. Do not start a phase until the previous phase's acceptance criteria pass.

---

## 0. Mission

Build a web app that looks like a **pixel-art open-office building** populated by **individual AI agents** arranged in a realistic corporate hierarchy (CEO, C-level, managers, leads, associates, support staff). The user (the "Client/Founder") submits a task. The **CEO** receives it, triages and plans it, and it cascades down the org chart: managers break it into tickets, leads review, associates do the work, support staff provide shared services. Results flow back up with review and integration at each level until the CEO delivers a finished result.

The pixel office is a **live visualization** of a real **multi-agent orchestration engine**. The two are separate systems connected by an event stream.

### Use context (shapes many decisions)
- Owner uses it personally to **build projects** and to do **freelance client work**. It must handle **every kind of task** (software, design, marketing, writing, research, data, operations, finance/proposals, and anything unusual). No task category may be rejected.
- Phase 1 runs on **Groq free-tier models** (strict rate limits). Later, the owner upgrades to stronger models. **Switching models/providers must be a config change, not a code change.**
- Reliability matters: long jobs must survive crashes, rate limits, and bad model output without losing work.

### Non-goals (for v1)
Multi-user auth/SaaS, billing, mobile layout, real money movement, sending real emails/messages to third parties, autonomous publishing. (Design extension points, don't build them.)

---

## 1. Tech stack (fixed unless blocked)

| Layer | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, asyncio, Pydantic v2, SQLAlchemy 2 + Alembic |
| DB | SQLite (WAL mode) for v1; schema must be Postgres-compatible |
| Realtime | WebSocket (FastAPI) streaming the event log |
| LLM access | `openai` Python SDK pointed at an OpenAI-compatible base URL (Groq: `https://api.groq.com/openai/v1`), wrapped in our own `LLMProvider` interface |
| Frontend | Vite + React + TypeScript, Zustand for state, Phaser 3 for the office, EasyStar.js for pathfinding |
| Tooling | `uv` (Python), `pnpm` (frontend), `pytest`, `ruff`, `mypy` (strict on core), `vitest`, Playwright for one e2e |
| Packaging | Monorepo, `Makefile` with `make dev`, `make test`, `make lint` |

Do **not** adopt LangChain/CrewAI/AutoGen. Orchestration is custom so behavior is inspectable, testable, and model-agnostic.

---

## 2. Repository layout

```
pixel-corp/
  BUILD.md
  DECISIONS.md              # agent logs every non-obvious decision here
  README.md
  Makefile
  .env.example
  config/
    models.yaml             # providers, model tiers, rate limits
    org.yaml                # departments, roles, hierarchy, tools, prompts
    settings.yaml           # budgets, depth caps, approval gates
  backend/
    pyproject.toml
    app/
      main.py
      api/                  # REST + WS routers
      core/                 # config loading, logging, ids, errors
      db/                   # models, session, migrations
      domain/               # pure domain logic: task state machine, org model
      llm/                  # provider interface, groq adapter, mock, limiter, router
      agents/               # runtime, prompt builder, context builder, schemas
      tools/                # tool registry + implementations + sandbox
      orchestrator/         # scheduler, triage, delegation, review, integration
      events/               # event bus, event types, persistence
      workspace/            # per-project file storage, artifact handling
    tests/
  frontend/
    package.json
    src/
      app/                  # shell, layout, routing
      state/                # zustand stores, ws client
      panels/               # task tree, kanban, inspector, chat, artifacts, usage
      office/               # phaser scenes, tilemap gen, sprites, agent FSM
      api/                  # typed client
  workspaces/               # runtime data: workspaces/<project_id>/... (gitignored)
```

---

## 3. Core domain model

### 3.1 Entities (DB tables)

- **projects**: `id, name, client_name, brief, status, created_at, due_at, settings_json`
- **agents**: `id, role_key, display_name, department, level, reports_to_agent_id, model_tier, system_prompt, tools_json, status (active|retired), sprite_json, created_at`
- **tasks**: `id, project_id, parent_id, root_id, depth, title, description, original_goal, acceptance_criteria_json, assignee_agent_id, creator_agent_id, reviewer_agent_id, status, attempt, max_attempts, depends_on_json, deliverable_artifact_id, review_notes_json, token_budget, tokens_used, priority, created_at, started_at, completed_at, error`
- **artifacts**: `id, project_id, task_id, kind (text|markdown|code|file|json|image_svg), path, summary, created_by_agent_id, version, created_at`
- **messages**: `id, task_id, from_agent_id, to_agent_id, kind, payload_json, created_at` (structured inter-agent messages, never free chat)
- **events**: `id (monotonic), ts, type, project_id, task_id, agent_id, payload_json` (append-only; source of truth for UI and replay)
- **llm_calls**: `id, ts, agent_id, task_id, provider, model, tier, prompt_tokens, completion_tokens, latency_ms, status, error, cost_estimate`
- **approvals**: `id, project_id, task_id, kind, request_json, status (pending|approved|rejected), decided_at`
- **wiki_notes**: `id, project_id (nullable = global), title, body, tags, created_by_agent_id, updated_at` (shared company knowledge)

### 3.2 Task state machine (implement as a pure, unit-tested module)

```
pending -> assigned -> in_progress -> in_review -> done
                         |   ^            |
                         v   |            v
                      blocked        revision_requested -> in_progress
in_progress -> failed (after max_attempts)
any non-terminal -> cancelled
```

Additional internal phase for parents: `integrating` (all children done; owner synthesizes children's deliverables, then goes to `in_review`).

Rules:
- A task is **ready** when status is `assigned` and every id in `depends_on` is `done`.
- Terminal states: `done`, `failed`, `cancelled`. Transitions out of terminal states are illegal and must raise.
- Every transition emits an event and is wrapped in a DB transaction.
- Guards: `max_depth` (default 4), `max_children_per_task` (default 8), `max_attempts` (default 3), per-task `token_budget`.

---

## 4. LLM layer (build this very carefully; it is the main risk on free tier)

### 4.1 Provider interface

```python
class LLMProvider(Protocol):
    async def chat(self, req: ChatRequest) -> ChatResponse: ...
# ChatRequest: model, messages, tools|None, response_format|None, temperature, max_tokens
# ChatResponse: text, tool_calls[], usage, finish_reason, raw_headers
```

Implementations: `GroqProvider` (OpenAI-compatible), `GenericOpenAICompatProvider`, `MockProvider` (scripted, deterministic, used in all tests). Leave a clearly marked stub for an Anthropic/other adapter.

### 4.2 Model tiers via config (never hardcode model IDs in code)

`config/models.yaml` example (**verify current Groq model IDs and limits in Groq's docs/console before filling in; they change**):

```yaml
default_provider: groq
providers:
  groq:
    base_url: https://api.groq.com/openai/v1
    api_key_env: GROQ_API_KEY
tiers:
  fast:    { provider: groq, model: "<small fast model, e.g. llama-3.1-8b-instant>", fallbacks: [] }
  smart:   { provider: groq, model: "<large model, e.g. llama-3.3-70b-versatile>",  fallbacks: ["<other large model>"] }
  premium: { provider: groq, model: "<same as smart for now>", fallbacks: [] }   # later: swap to a stronger provider
limits:   # per model; fill from Groq rate-limit docs
  "<model-id>": { rpm: 30, tpm: 6000, rpd: 1000, tpd: 100000 }
```

Role-to-tier mapping lives in `org.yaml` (e.g., CEO/CTO/reviewers = `smart`; associates/support = `fast` initially). The owner can later edit one file to move everything to stronger models.

### 4.3 Rate limiting and resilience (required)

- **Central limiter** per model: token-bucket for RPM and TPM, plus daily counters (RPD/TPD) persisted in DB so restarts don't reset them.
- Read provider response headers (`retry-after`, `x-ratelimit-*`) and adapt.
- On `429`/`5xx`/timeouts: exponential backoff with jitter, honoring `retry-after`; after N tries, **fall back** down the tier's `fallbacks` list; if all exhausted, **park** the task as `blocked(reason=rate_limited)` with an automatic resume time, never fail the task for rate limits.
- When the daily quota is exhausted: pause scheduler, emit `system.quota_exhausted`, show in UI, resume automatically at reset.
- Priority queue for LLM calls: higher-rank agents and review steps first; cap global concurrency (config, default 2 for free tier).
- Log every call to `llm_calls`. Provide a usage endpoint and UI meter ("payroll").

### 4.4 Structured output

- All orchestration outputs (plans, delegation, reviews) are validated against Pydantic schemas.
- Prefer native tool/function calling when the model supports it; otherwise JSON mode with schema in prompt.
- On validation failure: **one repair call** that includes the validation error; on second failure, count as a failed attempt (do not crash).
- Strip/handle code fences, trailing text, and partial JSON defensively. Unit-test with malformed samples.

---

## 5. Agent runtime

### 5.1 An agent turn
1. Build **task packet** (see 5.2).
2. Run a bounded **tool loop** (default max 8 steps): call LLM -> execute tool calls -> append results -> repeat until the agent calls a terminal tool (`submit_deliverable`, `delegate`, `review_decision`, `request_help`, `report_blocked`).
3. Persist outputs, emit events, update token usage.
4. Enforce step cap, token budget, and wall-clock timeout; on breach, force a wrap-up call asking for best-effort output.

### 5.2 Context building (prevents "telephone game" loss)
Every task packet contains:
- **Company charter** (short, shared) + **role prompt** + **tool descriptions**
- **Original goal** (verbatim from user, always included, at every depth)
- The task's title, description, **acceptance criteria**
- **Ancestor chain**: titles + one-line intents only
- **Dependency outputs**: summaries (with artifact refs to read full content on demand via `read_file`)
- **Relevant wiki notes** (keyword search)
- **Previous attempts' review notes** if this is a revision
- Hard token cap with truncation order defined; a `summarize()` helper (fast tier) compresses long material.

### 5.3 Tools (registry; permissions per role in `org.yaml`)

| Tool | Who | Notes |
|---|---|---|
| `delegate(subtasks[])` | CEO, execs, managers, leads | Creates child tasks with assignee role, acceptance criteria, depends_on. Validates caps. |
| `submit_deliverable(summary, artifact_ids[])` | everyone doing work | Moves task to `in_review` |
| `review_decision(decision, notes)` | reviewers | `approve` / `revise` (notes required) / `escalate` |
| `request_help(role_or_service, question)` | all | Creates a small support task (QA, researcher, librarian, editor) |
| `report_blocked(reason)` | all | Moves to `blocked`, notifies manager |
| `web_search(query)` | research, marketing, others | Free provider (e.g., DuckDuckGo lib) behind an interface; optional Tavily/Brave key later |
| `fetch_url(url)` | same | Text extraction, size cap, timeout, SSRF guard (block private IPs) |
| `write_file / read_file / list_files` | all | Scoped to the project workspace; **path traversal prevented** |
| `run_code(language, code)` | engineering, data, QA | Sandbox (see 5.4) |
| `wiki_search / wiki_write` | all | Shared knowledge |
| `create_artifact(kind, title, content)` | all | Registers deliverable files with versions |

Tools return structured results and **never raise into the loop**; errors are returned as tool results the agent can react to.

### 5.4 Code execution sandbox (v1)
- Subprocess in the project's workspace dir, with timeout, output size cap, memory/CPU limits where the OS supports them, **no network by default**, a scrubbed environment (no API keys), and an allowlist of interpreters (python, node).
- Abstract behind `Sandbox` interface so Docker isolation can be added later without touching callers. Document the limits honestly in README.

### 5.5 Safety/approval gates
Configurable in `settings.yaml` (all default **on**): require approval for (a) any tool with external side effects (none in v1 but plumb the check), (b) hiring beyond N dynamic agents, (c) marking a **freelance project** "client-ready" (final human review before delivery). Approvals appear in the UI and block only the affected branch.

---

## 6. Orchestrator

### 6.1 Triage (the CEO's first step)
CEO receives the user task and outputs a validated `TriagePlan`:
```
complexity: trivial | standard | complex
objectives: [{ title, department, acceptance_criteria[], depends_on[], notes }]
```
- **trivial** -> skip layers: CEO routes straight to the right dept head or a single associate (don't burn calls).
- **standard/complex** -> full cascade.
- **Unknown/unmatched work** -> CEO asks the **HR/Recruiter** (support) to draft a role spec; CEO approves; a **dynamic agent** is created under the "Special Projects" department. **No task is ever rejected as out-of-scope.**

### 6.2 Delegation
Managers/leads convert objectives into tickets (DAG supported via `depends_on`). Cycle detection on insert (reject and ask the agent to fix). Assignees are chosen by role key, with load balancing across agents of the same role.

### 6.3 Execution scheduler
- Async worker pool; concurrency capped by limiter config.
- Picks **ready** tasks; prefers finishing in-flight branches (depth-first bias), then priority, then age.
- **Crash-safe**: on startup, tasks stuck `in_progress` with no live worker are re-queued (attempt not incremented unless the last call completed).
- Idempotency: each turn has a `turn_id`; repeated writes with the same id are ignored.

### 6.4 Review loops
- Reviewer = assignee's `reports_to` agent (configurable per role). Support QA can be added as a second reviewer for engineering/design deliverables.
- `revise` returns the task to `in_progress` with notes injected into context; `max_revisions` (default 2) then **escalate** to the next level up, who either accepts-with-flag or reassigns.
- Reviews must cite acceptance criteria one by one (schema-enforced) to avoid rubber-stamping.

### 6.5 Integration (bottom-up synthesis)
When all children are `done`, the parent owner runs an **integration turn** that reads children deliverables, resolves conflicts, produces one consolidated deliverable, and submits it up. The CEO's integration produces the **final project deliverable** and a short executive summary.

### 6.6 Guardrails against runaway behavior
- Global and per-task token budgets; depth, fan-out, attempts, and wall-clock caps.
- Loop detector: identical consecutive tool calls or near-duplicate delegations -> force a wrap-up/escalation.
- Cancel/pause/resume controls on any task subtree, honored at the next safe point.

---

## 7. Organization (`config/org.yaml`)

Define every role with: `key, title, department, level, reports_to, tier, tools, prompt, count`. Ship this default org (editable):

- **Executive:** CEO, COO (ops/coordination, intake & scheduling)
- **Engineering/IT (CTO):** Eng Manager; Leads: Frontend, Backend, DevOps/Data; Associates: Frontend Dev, Backend Dev, DevOps Engineer, Data Engineer; QA Engineer
- **Design (Head of Design):** Design Manager; Leads: UI/UX, Brand/Visual; Associates: UI Designer, Graphic/SVG Designer, Copy-for-UI Writer
- **Marketing (CMO):** Marketing Manager; Leads: Content, Growth/SEO; Associates: Copywriter, Social Media, SEO Analyst
- **Content & Creative:** Editor-in-Chief; Associates: Technical Writer, Creative Writer, Script/Video Writer
- **Research & Analytics:** Research Lead; Associates: Market Researcher, Data Analyst
- **Operations/Project Management (COO):** Project Manager; Associates: Project Coordinator, Admin Assistant
- **Finance & Admin (CFO):** Finance Manager; Associates: Proposal/Quote Writer, Invoice Drafter, Contract Reviewer (always labeled "not legal advice")
- **Support / Shared Services (report to COO):** QA Reviewer, Librarian (wiki), On-demand Researcher, Proofreader, **HR/Recruiter** (creates new roles)
- **Special Projects:** empty by default; filled by dynamic hires

Role prompts must state: role purpose, authority limits (what they may delegate/approve), output standards, escalation rules, and tone. Include a shared charter: "Be concise; produce concrete deliverables; never fabricate sources; flag uncertainty; write artifacts to the workspace."

Org must be **hot-editable** at runtime (hire, retire, rename, edit prompt, change tier) via API and UI, and persisted to DB (YAML is the seed).

---

## 8. API (REST + WebSocket)

```
POST   /api/projects                    create project (name, client, brief, due)
GET    /api/projects, /api/projects/{id}
POST   /api/projects/{id}/tasks         user submits a task -> assigned to CEO
GET    /api/projects/{id}/tree          full task tree with statuses
POST   /api/tasks/{id}/cancel | pause | resume | retry
GET    /api/tasks/{id}                  detail + messages + reviews
GET    /api/agents, /api/agents/{id}
POST   /api/agents                      hire (dynamic or from template)
PATCH  /api/agents/{id}                 edit prompt/tier/tools/department
DELETE /api/agents/{id}                 retire (soft)
GET    /api/artifacts/{id}              metadata + content; /download; project export as .zip
GET    /api/approvals ; POST /api/approvals/{id}/decide
GET    /api/usage                       tokens, calls, quota status per model
GET    /api/events?after=<id>           catch-up
WS     /ws                              live events; client sends last_event_id to resume
```
Standard error envelope, request validation, pagination where lists can grow, OpenAPI docs enabled. Generate the TS client types from the OpenAPI schema.

### Event types (the contract between engine and UI; document in `docs/events.md`)
`task.created, task.assigned, task.started, task.delegated, task.submitted, task.review_requested, task.revision_requested, task.approved, task.blocked, task.failed, task.done, agent.thinking, agent.tool_call, agent.tool_result, agent.message, agent.hired, agent.retired, artifact.created, approval.requested, approval.decided, system.rate_limited, system.quota_exhausted, system.resumed, project.completed`

Events are **persisted before broadcast**. The UI can rebuild any state by replaying events (also powers a **Replay/Time-lapse** feature).

---

## 9. Frontend

### 9.1 App shell
Three regions: **Office canvas** (center), **Left sidebar** (projects + task input + CEO chat), **Right drawer** (context panels). Bottom bar: **usage/"payroll" meter**, quota status, pause-all.

Panels: Task Tree (collapsible, status colors), Kanban (by status), Agent Inspector (current task, recent messages/tool calls, edit prompt/tier, retire), Artifacts viewer (markdown/code/SVG preview, version list, download, project zip), Approvals inbox, Org Editor (hire/edit), Event Log (filterable), Replay controls.

### 9.2 Pixel office (Phaser 3)
- **Layout engine generates the building from `org.yaml`/DB**: each department is a room; each agent gets a desk; adding an agent auto-adds a desk. Suggested floors: Executive suite (top), Engineering + Design, Marketing + Content + Research + Finance, Ground floor with **Lobby/Intake desk (where the user's task "enters")**, Support wing, HR, break room.
- **Phase 1 art is procedural**: generate tiles/furniture/characters with code (16x16 palette-based sprites; role-colored outfits, level-based accessories like a tie for managers, crown-ish badge for CEO). Keep an `AssetPack` interface so an artist's spritesheet can replace it later with zero logic changes.
- Camera: pan, zoom, click floor to focus; minimap optional.
- **Agent FSM** (driven only by events): `idle, walking, working (typing), thinking (dots bubble), in_meeting, reviewing, blocked (!), celebrating (done), break`.
- Event -> animation examples: `task.delegated` = delegator walks to assignee's desk and a "paper" sprite is handed over; `task.review_requested` = assignee walks to reviewer; `agent.thinking` = bubble; `task.blocked` = red "!"; idle > N sec = coffee break; project completed = confetti.
- Pathfinding via EasyStar on a collision grid; agents never walk through walls; movement queued so animations never contradict state.
- Click agent -> Inspector. Hover -> tooltip (role, current task, status). Speech bubbles show **short summaries**, never raw LLM dumps.
- Performance target: 60 fps with 60 agents; animations pause when the tab is hidden.
- **The canvas must never be the source of truth**; it only renders state derived from the event stream.

### 9.3 Robustness
WS auto-reconnect with `last_event_id` resume; optimistic UI only for commands, never for state; error boundaries; loading/empty states for every panel.

---

## 10. Freelance/project features (build in Phase 9)
- Project **brief intake**: client name, requirements, deadline, constraints, reference links/files.
- **Deliverables bundle**: per-project export zip with README summarizing what was produced and by whom.
- **Proposal/quote** and **invoice draft** flows via Finance team (templated artifacts; no real sending).
- **Client-ready gate**: final human approval before a project is marked delivered.
- **Revision rounds**: user feedback on a delivered project creates a follow-up task tree under the same project with prior context linked.
- **Reusable playbooks**: save a successful task tree as a template ("Landing page", "Brand kit", "Blog series") that the CEO can reuse for triage.

---

## 11. Configuration, secrets, observability

- `.env` for secrets (`GROQ_API_KEY`, optional search keys). Never log keys. Provide `.env.example`.
- Structured JSON logging with `task_id/agent_id` correlation; log level configurable.
- `/api/health` and `/api/ready`.
- DB backups: a simple `make backup` copying the SQLite file + workspaces.
- `settings.yaml` holds: `max_depth, max_children, max_attempts, max_revisions, tool_step_cap, task_token_budget, global_concurrency, approval_gates, wip_limit_per_agent`.

---

## 12. Testing strategy (required, not optional)

1. **Unit**: state machine (all legal/illegal transitions), DAG cycle detection, limiter math, context builder truncation, schema repair logic, path-traversal guard, SSRF guard, sandbox limits.
2. **Mock-LLM integration** (`MockProvider` with scripted responses): full golden path "Build a landing page" -> CEO triage -> delegation across Design + Engineering + Marketing -> reviews (including one `revise` loop) -> integration -> final deliverable. Assert tree shape, event sequence, artifacts, token accounting.
3. **Fault injection**: simulated 429s, timeouts, malformed JSON, tool exceptions, **process kill mid-task then restart resumes correctly**.
4. **Guardrails**: runaway delegation, infinite revise loop, budget exhaustion, cancellation of a subtree.
5. **API tests** with httpx; **WS test** for resume with `last_event_id`.
6. **Frontend**: vitest for stores/event reducers and the agent FSM; one Playwright e2e that submits a task against the mock backend and sees the tree complete.
7. **Smoke test with real Groq** (manual, behind `make smoke`) using a tiny task; document observed rate-limit behavior in `DECISIONS.md`.

CI-style command `make test` must pass with **no network and no API key**.

---

## 13. Phased delivery plan (with acceptance criteria)

**Phase 0 — Scaffold.** Monorepo, tooling, Makefile, lint/type/test wiring, config loader, `.env.example`.
*Accept:* `make lint test` passes on an empty-but-wired project; `make dev` boots backend + frontend.

**Phase 1 — Domain, DB, events.** Models, migrations, task state machine, event bus + persistence, org seeding from YAML.
*Accept:* unit tests for all transitions; events persisted and queryable; org seeded into DB.

**Phase 2 — LLM layer.** Provider interface, Groq adapter, Mock provider, limiter with persisted daily counters, backoff/fallback, structured-output validation/repair, `llm_calls` logging.
*Accept:* fault-injection tests pass; limiter never exceeds configured RPM/TPM in a simulated burst.

**Phase 3 — Agent runtime & tools.** Context builder, tool registry, tool loop, sandbox, workspace, wiki.
*Accept:* a single agent can complete a task end-to-end with mock LLM, using tools, producing an artifact; budget/step caps enforced.

**Phase 4 — Orchestrator.** Triage, delegation with DAG, scheduler, review loops, integration, guardrails, crash-resume, dynamic hiring via HR.
*Accept:* golden-path mock test passes; kill-and-restart test passes; runaway tests are contained.

**Phase 5 — API + WebSocket.** All endpoints, OpenAPI, WS resume.
*Accept:* API/WS tests pass; a task submitted via API completes and streams events in order.

**Phase 6 — Frontend shell (no office yet).** Panels, stores, WS client, task input, tree, kanban, inspector, artifacts, approvals, usage meter.
*Accept:* with the mock backend, a user can run a task and watch it complete using panels only.

**Phase 7 — Pixel office.** Layout generator, procedural art, agent FSM, pathfinding, event-driven animations, camera, tooltips.
*Accept:* every event type maps to a visible behavior; 60 agents at stable fps; reconnect doesn't desync the scene.

**Phase 8 — Org management.** Hire/retire/edit prompt/tier in UI, hot reload, HR dynamic-hire flow, desk auto-creation.
*Accept:* hiring in UI makes a new agent appear at a new desk and receive work.

**Phase 9 — Freelance features.** Brief intake, export zip, proposal/invoice flows, client-ready gate, revision rounds, playbooks, replay mode.
*Accept:* run a sample freelance project from brief to approved export bundle.

**Phase 10 — Hardening & docs.** Real-Groq smoke test, tune concurrency/limits, README (setup, architecture diagram, how to change models), `docs/events.md`, `docs/org.md`, `docs/upgrading-models.md`.
*Accept:* fresh clone -> working app following README in under 10 minutes; changing `models.yaml` alone switches providers/models.

---

## 14. Working rules for the coding agent

1. Work phase by phase; **commit at the end of each phase** with a clear message, and keep `main` green.
2. Write tests alongside code. Do not mark a phase done until its acceptance criteria pass.
3. Log every non-obvious decision, assumption, and known limitation in `DECISIONS.md`.
4. Prefer simple, readable code; core domain logic must be pure and typed.
5. Never hardcode model IDs, API keys, or rate limits; always read from config/env.
6. If a requirement is ambiguous, choose the simplest reasonable option, record it in `DECISIONS.md`, and continue. Ask the owner only when truly blocked.
7. Do not add features outside this document without recording why.
8. Verify external facts (Groq model names/limits, library APIs) against current docs rather than memory.

---

## 15. Definition of done (v1)

- A user can create a project, submit any kind of task, and watch the pixel office carry it from CEO to associates and back, with reviews and integration, ending in a downloadable deliverable.
- The system survives rate limits, malformed model output, and restarts without losing work.
- The org is editable at runtime and can create new roles for unusual tasks.
- Swapping to stronger models requires editing config only.
- `make test` passes offline; README lets a new developer run it quickly.
