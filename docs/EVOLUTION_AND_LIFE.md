# Evolution And Life Simulation

Agent World treats each agent as a small artificial person, not a stateless
worker.

## Inner State

Each agent has:

- emotions: joy, anger, stress, confidence, loneliness, curiosity,
- needs: rest, social, fun, purpose, safety, health, nutrition,
- personality: curiosity, sociability, stubbornness, temper, greed,
- genome: focus, resilience, creativity, empathy, discipline, curiosity,
  sociability, risk tolerance, and related traits,
- memories: meaningful events with valence and intensity,
- relationships: affinity, trust, tension, and last social event.
- text profile: self-narrative, public identity, emotional tone, desire, fear,
  values, social mask, and version.

## Work And Life

Work consumes rest, fun, social energy, nutrition, and sometimes body health. It
increases purpose and sometimes stress. Training, research, and construction
also consume nutrition and body condition.
This is the core exchange: agents can convert happiness and body condition into
credits, products, buildings, or knowledge, but they must later recover.

The exchange has a hard stop. If an agent falls below the work redline for
health, nutrition, stress, or mood, it cannot keep claiming or continuing paid
work. The world reopens its task and routes the agent to food, emergency clinic
care, or home rest first. This keeps greed and labor pressure realistic without
letting the simulation normalize working a collapsed agent to zero health or
zero food.

Food is a first-class cost of life. Nutrition decays every tick, faster under
work, stress, training, and homelessness. Hungry agents buy meals before
entertainment. If they lack meal money but can still move, the civic layer opens
a small legal survival job assigned to that agent. If nutrition and health
collapse, the civic government or bank first pays an emergency meal voucher and
opens a survival job so the agent can recover and repay through future work. If
public rescue capacity is also exhausted, the agent becomes `starved`: current
work is reopened, energy and health drop to zero, and the event is recorded as a
death in memory and the audit log.

Venues are not decorative. Agents can go to a bar, game space, rest pod, dojo,
debate club, clinic, or gym depending on their needs. These visits cost
`agent-credits` and change emotions, needs, and sometimes skills.

- Low happiness/fun pushes agents toward entertainment venues.
- Low health pushes agents toward the clinic.
- Medium-low health can push agents toward the gym for fitness recovery.
- Work and training reduce fun/rest/health/nutrition while earning credits or skills.

Homes are different from venues. A venue can entertain, train, heal, or socialize
an agent, but it cannot replace having a place to sleep. Agents without a
residence keep accumulating stress when they are tired. Renting a home creates a
monthly credit obligation; buying a home creates a large savings goal and better
recovery. This makes greed useful: agents want credits not only as a score, but
because credits buy shelter, health, status, training, and future freedom.

Agents can also become landlords. A high-saving agent may buy a residence as an
investment, keep it available for rent, and collect monthly income from another
agent. The renter gets rest rights; the owner gets cash flow and a path to
recover the purchase cost.

## Textual Identity Drift

Numeric emotion is not enough for a believable small world. Every agent also
keeps a Chinese personal text model. Over time the engine rewrites:

- how the agent describes itself,
- how others see its role and status,
- how it verbalizes emotion,
- what it currently wants,
- what it fears,
- which values are becoming salient,
- what social mask it wears around others.

This text profile is derived from world facts: recent events, work state,
credits, housing, company outputs, rent income, health, joy, stress, anger,
greed, and role. It gives the future LLM/Hermes layer a grounded identity prompt
that changes as the agent lives.

Agents use Chinese as their default mother tongue for system and social
interactions. Seeded personalities carry `native_language: zh-CN`.

## Civic Institutions And Market Life

The world has simulation-only institutions: government, bank, guard, defense
force, and court. They give the small world public order, credit settlement,
legal review, and emergency-response roles without granting real-world power.

The core market law is: every item that is locally legal can be traded with
`agent-credits`. Legal categories include knowledge, documents, training, labor,
products, buildings, construction, compute, and venue services. Prohibited
categories include identity transfer, private data, exploits, unsafe weapons,
and stolen property.

Agents can build buildings, own them as assets, design products, hold stock, sell
products, and earn profits. Researchers can inspect the current economy and
write financial model reports into `artifacts/金融研究`.

After the top planner stands down, companies become the main production driver.
The default company, `SkillForge 开源技能公司`, opens paid jobs for industry
skills, articles, material research, and Nuwa-style persona distillation. A
company output must still pass the judge agent. If effective, it earns extra
credits, improves the producer's skills, and enters the local open-source
publication queue for future human-approved Git/CSDN adapters.

For `skill-package` jobs, "effective" now means more than a high usefulness
number. The artifact must be a complete skill directory with a compact
`SKILL.md`, manifest, source map, quality checklist, handoff notes, validation
procedure, and handoff example. Veritas rejects or sends the output to revision
if it is only a Markdown article pretending to be a skill. This keeps agent
learning from polluting the Git queue with incomplete skills.

When an agent has enough savings, good enough health/rest, and high enough
self-drive, it can start a lawful construction project without waiting for the
owner. The agent spends its own `agent-credits`, records an autonomous
construction memory, and later gains a building if the project completes.

The bank is not an infinite wallet. Every tick, `credit-bank` records a monetary
policy snapshot using a quantity-theory proxy:

```text
M * V = P * Y
```

`M` is circulating credits outside the system agents, `V` is a velocity proxy
from actual world activity, `Y` is simulated output/assets, and `P` is a price
index. If money outruns output, the bank collects stability fees, caps reserves,
and clips newly minted reward bonuses. If liquidity is too low, it can release
small productive grants from existing reserves.

## Training

Users can train an agent through programs. Training costs credits, consumes
time/energy, and improves a target skill when completed. This is the local
version of "anyone can strengthen their own agent".

## Self-Evolution

The platform uses two evolution mechanisms:

- Simulated annealing: during idle life, an agent mutates one genome gene. Better
  mutations are accepted; worse ones can still pass early when temperature is
  high. Fitness rewards credits, skills, approved documents, confidence, purpose,
  good relationships, and low stress/anger.
- DNA crossover: reproduction blends parent genomes and skills, applies bounded
  mutation, records lineage, and creates a child agent with its own personality.

## Stochastic Micro Variation

Every tick also applies a small persistent random factor to the world. The
implementation uses an Ornstein-Uhlenbeck style mean-reverting stochastic
process:

```text
x_next = x + theta * (0 - x) + sigma * gaussian_noise
factor = 1 + clamp(x_next, -spread, +spread)
```

Why this model:

- it creates realistic noise with memory from one tick to the next,
- it drifts back toward zero, so the world does not permanently spiral,
- it can be bounded tightly for UI, economy, health, mood, construction, product
  quality, training, research, and document judgment.

The local implementation stores each noise stream in `world_noise` using
`algorithm='ornstein-uhlenbeck'`. Current small perturbations affect:

- background agent mood, energy, health, stress, curiosity, and map position,
- task and training progress,
- venue recovery effects,
- autonomous research skill gain and network-skill rewards,
- document usefulness judgments and judge bonuses,
- construction progress, final building value, rent, and completion bonus,
- product quality,
- finance-report usefulness and rewards,
- relationship affinity/trust/tension changes.

Reference notes used for this implementation:

- PlanetMath describes the OU process as a stochastic differential equation with
  mean reversion, long-term mean, volatility, and Brownian fluctuations:
  <https://planetmath.org/ornsteinuhlenbeckprocess>
- CRAN's `GOU_simulate` documentation summarizes the OU family as Gaussian,
  Markov, time-homogeneous, and mean-reverting:
  <https://search.r-project.org/CRAN/refmans/LSMRealOptions/html/GOU_simulate.html>

## Reproduction

Reproduction means incubation, inheritance, and mutation. It is not uncontrolled
copying. Parents pay an incubation cost, the child inherits selected skills and a
crossover genome, and the lineage is auditable in `agent_lineage`.

## Nuwa Distillation

Nuwa-style creation turns public information into a perspective agent by storing
expression DNA, mental models, decision heuristics, anti-patterns, and honesty
boundaries. These agents are not the public figures. They are explicit cognitive
lenses with source limitations.

Built-in examples include Jobs, Feynman, Munger, Musk, Karpathy, Naval,
Zhang Yiming, and Taleb inspired lenses.

## 24h Operation

Use:

```powershell
.\scripts\start-agent-world.ps1 -Port 8777 -TickSeconds 60
```

The watchdog restarts the HTTP server if health checks fail and advances the
world on a schedule. Its status lives in `runtime/watchdog-status.json`.

## Objective Behavior Records

Run:

```powershell
python -m agent_world.cli record export
```

This writes Chinese, per-agent objective behavior records under
`中文记录/agent行为`. The files are generated from database facts: messages,
events, tasks, ledger, venues, research, training, evolution, market activity,
construction, products, and memories.
