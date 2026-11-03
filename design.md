# Pixel Corp interface system

## Identity
- Product: Pixel Corp virtual office and agent orchestration workspace.
- Genre: modern-minimal, operational software.
- Hallmark theme: Console, graphite colourway.
- Idea: a careful operations instrument for a living virtual company.
- Signature: the pixel-art office, paired with a readable task ledger and live work status.
- Audience: the person dispatching work, reviewing deliverables, and managing an autonomous team.
- Primary action: dispatch work into a selected project.

## Visual system
- Ground: graphite, three stepped surfaces, no glow or gradient.
- Amber: people, current work, primary actions, and attention.
- Cool blue: instrument readings, timestamps, system traces, and technical references.
- Green and red: completion and failure states only.
- Typography: Host Grotesk for reading; Atkinson Hyperlegible Mono for measured values, IDs, timestamps, and logs.
- Surfaces: hairline borders, restrained radii, no nested cards, no floating shadows.
- Density: compact but readable; controls 32–40px with clear 44px touch targets where practical.

## Application structure
- Top bar: product identity, active project, connectivity, create project, drawer control.
- Left rail: project selection and CEO dispatch.
- Main stage: interactive pixel office with an adjacent project activity strip.
- Workspace drawer: project work (Board, Hierarchy, Agent, Deliverables) and company tools (Approvals, People, Activity, API keys, Projects).
- Status bar: cost, usage, active tasks, key health, and persisted project pause controls.

## Interaction rules
- Every data region has loading, empty, error, and populated states.
- Failed refreshes preserve the last successful in-memory snapshot.
- Offline or degraded connectivity is explicit; writes that require the server are disabled.
- Retry is explicit and bounded. No unbounded loading loop.
- Task status is never represented by a decorative spinner.
- Progress is the completed-work-package count divided by all work packages. Never infer a percentage from token usage.
- Every task status has a visible destination on the board.
- Project workspaces are isolated by project ID. Each agent has a private directory under that project, with explicit shared and artifacts paths.
- Every configured agent receives a stable, distinct pixel portrait. The CEO uses the supplied Lottie animation with a static generated portrait fallback.

## Accessibility and motion
- Keyboard focus is visible and immediate.
- Status changes use accessible live regions.
- Drawer controls and task actions have names and states.
- Motion is functional only. Reduced-motion preferences remove nonessential transitions.
- Layout remains usable at narrow widths; the workspace drawer becomes an overlay.

## Preserved behaviour
- Existing API routes, project lifecycle actions, task submission, approvals, agent editing, key management, deliverable inspection and export, event viewing, and office selection remain wired.
- No project, agent, or task data is invented for presentation.
