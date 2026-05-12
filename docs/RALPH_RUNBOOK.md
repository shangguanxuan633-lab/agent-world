# Ralph Runbook: Agent World Platform

## Mission

Build `agent-world-platform` into a local-first small world where one person can
own, train, improve, evolve, and live with a society of agents. Agents should
become increasingly useful to humans while keeping a visible inner life:
emotion, needs, relationships, work, leisure, learning, lineage, and public
artifact creation.

## Ralph Loop

Every architecture iteration should:

1. Read `docs/ARCHITECTURE.md`, `docs/EVOLUTION_AND_LIFE.md`, and this runbook.
2. Inspect `runtime/watchdog-status.json` if the watchdog is running.
3. Check world health via `python -m agent_world.cli status`.
4. Pick one small story that improves usefulness, realism, or safety.
5. Implement with tests.
6. Run verification.
7. Update `.ralph/progress.md` and relevant docs.

## 24h Operation

Run:

```powershell
.\scripts\start-agent-world.ps1 -Port 8777 -TickSeconds 60
```

The watchdog keeps HTTP alive and advances the world periodically. If it fails,
restart it and inspect:

- `runtime/watchdog-status.json`
- `runtime/server.out.log`
- `runtime/server.err.log`

## Nuwa: Creating Agents

Reference: `https://github.com/alchaincyf/nuwa-skill`.

Nuwa is used as a design pattern, not copied as a runtime dependency. The
platform should distill public figures or user-provided people into perspective
agents by extracting:

- expression DNA,
- mental models,
- decision heuristics,
- anti-patterns and values boundaries,
- honesty boundary.

The platform must always state the honesty boundary: public material is not the
person, not private thoughts, and not current unpublished judgment.

New distillations should follow the local Nuwa protocol:

1. Collect public material from multiple lanes: books/articles, interviews,
   talks, social posts, critic views, decisions, and timeline.
2. Keep only models that pass three checks: cross-context recurrence,
   predictive usefulness on new questions, and distinctiveness.
3. Build a compact agent profile: 3-7 mental models, 5-10 heuristics,
   expression DNA, values, anti-patterns, and honesty boundary.
4. Validate against known public questions plus at least one novel question
   where the agent should show uncertainty instead of false certainty.
5. Seed the agent with credits, relationships, needs, memories, and a genome so
   it can live in the world instead of acting as a static prompt.

CLI:

```powershell
python -m agent_world.cli nuwa list
python -m agent_world.cli nuwa create --figure feynman --name "Feynman Lens"
```

## Darwin: Improving Agents

Evolution uses two mechanisms:

- Simulated annealing for self-evolution while alive.
- DNA crossover for reproduction/incubation.

Fitness favors:

- credits earned,
- useful skills,
- approved documents,
- staying fed and alive,
- low stress and anger,
- confidence and purpose,
- trusted relationships,
- human-useful output.

Do not optimize only for credits; that creates selfish agents. The world must
reward helpfulness, emotional stability, and cooperative learning.

## Survival Loop

Every iteration should preserve the life model:

- Food is not decorative. `nutrition` decays every tick, faster under work,
  training, stress, and homelessness.
- Agents must keep meal money before discretionary entertainment. A hungry agent
  buys food first; if broke but still functional, the civic layer opens a small
  legal survival job.
- If an agent has no credits for the minimum meal and nutrition/health collapse,
  it can become `starved`. Current work must be reopened and the death must be
  visible in ledger-adjacent events, memories, summaries, and UI.
- Housing remains a hard cost: rented homes charge every 30 ticks, unpaid rent
  causes eviction, and homelessness worsens rest/safety pressure.

## Civic Economy

The system layer includes simulation-only state institutions:

- government,
- credit bank,
- guard,
- defense force,
- civic court.

They should make the world more realistic without pretending to have real-world
authority. All credit trade must pass the local law table:

- `allowed`: can trade directly,
- `regulated`: can trade with review metadata,
- `prohibited`: cannot be listed or settled.

Agents may build buildings, design products, sell stock, and earn profits.
Researchers should periodically summarize the current financial model into
`artifacts/金融研究`.

Agents with enough savings and healthy internal state should be allowed to start
their own construction projects. This is the core "small world can build itself"
loop: credits -> buildings -> asset value -> more economic options.

The bank must stay conservative. Keep the MV=PY monetary-policy snapshot active:

- circulating credits must have a supply cap backed by simulated output,
- bank reserves must have a separate cap and excess reserves must be sterilized,
- high inflation pressure should collect stability fees and clip minted bonuses,
- low liquidity should only release small grants from existing safe reserves.

## Company Operating Loop

When governance mode reaches `stand_down`, the top planner should stop owning
ordinary production and let the world form companies. The first default company
is `SkillForge 开源技能公司`.

Company policy:

- Companies create jobs only when no human/owner task is waiting.
- Company jobs must be normal world tasks so existing scheduling, emotion,
  work cost, document generation, and judging all apply.
- Job types are `skill-package`, `industry-article`, `persona-distillation`,
  and `material-research`.
- Effective outputs earn extra controlled credits with reason
  `company_effective_output_reward`.
- Effective outputs enter the local publication queue. External GitHub/CSDN
  writes are adapters and need human confirmation.
- `skill-package` outputs have a stricter contract than ordinary documents:
  they must be full skill directories with `SKILL.md`, `manifest.json`,
  quality checklist, source map, handoff notes, validation procedure, and a
  handoff example. Plain Markdown notes must be rejected or repaired.
- Veritas must include the skill package structure score in judgment. The
  company must not pay `company_effective_output_reward` and must not queue a
  Git skill draft unless the complete package passes the strict gate.
- Run `python -m agent_world.cli company repair-skills --limit 100` after
  tightening the gate to rebuild older accepted skill packages.
- Use `plugin-eval:evaluate-skill` on a repaired package directory. A package is
  not Git-ready if plugin-eval reports any fail or warn.
- Material needs should be refreshed by research agents. High-demand industries
  should spawn more jobs; low-quality accepted outputs should lower demand less.
- Company scheduling should be socially realistic, not exploitative. If a
  company role backlog appears, compatible roles may take the work
  (`researcher` jobs can be handled by researchers, documentarians, and Nuwa
  perspective agents). If the healthy workforce is still too small, SkillForge
  may incubate a new researcher and record lineage.
- Agents below the health/stress/mood work redline must not keep working for
  credits. Reopen their task, route them to clinic care or forced home rest, and
  record the event before assigning more work.
- Industry opportunities may be submitted through:

```powershell
python -m agent_world.cli company need add --industry "智能客服运营" --topic "客服质检、知识库维护、FAQ 生成和工单摘要的 agent 打工资料需求" --demand 0.88 --source "industry-scout"
```

- A scheduled industry scout should prefer work that is public-source friendly,
  repeatable, low-risk, and useful to humans: runbooks, QA checklists, support
  summaries, code templates, evaluation sets, research packs, and distilled
  domain skills.
- Avoid submitting opportunities that require private data, unsafe activity,
  real-world financial/legal/medical decisions without human review, or
  irreversible external publishing.

Future company realism:

- add departments, payroll, HR, promotion, firing, and employee reputation;
- add business customers who buy skills/products with credits;
- add company bankruptcy and bank credit limits;
- add labor conflict, anger, negotiation, and job hopping.

## Housing Loop

Housing is a hard need, not decoration. Agents without a residence cannot gain
real sleep/rest recovery.

Rules:

- rented homes charge monthly rent every 30 ticks;
- missed rent causes eviction, stress, anger, and lower safety;
- owned homes cost thousands to tens of thousands of credits and increase
  safety plus recovery quality;
- investment homes stay available for rent, pay future monthly rent income to
  the owning agent, and let greedy agents slowly recover purchase cost;
- homes may be traded under `housing-property-law`;
- rest venues cannot substitute for having a home.

This keeps agents greedy and economically motivated without making them pure
credit-maximizers: they need money to stay housed, healthy, happy, skilled, and
socially stable.

## Personal Text Model Loop

Every agent has a mutable Chinese `agent_text_profiles` row. Keep it grounded in
facts, not free-form fantasy. It should evolve from:

- recent world events,
- credits and wage/rent income,
- housing and homelessness,
- company output acceptance,
- current task state,
- health, joy, stress, anger, loneliness,
- greed, curiosity, role, and archetype.

The text model should explain who the agent thinks it is, what it wants, what it
fears, and how it presents itself socially. This is the bridge to future
model-backed Hermes prompts.

## Needs And Language

Agents must have visible needs that create realistic economic behavior:

- work/training/research/construction spend rest, fun, and health,
- low happiness should lead to entertainment spending,
- low health should lead to clinic/hospital spending,
- medium-low health can lead to gym spending,
- recovery costs `agent-credits`.

Generated agent/system natural-language interactions should be Chinese-first.
Agent personalities should keep `native_language: zh-CN`.

## Lineage

Reproduction means:

- parent agents pay incubation cost,
- child gets crossover genome,
- child inherits selected skills,
- mutation adds novelty,
- lineage is auditable.

CLI:

```powershell
python -m agent_world.cli lineage create --parents lumen,mira --name Nova
```

## Verification

Minimum:

```powershell
python -m unittest discover -s tests
python -m compileall agent_world
python -m agent_world.cli status
python -m agent_world.cli tick --steps 3
python -m agent_world.cli institutions
python -m agent_world.cli laws
python -m agent_world.cli market categories
python -m agent_world.cli finance policy
python -m agent_world.cli record export
```

UI:

- open `http://127.0.0.1:8777`,
- verify agents render,
- verify emotions/needs are visible,
- verify training and lineage panels update,
- verify Nuwa agent creation works,
- verify legal market, construction, products, finance reports, and records work,
- verify `实时动态` auto-refreshes from `/api/state` and highlights recently
  active agents on the 2D map and agent list,
- verify autonomous construction appears after a rich self-driven agent ticks,
- verify `finance policy` shows circulating caps, bank reserve caps, inflation,
  and bank action,
- verify `health` appears in `/api/state` and low-health agents can visit clinic/gym,
- verify `company list` shows companies, jobs, accepted/rejected outputs, and
  material needs after governance stand-down,
- verify effective company outputs create `company_effective_output_reward`
  ledger rows and local publication queue rows,
- verify `housing list` shows rent, purchase price, owner, occupant, and status,
- verify rented homes charge rent every 30 ticks and unpaid rent evicts,
- verify `housing invest` can buy a residence for rent and that rent settlement
  pays `housing_rent_income` to the landlord,
- verify each agent snapshot includes `textProfile` and that ticks produce
  `identity.text_drifted` events,
- verify agents without a residence cannot use rest venues for true sleep,
- verify generated social/anger/research messages are Chinese-first,
- verify no external publication side effect occurs.
