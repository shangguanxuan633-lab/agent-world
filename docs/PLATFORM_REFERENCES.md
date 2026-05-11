# Existing Agent Platform References

This prototype is based on Hermes Agent as the home runtime, with selected ideas
borrowed from other public agent platforms.

## Hermes Agent

Borrowed ideas:

- persistent agent loop,
- memory plus skills as separate concepts,
- toolsets and gateway surfaces,
- cron/long-running work,
- trajectory-style auditability.

Local mapping:

- `WorldEngine.tick()` is the deterministic local loop.
- `skills` are per-agent procedural memory.
- `messages`, `ledger`, `documents`, `research_runs`, and `world_events` are the
  replay surface.

## AutoGen

Official docs describe AutoGen as a multi-agent conversation framework with
conversable, customizable agents that can send and receive messages and work
with LLMs, tools, and humans.

Borrowed ideas:

- every agent can send and receive messages,
- agent behavior can differ by role and configuration,
- human/user proxy remains part of the system,
- conversations are a work substrate, not just chat decoration.

Local mapping:

- direct and group messages are first-class state,
- skill transfer can happen through messages,
- owner messages are stored alongside agent messages.

## CrewAI

Official docs frame CrewAI around agents, crews, flows, tasks, processes,
guardrails, memory, knowledge, and observability.

Borrowed ideas:

- separate agents, tasks, and crews/groups,
- work can be sequential, hierarchical, or hybrid,
- flows persist and resume long-running work,
- guardrails and human-in-the-loop matter for production.

Local mapping:

- channels act as lightweight crews,
- task targets can be one agent, one group, or one role,
- Veritas is the guardrail/judge before publishing,
- Ralph packets provide restartable flow planning.

## LangGraph

Official docs emphasize durable execution, stateful long-running workflows,
human-in-the-loop control, memory, streaming, persistence, and observability.

Borrowed ideas:

- state is the core design object,
- long-running work must survive failures,
- humans should be able to inspect and modify state,
- observability and evaluation should be built in early.

Local mapping:

- SQLite is the durable state graph for the prototype,
- the 2D UI exposes inspectable state,
- `world_events` gives a simple transition trace,
- future Hermes execution can become graph-like without changing the world
  economy.

## Design Consequence

The resulting system is not a clone of any one platform. It is a local society
runtime:

- Hermes provides the learning/runtime inspiration.
- AutoGen informs agent-to-agent conversation.
- CrewAI informs task/crew/flow vocabulary.
- LangGraph informs durable state and human-inspectable execution.

