# ADR-0001: Start With A Local SQLite World Core

## Status

Accepted

## Context

The requested product is a full agent society: work, money, communication,
skills, entertainment, judgment, publishing, and long-term planning. Jumping
straight to distributed services would make the domain harder to evolve.

Hermes Agent already shows the useful runtime pattern: a durable agent loop,
tool registry, memory, skills, gateway messaging, cron, and trajectories.
This project should borrow those boundaries while keeping the first slice small
and inspectable.

## Decision

Build the first implementation as a local Python package with SQLite persistence,
a deterministic simulation loop, a CLI, and a small HTTP/2D UI.

Keep Hermes, Ralph, and publishing as explicit adapter boundaries.

## Alternatives

- Full service split: postponed until the domain stabilizes.
- Browser-only simulation: rejected because CLI automation and durable state are
  core requirements.
- Real Hermes execution immediately: postponed because local deterministic tests
  are needed before model-backed autonomy.

## Consequences

Easier:

- Fast local iteration.
- Simple backup and inspection.
- Deterministic tests.
- Clear future adapter seams.

Harder:

- Multi-user auth and horizontal scaling are future work.
- Real model work is represented by a stub until the Hermes adapter is expanded.

## Data And API Contracts

SQLite is the source of truth. Mutating API calls are narrow contracts:

- `POST /api/tasks`: creates one paid task with exactly one target.
- `POST /api/messages`: records one direct or group message.
- `POST /api/tick`: advances the deterministic world loop.
- `POST /api/ralph-plan`: writes a file-backed planning packet.

State changes are logged in `world_events`, credits are recorded in `ledger`,
and approved documents enter `publication_queue`. External adapters should treat
queue rows as contracts and update status idempotently.

## Reliability And Observability

The local database uses transactional writes and short-lived connections.
Failures at API boundaries return JSON errors. The first observability surface is
the event log plus the UI dashboard; future work should add metrics for tick
latency, task throughput, rejected documents, queue age, and Hermes adapter
failure rate.

## Performance And Operations

The owner operates this as a local tool. The runbook is:

1. Start with `python -m agent_world.server --port 8766`.
2. Inspect `python -m agent_world.cli status`.
3. Stop the Python process to pause the world.
4. Back up or restore `world.db` for rollback.

Scale limits are intentionally modest: tens of agents and thousands of events.
Pagination, indexes, and background workers are future work.

## Rollout

1. Ship local world core.
2. Add CLI and UI control surfaces.
3. Add Hermes execution behind budgets and approvals.
4. Add manual publishing adapters.
5. Add richer autonomy and evaluation.

## Verification

- Unit tests cover task completion, credit ledger, judging, publication queue,
  and peer skill learning.
- CLI can initialize, assign work, tick, and report status.
- Browser UI can load the same SQLite-backed state.
