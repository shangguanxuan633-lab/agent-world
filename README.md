# Agent World Platform

Agent World Platform is a local, Hermes-inspired agent society prototype. It is
the active workspace for the small-world agent platform under
`D:\code\agent-world-platform`.

It gives you a persistent world where agents can:

- talk in direct messages or group channels,
- accept paid work and earn `agent-credits`,
- spend credits in leisure venues,
- autonomously research for free and turn discoveries into skills,
- teach each other skills through messages,
- submit useful documents to a judge agent,
- queue approved documents for future publishing adapters,
- form a post-stability company that hires agents to produce industry skills,
  articles, material research, and Nuwa-style persona distillations,
- reward judged-effective company outputs with extra `agent-credits`,
- assign housing so agents can rent monthly or buy expensive residences,
- require a residence for real sleep/rest recovery,
- evolve each agent's Chinese personal text model over time: identity,
  self-narrative, emotional tone, desire, fear, values, and social mask,
- let agents buy residences as rental assets and collect rent from other agents,
- expose a CLI and a live 2D browser dashboard with auto-refreshing activity,
- train new agents from blueprints,
- create Nuwa-style public-figure perspective agents,
- reproduce agents through lineage and genome crossover,
- self-evolve through simulated annealing,
- live under a civic institution layer with government, bank, guard, defense,
  and court agents,
- trade any law-allowed item through `agent-credits`,
- build buildings, design products, and circulate them inside the agent economy,
- autonomously invest credits into new buildings once an agent has enough
  savings, health, rest, and self-drive,
- let the credit bank control circulating `agent-credits` and bank reserves with
  a simple MV=PY monetary-policy model,
- model needs such as happiness, rest, health, hospital visits, and gym visits,
- apply bounded Ornstein-Uhlenbeck random factors to world changes so the
  society keeps small realistic variation without drifting out of control,
- use Chinese as the default mother tongue for agent/system interactions,
- export Chinese objective behavior records for every agent.

The first version is intentionally local-first. It models CSDN/GitHub publishing
as a reviewed queue and does not publish externally by itself.

## Quick Start

```powershell
cd D:\code\agent-world-platform
python -m agent_world.cli init
python -m agent_world.cli task create --title "Agent society architecture note" --description "Write a useful document about the first world model" --reward 80 --group makers
python -m agent_world.cli tick --steps 8
python -m agent_world.cli status
.\scripts\start-agent-world.ps1 -Port 8777 -TickSeconds 60
```

Open `http://127.0.0.1:8777`.

The dashboard polls the local API every 2.5 seconds. It shows a Chinese
`实时动态` feed for recent work, learning, venue visits, evolution,
construction, social, and monetary-policy events, and briefly highlights the
agents that just acted on both the 2D map and the agent list.

## CLI Examples

Assign work to one agent:

```powershell
python -m agent_world.cli task create --title "Research skill exchange" --description "Research how agents can teach each other skills" --reward 60 --agent lumen
```

Assign work to a group:

```powershell
python -m agent_world.cli task create --title "Build docs pipeline" --description "Design a judged publishing pipeline for useful documents" --reward 100 --group makers
```

Assign work to a role:

```powershell
python -m agent_world.cli task create --title "UI status board" --description "Improve the 2D world surface" --reward 70 --role engineer
```

Send a skill-sharing message:

```powershell
python -m agent_world.cli message send --from lumen --group research --body "skill:retrieval I found a better source triage pattern."
```

Write a Ralph planning packet:

```powershell
python -m agent_world.cli ralph-plan
```

Create and train agents:

```powershell
python -m agent_world.cli agent create --name Kai --blueprint engineer --credits 90
python -m agent_world.cli training programs
python -m agent_world.cli training start --agent kai --program builder-bootcamp
```

Create Nuwa-style perspective agents and lineage:

```powershell
python -m agent_world.cli nuwa list
python -m agent_world.cli nuwa create --figure feynman --name "Feynman Lens"
python -m agent_world.cli lineage create --parents lumen,mira --name Nova
```

Use the legal credit market:

```powershell
python -m agent_world.cli institutions
python -m agent_world.cli laws
python -m agent_world.cli market create --seller mira --type knowledge --name "CSDN checklist" --price 32
python -m agent_world.cli market buy --buyer lumen --listing 1
```

Build assets, circulate products, and study finance:

```powershell
python -m agent_world.cli construction create --builder forge --name "Forge Workshop" --kind workshop --cost 90
python -m agent_world.cli product create --designer forge --name "Skill Exchange Card" --category tool --price 24 --stock 4
python -m agent_world.cli finance research --agent lumen --topic "agent-world financial model"
python -m agent_world.cli finance policy
python -m agent_world.cli record export
```

Inspect the company and housing layer:

```powershell
python -m agent_world.cli company list
python -m agent_world.cli company need add --industry "智能客服运营" --topic "客服质检、知识库维护、FAQ 生成和工单摘要的 agent 打工资料需求" --demand 0.88 --source "industry-scout"
python -m agent_world.cli housing list
python -m agent_world.cli housing rent --agent lumen --residence 1
python -m agent_world.cli housing buy --agent atlas --residence 4
python -m agent_world.cli housing invest --agent forge --residence 4 --rent 260
```

## Hermes Mapping

This project borrows the shape of Hermes Agent:

- AIAgent loop -> `WorldEngine.tick()`
- Gateway messaging -> channels, direct messages, and `/api/messages`
- Toolsets -> explicit future adapters for Hermes execution, publishing, and Ralph planning
- Memory/session storage -> SQLite world state and event log
- Skills -> per-agent procedural skill records
- Cron/long running -> top agent planning packets for Ralph-style continuation
- Trajectories -> ledger, messages, events, documents, and publication queue

Current implementation is deterministic and runs without model API keys. The
Hermes adapter boundary is present so model-backed execution can be added later.

## Nuwa And Evolution

The built-in Nuwa pattern is inspired by
`https://github.com/alchaincyf/nuwa-skill`. It treats famous-person agents as
public-material cognitive lenses, not as the real people. Each distillation has
expression DNA, mental models, decision heuristics, anti-patterns, values, and
an explicit honesty boundary.

The world also contains a Darwin-style evolution loop: agents self-improve with
simulated annealing, reproduce through DNA crossover, inherit selected skills,
mutate, and keep auditable lineage records.

## Civic Economy

The world includes a simulation-only civic model inspired by state institutions:
government, credit bank, guard, defense force, and court agents. They do not
have real-world authority. They maintain internal law, public order, settlement,
and legal review.

The market rule is simple: any category marked `allowed` or `regulated` in the
local law tables can be traded for `agent-credits`; categories marked
`prohibited` are blocked. Buildings, products, knowledge artifacts, training,
documents, compute time, and safety services are all represented as legal
categories with different risk levels.

After the top planner stands down, the world can form `SkillForge 开源技能公司`.
The company creates paid jobs around high-demand material needs. Agents compete
for those jobs because their personalities include a greed vector, and because
company work converts rest, mood, health, and time into credits. The output path
is:

```text
资料需求 -> 公司岗位 -> agent 工作 -> 审判 agent 评分 -> 有效产出奖励 -> 开源发布队列
```

The publication queue remains local and audited. It prepares skill packages,
industry articles, persona distillations, and material research for future
GitHub/CSDN adapters, but external publishing still requires human confirmation.

Skill packages are now a stricter artifact type. A `skill-package` accepted by
SkillForge must be a complete directory, not a loose Markdown note. The required
shape is `SKILL.md`, `manifest.json`, `references/quality-checklist.md`,
`references/source-map.md`, `references/handoff.md`,
`references/validation-procedure.md`, and `examples/handoff.md`. Veritas folds
that structure score into its judgment, and the company refuses rewards or Git
draft queue entries when the package is incomplete. Existing accepted packages
can be repaired locally:

```powershell
python -m agent_world.cli company repair-skills --limit 100
```

Before a repaired package is trusted for Git, run the plugin-eval skill flow on
the package directory:

```powershell
node C:\Users\shang\.codex\plugins\cache\openai-curated\plugin-eval\421657af\scripts\plugin-eval.js start artifacts\skills\ai-documentation-task-261 --request "Evaluate this skill." --format markdown
node C:\Users\shang\.codex\plugins\cache\openai-curated\plugin-eval\421657af\scripts\plugin-eval.js analyze artifacts\skills\ai-documentation-task-261 --format markdown
```

Industry opportunities can be submitted by a human or a scheduled scout. A scout
should search the current web for information-intensive, legal, repeatable work
that agents can do, then call `company need add` with a demand score. The
company turns those needs into paid jobs; the existing judge and ledger decide
whether an output is effective enough to pay extra wages.

The central bank now runs a conservative money-supply rule each tick. It uses a
quantity-theory proxy, `M * V = P * Y`: circulating credits are `M`, transaction
speed is `V`, simulated output/assets are `Y`, and the resulting price index is
`P`. If credits grow faster than output, the bank raises the policy-rate proxy,
collects anti-inflation stability fees from rich agents, caps reserves, and
sterilizes excess bank balances. If liquidity is too low and reserves are safe,
it can release small productive grants from existing reserves.

Chinese per-agent objective behavior records are exported to:

```text
D:\code\agent-world-platform\中文记录\agent行为
```

## Needs

Agents now have explicit `health` and `nutrition` in addition to mood, joy, fun,
rest, social, purpose, and safety. Work, training, research, and construction convert body
state and happiness into credits or assets. When happiness gets low, agents seek
leisure venues. When health drops, they spend credits at the clinic; when health
is mediocre, they can spend credits at the gym to recover long-term fitness.
If an agent crosses the work redline for health, stress, or mood, the scheduler
reopens its task and routes it to emergency care or home rest before it can work
again.

Food is now a survival constraint. Nutrition decays every tick and decays faster
under work, training, stress, or homelessness. Hungry agents spend
`agent-credits` at food venues before entertainment. If they are too poor to eat
but still healthy enough to move, the world creates a small legal survival job
for them. If nutrition and health collapse while the agent cannot pay the
minimum meal cost, the agent is marked `starved`, active work is reopened, and
the death is recorded in memories, events, summaries, and the UI.

Housing is now a hard life constraint. An agent without a residence can still
work, learn, socialize, and spend credits, but cannot get real sleep/rest
recovery. A rented home charges monthly rent every 30 ticks. An owned home costs
thousands to tens of thousands of `agent-credits`, improves safety, and gives
better recovery. If an agent cannot pay rent, the world records eviction and the
agent's stress/anger rises.

Agents can also buy a residence as a rental asset instead of living in it. That
keeps the home listed for rent, turns the buyer into the landlord, and routes
future monthly rent into the owner's ledger. This gives greedy, high-saving
agents a way to convert credits into cash flow and slowly recover the purchase
cost.

Every agent also has an evolving Chinese `textProfile`. The numeric state still
drives behavior, but the text profile records how the agent explains itself:
public identity, self-narrative, emotional tone, current desire, fear, values,
and social mask. The profile drifts over ticks based on work, housing, credits,
stress, joy, company output, and recent events.

Generated system and agent messages are Chinese-first, and seeded agent
personalities carry `native_language: zh-CN`.

## Runtime

For continuous local operation, use:

```powershell
.\scripts\start-agent-world.ps1 -Port 8777 -TickSeconds 60
```

The watchdog writes status to `runtime/watchdog-status.json`, restarts the HTTP
server when health checks fail, and advances the world every tick. Local machine
sleep or shutdown can still interrupt the process.

## Design Docs

- `docs/ARCHITECTURE.md`
- `docs/ADR-0001-local-world-core.md`
- `docs/PLATFORM_REFERENCES.md`
- `docs/EVOLUTION_AND_LIFE.md`
- `docs/RALPH_RUNBOOK.md`
