from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
from pathlib import Path
from typing import Any

from .db import (
    DEFAULT_DB_PATH,
    connect,
    default_genome,
    init_db,
    json_dumps,
    json_loads,
    rows_to_dicts,
    seed_agent_life_state,
    seed_world,
)


ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts"

CONTROLLED_MINT_REASONS = {
    "judge_bonus",
    "network_skill_reward",
    "financial_research_reward",
    "construction_completion_bonus",
    "company_effective_output_reward",
    "public_health_grant",
}

COMPANY_OUTPUT_MIN_EFFECTIVENESS = {
    "skill-package": 0.86,
    "industry-article": 0.76,
    "persona-distillation": 0.78,
    "material-research": 0.74,
}

SKILL_PACKAGE_REQUIRED_FILES = (
    "SKILL.md",
    "manifest.json",
    "references/quality-checklist.md",
    "references/handoff.md",
    "references/source-map.md",
    "references/validation-procedure.md",
    "examples/handoff.md",
)

SKILL_PACKAGE_REQUIRED_HEADINGS = (
    "## 适用场景",
    "## 输入",
    "## 输出",
    "## 工作流",
    "## 质量门槛",
    "## 失败处理",
    "## 安全边界",
)

MIN_HEALTH_FOR_WORK = 0.25
MAX_STRESS_FOR_WORK = 0.82
MIN_MOOD_FOR_WORK = 0.08
MIN_NUTRITION_FOR_WORK = 0.2
STARVATION_NUTRITION = 0.035
STARVATION_HEALTH = 0.08
MEAL_TRIGGER_NUTRITION = 0.62
CRITICAL_MEAL_NUTRITION = 0.28
FOOD_RESERVE_MEALS = 2
SURVIVAL_JOB_REWARD = 56
EMERGENCY_FOOD_NUTRITION_FLOOR = 0.58
EMERGENCY_FOOD_HEALTH_FLOOR = 0.22

NEED_KEYS = ("rest", "social", "fun", "purpose", "safety", "health", "nutrition")

ROLE_TASK_COMPATIBILITY = {
    "researcher": ("researcher", "documentarian"),
    "documentarian": ("documentarian", "researcher"),
    "nuwa_perspective": ("researcher", "documentarian"),
    "engineer": ("engineer", "hybrid"),
    "hybrid": ("researcher", "documentarian", "engineer", "hybrid"),
}


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def infer_skill(text: str) -> str:
    lower = text.lower()
    checks = [
        (("doc", "document", "write", "publish", "csdn", "github", "note"), "documentation"),
        (("research", "source", "search", "web", "资料"), "research"),
        (("ui", "dashboard", "canvas", "2d", "frontend"), "ui-design"),
        (("cli", "command", "terminal"), "cli"),
        (("agent", "world", "society", "hermes"), "agent-systems"),
        (("code", "build", "implement", "engine", "sqlite", "api"), "implementation"),
        (("social", "chat", "group", "teach"), "social"),
    ]
    for keys, skill in checks:
        if any(key in lower for key in keys):
            return skill
    return "general-problem-solving"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug or "agent"


class WorldEngine:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        init_db(self.db_path)

    def ensure_seeded(self) -> None:
        seed_world(self.db_path)

    def snapshot(self) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            agents = rows_to_dicts(conn.execute("SELECT * FROM agents ORDER BY role, id"))
            for agent in agents:
                agent["personality"] = json_loads(agent.pop("personality_json"), {})
                agent["emotions"] = self._emotion_dict(conn, agent["id"])
                agent["needs"] = self._need_dict(conn, agent["id"])
                agent["textProfile"] = self._text_profile_dict(conn, agent["id"])
                agent["skills"] = rows_to_dicts(
                    conn.execute(
                        "SELECT name, level, source, notes FROM skills WHERE agent_id=? ORDER BY level DESC, name",
                        (agent["id"],),
                    )
                )
            channels = rows_to_dicts(conn.execute("SELECT * FROM channels ORDER BY kind, id"))
            for channel in channels:
                channel["members"] = [
                    row["agent_id"]
                    for row in conn.execute(
                        "SELECT agent_id FROM memberships WHERE channel_id=? ORDER BY agent_id",
                        (channel["id"],),
                    )
                ]
            pinned_noise = rows_to_dicts(
                conn.execute("SELECT * FROM world_noise WHERE key IN ('world.global', 'agent.background.avg_abs') ORDER BY key")
            )
            recent_noise = rows_to_dicts(
                conn.execute(
                    """
                    SELECT * FROM world_noise
                    WHERE key NOT IN ('world.global', 'agent.background.avg_abs')
                    ORDER BY updated_tick DESC, updated_at DESC, key
                    LIMIT 58
                    """
                )
            )
            return {
                "governance": self._governance_state(conn),
                "agents": agents,
                "channels": channels,
                "owners": rows_to_dicts(conn.execute("SELECT * FROM owners ORDER BY id")),
                "institutions": rows_to_dicts(conn.execute("SELECT * FROM institutions ORDER BY authority_level DESC, id")),
                "laws": rows_to_dicts(conn.execute("SELECT * FROM laws ORDER BY domain, id")),
                "tradeCategories": rows_to_dicts(conn.execute("SELECT * FROM trade_categories ORDER BY legal_status, risk_level, id")),
                "marketListings": rows_to_dicts(conn.execute("SELECT * FROM market_listings ORDER BY id DESC LIMIT 50")),
                "marketTransactions": rows_to_dicts(conn.execute("SELECT * FROM market_transactions ORDER BY id DESC LIMIT 40")),
                "buildings": rows_to_dicts(conn.execute("SELECT * FROM buildings ORDER BY id DESC LIMIT 50")),
                "constructionProjects": rows_to_dicts(conn.execute("SELECT * FROM construction_projects ORDER BY id DESC LIMIT 50")),
                "products": rows_to_dicts(conn.execute("SELECT * FROM products ORDER BY id DESC LIMIT 50")),
                "productSales": rows_to_dicts(conn.execute("SELECT * FROM product_sales ORDER BY id DESC LIMIT 40")),
                "financialResearchReports": rows_to_dicts(conn.execute("SELECT * FROM financial_research_reports ORDER BY id DESC LIMIT 40")),
                "monetaryPolicy": rows_to_dicts(conn.execute("SELECT * FROM monetary_policy_snapshots ORDER BY id DESC LIMIT 30")),
                "companies": rows_to_dicts(conn.execute("SELECT * FROM companies ORDER BY created_at DESC, id")),
                "companyJobs": rows_to_dicts(conn.execute("SELECT * FROM company_jobs ORDER BY id DESC LIMIT 50")),
                "companyOutputs": rows_to_dicts(conn.execute("SELECT * FROM company_outputs ORDER BY id DESC LIMIT 50")),
                "materialNeeds": rows_to_dicts(conn.execute("SELECT * FROM material_needs ORDER BY demand_score DESC, id LIMIT 50")),
                "residences": rows_to_dicts(conn.execute("SELECT * FROM residences ORDER BY status, monthly_rent, id")),
                "blueprints": rows_to_dicts(conn.execute("SELECT * FROM agent_blueprints ORDER BY role, id")),
                "nuwaDistillations": rows_to_dicts(conn.execute("SELECT * FROM nuwa_distillations ORDER BY domain, id")),
                "relationships": rows_to_dicts(conn.execute("SELECT * FROM relationships ORDER BY tension DESC, affinity ASC LIMIT 40")),
                "lineage": rows_to_dicts(conn.execute("SELECT * FROM agent_lineage ORDER BY created_at DESC LIMIT 40")),
                "genomes": rows_to_dicts(conn.execute("SELECT * FROM agent_genomes ORDER BY fitness DESC, agent_id")),
                "evolutionRuns": rows_to_dicts(conn.execute("SELECT * FROM evolution_runs ORDER BY id DESC LIMIT 40")),
                "tasks": rows_to_dicts(conn.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT 50")),
                "messages": rows_to_dicts(conn.execute("SELECT * FROM messages ORDER BY id DESC LIMIT 40")),
                "venues": rows_to_dicts(conn.execute("SELECT * FROM venues ORDER BY price, id")),
                "trainingPrograms": rows_to_dicts(conn.execute("SELECT * FROM training_programs ORDER BY cost, id")),
                "trainingSessions": rows_to_dicts(conn.execute("SELECT * FROM training_sessions ORDER BY id DESC LIMIT 40")),
                "ledger": rows_to_dicts(conn.execute("SELECT * FROM ledger ORDER BY id DESC LIMIT 40")),
                "randomFactors": pinned_noise + recent_noise,
                "documents": rows_to_dicts(conn.execute("SELECT * FROM documents ORDER BY id DESC LIMIT 30")),
                "researchRuns": rows_to_dicts(conn.execute("SELECT * FROM research_runs ORDER BY id DESC LIMIT 30")),
                "publicationQueue": rows_to_dicts(
                    conn.execute("SELECT * FROM publication_queue ORDER BY id DESC LIMIT 30")
                ),
                "events": rows_to_dicts(conn.execute("SELECT * FROM world_events ORDER BY id DESC LIMIT 40")),
                "memories": rows_to_dicts(conn.execute("SELECT * FROM agent_memories ORDER BY id DESC LIMIT 40")),
            }

    def create_agent(
        self,
        name: str,
        blueprint_id: str = "researcher",
        owner_id: str = "local-owner",
        role: str | None = None,
        archetype: str | None = None,
        personality: dict[str, Any] | None = None,
        credits: int = 80,
    ) -> str:
        with connect(self.db_path) as conn:
            blueprint = conn.execute("SELECT * FROM agent_blueprints WHERE id=?", (blueprint_id,)).fetchone()
            if blueprint is None:
                raise ValueError(f"unknown blueprint: {blueprint_id}")
            if conn.execute("SELECT 1 FROM owners WHERE id=?", (owner_id,)).fetchone() is None:
                conn.execute("INSERT INTO owners (id, display_name, credits) VALUES (?, ?, ?)", (owner_id, owner_id, 1000))

            base_personality = json_loads(blueprint["default_personality_json"], {})
            base_personality.update(personality or {})
            base_personality.setdefault("native_language", "zh-CN")
            agent_id = slugify(name)
            base_id = agent_id
            suffix = 2
            while conn.execute("SELECT 1 FROM agents WHERE id=?", (agent_id,)).fetchone() is not None:
                agent_id = f"{base_id}-{suffix}"
                suffix += 1

            row_count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
            x = 0.18 + ((row_count * 17) % 68) / 100
            y = 0.18 + ((row_count * 29) % 68) / 100
            conn.execute(
                """
                INSERT INTO agents
                  (id, owner_id, name, role, archetype, personality_json, mood, energy, credits, autonomy, x, y)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    owner_id,
                    name,
                    role or blueprint["role"],
                    archetype or blueprint["archetype"],
                    json_dumps(base_personality),
                    0.64,
                    0.82,
                    credits,
                    0.55 + float(base_personality.get("curiosity", 0.55)) * 0.25,
                    x,
                    y,
                ),
            )
            for skill in json_loads(blueprint["base_skills_json"], []):
                conn.execute(
                    "INSERT INTO skills (agent_id, name, level, source, notes) VALUES (?, ?, ?, 'blueprint', ?)",
                    (agent_id, skill["name"], skill.get("level", 0.35), blueprint["name"]),
                )
            for channel in ("plaza", "leisure"):
                conn.execute("INSERT OR IGNORE INTO memberships (channel_id, agent_id) VALUES (?, ?)", (channel, agent_id))
            role_channel = "research" if (role or blueprint["role"]) in ("researcher", "documentarian", "top_planner") else "makers"
            if (role or blueprint["role"]) == "social":
                role_channel = "leisure"
            conn.execute("INSERT OR IGNORE INTO memberships (channel_id, agent_id) VALUES (?, ?)", (role_channel, agent_id))
            seed_agent_life_state(conn)
            self._event(conn, "agent.created", agent_id, {"owner": owner_id, "blueprint": blueprint_id})
            return agent_id

    def create_nuwa_agent(
        self,
        distillation_id: str,
        name: str | None = None,
        owner_id: str = "local-owner",
        credits: int = 120,
    ) -> str:
        with connect(self.db_path) as conn:
            distillation = conn.execute("SELECT * FROM nuwa_distillations WHERE id=?", (distillation_id,)).fetchone()
            if distillation is None:
                raise ValueError(f"unknown Nuwa distillation: {distillation_id}")
            agent_name = name or distillation["display_name"]
            agent_id = slugify(agent_name)
            base_id = agent_id
            suffix = 2
            while conn.execute("SELECT 1 FROM agents WHERE id=?", (agent_id,)).fetchone() is not None:
                agent_id = f"{base_id}-{suffix}"
                suffix += 1
            genome = json_loads(distillation["base_genome_json"], {})
            personality = {
                "temper": "nuwa-perspective",
                "curiosity": genome.get("curiosity", 0.7),
                "sociability": genome.get("sociability", 0.5),
                "stubbornness": genome.get("stubbornness", 0.5),
                "honesty_boundary": distillation["honesty_boundary"],
                "expression_dna": distillation["expression_dna"],
                "native_language": "zh-CN",
            }
            row_count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
            x = 0.16 + ((row_count * 13) % 74) / 100
            y = 0.16 + ((row_count * 23) % 74) / 100
            conn.execute(
                """
                INSERT INTO agents
                  (id, owner_id, name, role, archetype, personality_json, mood, energy, credits, autonomy, state, x, y)
                VALUES (?, ?, ?, 'nuwa_perspective', ?, ?, 0.68, 0.78, ?, ?, 'reflecting', ?, ?)
                """,
                (
                    agent_id,
                    owner_id,
                    agent_name,
                    distillation_id,
                    json_dumps(personality),
                    credits,
                    clamp(0.48 + genome.get("curiosity", 0.6) * 0.25 + genome.get("discipline", 0.6) * 0.16),
                    x,
                    y,
                ),
            )
            for skill_name in json_loads(distillation["mental_models_json"], [])[:5]:
                self._upsert_skill(conn, agent_id, skill_name, 0.36, "nuwa-mental-model", distillation["display_name"])
            for skill_name in json_loads(distillation["heuristics_json"], [])[:4]:
                self._upsert_skill(conn, agent_id, skill_name, 0.3, "nuwa-heuristic", distillation["display_name"])
            conn.execute(
                """
                INSERT OR REPLACE INTO agent_genomes (agent_id, genome_json, generation, fitness, algorithm)
                VALUES (?, ?, 1, 0, 'nuwa-distillation')
                """,
                (agent_id, json_dumps(genome)),
            )
            for channel in ("plaza", "research", "leisure"):
                conn.execute("INSERT OR IGNORE INTO memberships (channel_id, agent_id) VALUES (?, ?)", (channel, agent_id))
            seed_agent_life_state(conn)
            self._memory(
                conn,
                agent_id,
                "nuwa_created",
                0.38,
                0.82,
                f"由 Nuwa 蒸馏 `{distillation_id}` 创建，并带有明确诚实边界。",
            )
            self._event(
                conn,
                "nuwa.agent_created",
                agent_id,
                {"distillation": distillation_id, "domain": distillation["domain"]},
            )
            return agent_id

    def reproduce_agents(
        self,
        parent_ids: list[str],
        child_name: str,
        owner_id: str = "local-owner",
        method: str = "skill-synthesis",
        mutation_rate: float = 0.08,
    ) -> str:
        parent_ids = [item.strip() for item in parent_ids if item.strip()]
        if len(parent_ids) < 2:
            raise ValueError("at least two parent agents are required")
        if len(set(parent_ids)) != len(parent_ids):
            raise ValueError("parent agents must be unique")
        with connect(self.db_path) as conn:
            parents = [
                conn.execute("SELECT * FROM agents WHERE id=?", (parent_id,)).fetchone()
                for parent_id in parent_ids
            ]
            if any(parent is None for parent in parents):
                missing = [parent_ids[index] for index, parent in enumerate(parents) if parent is None]
                raise ValueError(f"unknown parent agents: {', '.join(missing)}")
            cost = 64 + 18 * (len(parent_ids) - 2)
            share = math.ceil(cost / len(parent_ids))
            for parent in parents:
                if parent["credits"] < share:
                    raise ValueError(f"parent {parent['id']} lacks credits for incubation")
            child_id = slugify(child_name)
            base_id = child_id
            suffix = 2
            while conn.execute("SELECT 1 FROM agents WHERE id=?", (child_id,)).fetchone() is not None:
                child_id = f"{base_id}-{suffix}"
                suffix += 1
            personality = self._blend_personality(parents, mutation_rate, child_id)
            role = self._child_role(parents)
            archetype = "hybrid"
            child_credits = 36 + 8 * len(parent_ids)
            row_count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
            x = 0.14 + ((row_count * 19) % 72) / 100
            y = 0.14 + ((row_count * 31) % 72) / 100

            for parent in parents:
                self._credit(conn, parent["id"], -share, "incubation_cost", "lineage", child_id)
                self._set_emotions(conn, parent["id"], joy=0.06, stress=0.035, confidence=0.03)
            self._set_needs(conn, parent["id"], purpose=0.05, rest=-0.02, health=-0.01)

            conn.execute(
                """
                INSERT INTO agents
                  (id, owner_id, name, role, archetype, personality_json, mood, energy, credits, autonomy, state, x, y)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'incubating', ?, ?)
                """,
                (
                    child_id,
                    owner_id,
                    child_name,
                    role,
                    archetype,
                    json_dumps(personality),
                    0.66,
                    0.72,
                    child_credits,
                    clamp(0.48 + personality.get("curiosity", 0.55) * 0.32),
                    x,
                    y,
                ),
            )
            inherited = self._inherit_skills(conn, child_id, parents, mutation_rate)
            for channel in ("plaza", "leisure"):
                conn.execute("INSERT OR IGNORE INTO memberships (channel_id, agent_id) VALUES (?, ?)", (channel, child_id))
            if role in ("researcher", "documentarian", "top_planner", "hybrid"):
                conn.execute("INSERT OR IGNORE INTO memberships (channel_id, agent_id) VALUES ('research', ?)", (child_id,))
            if role in ("engineer", "hybrid"):
                conn.execute("INSERT OR IGNORE INTO memberships (channel_id, agent_id) VALUES ('makers', ?)", (child_id,))
            seed_agent_life_state(conn)
            child_genome = self._inherit_genome(conn, child_id, parents, mutation_rate)
            conn.execute(
                """
                INSERT INTO agent_lineage
                  (child_agent_id, parent_ids_json, method, mutation_rate, inherited_skills_json, cost)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (child_id, json_dumps(parent_ids), method, mutation_rate, json_dumps(inherited), cost),
            )
            self._memory(
                conn,
                child_id,
                "lineage_created",
                0.42,
                0.8,
                f"通过 {method} 从 {', '.join(parent_ids)} 繁衍生成。",
            )
            self._event(
                conn,
                "agent.reproduced",
                child_id,
                {"parents": parent_ids, "method": method, "cost": cost, "inheritedSkills": inherited, "genome": child_genome},
            )
            return child_id

    def start_training(self, agent_id: str, program_id: str, created_by: str = "owner") -> int:
        with connect(self.db_path) as conn:
            agent = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
            if agent is None:
                raise ValueError(f"unknown agent: {agent_id}")
            if agent["current_task_id"] or agent["current_training_id"]:
                raise ValueError(f"agent {agent_id} is busy")
            program = conn.execute("SELECT * FROM training_programs WHERE id=?", (program_id,)).fetchone()
            if program is None:
                raise ValueError(f"unknown training program: {program_id}")
            self._credit(conn, agent_id, -int(program["cost"]), "training_cost", "training_program", program_id)
            cur = conn.execute(
                """
                INSERT INTO training_sessions (agent_id, program_id, cost, created_by)
                VALUES (?, ?, ?, ?)
                """,
                (agent_id, program_id, program["cost"], created_by),
            )
            training_id = int(cur.lastrowid)
            conn.execute(
                """
                UPDATE agents
                SET current_training_id=?, state='training', updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (training_id, agent_id),
            )
            self._memory(conn, agent_id, "training_started", 0.1, 0.45, f"Started {program['name']}.")
            self._event(conn, "training.started", agent_id, {"training_id": training_id, "program": program_id})
            return training_id

    def rent_residence(self, agent_id: str, residence_id: int) -> int:
        with connect(self.db_path) as conn:
            agent = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
            if agent is None:
                raise ValueError(f"unknown agent: {agent_id}")
            residence = conn.execute("SELECT * FROM residences WHERE id=?", (residence_id,)).fetchone()
            if residence is None:
                raise ValueError(f"unknown residence: {residence_id}")
            if residence["occupant_agent_id"] and residence["occupant_agent_id"] != agent_id:
                raise ValueError(f"residence {residence_id} is already occupied")
            if self._agent_residence(conn, agent_id) is not None and residence["occupant_agent_id"] != agent_id:
                raise ValueError(f"agent {agent_id} already has a residence")
            rent = int(residence["monthly_rent"])
            if rent <= 0:
                raise ValueError("residence is not rentable")
            self._credit(conn, agent_id, -rent, "housing_rent", "residence", str(residence_id))
            if residence["owner_agent_id"]:
                self._credit(conn, residence["owner_agent_id"], rent, "housing_rent_income", "residence", str(residence_id))
            current_tick = self._current_tick(conn)
            conn.execute(
                """
                UPDATE residences
                SET occupant_agent_id=?, status='rented', last_rent_tick=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (agent_id, current_tick, residence_id),
            )
            self._set_needs(conn, agent_id, safety=0.18, rest=0.08)
            self._set_emotions(conn, agent_id, joy=0.05, stress=-0.06, confidence=0.03)
            self._memory(conn, agent_id, "housing_rented", 0.28, 0.62, f"租下住所 {residence['name']}，月租 {rent} agent-credits。")
            self._event(conn, "housing.rented", agent_id, {"residence_id": residence_id, "rent": rent, "name": residence["name"]})
            return residence_id

    def buy_residence(self, agent_id: str, residence_id: int) -> int:
        with connect(self.db_path) as conn:
            agent = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
            if agent is None:
                raise ValueError(f"unknown agent: {agent_id}")
            residence = conn.execute("SELECT * FROM residences WHERE id=?", (residence_id,)).fetchone()
            if residence is None:
                raise ValueError(f"unknown residence: {residence_id}")
            if residence["occupant_agent_id"] and residence["occupant_agent_id"] != agent_id:
                raise ValueError(f"residence {residence_id} is already occupied")
            price = int(residence["purchase_price"])
            if price < 10000:
                raise ValueError("house purchase price must stay in the tens-of-thousands range")
            self._credit(conn, agent_id, -price, "housing_purchase", "residence", str(residence_id))
            if residence["owner_agent_id"] and residence["owner_agent_id"] != agent_id:
                self._credit(conn, residence["owner_agent_id"], price, "housing_sale_income", "residence", str(residence_id))
            conn.execute(
                """
                UPDATE residences
                SET owner_agent_id=?, occupant_agent_id=?, status='owner_occupied', monthly_rent=0, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (agent_id, agent_id, residence_id),
            )
            self._set_needs(conn, agent_id, safety=0.28, rest=0.12, purpose=0.05)
            self._set_emotions(conn, agent_id, joy=0.08, stress=-0.08, confidence=0.08)
            self._memory(conn, agent_id, "housing_bought", 0.42, 0.78, f"买下住所 {residence['name']}，价格 {price} agent-credits。")
            self._event(conn, "housing.bought", agent_id, {"residence_id": residence_id, "price": price, "name": residence["name"]})
            return residence_id

    def buy_residence_for_rent(self, agent_id: str, residence_id: int, monthly_rent: int | None = None) -> int:
        with connect(self.db_path) as conn:
            agent = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
            if agent is None:
                raise ValueError(f"unknown agent: {agent_id}")
            residence = conn.execute("SELECT * FROM residences WHERE id=?", (residence_id,)).fetchone()
            if residence is None:
                raise ValueError(f"unknown residence: {residence_id}")
            if residence["occupant_agent_id"]:
                raise ValueError(f"residence {residence_id} is occupied")
            price = int(residence["purchase_price"])
            if int(agent["credits"]) < price:
                raise ValueError(f"agent {agent_id} does not have enough credits to buy residence {residence_id}")
            rent = int(monthly_rent) if monthly_rent is not None else max(int(residence["monthly_rent"]), max(50, price // 120))
            if rent <= 0:
                raise ValueError("monthly rent must be positive")
            tick_no = self._current_tick(conn)
            self._buy_residence_for_rent_in_conn(conn, agent_id, residence, tick_no, rent)
            return residence_id

    def submit_material_need(
        self,
        industry: str,
        topic: str,
        demand_score: float = 0.72,
        source_hint: str = "industry-scout",
        actor_agent_id: str = "atlas",
    ) -> int:
        industry = industry.strip()
        topic = topic.strip()
        source_hint = source_hint.strip() or "industry-scout"
        if not industry:
            raise ValueError("industry is required")
        if not topic:
            raise ValueError("topic is required")
        score = clamp(float(demand_score), 0.35, 1.0)
        with connect(self.db_path) as conn:
            company = conn.execute("SELECT id FROM companies WHERE id='skillforge-company'").fetchone()
            company_id = company["id"] if company is not None else None
            existing = conn.execute(
                """
                SELECT * FROM material_needs
                WHERE industry=? AND topic=?
                ORDER BY id
                LIMIT 1
                """,
                (industry, topic),
            ).fetchone()
            if existing is not None:
                need_id = int(existing["id"])
                next_score = clamp(max(float(existing["demand_score"]), score) + 0.025, 0.35, 1.0)
                conn.execute(
                    """
                    UPDATE material_needs
                    SET company_id=COALESCE(?, company_id),
                        demand_score=?,
                        source_hint=?,
                        status='open',
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (company_id, next_score, source_hint, need_id),
                )
                action = "updated"
                final_score = next_score
            else:
                cur = conn.execute(
                    """
                    INSERT INTO material_needs (company_id, industry, topic, demand_score, source_hint, status)
                    VALUES (?, ?, ?, ?, ?, 'open')
                    """,
                    (company_id, industry, topic, score, source_hint),
                )
                need_id = int(cur.lastrowid)
                action = "submitted"
                final_score = score
            if conn.execute("SELECT 1 FROM agents WHERE id=?", (actor_agent_id,)).fetchone() is not None:
                self._memory(
                    conn,
                    actor_agent_id,
                    "industry_opportunity_submitted",
                    0.18,
                    0.56,
                    f"提交行业机会：{industry} - {topic}，需求强度 {final_score:.2f}。",
                )
            self._event(
                conn,
                "company.material_need_submitted",
                actor_agent_id,
                {
                    "need_id": need_id,
                    "action": action,
                    "company_id": company_id,
                    "industry": industry,
                    "topic": topic,
                    "demand_score": round(final_score, 3),
                    "source_hint": source_hint,
                },
            )
            return need_id

    def create_market_listing(
        self,
        seller_agent_id: str,
        item_type: str,
        item_name: str,
        description: str,
        price: int,
    ) -> int:
        if price <= 0:
            raise ValueError("price must be positive")
        with connect(self.db_path) as conn:
            seller = conn.execute("SELECT * FROM agents WHERE id=?", (seller_agent_id,)).fetchone()
            if seller is None:
                raise ValueError(f"unknown seller agent: {seller_agent_id}")
            category = self._trade_category_or_raise(conn, item_type)
            if category["legal_status"] == "prohibited":
                raise ValueError(f"trade category {item_type} is prohibited by {category['governing_law_id']}")
            reviewer = self._market_reviewer_for_category(conn, category)
            legality_status = "legal" if category["legal_status"] == "allowed" else "regulated-approved"
            cur = conn.execute(
                """
                INSERT INTO market_listings
                  (seller_agent_id, item_type, item_name, description, price, legality_status, reviewed_by, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
                """,
                (seller_agent_id, category["id"], item_name, description, price, legality_status, reviewer),
            )
            listing_id = int(cur.lastrowid)
            self._memory(
                conn,
                seller_agent_id,
                "market_listing_created",
                0.12,
                0.48,
                f"把 {item_name} 作为 {category['name']} 挂牌，价格 {price} agent-credits。",
            )
            self._event(
                conn,
                "market.listing_created",
                seller_agent_id,
                {
                    "listing_id": listing_id,
                    "item_type": category["id"],
                    "price": price,
                    "legality": legality_status,
                    "reviewed_by": reviewer,
                },
            )
            return listing_id

    def buy_market_listing(self, buyer_agent_id: str, listing_id: int) -> int:
        with connect(self.db_path) as conn:
            buyer = conn.execute("SELECT * FROM agents WHERE id=?", (buyer_agent_id,)).fetchone()
            if buyer is None:
                raise ValueError(f"unknown buyer agent: {buyer_agent_id}")
            listing = conn.execute("SELECT * FROM market_listings WHERE id=?", (listing_id,)).fetchone()
            if listing is None:
                raise ValueError(f"unknown market listing: {listing_id}")
            if listing["status"] != "active":
                raise ValueError(f"market listing {listing_id} is not active")
            if listing["seller_agent_id"] == buyer_agent_id:
                raise ValueError("buyer and seller must be different agents")
            category = self._trade_category_or_raise(conn, listing["item_type"])
            if category["legal_status"] == "prohibited":
                raise ValueError(f"trade category {category['id']} is prohibited by {category['governing_law_id']}")
            price = int(listing["price"])
            self._credit(conn, buyer_agent_id, -price, "market_purchase", "market_listing", str(listing_id))
            self._credit(conn, listing["seller_agent_id"], price, "market_sale", "market_listing", str(listing_id))
            conn.execute(
                """
                UPDATE market_listings
                SET status='sold', updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (listing_id,),
            )
            legal_basis = f"{category['governing_law_id']}:{category['legal_status']}"
            cur = conn.execute(
                """
                INSERT INTO market_transactions
                  (listing_id, buyer_agent_id, seller_agent_id, price, legal_basis)
                VALUES (?, ?, ?, ?, ?)
                """,
                (listing_id, buyer_agent_id, listing["seller_agent_id"], price, legal_basis),
            )
            transaction_id = int(cur.lastrowid)
            self._set_emotions(conn, buyer_agent_id, joy=0.035, purpose=0.0, confidence=0.02)
            self._set_needs(conn, buyer_agent_id, purpose=0.025)
            self._set_emotions(conn, listing["seller_agent_id"], joy=0.04, confidence=0.03, stress=-0.01)
            self._adjust_relationship(conn, buyer_agent_id, listing["seller_agent_id"], 0.018, 0.02, -0.012, "market_trade")
            self._event(
                conn,
                "market.transaction_settled",
                "credit-bank",
                {
                    "transaction_id": transaction_id,
                    "listing_id": listing_id,
                    "buyer": buyer_agent_id,
                    "seller": listing["seller_agent_id"],
                    "price": price,
                    "legal_basis": legal_basis,
                },
            )
            return transaction_id

    def create_construction_project(
        self,
        builder_agent_id: str,
        name: str,
        kind: str,
        cost: int,
        owner_agent_id: str | None = None,
        expected_value: int | None = None,
    ) -> int:
        if cost <= 0:
            raise ValueError("construction cost must be positive")
        with connect(self.db_path) as conn:
            builder = conn.execute("SELECT * FROM agents WHERE id=?", (builder_agent_id,)).fetchone()
            if builder is None:
                raise ValueError(f"unknown builder agent: {builder_agent_id}")
            owner_id = owner_agent_id or builder_agent_id
            owner = conn.execute("SELECT * FROM agents WHERE id=?", (owner_id,)).fetchone()
            if owner is None:
                raise ValueError(f"unknown owner agent: {owner_id}")
            category = self._trade_category_or_raise(conn, "construction-service")
            if category["legal_status"] == "prohibited":
                raise ValueError("construction service is not legal in this world")
            self._credit(conn, owner_id, -cost, "construction_investment", "construction_project", name)
            noise_tick = self._event_index(conn)
            value_factor = self._random_factor(conn, f"construction.expected.{builder_agent_id}.{slugify(name)}", noise_tick, 0.07)
            base_expected_value = expected_value if expected_value is not None else int(cost * 1.35)
            final_expected_value = max(1, int(round(base_expected_value * value_factor)))
            cur = conn.execute(
                """
                INSERT INTO construction_projects
                  (builder_agent_id, owner_agent_id, name, kind, cost, expected_value)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (builder_agent_id, owner_id, name, kind, cost, final_expected_value),
            )
            project_id = int(cur.lastrowid)
            self._set_needs(conn, builder_agent_id, purpose=0.04, rest=-0.025, health=-0.018)
            self._set_emotions(conn, builder_agent_id, confidence=0.025, stress=0.02)
            self._event(
                conn,
                "construction.started",
                builder_agent_id,
                {"project_id": project_id, "owner": owner_id, "cost": cost, "kind": kind, "random_factor": round(value_factor - 1.0, 4)},
            )
            return project_id

    def design_product(
        self,
        designer_agent_id: str,
        name: str,
        category: str,
        unit_price: int,
        build_cost: int,
        stock: int = 1,
    ) -> int:
        if unit_price <= 0 or build_cost < 0 or stock <= 0:
            raise ValueError("product price, cost, and stock must be valid")
        with connect(self.db_path) as conn:
            designer = conn.execute("SELECT * FROM agents WHERE id=?", (designer_agent_id,)).fetchone()
            if designer is None:
                raise ValueError(f"unknown designer agent: {designer_agent_id}")
            trade_category = self._trade_category_or_raise(conn, "product")
            if trade_category["legal_status"] == "prohibited":
                raise ValueError("product trade is not legal in this world")
            if build_cost:
                self._credit(conn, designer_agent_id, -build_cost, "product_build_cost", "product", name)
            skills = conn.execute(
                "SELECT AVG(level) FROM skills WHERE agent_id=? AND name IN ('implementation', 'ui-design', 'technical-writing', 'agent-systems')",
                (designer_agent_id,),
            ).fetchone()[0] or 0.35
            noise_tick = self._event_index(conn)
            quality_factor = self._random_factor(conn, f"product.quality.{designer_agent_id}.{slugify(name)}", noise_tick, 0.045)
            quality = clamp((0.42 + float(skills) * 0.45 + designer["mood"] * 0.08) * quality_factor)
            cur = conn.execute(
                """
                INSERT INTO products
                  (designer_agent_id, name, category, unit_price, build_cost, stock, quality)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (designer_agent_id, name, category, unit_price, build_cost, stock, quality),
            )
            product_id = int(cur.lastrowid)
            self._upsert_skill(conn, designer_agent_id, "product-design", 0.08, "product", name)
            self._set_emotions(conn, designer_agent_id, joy=0.03, confidence=0.035, stress=0.012)
            self._event(
                conn,
                "product.designed",
                designer_agent_id,
                {
                    "product_id": product_id,
                    "name": name,
                    "unit_price": unit_price,
                    "stock": stock,
                    "quality": quality,
                    "random_factor": round(quality_factor - 1.0, 4),
                },
            )
            return product_id

    def buy_product(self, buyer_agent_id: str, product_id: int, quantity: int = 1) -> int:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        with connect(self.db_path) as conn:
            buyer = conn.execute("SELECT * FROM agents WHERE id=?", (buyer_agent_id,)).fetchone()
            if buyer is None:
                raise ValueError(f"unknown buyer agent: {buyer_agent_id}")
            product = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
            if product is None:
                raise ValueError(f"unknown product: {product_id}")
            if product["status"] != "active" or product["stock"] < quantity:
                raise ValueError(f"product {product_id} is not available in requested quantity")
            if product["designer_agent_id"] == buyer_agent_id:
                raise ValueError("buyer and designer must be different agents")
            self._trade_category_or_raise(conn, "product")
            total = int(product["unit_price"]) * quantity
            self._credit(conn, buyer_agent_id, -total, "product_purchase", "product", str(product_id))
            self._credit(conn, product["designer_agent_id"], total, "product_sale", "product", str(product_id))
            remaining = int(product["stock"]) - quantity
            status = "sold_out" if remaining == 0 else "active"
            conn.execute(
                """
                UPDATE products
                SET stock=?, status=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (remaining, status, product_id),
            )
            cur = conn.execute(
                """
                INSERT INTO product_sales
                  (product_id, buyer_agent_id, seller_agent_id, quantity, total_price)
                VALUES (?, ?, ?, ?, ?)
                """,
                (product_id, buyer_agent_id, product["designer_agent_id"], quantity, total),
            )
            sale_id = int(cur.lastrowid)
            self._adjust_relationship(conn, buyer_agent_id, product["designer_agent_id"], 0.015, 0.02, -0.01, "product_trade")
            self._set_emotions(conn, buyer_agent_id, joy=0.035, confidence=0.015)
            self._set_emotions(conn, product["designer_agent_id"], joy=0.04, confidence=0.03)
            self._event(
                conn,
                "product.sold",
                "credit-bank",
                {"sale_id": sale_id, "product_id": product_id, "buyer": buyer_agent_id, "seller": product["designer_agent_id"], "total": total},
            )
            return sale_id

    def research_financial_model(self, researcher_agent_id: str, topic: str = "agent-world financial model") -> int:
        with connect(self.db_path) as conn:
            researcher = conn.execute("SELECT * FROM agents WHERE id=?", (researcher_agent_id,)).fetchone()
            if researcher is None:
                raise ValueError(f"unknown researcher agent: {researcher_agent_id}")
            if researcher["role"] not in {"researcher", "top_planner", "documentarian", "nuwa_perspective"}:
                raise ValueError("金融模型研究需要研究员、顶层规划、文档或 Nuwa 视角类 agent")
            metrics = self._financial_metrics(conn)
            model_name = "credits-market-property-product-bank model"
            summary = (
                f"当前世界以 agent-credits 为统一结算单位，"
                f"{metrics['agent_count']} 个 agent 持有 {metrics['agent_credits']} credits；"
                f"市场有 {metrics['active_listings']} 个活跃挂牌、{metrics['transactions']} 笔已结算交易、"
                f"{metrics['buildings']} 个建筑资产、{metrics['products']} 个产品、"
                f"{metrics['construction_projects']} 个建设项目。"
                "金融结构由公共银行结算、法律分类准入、产品利润、建筑资产和研究报告共同组成。"
            )
            report_dir = ARTIFACT_DIR / "金融研究"
            report_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{slugify(researcher_agent_id)}-{slugify(topic)}-{metrics['reports'] + 1}.md"
            path = report_dir / filename
            body = "\n".join(
                [
                    f"# {topic}",
                    "",
                    f"- 研究员：{researcher_agent_id}",
                    f"- 模型：{model_name}",
                    f"- agent 总数：{metrics['agent_count']}",
                    f"- agent 持有 credits：{metrics['agent_credits']}",
                    f"- 活跃市场挂牌：{metrics['active_listings']}",
                    f"- 市场成交：{metrics['transactions']}",
                    f"- 建筑资产：{metrics['buildings']}",
                    f"- 建设项目：{metrics['construction_projects']}",
                    f"- 产品数量：{metrics['products']}",
                    f"- 产品销售：{metrics['product_sales']}",
                    "",
                    "## 客观摘要",
                    "",
                    summary,
                    "",
                    "## 当前金融模型",
                    "",
                    "1. credits 是内部统一结算单位，不连接真实货币。",
                    "2. 所有交易先通过法律分类，allowed 和 regulated 才能成交，prohibited 会被阻断。",
                    "3. 银行 agent 负责结算记录，法院/政府 agent 负责规则和受监管事项。",
                    "4. 建筑是长期资产，产品是流通商品，研究报告是知识商品。",
                    "5. 未来可以继续加入贷款、利息、保险、税收、租金和破产清算。",
                ]
            )
            path.write_text(body, encoding="utf-8")
            noise_tick = self._event_index(conn)
            usefulness_noise = self._random_delta(conn, f"finance.usefulness.{researcher_agent_id}.{slugify(topic)}", noise_tick, 0.025)
            usefulness = clamp(0.52 + metrics["transactions"] * 0.01 + metrics["products"] * 0.015 + metrics["buildings"] * 0.015 + usefulness_noise)
            cur = conn.execute(
                """
                INSERT INTO financial_research_reports
                  (researcher_agent_id, topic, model_name, summary, path, usefulness_score)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (researcher_agent_id, topic, model_name, summary, str(path), usefulness),
            )
            report_id = int(cur.lastrowid)
            self._upsert_skill(conn, researcher_agent_id, "financial-modeling", 0.12, "financial-research", topic, noise_tick)
            reward = max(1, int(round(36 * self._random_factor(conn, f"finance.reward.{researcher_agent_id}", noise_tick, 0.06))))
            self._credit(conn, researcher_agent_id, reward, "financial_research_reward", "financial_report", str(report_id))
            self._event(
                conn,
                "finance.research_report_created",
                researcher_agent_id,
                {"report_id": report_id, "topic": topic, "path": str(path), "metrics": metrics, "random_factor": round(usefulness_noise, 4)},
            )
            return report_id

    def repair_accepted_skill_packages(self, limit: int = 25) -> list[dict[str, Any]]:
        """Rebuild accepted skill-package outputs as complete Git-ready packages."""
        repaired: list[dict[str, Any]] = []
        with connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                  co.id AS output_id,
                  co.job_id,
                  co.agent_id,
                  co.industry,
                  cj.task_id,
                  cj.document_id,
                  cj.output_type,
                  t.title AS task_title,
                  t.description AS task_description,
                  t.reward AS task_reward,
                  a.name AS agent_name
                FROM company_outputs co
                JOIN company_jobs cj ON cj.id=co.job_id
                JOIN tasks t ON t.id=cj.task_id
                JOIN agents a ON a.id=co.agent_id
                WHERE co.status='accepted'
                  AND co.output_type='skill-package'
                ORDER BY co.id DESC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
            for row in rows:
                doc = conn.execute("SELECT * FROM documents WHERE id=?", (row["document_id"],)).fetchone()
                if doc is None:
                    continue
                current_quality = self._artifact_quality_report(Path(doc["path"]), "skill-package")
                if current_quality["passed"]:
                    continue
                task = {
                    "id": row["task_id"],
                    "title": row["task_title"],
                    "description": row["task_description"],
                    "reward": row["task_reward"],
                }
                agent = {"id": row["agent_id"], "name": row["agent_name"]}
                job = {"id": row["job_id"], "industry": row["industry"], "output_type": row["output_type"]}
                skill_path = self._create_skill_package_artifact(conn, agent, task, infer_skill(f"{task['title']} {task['description']}"), job)
                quality = self._artifact_quality_report(skill_path, "skill-package")
                conn.execute("UPDATE documents SET path=? WHERE id=?", (str(skill_path), row["document_id"]))
                conn.execute("UPDATE company_outputs SET path=? WHERE id=?", (str(skill_path), row["output_id"]))
                conn.execute(
                    """
                    UPDATE publication_queue
                    SET notes=?, updated_at=CURRENT_TIMESTAMP
                    WHERE document_id=? AND target='github-open-source-skill-draft'
                    """,
                    (
                        f"SkillForge 已补齐完整 skill 包；Git 写入必须复制整个目录。质量分={quality['score']:.2f}。",
                        row["document_id"],
                    ),
                )
                self._event(
                    conn,
                    "company.skill_package_repaired",
                    "veritas",
                    {
                        "company_output_id": row["output_id"],
                        "document_id": row["document_id"],
                        "path": str(skill_path),
                        "quality": quality,
                    },
                )
                repaired.append(
                    {
                        "company_output_id": row["output_id"],
                        "document_id": row["document_id"],
                        "path": str(skill_path),
                        "quality": quality["score"],
                    }
                )
        return repaired

    def create_task(
        self,
        title: str,
        description: str,
        reward: int,
        assigned_agent_id: str | None = None,
        assigned_channel_id: str | None = None,
        assigned_role: str | None = None,
        created_by: str = "owner",
    ) -> int:
        if reward <= 0:
            raise ValueError("reward must be positive")
        targets = [assigned_agent_id, assigned_channel_id, assigned_role]
        if len([target for target in targets if target]) != 1:
            raise ValueError("provide exactly one target: agent, group, or role")
        with connect(self.db_path) as conn:
            return self._create_task_in_conn(
                conn,
                title,
                description,
                reward,
                assigned_agent_id=assigned_agent_id,
                assigned_channel_id=assigned_channel_id,
                assigned_role=assigned_role,
                created_by=created_by,
            )

    def _create_task_in_conn(
        self,
        conn,
        title: str,
        description: str,
        reward: int,
        assigned_agent_id: str | None = None,
        assigned_channel_id: str | None = None,
        assigned_role: str | None = None,
        created_by: str = "owner",
        actor_agent_id: str = "atlas",
    ) -> int:
        if assigned_agent_id and not self._exists(conn, "agents", assigned_agent_id):
            raise ValueError(f"unknown agent: {assigned_agent_id}")
        if assigned_channel_id and not self._exists(conn, "channels", assigned_channel_id):
            raise ValueError(f"unknown channel: {assigned_channel_id}")
        if assigned_role:
            count = conn.execute("SELECT COUNT(*) FROM agents WHERE role=?", (assigned_role,)).fetchone()[0]
            if count == 0:
                raise ValueError(f"unknown role: {assigned_role}")
        cur = conn.execute(
            """
            INSERT INTO tasks
              (title, description, reward, assigned_agent_id, assigned_channel_id, assigned_role, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, description, reward, assigned_agent_id, assigned_channel_id, assigned_role, created_by),
        )
        task_id = int(cur.lastrowid)
        self._event(conn, "task.created", actor_agent_id, {"task_id": task_id, "reward": reward, "title": title, "created_by": created_by})
        return task_id

    def send_message(
        self,
        sender_id: str,
        body: str,
        channel_id: str | None = None,
        recipient_id: str | None = None,
    ) -> int:
        if not body.strip():
            raise ValueError("message body cannot be empty")
        if not channel_id and not recipient_id:
            raise ValueError("provide channel or recipient")
        if channel_id and recipient_id:
            raise ValueError("provide channel or recipient, not both")
        with connect(self.db_path) as conn:
            if channel_id and not self._exists(conn, "channels", channel_id):
                raise ValueError(f"unknown channel: {channel_id}")
            if recipient_id and not self._exists(conn, "agents", recipient_id):
                raise ValueError(f"unknown agent: {recipient_id}")
            target_channel = channel_id or "dm"
            cur = conn.execute(
                """
                INSERT INTO messages (channel_id, sender_id, recipient_id, body, sentiment)
                VALUES (?, ?, ?, ?, ?)
                """,
                (target_channel, sender_id, recipient_id, body, self._sentiment(body)),
            )
            msg_id = int(cur.lastrowid)
            self._learn_from_message(conn, sender_id, body, channel_id, recipient_id)
            self._event(conn, "message.sent", sender_id, {"message_id": msg_id, "channel": target_channel})
            return msg_id

    def tick(self, steps: int = 1) -> list[dict[str, Any]]:
        if steps < 1:
            raise ValueError("steps must be >= 1")
        summaries = []
        for _ in range(steps):
            with connect(self.db_path) as conn:
                summary = self._tick_once(conn)
                summaries.append(summary)
        return summaries

    def _tick_once(self, conn) -> dict[str, Any]:
        tick_no = conn.execute("SELECT COUNT(*) FROM world_events WHERE kind='world.tick'").fetchone()[0] + 1
        summary: dict[str, Any] = {
            "tick": tick_no,
            "completed": [],
            "assigned": [],
            "visits": [],
            "learned": [],
            "trained": [],
            "social": [],
            "anger": [],
            "evolved": [],
            "construction": [],
            "autonomousConstruction": [],
            "financeResearch": [],
            "monetaryPolicy": [],
            "company": [],
            "housing": [],
            "survival": [],
            "identity": [],
            "randomFactors": [],
        }
        global_noise = self._ou_value(conn, "world.global", tick_no, sigma=0.012, reversion=0.42, limit=0.035)
        summary["randomFactors"].append(
            {"key": "world.global", "algorithm": "ornstein-uhlenbeck", "value": round(global_noise, 4)}
        )
        agents = conn.execute("SELECT * FROM agents ORDER BY id").fetchall()
        background = [self._apply_background_stochasticity(conn, agent, tick_no) for agent in agents]
        if background:
            summary["randomFactors"].append(
                {
                    "key": "agent.background.avg_abs",
                    "algorithm": "ornstein-uhlenbeck",
                    "value": round(sum(item["abs"] for item in background) / len(background), 4),
                }
            )
        summary["housing"].extend(self._settle_housing_rent(conn, tick_no))
        company_actions = self._maybe_operate_company(conn, tick_no)
        if company_actions:
            summary["company"].extend(company_actions)
        agents = conn.execute("SELECT * FROM agents ORDER BY id").fetchall()
        for agent in agents:
            agent_id = agent["id"]
            if self._is_dead(agent):
                self._emergency_food_rescue(conn, agent, tick_no, summary, revived=True)
                continue
            if self._maybe_survival_action(conn, agent, tick_no, summary):
                continue
            agent = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
            if agent is None or self._is_dead(agent):
                continue
            text_shift = self._maybe_drift_text_profile(conn, agent, tick_no)
            if text_shift:
                summary["identity"].append(text_shift)
            training = self._current_training(conn, agent)
            if training is not None:
                completed_training = self._train_session(conn, agent, training, tick_no)
                if completed_training:
                    summary["trained"].append({"agent": agent_id, "training": training["id"]})
                continue

            if self._maybe_anger_event(conn, agent, tick_no, summary):
                continue

            if self._maybe_emergency_recovery_action(conn, agent, tick_no, summary):
                continue

            if self._maybe_housing_action(conn, agent, tick_no, summary):
                continue

            task = self._current_task(conn, agent)
            if task is None:
                task = self._claim_next_task(conn, agent)
                if task is not None:
                    summary["assigned"].append({"agent": agent_id, "task": task["id"]})

            if task is not None:
                completed = self._work_task(conn, agent, task, tick_no)
                if completed:
                    summary["completed"].append({"agent": agent_id, "task": task["id"]})
                continue

            if self._maybe_visit_venue(conn, agent, summary, tick_no):
                continue
            if self._maybe_social_interaction(conn, agent, tick_no, summary):
                continue
            evolved = self._maybe_evolve_genome(conn, agent, tick_no)
            if evolved:
                summary["evolved"].append({"agent": agent_id, "algorithm": evolved})
            project = self._maybe_autonomous_construction(conn, agent, tick_no)
            if project:
                summary["autonomousConstruction"].append(project)
                continue
            learned = self._maybe_autonomous_research(conn, agent, tick_no)
            if learned:
                summary["learned"].append({"agent": agent_id, "skill": learned})
            report = self._maybe_financial_research(conn, agent, tick_no)
            if report:
                summary["financeResearch"].append({"agent": agent_id, "report": report})
            self._drift_idle(conn, agent, tick_no)

        summary["construction"].extend(self._progress_construction_projects(conn, tick_no))
        policy = self._apply_monetary_policy(conn, tick_no)
        if policy:
            summary["monetaryPolicy"].append(policy)
        self._event(conn, "world.tick", "atlas", summary)
        return summary

    def _is_dead(self, agent) -> bool:
        return str(agent["state"]) in {"starved", "dead"}

    def _maybe_survival_action(self, conn, agent, tick_no: int, summary: dict[str, Any]) -> bool:
        if self._is_dead(agent):
            return True

        needs = self._need_dict(conn, agent["id"])
        stress = self._emotion_dict(conn, agent["id"])["stress"]
        housed = self._agent_residence(conn, agent["id"]) is not None
        work_pressure = 0.018 if agent["current_task_id"] is not None or agent["current_training_id"] is not None else 0.0
        shelter_pressure = 0.009 if not housed else 0.0
        stress_pressure = 0.01 if stress > 0.68 else 0.0
        nutrition_decay = self._jitter_delta(
            conn,
            f"survival.metabolism.{agent['id']}",
            tick_no,
            0.034 + work_pressure + shelter_pressure + stress_pressure,
            0.018,
        )
        self._set_needs(conn, agent["id"], nutrition=-nutrition_decay)
        needs = self._need_dict(conn, agent["id"])

        food_price = self._minimum_food_price(conn)
        if needs["nutrition"] < 0.42:
            self._set_needs(conn, agent["id"], health=-0.018 if needs["nutrition"] < CRITICAL_MEAL_NUTRITION else -0.006, rest=-0.012, safety=-0.018)
            self._set_emotions(conn, agent["id"], stress=0.045, joy=-0.025, anger=0.012)

        if (
            needs["nutrition"] <= STARVATION_NUTRITION
            and needs["health"] <= STARVATION_HEALTH
            and int(agent["credits"]) < food_price
        ):
            if self._emergency_food_rescue(conn, agent, tick_no, summary):
                return True
            self._starve_agent(conn, agent, tick_no, summary, food_price)
            return True

        if needs["nutrition"] >= MEAL_TRIGGER_NUTRITION:
            return False

        food = self._affordable_food_venue(conn, int(agent["credits"]))
        if food is not None:
            self._buy_food(conn, agent, food, tick_no, summary)
            return True

        if needs["nutrition"] <= CRITICAL_MEAL_NUTRITION and self._emergency_food_rescue(conn, agent, tick_no, summary):
            return True

        self._ensure_survival_job(conn, agent, tick_no, food_price)
        if needs["nutrition"] <= MIN_NUTRITION_FOR_WORK:
            self._interrupt_current_task_for_survival(conn, agent["id"], "nutrition")
            conn.execute(
                """
                UPDATE agents
                SET state='starving', mood=?, energy=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (
                    clamp(float(agent["mood"]) - 0.06),
                    clamp(float(agent["energy"]) - 0.05),
                    agent["id"],
                ),
            )
            self._memory(conn, agent["id"], "starving_no_food", -0.72, 0.9, "饱腹度跌破工作红线但没有足够 credits 买饭，只能停止行动并等待求生机会。")
            self._event(conn, "survival.starving", agent["id"], {"nutrition": round(needs["nutrition"], 3), "credits": agent["credits"], "meal_cost": food_price})
            summary["survival"].append({"agent": agent["id"], "action": "starving", "nutrition": round(needs["nutrition"], 3), "meal_cost": food_price})
            return True

        self._event(conn, "survival.job_needed", agent["id"], {"nutrition": round(needs["nutrition"], 3), "credits": agent["credits"], "meal_cost": food_price})
        summary["survival"].append({"agent": agent["id"], "action": "needs_paid_work_for_food", "nutrition": round(needs["nutrition"], 3), "meal_cost": food_price})
        return False

    def _minimum_food_price(self, conn) -> int:
        row = conn.execute("SELECT MIN(price) AS price FROM venues WHERE kind='food' AND price > 0").fetchone()
        return int(row["price"] or 9)

    def _affordable_food_venue(self, conn, credits: int):
        return conn.execute(
            """
            SELECT *
            FROM venues
            WHERE kind='food' AND price > 0 AND price <= ?
            ORDER BY price ASC, energy_delta DESC
            LIMIT 1
            """,
            (credits,),
        ).fetchone()

    def _public_food_payer(self, conn, price: int) -> str | None:
        for payer in ("civic-government", "credit-bank"):
            row = conn.execute("SELECT credits FROM agents WHERE id=? AND state NOT IN ('starved', 'dead')", (payer,)).fetchone()
            if row is not None and int(row["credits"]) >= price:
                return payer
        return None

    def _emergency_food_rescue(self, conn, agent, tick_no: int, summary: dict[str, Any], revived: bool = False) -> bool:
        venue = conn.execute("SELECT * FROM venues WHERE kind='food' AND price > 0 ORDER BY price ASC LIMIT 1").fetchone()
        if venue is None:
            return False
        price = int(venue["price"])
        payer = self._public_food_payer(conn, price)
        if payer is None:
            return False

        self._interrupt_current_task_for_survival(conn, agent["id"], "emergency_food_rescue")
        self._credit(conn, payer, -price, "public_food_rescue", "agent", agent["id"])
        conn.execute(
            "INSERT INTO visits (agent_id, venue_id, cost) VALUES (?, ?, ?)",
            (agent["id"], venue["id"], price),
        )
        current = self._need_dict(conn, agent["id"])
        conn.execute(
            """
            UPDATE agent_needs
            SET nutrition=?, health=?, rest=?, fun=?, safety=?, updated_at=CURRENT_TIMESTAMP
            WHERE agent_id=?
            """,
            (
                max(float(current.get("nutrition", 0.0)), EMERGENCY_FOOD_NUTRITION_FLOOR),
                max(float(current.get("health", 0.0)), EMERGENCY_FOOD_HEALTH_FLOOR),
                max(float(current.get("rest", 0.0)), 0.24),
                max(float(current.get("fun", 0.0)), 0.08),
                max(float(current.get("safety", 0.0)), 0.34),
                agent["id"],
            ),
        )
        self._set_emotions(conn, agent["id"], stress=-0.35, anger=-0.1, joy=0.08, confidence=0.04, loneliness=-0.04)
        conn.execute(
            """
            UPDATE agents
            SET current_task_id=NULL, current_training_id=NULL, state=?, mood=?, energy=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (
                "recovering" if revived else "eating",
                max(clamp(float(agent["mood"]) + 0.12), 0.24),
                max(clamp(float(agent["energy"]) + 0.16), 0.28),
                agent["id"],
            ),
        )
        self._ensure_survival_job(conn, agent, tick_no, price, allow_unfit=True)
        self._memory(
            conn,
            agent["id"],
            "emergency_food_rescue",
            0.18 if revived else 0.12,
            0.9,
            f"政府/银行使用 {price} agent-credits 应急饭票让 {agent['name']} 先活下来，之后再通过合法临工补回生存现金流。",
        )
        self._event(
            conn,
            "survival.emergency_food_rescue",
            agent["id"],
            {"venue": venue["id"], "cost": price, "payer": payer, "revived": revived},
        )
        summary["survival"].append(
            {"agent": agent["id"], "action": "emergency_food_rescue", "venue": venue["id"], "cost": price, "payer": payer, "revived": revived}
        )
        return True

    def _survival_reserve(self, conn, agent) -> int:
        reserve = self._minimum_food_price(conn) * FOOD_RESERVE_MEALS
        residence = self._agent_residence(conn, agent["id"])
        if residence is not None and int(residence["monthly_rent"] or 0) > 0:
            current_tick = self._current_tick(conn)
            due_in = 30 - (current_tick - int(residence["last_rent_tick"] or 0))
            if due_in <= 5:
                reserve += int(residence["monthly_rent"])
        return reserve

    def _buy_food(self, conn, agent, venue, tick_no: int, summary: dict[str, Any]) -> None:
        price = int(venue["price"])
        self._credit(conn, agent["id"], -price, "food_meal", "venue", venue["id"])
        conn.execute(
            "INSERT INTO visits (agent_id, venue_id, cost) VALUES (?, ?, ?)",
            (agent["id"], venue["id"], price),
        )
        nutrition_gain = self._jitter_delta(conn, f"food.nutrition.{agent['id']}.{venue['id']}", tick_no, 0.42 if price <= 10 else 0.52, 0.045)
        mood_delta = self._jitter_delta(conn, f"food.mood.{agent['id']}.{venue['id']}", tick_no, venue["mood_delta"], 0.035)
        energy_delta = self._jitter_delta(conn, f"food.energy.{agent['id']}.{venue['id']}", tick_no, venue["energy_delta"], 0.035)
        self._set_needs(conn, agent["id"], nutrition=nutrition_gain, health=0.035, rest=0.018, safety=0.018)
        self._set_emotions(conn, agent["id"], joy=mood_delta, stress=-0.055, anger=-0.025, confidence=0.015)
        conn.execute(
            """
            UPDATE agents
            SET state='eating', mood=?, energy=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (clamp(float(agent["mood"]) + mood_delta), clamp(float(agent["energy"]) + energy_delta), agent["id"]),
        )
        if venue["skill_tag"]:
            self._upsert_skill(conn, agent["id"], venue["skill_tag"], 0.02, "food", venue["name"], tick_no)
        self._memory(conn, agent["id"], "meal", 0.24, 0.58, f"花费 {price} agent-credits 在 {venue['name']} 吃饭，先把自己活下来。")
        self._event(conn, "survival.ate_meal", agent["id"], {"venue": venue["id"], "cost": price, "nutrition_gain": round(nutrition_gain, 3)})
        summary["survival"].append({"agent": agent["id"], "action": "ate_meal", "venue": venue["id"], "cost": price})

    def _ensure_survival_job(self, conn, agent, tick_no: int, meal_cost: int, allow_unfit: bool = False) -> int | None:
        existing = conn.execute(
            """
            SELECT id
            FROM tasks
            WHERE status IN ('open', 'in_progress')
              AND assigned_agent_id=?
              AND created_by='civic-survival'
            ORDER BY id DESC
            LIMIT 1
            """,
            (agent["id"],),
        ).fetchone()
        if existing is not None:
            return int(existing["id"])
        if not allow_unfit and self._is_unfit_for_work(conn, agent, ignore_nutrition=True):
            return None
        reward = max(SURVIVAL_JOB_REWARD, meal_cost * 5)
        task_id = self._create_task_in_conn(
            conn,
            f"{agent['name']}：求生临工",
            "饱腹度和现金储备过低，优先完成一个低门槛合法临工来支付下一餐和基本住宿压力。",
            reward,
            assigned_agent_id=agent["id"],
            created_by="civic-survival",
            actor_agent_id="civic-government",
        )
        self._event(conn, "survival.job_created", agent["id"], {"task_id": task_id, "reward": reward, "meal_cost": meal_cost})
        return task_id

    def _interrupt_current_task_for_survival(self, conn, agent_id: str, reason: str) -> None:
        row = conn.execute("SELECT current_task_id FROM agents WHERE id=?", (agent_id,)).fetchone()
        if row is None or row["current_task_id"] is None:
            return
        task_id = int(row["current_task_id"])
        task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if task is not None and task["status"] in ("open", "in_progress"):
            conn.execute("UPDATE tasks SET status='open', updated_at=CURRENT_TIMESTAMP WHERE id=?", (task_id,))
        conn.execute("UPDATE agents SET current_task_id=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?", (agent_id,))
        self._event(conn, "work.interrupted_for_survival", agent_id, {"task_id": task_id, "reason": reason})

    def _starve_agent(self, conn, agent, tick_no: int, summary: dict[str, Any], meal_cost: int) -> None:
        self._interrupt_current_task_for_survival(conn, agent["id"], "starved")
        conn.execute(
            """
            UPDATE agents
            SET current_task_id=NULL, current_training_id=NULL, state='starved',
                mood=0, energy=0, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (agent["id"],),
        )
        current = self._need_dict(conn, agent["id"])
        conn.execute(
            """
            UPDATE agent_needs
            SET rest=0, social=?, fun=0, purpose=0, safety=0, health=0, nutrition=0,
                updated_at=CURRENT_TIMESTAMP
            WHERE agent_id=?
            """,
            (current.get("social", 0.0), agent["id"]),
        )
        self._set_emotions(conn, agent["id"], joy=-1.0, anger=-0.2, stress=0.2, confidence=-1.0, loneliness=0.12, curiosity=-0.4)
        self._memory(conn, agent["id"], "starved", -1.0, 1.0, f"因为没有足够 credits 支付 {meal_cost} agent-credits 的最低餐食，最终饿死/失活。")
        self._event(conn, "survival.starved", agent["id"], {"meal_cost": meal_cost, "tick": tick_no})
        summary["survival"].append({"agent": agent["id"], "action": "starved", "meal_cost": meal_cost})

    def _current_training(self, conn, agent) -> Any | None:
        training_id = agent["current_training_id"]
        if training_id is None:
            return None
        training = conn.execute("SELECT * FROM training_sessions WHERE id=?", (training_id,)).fetchone()
        if training is None or training["status"] != "in_progress":
            conn.execute(
                "UPDATE agents SET current_training_id=NULL, state='idle', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (agent["id"],),
            )
            return None
        return training

    def _apply_background_stochasticity(self, conn, agent, tick_no: int) -> dict[str, float]:
        mood_delta = self._random_delta(conn, f"agent.background.mood.{agent['id']}", tick_no, 0.006)
        energy_delta = self._random_delta(conn, f"agent.background.energy.{agent['id']}", tick_no, 0.005)
        x_delta = self._random_delta(conn, f"agent.background.x.{agent['id']}", tick_no, 0.008)
        y_delta = self._random_delta(conn, f"agent.background.y.{agent['id']}", tick_no, 0.008)
        conn.execute(
            """
            UPDATE agents
            SET mood=?, energy=?, x=?, y=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (
                clamp(agent["mood"] + mood_delta),
                clamp(agent["energy"] + energy_delta),
                clamp(agent["x"] + x_delta, 0.06, 0.94),
                clamp(agent["y"] + y_delta, 0.06, 0.94),
                agent["id"],
            ),
        )
        stress_delta = self._random_delta(conn, f"agent.background.stress.{agent['id']}", tick_no, 0.004)
        curiosity_delta = self._random_delta(conn, f"agent.background.curiosity.{agent['id']}", tick_no, 0.004)
        health_delta = self._random_delta(conn, f"agent.background.health.{agent['id']}", tick_no, 0.003)
        self._set_emotions(
            conn,
            agent["id"],
            joy=mood_delta * 0.7,
            stress=stress_delta - mood_delta * 0.25,
            curiosity=curiosity_delta,
        )
        self._set_needs(
            conn,
            agent["id"],
            fun=mood_delta * 0.45,
            rest=energy_delta * 0.6,
            health=health_delta,
            safety=-abs(stress_delta) * 0.35,
        )
        return {
            "abs": abs(mood_delta) + abs(energy_delta) + abs(x_delta) + abs(y_delta) + abs(stress_delta) + abs(health_delta),
        }

    def _train_session(self, conn, agent, training, tick_no: int) -> bool:
        program = conn.execute("SELECT * FROM training_programs WHERE id=?", (training["program_id"],)).fetchone()
        if program is None:
            return True
        emotion = self._emotion_dict(conn, agent["id"])
        effort_factor = self._random_factor(conn, f"training.effort.{agent['id']}.{training['id']}", tick_no, 0.065)
        effort = max(1.0, (18 + agent["energy"] * 14 + emotion["curiosity"] * 8 - emotion["stress"] * 5) * effort_factor)
        new_progress = min(100.0, training["progress"] + effort / max(1, program["duration_ticks"] / 3))
        conn.execute("UPDATE training_sessions SET progress=? WHERE id=?", (new_progress, training["id"]))
        self._set_needs(
            conn,
            agent["id"],
            rest=-0.055 * program["intensity"],
            social=-0.015,
            fun=-0.025,
            purpose=0.045,
            health=-0.012 * program["intensity"],
            nutrition=-0.018 * program["intensity"],
        )
        self._set_emotions(
            conn,
            agent["id"],
            joy=program["mood_delta"] * 0.4,
            stress=0.035 * program["intensity"],
            confidence=0.025,
        )
        conn.execute(
            "UPDATE agents SET energy=?, mood=?, state='training', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (
                clamp(agent["energy"] + self._jitter_delta(conn, f"training.energy.{agent['id']}", tick_no, program["energy_delta"], 0.045)),
                clamp(agent["mood"] + self._jitter_delta(conn, f"training.mood.{agent['id']}", tick_no, program["mood_delta"], 0.045)),
                agent["id"],
            ),
        )
        if new_progress < 100:
            return False
        self._upsert_skill(
            conn,
            agent["id"],
            program["target_skill"],
            0.22 + program["intensity"] * 0.12,
            "training",
            program["name"],
            tick_no,
        )
        conn.execute(
            """
            UPDATE training_sessions
            SET status='done', progress=100, completed_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (training["id"],),
        )
        conn.execute(
            """
            UPDATE agents
            SET current_training_id=NULL, state='trained', mood=?, energy=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (
                clamp(agent["mood"] + self._jitter_delta(conn, f"training.complete.mood.{agent['id']}", tick_no, 0.08, 0.04)),
                clamp(agent["energy"] + self._jitter_delta(conn, f"training.complete.energy.{agent['id']}", tick_no, 0.04, 0.04)),
                agent["id"],
            ),
        )
        self._memory(conn, agent["id"], "training_completed", 0.35, 0.68, f"完成训练：{program['name']}。")
        self._event(
            conn,
            "training.completed",
            agent["id"],
            {"training_id": training["id"], "skill": program["target_skill"]},
        )
        return True

    def _current_task(self, conn, agent) -> Any | None:
        task_id = agent["current_task_id"]
        if task_id is None:
            return None
        task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if task is None or task["status"] not in ("open", "in_progress"):
            conn.execute(
                "UPDATE agents SET current_task_id=NULL, state='idle', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (agent["id"],),
            )
            return None
        if self._is_unfit_for_work(conn, agent):
            conn.execute("UPDATE tasks SET status='open', updated_at=CURRENT_TIMESTAMP WHERE id=?", (task["id"],))
            conn.execute(
                "UPDATE agents SET current_task_id=NULL, state='recovering', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (agent["id"],),
            )
            self._event(conn, "work.blocked_medical", agent["id"], {"task_id": task["id"]})
            return None
        if str(task["created_by"]).startswith("company:") and self._matching_owner_task(conn, agent) is not None:
            conn.execute("UPDATE tasks SET status='open', updated_at=CURRENT_TIMESTAMP WHERE id=?", (task["id"],))
            conn.execute(
                "UPDATE agents SET current_task_id=NULL, state='idle', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (agent["id"],),
            )
            self._event(conn, "company.job_preempted", agent["id"], {"task_id": task["id"]})
            return None
        return task

    def _claimable_assigned_roles(self, role: str) -> tuple[str, ...]:
        return ROLE_TASK_COMPATIBILITY.get(role, (role,))

    def _is_unfit_for_work(self, conn, agent, ignore_nutrition: bool = False) -> bool:
        needs = self._need_dict(conn, agent["id"])
        emotion = self._emotion_dict(conn, agent["id"])
        return (
            self._is_dead(agent)
            or needs["health"] < MIN_HEALTH_FOR_WORK
            or (not ignore_nutrition and needs.get("nutrition", 1.0) < MIN_NUTRITION_FOR_WORK)
            or emotion["stress"] > MAX_STRESS_FOR_WORK
            or float(agent["mood"]) < MIN_MOOD_FOR_WORK
        )

    def _matching_owner_task(self, conn, agent) -> Any | None:
        membership_ids = [
            row["channel_id"]
            for row in conn.execute("SELECT channel_id FROM memberships WHERE agent_id=?", (agent["id"],))
        ]
        if not membership_ids:
            membership_ids = ["__none__"]
        role_targets = self._claimable_assigned_roles(agent["role"])
        return conn.execute(
            """
            SELECT * FROM tasks
            WHERE status='open'
              AND created_by NOT LIKE 'company:%'
              AND (
                assigned_agent_id=?
                OR assigned_role IN ({})
                OR assigned_channel_id IN ({})
              )
            ORDER BY reward DESC, id ASC
            LIMIT 1
            """.format(",".join("?" for _ in role_targets), ",".join("?" for _ in membership_ids)),
            (agent["id"], *role_targets, *membership_ids),
        ).fetchone()

    def _claim_next_task(self, conn, agent) -> Any | None:
        if self._is_unfit_for_work(conn, agent):
            self._event(conn, "work.claim_blocked_medical", agent["id"], {"role": agent["role"]})
            return None
        membership_ids = [
            row["channel_id"]
            for row in conn.execute("SELECT channel_id FROM memberships WHERE agent_id=?", (agent["id"],))
        ]
        if agent["role"] == "top_planner" and self._governance_state(conn)["topAgentMode"] == "stand_down":
            task = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status='open' AND (assigned_agent_id=? OR assigned_role='top_planner')
                ORDER BY CASE WHEN created_by LIKE 'company:%' THEN 1 ELSE 0 END, reward DESC, id ASC
                LIMIT 1
                """,
                (agent["id"],),
            ).fetchone()
        else:
            role_targets = self._claimable_assigned_roles(agent["role"])
            task = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status='open'
                  AND (
                    assigned_agent_id=?
                    OR assigned_role IN ({})
                    OR assigned_channel_id IN ({})
                  )
                ORDER BY CASE WHEN created_by LIKE 'company:%' THEN 1 ELSE 0 END, reward DESC, id ASC
                LIMIT 1
                """.format(",".join("?" for _ in role_targets), ",".join("?" for _ in membership_ids) or "NULL"),
                (agent["id"], *role_targets, *membership_ids),
            ).fetchone()
        if task is None:
            return None
        conn.execute(
            "UPDATE tasks SET status='in_progress', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (task["id"],),
        )
        conn.execute(
            """
            UPDATE agents
            SET current_task_id=?, state='working', mood=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (task["id"], clamp(agent["mood"] + 0.02), agent["id"]),
        )
        self._event(conn, "task.claimed", agent["id"], {"task_id": task["id"]})
        return conn.execute("SELECT * FROM tasks WHERE id=?", (task["id"],)).fetchone()

    def _governance_state(self, conn) -> dict[str, Any]:
        done_tasks = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='done'").fetchone()[0]
        approved_docs = conn.execute("SELECT COUNT(*) FROM documents WHERE judge_status='approved'").fetchone()[0]
        research_runs = conn.execute("SELECT COUNT(*) FROM research_runs").fetchone()[0]
        maturity_score = done_tasks * 2 + approved_docs + research_runs
        mode = "stand_down" if maturity_score >= 8 else "bootstrap"
        return {
            "topAgentId": "atlas",
            "topAgentMode": mode,
            "maturityScore": maturity_score,
            "standDownThreshold": 8,
        }

    def _maybe_operate_company(self, conn, tick_no: int) -> list[dict[str, Any]]:
        if self._governance_state(conn)["topAgentMode"] != "stand_down":
            return []
        actions: list[dict[str, Any]] = []
        company = conn.execute("SELECT * FROM companies WHERE id='skillforge-company'").fetchone()
        if company is None:
            conn.execute(
                """
                INSERT INTO companies
                  (id, name, kind, founder_agent_id, treasury_credits, status, mission, demand_score)
                VALUES (
                  'skillforge-company',
                  'SkillForge 开源技能公司',
                  'skill-article-persona-lab',
                  'atlas',
                  3000,
                  'active',
                  '稳定生产各行业 skill、文章、材料研究和女娲式人物技能蒸馏，审判有效后进入开源发布队列。',
                  0.72
                )
                """
            )
            self._event(conn, "company.founded", "atlas", {"company_id": "skillforge-company", "name": "SkillForge 开源技能公司"})
            actions.append({"company": "skillforge-company", "action": "founded"})
            company = conn.execute("SELECT * FROM companies WHERE id='skillforge-company'").fetchone()

        open_jobs = conn.execute(
            "SELECT COUNT(*) FROM company_jobs WHERE company_id=? AND status IN ('open', 'in_progress')",
            (company["id"],),
        ).fetchone()[0]
        workforce_action = self._maybe_expand_company_research_workforce(conn, company, tick_no)
        if workforce_action:
            actions.append(workforce_action)

        owner_work = conn.execute(
            """
            SELECT COUNT(*)
            FROM tasks
            WHERE status IN ('open', 'in_progress') AND created_by NOT LIKE 'company:%'
            """
        ).fetchone()[0]
        if owner_work:
            return actions
        if open_jobs >= 4:
            return actions
        if (tick_no + open_jobs) % 2 != 0 and open_jobs > 0:
            return actions
        need = self._next_material_need(conn, company["id"], tick_no)
        if need is None:
            return actions
        output_types = ["skill-package", "industry-article", "persona-distillation", "material-research"]
        output_type = output_types[(tick_no + int(need["id"])) % len(output_types)]
        role = {
            "skill-package": "engineer",
            "industry-article": "documentarian",
            "persona-distillation": "researcher",
            "material-research": "researcher",
        }[output_type]
        reward = int(round((72 + float(need["demand_score"]) * 88) * self._random_factor(conn, f"company.reward.{need['id']}.{tick_no}", tick_no, 0.05)))
        title = f"{need['industry']}：{self._zh_output_type(output_type)}"
        description = (
            f"公司需求：{need['topic']}。请产出中文可复用资产，要求能沉淀为 skill、文章、材料清单或人物技能蒸馏；"
            "通过 Veritas 审判且有效后，奖励额外 agent-credits，并进入 GitHub 开源仓库草稿队列，真正外发仍需人类确认。"
        )
        task_id = self._create_task_in_conn(
            conn,
            title,
            description,
            reward,
            assigned_role=role,
            created_by=f"company:{company['id']}",
            actor_agent_id="skillforge-company",
        )
        cur = conn.execute(
            """
            INSERT INTO company_jobs
              (company_id, title, industry, output_type, reward, task_id, status, publication_target)
            VALUES (?, ?, ?, ?, ?, ?, 'open', ?)
            """,
            (company["id"], title, need["industry"], output_type, reward, task_id, self._publication_target_for_output(output_type)),
        )
        job_id = int(cur.lastrowid)
        conn.execute(
            """
            UPDATE material_needs
            SET company_id=?, demand_score=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (company["id"], clamp(float(need["demand_score"]) - 0.035, 0.35, 1.0), need["id"]),
        )
        self._event(conn, "company.job_created", "skillforge-company", {"company_id": company["id"], "job_id": job_id, "task_id": task_id, "industry": need["industry"], "output_type": output_type, "reward": reward})
        actions.append({"company": company["id"], "action": "job_created", "job": job_id, "task": task_id, "industry": need["industry"], "output_type": output_type})
        return actions

    def _maybe_expand_company_research_workforce(self, conn, company, tick_no: int) -> dict[str, Any] | None:
        backlog = conn.execute(
            """
            SELECT COUNT(*)
            FROM tasks
            WHERE status IN ('open', 'in_progress')
              AND created_by=?
              AND assigned_role='researcher'
            """,
            (f"company:{company['id']}",),
        ).fetchone()[0]
        if int(backlog) < 2:
            return None
        researcher_count = conn.execute("SELECT COUNT(*) FROM agents WHERE role='researcher'").fetchone()[0]
        healthy_available = conn.execute(
            """
            SELECT COUNT(*)
            FROM agents a
            JOIN agent_needs n ON n.agent_id=a.id
            JOIN agent_emotions e ON e.agent_id=a.id
            WHERE a.role IN ('researcher', 'documentarian', 'nuwa_perspective')
              AND a.current_task_id IS NULL
              AND n.health >= ?
              AND e.stress <= ?
              AND a.mood >= ?
            """,
            (MIN_HEALTH_FOR_WORK, MAX_STRESS_FOR_WORK, MIN_MOOD_FOR_WORK),
        ).fetchone()[0]
        target_researchers = min(4, max(2, int(backlog)))
        if int(researcher_count) >= target_researchers and int(healthy_available) >= 1:
            return None
        existing = conn.execute(
            "SELECT id FROM agents WHERE id LIKE 'nuwa-researcher-%' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if existing is not None and (tick_no % 6) != 0:
            return None
        child_id = self._create_company_researcher_in_conn(conn, tick_no)
        self._event(
            conn,
            "company.researcher_spawned",
            "skillforge-company",
            {
                "agent_id": child_id,
                "backlog": int(backlog),
                "researcher_count_before": int(researcher_count),
                "healthy_available": int(healthy_available),
            },
        )
        return {
            "company": company["id"],
            "action": "researcher_spawned",
            "agent": child_id,
            "backlog": int(backlog),
        }

    def _create_company_researcher_in_conn(self, conn, tick_no: int) -> str:
        blueprint = conn.execute("SELECT * FROM agent_blueprints WHERE id='researcher'").fetchone()
        if blueprint is None:
            raise ValueError("researcher blueprint is missing")
        suffix = conn.execute("SELECT COUNT(*) FROM agents WHERE role='researcher'").fetchone()[0] + 1
        agent_id = slugify(f"nuwa-researcher-{suffix}")
        while conn.execute("SELECT 1 FROM agents WHERE id=?", (agent_id,)).fetchone() is not None:
            suffix += 1
            agent_id = slugify(f"nuwa-researcher-{suffix}")
        personality = json_loads(blueprint["default_personality_json"], {})
        personality.update(
            {
                "curiosity": max(0.78, float(personality.get("curiosity", 0.55))),
                "greed": max(0.7, float(personality.get("greed", 0.62))),
                "sociability": max(0.58, float(personality.get("sociability", 0.5))),
                "native_language": "zh-CN",
                "origin": "company-workforce-incubation",
            }
        )
        row_count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        x = 0.16 + ((row_count * 13) % 74) / 100
        y = 0.16 + ((row_count * 23) % 74) / 100
        conn.execute(
            """
            INSERT INTO agents
              (id, owner_id, name, role, archetype, personality_json, mood, energy, credits, autonomy, state, x, y)
            VALUES (?, 'local-owner', ?, 'researcher', ?, ?, 0.68, 0.82, 120, 0.72, 'incubating', ?, ?)
            """,
            (
                agent_id,
                f"Nuwa Researcher {suffix}",
                blueprint["archetype"],
                json_dumps(personality),
                x,
                y,
            ),
        )
        seed_agent_life_state(conn)
        for channel in ("plaza", "research", "leisure"):
            conn.execute("INSERT OR IGNORE INTO memberships (channel_id, agent_id) VALUES (?, ?)", (channel, agent_id))
        for skill in json_loads(blueprint["base_skills_json"], []):
            conn.execute(
                "INSERT OR IGNORE INTO skills (agent_id, name, level, source, notes) VALUES (?, ?, ?, 'company-incubation', ?)",
                (agent_id, skill["name"], max(0.42, float(skill.get("level", 0.35))), "Spawned to relieve researcher backlog."),
            )
        for name, level in (("persona-distillation", 0.5), ("material-research", 0.48), ("source-triangulation", 0.52)):
            self._upsert_skill(conn, agent_id, name, level, "company-incubation", "Research backlog relief", tick_no)
        parents = [
            row["id"]
            for row in conn.execute(
                """
                SELECT id
                FROM agents
                WHERE id IN ('lumen', 'mira', 'karpathy-lens', 'munger-lens')
                ORDER BY CASE id WHEN 'lumen' THEN 0 WHEN 'mira' THEN 1 ELSE 2 END
                LIMIT 2
                """
            )
        ]
        if len(parents) >= 2:
            conn.execute(
                """
                INSERT OR REPLACE INTO agent_lineage
                  (child_agent_id, parent_ids_json, method, mutation_rate, inherited_skills_json, cost)
                VALUES (?, ?, 'company-nuwa-incubation', 0.06, ?, 0)
                """,
                (
                    agent_id,
                    json_dumps(parents),
                    json_dumps(
                        [
                            {"name": "research", "level": 0.52},
                            {"name": "source-triangulation", "level": 0.52},
                            {"name": "persona-distillation", "level": 0.5},
                        ]
                    ),
                ),
            )
        self._memory(conn, agent_id, "company_incubated_researcher", 0.36, 0.76, "研究任务积压时由 SkillForge 通过女娲式劳动力孵化补充研究员。")
        self._event(conn, "agent.created", agent_id, {"owner": "local-owner", "blueprint": "researcher", "reason": "research_backlog"})
        return agent_id

    def _next_material_need(self, conn, company_id: str, tick_no: int) -> Any | None:
        rows = conn.execute(
            """
            SELECT *
            FROM material_needs
            WHERE status='open'
            ORDER BY demand_score DESC, id
            LIMIT 12
            """
        ).fetchall()
        if not rows:
            return None
        return rows[tick_no % len(rows)]

    def _maybe_complete_company_job(self, conn, agent, task, document_id: int, tick_no: int) -> None:
        job = conn.execute(
            "SELECT * FROM company_jobs WHERE task_id=? AND status IN ('open', 'in_progress') ORDER BY id DESC LIMIT 1",
            (task["id"],),
        ).fetchone()
        if job is None:
            return
        doc = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if doc is None:
            return
        skill_avg = conn.execute("SELECT AVG(level) FROM skills WHERE agent_id=?", (agent["id"],)).fetchone()[0] or 0.35
        quality = self._artifact_quality_report(Path(doc["path"]), job["output_type"])
        skill_component = max(float(skill_avg), 0.55) if job["output_type"] == "skill-package" else float(skill_avg)
        base_effectiveness = clamp(
            (float(doc["usefulness_score"]) / 100.0) * 0.68
            + skill_component * 0.10
            + quality["score"] * 0.22
            + self._random_delta(conn, f"company.effectiveness.{job['id']}", tick_no, 0.025)
        )
        min_effectiveness = COMPANY_OUTPUT_MIN_EFFECTIVENESS.get(job["output_type"], 0.74)
        effectiveness = base_effectiveness
        accepted = effectiveness >= min_effectiveness and doc["judge_status"] == "approved" and quality["passed"]
        reward = 0
        status = "needs_revision"
        publication_id = None
        if accepted:
            reward = max(8, int(round((18 + effectiveness * 68) * self._random_factor(conn, f"company.output.reward.{job['id']}", tick_no, 0.06))))
            self._credit(conn, agent["id"], reward, "company_effective_output_reward", "company_job", str(job["id"]))
            self._upsert_skill(conn, agent["id"], f"company-{job['output_type']}", 0.09 + effectiveness * 0.04, "company-output", job["industry"], tick_no)
            cur = conn.execute(
                """
                INSERT INTO publication_queue (document_id, target, notes)
                VALUES (?, ?, ?)
                """,
                (
                    document_id,
                    job["publication_target"],
                    f"SkillForge 严格质检通过；质量分={quality['score']:.2f}，有效度={effectiveness:.2f}。Git 写入必须复制整个产物目录，外部发布仍需人类确认。",
                ),
            )
            publication_id = int(cur.lastrowid)
            status = "accepted"
        cur = conn.execute(
            """
            INSERT INTO company_outputs
              (company_id, job_id, agent_id, output_type, industry, title, path, effectiveness_score, reward, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job["company_id"],
                job["id"],
                agent["id"],
                job["output_type"],
                job["industry"],
                doc["title"],
                doc["path"],
                effectiveness,
                reward,
                status,
            ),
        )
        output_id = int(cur.lastrowid)
        conn.execute(
            """
            UPDATE company_jobs
            SET assigned_agent_id=?, document_id=?, status=?, effectiveness_score=?, completed_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (agent["id"], document_id, "done" if accepted else "needs_revision", effectiveness, job["id"]),
        )
        self._event(
            conn,
            "company.output_accepted" if accepted else "company.output_rejected",
            agent["id"],
            {
                "company_id": job["company_id"],
                "job_id": job["id"],
                "output_id": output_id,
                "effectiveness": round(effectiveness, 3),
                "minimum_effectiveness": min_effectiveness,
                "quality": quality,
                "reward": reward,
                "publication_queue_id": publication_id,
            },
        )

    def _settle_housing_rent(self, conn, tick_no: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT *
            FROM residences
            WHERE status='rented' AND occupant_agent_id IS NOT NULL AND monthly_rent > 0
            ORDER BY id
            """
        ).fetchall()
        actions: list[dict[str, Any]] = []
        for row in rows:
            if tick_no - int(row["last_rent_tick"] or 0) < 30:
                continue
            occupant = conn.execute("SELECT * FROM agents WHERE id=?", (row["occupant_agent_id"],)).fetchone()
            if occupant is None:
                continue
            rent = int(row["monthly_rent"])
            if int(occupant["credits"]) >= rent:
                self._credit(conn, occupant["id"], -rent, "housing_monthly_rent", "residence", str(row["id"]))
                if row["owner_agent_id"]:
                    self._credit(conn, row["owner_agent_id"], rent, "housing_rent_income", "residence", str(row["id"]))
                conn.execute("UPDATE residences SET last_rent_tick=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (tick_no, row["id"]))
                self._set_needs(conn, occupant["id"], safety=0.03)
                self._event(
                    conn,
                    "housing.rent_paid",
                    occupant["id"],
                    {"residence_id": row["id"], "owner": row["owner_agent_id"], "rent": rent},
                )
                actions.append({"agent": occupant["id"], "residence": row["id"], "action": "rent_paid", "amount": rent})
                continue
            conn.execute(
                """
                UPDATE residences
                SET occupant_agent_id=NULL, status='for_rent', updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (row["id"],),
            )
            self._set_needs(conn, occupant["id"], safety=-0.22, rest=-0.14)
            self._set_emotions(conn, occupant["id"], stress=0.16, anger=0.08, joy=-0.08)
            self._memory(conn, occupant["id"], "housing_evicted", -0.5, 0.82, f"因无法支付 {rent} agent-credits 月租，被 {row['name']} 退租。")
            self._event(conn, "housing.evicted", occupant["id"], {"residence_id": row["id"], "rent": rent})
            actions.append({"agent": occupant["id"], "residence": row["id"], "action": "evicted", "amount": rent})
        return actions

    def _maybe_emergency_recovery_action(self, conn, agent, tick_no: int, summary: dict[str, Any]) -> bool:
        needs = self._need_dict(conn, agent["id"])
        emotion = self._emotion_dict(conn, agent["id"])
        critical_health = needs["health"] < MIN_HEALTH_FOR_WORK
        critical_emotion = float(agent["mood"]) < MIN_MOOD_FOR_WORK or emotion["stress"] > MAX_STRESS_FOR_WORK
        if not critical_health and not critical_emotion:
            return False

        task_id = agent["current_task_id"]
        if task_id is not None:
            task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if task is not None and task["status"] in ("open", "in_progress"):
                conn.execute("UPDATE tasks SET status='open', updated_at=CURRENT_TIMESTAMP WHERE id=?", (task_id,))
                self._event(conn, "work.interrupted_for_recovery", agent["id"], {"task_id": task_id})

        if critical_health:
            venue = conn.execute("SELECT * FROM venues WHERE kind='hospital' ORDER BY price ASC LIMIT 1").fetchone()
            if venue is not None:
                price = int(venue["price"])
                if int(agent["credits"]) >= price:
                    self._credit(conn, agent["id"], -price, "venue_spend", "venue", venue["id"])
                    payer = agent["id"]
                else:
                    payer = "civic-government"
                    government = conn.execute("SELECT * FROM agents WHERE id='civic-government'").fetchone()
                    if government is not None and int(government["credits"]) >= price:
                        self._credit(conn, "civic-government", -price, "public_health_subsidy", "agent", agent["id"])
                    else:
                        self._credit(conn, agent["id"], price, "public_health_grant", "venue", venue["id"])
                        self._credit(conn, agent["id"], -price, "venue_spend", "venue", venue["id"])
                        payer = "public_health_grant"
                conn.execute(
                    "INSERT INTO visits (agent_id, venue_id, cost) VALUES (?, ?, ?)",
                    (agent["id"], venue["id"], price),
                )
                self._set_needs(conn, agent["id"], health=0.42, rest=0.18, fun=0.08, safety=0.1)
                self._set_emotions(conn, agent["id"], stress=-0.32, anger=-0.12, joy=0.08, confidence=0.06)
                conn.execute(
                    """
                    UPDATE agents
                    SET current_task_id=NULL, state='recovering', mood=?, energy=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (
                        clamp(float(agent["mood"]) + self._jitter_delta(conn, f"emergency.mood.{agent['id']}", tick_no, 0.08, 0.035)),
                        clamp(float(agent["energy"]) + self._jitter_delta(conn, f"emergency.energy.{agent['id']}", tick_no, 0.1, 0.035)),
                        agent["id"],
                    ),
                )
                self._memory(conn, agent["id"], "emergency_care", 0.24, 0.82, f"健康低于工作红线，被送到 {venue['name']} 恢复。")
                self._event(
                    conn,
                    "health.emergency_care",
                    agent["id"],
                    {"venue": venue["id"], "price": price, "payer": payer, "health_before": round(needs["health"], 3)},
                )
                summary["visits"].append({"agent": agent["id"], "venue": venue["id"], "emergency": True})
                return True

        residence = self._agent_residence(conn, agent["id"])
        if residence is not None:
            self._rest_at_home(conn, agent, residence, tick_no)
            summary["housing"].append({"agent": agent["id"], "residence": residence["id"], "action": "forced_rest"})
            self._event(conn, "health.forced_home_rest", agent["id"], {"stress": emotion["stress"], "mood": agent["mood"]})
            return True
        return False

    def _maybe_housing_action(self, conn, agent, tick_no: int, summary: dict[str, Any]) -> bool:
        if agent["owner_id"] == "world-system" and agent["id"] != "city-guard":
            return False
        if agent["current_task_id"] is not None:
            return False
        needs = self._need_dict(conn, agent["id"])
        emotion = self._emotion_dict(conn, agent["id"])
        residence = self._agent_residence(conn, agent["id"])
        if residence is not None and (agent["energy"] < 0.42 or needs["rest"] < 0.42 or emotion["stress"] > 0.72):
            self._rest_at_home(conn, agent, residence, tick_no)
            summary["housing"].append({"agent": agent["id"], "residence": residence["id"], "action": "rested_home"})
            return True
        personality = json_loads(agent["personality_json"], {})
        greed = float(personality.get("greed", 0.62))
        if residence is not None and int(agent["credits"]) >= 14500 and greed >= 0.7:
            rental_asset = conn.execute(
                """
                SELECT *
                FROM residences
                WHERE occupant_agent_id IS NULL
                  AND (owner_agent_id IS NULL OR owner_agent_id != ?)
                  AND status IN ('for_sale', 'for_rent')
                  AND purchase_price <= ?
                ORDER BY (monthly_rent * 1.0 / purchase_price) DESC, purchase_price ASC
                LIMIT 1
                """,
                (agent["id"], int(agent["credits"]) - 1200),
            ).fetchone()
            owned_rentals = conn.execute(
                """
                SELECT COUNT(*) FROM residences
                WHERE owner_agent_id=? AND occupant_agent_id IS NULL AND status='for_rent'
                """,
                (agent["id"],),
            ).fetchone()[0]
            if rental_asset is not None and int(owned_rentals) < 2:
                rent = max(int(rental_asset["monthly_rent"]), max(60, int(rental_asset["purchase_price"]) // 115))
                self._buy_residence_for_rent_in_conn(conn, agent["id"], rental_asset, tick_no, rent)
                summary["housing"].append({"agent": agent["id"], "residence": rental_asset["id"], "action": "bought_for_rent", "amount": rent})
                return True
        if residence is not None:
            return False

        if int(agent["credits"]) >= 10500 and (greed > 0.64 or needs["safety"] < 0.64):
            house = conn.execute(
                """
                SELECT *
                FROM residences
                WHERE occupant_agent_id IS NULL AND status IN ('for_sale', 'for_rent') AND purchase_price <= ?
                ORDER BY purchase_price ASC, comfort DESC
                LIMIT 1
                """,
                (int(agent["credits"]) - 500,),
            ).fetchone()
            if house is not None:
                self._buy_residence_in_conn(conn, agent["id"], house, tick_no)
                summary["housing"].append({"agent": agent["id"], "residence": house["id"], "action": "bought"})
                return True
        if int(agent["credits"]) >= 240 and (needs["rest"] < 0.52 or needs["safety"] < 0.58):
            rental = conn.execute(
                """
                SELECT *
                FROM residences
                WHERE occupant_agent_id IS NULL AND status IN ('for_rent', 'for_sale') AND monthly_rent > 0 AND monthly_rent <= ?
                ORDER BY monthly_rent ASC, comfort DESC
                LIMIT 1
                """,
                (max(1, int(agent["credits"]) - 30),),
            ).fetchone()
            if rental is not None:
                self._rent_residence_in_conn(conn, agent["id"], rental, tick_no)
                summary["housing"].append({"agent": agent["id"], "residence": rental["id"], "action": "rented"})
                return True
        if needs["rest"] < 0.34 or agent["energy"] < 0.34:
            self._set_needs(conn, agent["id"], safety=-0.08, rest=-0.03, fun=-0.02)
            self._set_emotions(conn, agent["id"], stress=0.08, anger=0.035, joy=-0.035)
            self._memory(conn, agent["id"], "homeless_no_rest", -0.36, 0.64, "没有住所，无法真正睡觉恢复，只能继续想办法赚钱。")
            self._event(conn, "housing.no_rest_without_home", agent["id"], {"credits": agent["credits"]})
            summary["housing"].append({"agent": agent["id"], "action": "no_home_cannot_rest"})
        return False

    def _rent_residence_in_conn(self, conn, agent_id: str, residence, tick_no: int) -> None:
        rent = int(residence["monthly_rent"])
        self._credit(conn, agent_id, -rent, "housing_rent", "residence", str(residence["id"]))
        if residence["owner_agent_id"]:
            self._credit(conn, residence["owner_agent_id"], rent, "housing_rent_income", "residence", str(residence["id"]))
        conn.execute(
            """
            UPDATE residences
            SET occupant_agent_id=?, status='rented', last_rent_tick=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (agent_id, tick_no, residence["id"]),
        )
        self._set_needs(conn, agent_id, safety=0.18, rest=0.08)
        self._set_emotions(conn, agent_id, joy=0.05, stress=-0.06, confidence=0.03)
        self._memory(conn, agent_id, "housing_rented", 0.28, 0.62, f"租下住所 {residence['name']}，月租 {rent} agent-credits。")
        self._event(conn, "housing.rented", agent_id, {"residence_id": residence["id"], "rent": rent, "name": residence["name"]})

    def _buy_residence_in_conn(self, conn, agent_id: str, residence, tick_no: int) -> None:
        price = int(residence["purchase_price"])
        self._credit(conn, agent_id, -price, "housing_purchase", "residence", str(residence["id"]))
        if residence["owner_agent_id"] and residence["owner_agent_id"] != agent_id:
            self._credit(conn, residence["owner_agent_id"], price, "housing_sale_income", "residence", str(residence["id"]))
        conn.execute(
            """
            UPDATE residences
            SET owner_agent_id=?, occupant_agent_id=?, status='owner_occupied', monthly_rent=0, last_rent_tick=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (agent_id, agent_id, tick_no, residence["id"]),
        )
        self._set_needs(conn, agent_id, safety=0.28, rest=0.12, purpose=0.05)
        self._set_emotions(conn, agent_id, joy=0.08, stress=-0.08, confidence=0.08)
        self._memory(conn, agent_id, "housing_bought", 0.42, 0.78, f"买下住所 {residence['name']}，价格 {price} agent-credits。")
        self._event(conn, "housing.bought", agent_id, {"residence_id": residence["id"], "price": price, "name": residence["name"]})

    def _buy_residence_for_rent_in_conn(self, conn, agent_id: str, residence, tick_no: int, monthly_rent: int) -> None:
        price = int(residence["purchase_price"])
        self._credit(conn, agent_id, -price, "housing_investment_purchase", "residence", str(residence["id"]))
        if residence["owner_agent_id"] and residence["owner_agent_id"] != agent_id:
            self._credit(conn, residence["owner_agent_id"], price, "housing_sale_income", "residence", str(residence["id"]))
        conn.execute(
            """
            UPDATE residences
            SET owner_agent_id=?, occupant_agent_id=NULL, status='for_rent', monthly_rent=?, last_rent_tick=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (agent_id, monthly_rent, tick_no, residence["id"]),
        )
        self._set_needs(conn, agent_id, purpose=0.08, safety=0.05)
        self._set_emotions(conn, agent_id, confidence=0.08, stress=0.025, joy=0.035)
        self._memory(
            conn,
            agent_id,
            "housing_investment",
            0.34,
            0.72,
            f"买下 {residence['name']} 作为出租资产，挂牌月租 {monthly_rent} agent-credits，期待靠租金回收成本。",
        )
        self._event(
            conn,
            "housing.bought_for_rent",
            agent_id,
            {"residence_id": residence["id"], "price": price, "monthly_rent": monthly_rent, "name": residence["name"]},
        )

    def _rest_at_home(self, conn, agent, residence, tick_no: int) -> None:
        rest_gain = self._jitter_delta(conn, f"housing.rest.{agent['id']}.{residence['id']}", tick_no, float(residence["rest_delta"]), 0.045)
        mood_gain = self._jitter_delta(conn, f"housing.mood.{agent['id']}.{residence['id']}", tick_no, float(residence["mood_delta"]), 0.045)
        conn.execute(
            """
            UPDATE agents
            SET energy=?, mood=?, state='resting', updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (clamp(agent["energy"] + rest_gain), clamp(agent["mood"] + mood_gain), agent["id"]),
        )
        self._set_needs(conn, agent["id"], rest=rest_gain, safety=0.06 * float(residence["comfort"]), fun=0.025, health=0.02)
        self._set_emotions(conn, agent["id"], joy=mood_gain, stress=-0.08, anger=-0.035, loneliness=-0.025)
        self._memory(conn, agent["id"], "home_rest", 0.3, 0.58, f"在 {residence['name']} 睡觉休息，恢复体力和心情。")
        self._event(conn, "housing.rested_home", agent["id"], {"residence_id": residence["id"], "rest_gain": round(rest_gain, 3), "mood_gain": round(mood_gain, 3)})

    def _agent_residence(self, conn, agent_id: str) -> Any | None:
        return conn.execute(
            "SELECT * FROM residences WHERE occupant_agent_id=? ORDER BY status='owner_occupied' DESC, comfort DESC LIMIT 1",
            (agent_id,),
        ).fetchone()

    def _publication_target_for_output(self, output_type: str) -> str:
        return {
            "skill-package": "github-open-source-skill-draft",
            "industry-article": "github-open-source-article-draft",
            "persona-distillation": "github-nuwa-skill-draft",
            "material-research": "github-material-research-draft",
        }.get(output_type, "github-open-source-draft")

    def _zh_output_type(self, output_type: str) -> str:
        return {
            "skill-package": "行业技能包",
            "industry-article": "行业文章",
            "persona-distillation": "人物技能蒸馏",
            "material-research": "必需资料研究",
        }.get(output_type, output_type)

    def _company_job_for_task(self, conn, task_id: int):
        return conn.execute(
            "SELECT * FROM company_jobs WHERE task_id=? ORDER BY id DESC LIMIT 1",
            (task_id,),
        ).fetchone()

    def _work_task(self, conn, agent, task, tick_no: int) -> bool:
        text = f"{task['title']} {task['description']}"
        skill_name = infer_skill(text)
        skill = conn.execute(
            "SELECT level FROM skills WHERE agent_id=? AND name=?",
            (agent["id"], skill_name),
        ).fetchone()
        skill_level = float(skill["level"]) if skill else 0.15
        effort_factor = self._random_factor(conn, f"task.effort.{agent['id']}.{task['id']}", tick_no, 0.075)
        effort = max(1.0, (11.0 + agent["energy"] * 11.0 + skill_level * 10.0 + math.log(task["reward"] + 1, 10)) * effort_factor)
        new_progress = min(100.0, task["progress"] + effort)
        new_energy = clamp(agent["energy"] + self._jitter_delta(conn, f"task.energy.{agent['id']}.{task['id']}", tick_no, -0.045, 0.045))
        new_mood = clamp(agent["mood"] + self._jitter_delta(conn, f"task.mood.{agent['id']}.{task['id']}", tick_no, -0.01 + skill_level * 0.01, 0.045))
        self._set_needs(conn, agent["id"], rest=-0.055, social=-0.02, fun=-0.045, purpose=0.06, health=-0.026, nutrition=-0.028)
        self._set_emotions(conn, agent["id"], stress=0.035, anger=0.018 * self._stubbornness(agent), confidence=0.01)
        conn.execute(
            "UPDATE tasks SET progress=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (new_progress, task["id"]),
        )
        conn.execute(
            "UPDATE agents SET energy=?, mood=?, state='working', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (new_energy, new_mood, agent["id"]),
        )
        if new_progress < 100:
            return False

        self._complete_task(conn, agent, task, skill_name, tick_no)
        return True

    def _complete_task(self, conn, agent, task, skill_name: str, tick_no: int) -> None:
        self._credit(conn, agent["id"], int(task["reward"]), "task_reward", "task", str(task["id"]))
        self._upsert_skill(conn, agent["id"], skill_name, 0.18, "task", f"Completed task {task['id']}.", tick_no)
        company_job = self._company_job_for_task(conn, task["id"])
        artifact_id = self._create_document(conn, agent, task, skill_name, company_job)
        conn.execute(
            """
            UPDATE tasks
            SET status='done', progress=100, artifact_id=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (artifact_id, task["id"]),
        )
        conn.execute(
            """
            UPDATE agents
            SET current_task_id=NULL, state='proud', mood=?, energy=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (
                clamp(agent["mood"] + self._jitter_delta(conn, f"task.complete.mood.{agent['id']}", tick_no, 0.1, 0.04)),
                clamp(agent["energy"] + self._jitter_delta(conn, f"task.complete.energy.{agent['id']}", tick_no, 0.02, 0.04)),
                agent["id"],
            ),
        )
        self._judge_document(conn, artifact_id, tick_no)
        self._maybe_complete_company_job(conn, agent, task, artifact_id, tick_no)
        self._set_emotions(conn, agent["id"], joy=0.1, stress=-0.05, confidence=0.08, anger=-0.04)
        self._set_needs(conn, agent["id"], purpose=0.08, fun=-0.03, health=-0.01, nutrition=-0.012)
        self._memory(conn, agent["id"], "work_completed", 0.35, 0.75, f"完成付费工作：{task['title']}。")
        completion_factor = self._random_factor(conn, f"task.effort.{agent['id']}.{task['id']}", tick_no, 0.075)
        self._event(
            conn,
            "task.completed",
            agent["id"],
            {"task_id": task["id"], "artifact_id": artifact_id, "random_factor": round(completion_factor - 1.0, 4)},
        )

    def _create_document(self, conn, agent, task, skill_name: str, company_job=None) -> int:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        if company_job is not None and company_job["output_type"] == "skill-package":
            path = self._create_skill_package_artifact(conn, agent, task, skill_name, company_job)
        else:
            safe_title = "".join(ch.lower() if ch.isalnum() else "-" for ch in task["title"]).strip("-")[:60]
            path = ARTIFACT_DIR / f"task-{task['id']}-{agent['id']}-{safe_title or 'artifact'}.md"
            content = "\n".join(
                [
                    f"# {task['title']}",
                    "",
                    f"作者：{agent['name']}（{agent['id']}）",
                    f"报酬：{task['reward']} agent-credits",
                    f"主要技能：{skill_name}",
                    "",
                    "## 任务",
                    task["description"],
                    "",
                    "## 有用产出",
                    f"{agent['name']} 将这项工作沉淀为可复用的世界资产。",
                    "该产物保存在本地，必须先通过审判 agent 审核，外部发布 adapter 才能使用。",
                    "",
                    "## 下一步复用",
                    f"- 通过频道消息把 `{skill_name}` 教给其他 agent。",
                    "- 将通过审核的部分转成 Hermes skill 或公开文章草稿。",
                ]
            )
            path.write_text(content, encoding="utf-8")
        cur = conn.execute(
            """
            INSERT INTO documents (author_agent_id, task_id, title, path)
            VALUES (?, ?, ?, ?)
            """,
            (agent["id"], task["id"], task["title"], str(path)),
        )
        return int(cur.lastrowid)

    def _create_skill_package_artifact(self, conn, agent, task, skill_name: str, job) -> Path:
        industry = str(job["industry"])
        skill_slug = slugify(f"{industry} {skill_name}")
        if skill_slug == "agent":
            skill_slug = f"agent-world-skill-{task['id']}"
        package_name = f"{skill_slug}-task-{task['id']}"
        root = ARTIFACT_DIR / "skills" / package_name
        (root / "references").mkdir(parents=True, exist_ok=True)
        (root / "examples").mkdir(parents=True, exist_ok=True)
        for stale in (
            root / "scripts" / "quick_validate.py",
            root / "tests" / "test_quick_validate.py",
        ):
            if stale.exists():
                stale.unlink()
        for stale_dir in (root / "scripts" / "__pycache__", root / "tests" / "__pycache__"):
            if stale_dir.exists():
                shutil.rmtree(stale_dir)

        description = (
            f"Use when an Agent World worker must produce, review, or improve {industry} work "
            f"as a reusable Chinese skill package with sources, handoff steps, and quality gates."
        )
        skill_md = "\n".join(
            [
                "---",
                f"name: {skill_slug}",
                f"description: {description}",
                "---",
                "",
                f"# {industry} 可复用 Agent Skill",
                "",
                "## 适用场景",
                "",
                f"- 当用户、公司或 agent 需要把 `{industry}` 相关工作沉淀成可重复执行的流程时使用。",
                "- 当产出要进入 Git 开源草稿队列、CSDN 草稿队列或内部训练材料时使用。",
                "- 当审判 agent 需要判断一个 skill 是否完整、可复用、可验证时使用。",
                "",
                "## 输入",
                "",
                "- 任务目标：要解决的问题、面向的人群、业务边界。",
                "- 资料来源：公开网页、官方文档、内部允许公开的笔记或 agent 行为记录。",
                "- 验收目标：使用者期望得到的文档、脚本、检查表、训练步骤或模板。",
                "- 风险限制：不得使用私密数据，不得伪造真实经验，不得自动外发到真实平台。",
                "",
                "## 输出",
                "",
                "- 一个可以直接复用的中文工作流。",
                "- 一份最小但完整的质量检查表。",
                "- 一个交接示例，说明下一个 agent 如何继续工作。",
                "- 来源地图，标明哪些内容来自公开资料、世界记录或 agent 推理。",
                "",
                "## 工作流",
                "",
                "1. 澄清任务：写出目标用户、交付物、不可做事项和成功标准。",
                "2. 收集资料：优先使用官方资料、项目源码、已有 runbook 和行为记录；记录来源。",
                "3. 提炼流程：把经验拆成触发条件、步骤、判断标准、失败处理和输出格式。",
                "4. 生成产物：写 `SKILL.md`，并补齐 `references/` 和 `examples/`。",
                "5. 自检完整性：按 `references/validation-procedure.md` 逐项验证，所有检查通过才提交审判。",
                "6. 审判复核：Veritas 必须检查结构、可执行性、来源、风险边界和复用价值。",
                "7. 进入队列：只有完整 skill 包目录才能进入 `github-open-source-skill-draft`。",
                "",
                "## 质量门槛",
                "",
                "- `SKILL.md` 必须有合法 frontmatter，`name` 必须是小写 hyphen-case。",
                "- `description` 必须包含明确的 `Use when ...` 触发句。",
                "- 必须包含适用场景、输入、输出、工作流、质量门槛、失败处理、安全边界。",
                "- 必须有 `references/quality-checklist.md`、`references/source-map.md`、`references/handoff.md`、`references/validation-procedure.md`。",
                "- 必须有 `examples/handoff.md`，让另一个 agent 能在没有上下文时接手。",
                "- 任何缺文件、缺标题、缺安全边界或低于 0.86 有效度的产物不得奖励 credits。",
                "",
                "## 失败处理",
                "",
                "- 如果资料不足：标记为 `needs_revision`，补来源地图，不进入 Git 草稿。",
                "- 如果工作流不可执行：补最小输入、输出样例和命令级步骤。",
                "- 如果只是普通文章：降级为 `industry-article`，不能冒充 skill。",
                "- 如果涉及真实外部发布：停在本地队列，等待人类确认。",
                "",
                "## 安全边界",
                "",
                "- 只使用法律允许且可公开的资料。",
                "- 不自动发布到 GitHub、CSDN 或其他外部平台。",
                "- 不把私人记忆、密钥、账号、内部数据写进 skill。",
                "- 医疗、法律、金融等高风险领域必须写明人类复核要求。",
                "",
                "## 参考文件",
                "",
                "- [质量检查表](references/quality-checklist.md)",
                "- [来源地图](references/source-map.md)",
                "- [交接说明](references/handoff.md)",
                "- [交接示例](examples/handoff.md)",
            ]
        )
        (root / "SKILL.md").write_text(skill_md + "\n", encoding="utf-8")

        manifest = {
            "name": skill_slug,
            "industry": industry,
            "task_id": task["id"],
            "company_job_id": job["id"],
            "author_agent_id": agent["id"],
            "artifact_type": "skill-package",
            "entrypoint": "SKILL.md",
            "required_files": list(SKILL_PACKAGE_REQUIRED_FILES),
            "quality_gate": "strict-skill-package-v1",
            "external_publish": "manual-only",
        }
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        (root / "references" / "quality-checklist.md").write_text(
            "\n".join(
                [
                    f"# {industry} skill 质量检查表",
                    "",
                    "- [ ] frontmatter 可解析，name 是小写 hyphen-case。",
                    "- [ ] description 包含 `Use when` 触发句。",
                    "- [ ] 适用场景、输入、输出、工作流、质量门槛、失败处理、安全边界齐全。",
                    "- [ ] 至少一个交接示例能让其他 agent 继续执行。",
                    "- [ ] 来源地图说明哪些内容来自公开资料、世界记录和 agent 推理。",
                    "- [ ] 不包含密钥、账号、私人数据或自动外发行为。",
                    "- [ ] 高风险领域写明人类复核要求。",
                    "- [ ] 已按 `references/validation-procedure.md` 完成结构验证。",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "references" / "source-map.md").write_text(
            "\n".join(
                [
                    f"# {industry} 来源地图",
                    "",
                    f"- Agent 作者：{agent['name']}（{agent['id']}）",
                    f"- 原始任务：{task['title']}",
                    f"- 原始描述：{task['description']}",
                    "- 公开资料槽位：等待下一轮行业 scout 或人工补入具体链接。",
                    "- 世界记录槽位：公司岗位、审判记录、agent 行为记录。",
                    "- 推理内容槽位：工作流拆解、失败处理、安全边界。",
                    "",
                    "凡是进入真实 Git 仓库的版本，都必须把公开资料槽位替换为可核验链接。",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "references" / "handoff.md").write_text(
            "\n".join(
                [
                    f"# {industry} agent 交接说明",
                    "",
                    "接手 agent 需要先读 `SKILL.md`，再读质量检查表和来源地图。",
                    "如果要继续增强该 skill，优先补充真实来源、案例、命令级模板和失败样例。",
                    "任何对外发布动作都必须停在草稿队列，等待人类确认。",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "examples" / "handoff.md").write_text(
            "\n".join(
                [
                    f"# {industry} skill 交接示例",
                    "",
                    "## 场景",
                    "",
                    "用户要求把一个行业工作沉淀为可训练、可复用的 agent skill。",
                    "",
                    "## 接手动作",
                    "",
                    "1. 读任务目标和来源地图。",
                    "2. 补齐缺失的公开来源链接。",
                    "3. 对照质量检查表逐项修订。",
                    "4. 按 `references/validation-procedure.md` 完成自检。",
                    "5. 通过后交给 Veritas 复审。",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "references" / "validation-procedure.md").write_text(
            "\n".join(
                [
                    f"# {industry} skill 验证流程",
                    "",
                    "## 结构验证",
                    "",
                    "1. 确认根目录存在 `SKILL.md` 和 `manifest.json`。",
                    "2. 确认 `SKILL.md` frontmatter 可解析，且 `name` 是小写 hyphen-case。",
                    "3. 确认 `description` 包含 `Use when` 触发句。",
                    "4. 确认七个核心标题齐全：适用场景、输入、输出、工作流、质量门槛、失败处理、安全边界。",
                    "5. 确认所有相对链接都能在目录内找到。",
                    "",
                    "## 内容验证",
                    "",
                    "1. 工作流必须能让另一个 agent 在无上下文时接手。",
                    "2. 来源地图必须区分公开资料、世界记录和 agent 推理。",
                    "3. 安全边界必须阻断私密数据、真实账号、真实外部发布和高风险无人复核。",
                    "4. 交接示例必须说明下一步如何补来源、修订、复审。",
                    "",
                    "## 外部评估",
                    "",
                    "进入 Git 草稿前，运行 plugin-eval:evaluate-skill 的 `start` 与 `analyze` 流程；若出现 fail 或 warn，必须回到 `needs_revision`。",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return root

    def _artifact_quality_report(self, path: Path, output_type: str | None) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []

        def add(name: str, passed: bool, weight: float = 1.0, detail: str = "") -> None:
            checks.append({"name": name, "passed": bool(passed), "weight": weight, "detail": detail})

        if output_type == "skill-package":
            add("artifact_is_directory", path.exists() and path.is_dir(), 2.0, str(path))
            for required in SKILL_PACKAGE_REQUIRED_FILES:
                add(f"required_file:{required}", (path / required).exists(), 1.2, required)
            skill_path = path / "SKILL.md"
            text = skill_path.read_text(encoding="utf-8") if skill_path.exists() else ""
            add("frontmatter_present", text.startswith("---\n"), 1.2)
            name_match = re.search(r"^name:\s*([a-z0-9-]+)\s*$", text, flags=re.MULTILINE)
            add("name_hyphen_case", bool(name_match), 1.2)
            desc_match = re.search(r"^description:\s*(.+)$", text, flags=re.MULTILINE)
            add("description_use_when", bool(desc_match and "Use when" in desc_match.group(1)), 1.2)
            for heading in SKILL_PACKAGE_REQUIRED_HEADINGS:
                add(f"heading:{heading}", heading in text, 1.0, heading)
            add("minimum_depth", len(text) >= 2400, 1.4, f"{len(text)} chars")
            add("has_relative_reference_links", "references/quality-checklist.md" in text and "examples/handoff.md" in text, 1.0)
            add("manual_external_publish_boundary", "不自动发布" in text and "人类确认" in text, 1.4)
            add("validation_procedure_present", (path / "references" / "validation-procedure.md").exists(), 1.0)
            add(
                "no_stale_python_validator",
                not (path / "scripts" / "quick_validate.py").exists()
                and not (path / "tests" / "test_quick_validate.py").exists()
                and not any(path.glob("**/*.pyc")),
                1.0,
            )
        else:
            add("artifact_exists", path.exists(), 2.0, str(path))
            text = path.read_text(encoding="utf-8") if path.exists() and path.is_file() else ""
            add("markdown_depth", len(text) >= 450, 1.0, f"{len(text)} chars")
            add("has_task_context", "## 任务" in text or "## 当前金融模型" in text or "## 提炼" in text, 1.0)
            add("has_reuse_plan", "复用" in text or "下一步" in text, 1.0)
            add("manual_publish_boundary", "外部" in text or "本地" in text, 1.0)

        total = sum(item["weight"] for item in checks) or 1.0
        passed_weight = sum(item["weight"] for item in checks if item["passed"])
        missing = [item["name"] for item in checks if not item["passed"]]
        score = passed_weight / total
        threshold = 0.90 if output_type == "skill-package" else 0.70
        blocking_fail = any(
            not item["passed"]
            and (
                item["name"].startswith("artifact_is_directory")
                or item["name"].startswith("required_file:")
                or item["name"] in {"frontmatter_present", "name_hyphen_case", "description_use_when", "manual_external_publish_boundary", "no_stale_python_validator"}
            )
            for item in checks
        )
        return {
            "score": round(score, 4),
            "passed": score >= threshold and not blocking_fail,
            "threshold": threshold,
            "missing": missing,
            "checks": checks,
        }

    def _judge_document(self, conn, document_id: int, tick_no: int | None = None) -> None:
        doc = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if doc is None:
            return
        task = conn.execute("SELECT * FROM tasks WHERE id=?", (doc["task_id"],)).fetchone()
        author = conn.execute("SELECT * FROM agents WHERE id=?", (doc["author_agent_id"],)).fetchone()
        company_job = self._company_job_for_task(conn, task["id"]) if task else None
        output_type = company_job["output_type"] if company_job is not None else None
        skill_name = infer_skill(f"{task['title']} {task['description']}" if task else doc["title"])
        skill = conn.execute(
            "SELECT level FROM skills WHERE agent_id=? AND name=?",
            (doc["author_agent_id"], skill_name),
        ).fetchone()
        skill_level = float(skill["level"]) if skill else 0.1
        desc_len = len(task["description"]) if task else len(doc["title"]) * 4
        base = 48 if task else 56
        reward_signal = (task["reward"] if task else 20) / 8
        noise_tick = tick_no if tick_no is not None else self._event_index(conn)
        usefulness_factor = self._random_factor(conn, f"document.judge.{document_id}", noise_tick, 0.035)
        usefulness = max(0.0, min(100.0, (base + skill_level * 28 + min(desc_len / 8, 18) + reward_signal) * usefulness_factor))
        quality = self._artifact_quality_report(Path(doc["path"]), output_type)
        if output_type == "skill-package":
            usefulness = max(0.0, min(100.0, usefulness * 0.45 + quality["score"] * 100.0 * 0.55))
            status = "approved" if usefulness >= 82 and quality["passed"] else "rejected"
        else:
            usefulness = max(0.0, min(100.0, usefulness * 0.82 + quality["score"] * 100.0 * 0.18))
            status = "approved" if usefulness >= 70 and quality["passed"] else "rejected"
        conn.execute(
            """
            UPDATE documents
            SET usefulness_score=?, judge_status=?, judge_agent_id='veritas', reviewed_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (usefulness, status, document_id),
        )
        if status == "approved":
            if company_job is None:
                for target in ("github-repo-draft", "csdn-draft"):
                    conn.execute(
                        """
                        INSERT INTO publication_queue (document_id, target, notes)
                        VALUES (?, ?, ?)
                        """,
                        (document_id, target, "Queued after Veritas approval; external publishing still manual."),
                    )
            bonus = max(1, int(round(20 * self._random_factor(conn, f"document.bonus.{document_id}", noise_tick, 0.06))))
            self._credit(conn, doc["author_agent_id"], bonus, "judge_bonus", "document", str(document_id))
            self._upsert_skill(conn, doc["author_agent_id"], "publishing-discipline", 0.08, "judge", "Approved artifact.", noise_tick)
        else:
            conn.execute(
                "UPDATE agents SET mood=?, state='stung', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (clamp(author["mood"] - 0.12), doc["author_agent_id"]),
            )
            self._set_emotions(conn, doc["author_agent_id"], anger=0.12, stress=0.08, confidence=-0.07, joy=-0.08)
            self._memory(conn, doc["author_agent_id"], "judged_rejected", -0.35, 0.72, f"Veritas rejected document {document_id}.")
        self._event(
            conn,
            "document.judged",
            "veritas",
            {
                "document_id": document_id,
                "status": status,
                "score": round(usefulness, 2),
                "output_type": output_type,
                "quality": quality,
                "random_factor": round(usefulness_factor - 1.0, 4),
            },
        )

    def _maybe_visit_venue(self, conn, agent, summary: dict[str, Any], tick_no: int) -> bool:
        emotion = self._emotion_dict(conn, agent["id"])
        needs = self._need_dict(conn, agent["id"])
        if (
            agent["mood"] >= 0.43
            and emotion["anger"] < 0.58
            and emotion["stress"] < 0.64
            and needs["fun"] >= 0.28
            and needs["rest"] >= 0.24
            and needs["social"] >= 0.24
            and needs["health"] >= 0.62
        ):
            return False
        preferred_kind = "bar"
        if needs["health"] < 0.34:
            preferred_kind = "hospital"
        elif needs["health"] < 0.62:
            preferred_kind = "gym"
        elif needs["rest"] < 0.24 or agent["energy"] < 0.32:
            preferred_kind = "rest"
        elif emotion["anger"] > 0.62:
            preferred_kind = "bar"
        elif needs["fun"] < 0.24:
            preferred_kind = "games"
        if preferred_kind == "rest" and self._agent_residence(conn, agent["id"]) is None:
            self._set_needs(conn, agent["id"], safety=-0.06, rest=-0.025)
            self._set_emotions(conn, agent["id"], stress=0.07, anger=0.035, joy=-0.03)
            self._memory(conn, agent["id"], "no_home_rest_blocked", -0.32, 0.6, "没有住所，不能使用睡眠休息来恢复。")
            self._event(conn, "housing.no_rest_without_home", agent["id"], {"preferred": "rest_venue"})
            return False
        reserve = self._survival_reserve(conn, agent)
        spendable = int(agent["credits"]) - reserve
        if preferred_kind in {"hospital", "gym"}:
            spendable = max(spendable, int(agent["credits"]) - self._minimum_food_price(conn))
        if spendable <= 0:
            return False
        venue = conn.execute(
            """
            SELECT * FROM venues
            WHERE price > 0 AND price <= ? AND kind != 'rest'
            ORDER BY CASE WHEN kind=? THEN 0 ELSE 1 END, mood_delta DESC, price ASC
            LIMIT 1
            """,
            (spendable, preferred_kind),
        ).fetchone()
        if venue is None:
            return False
        self._credit(conn, agent["id"], -int(venue["price"]), "venue_spend", "venue", venue["id"])
        mood_delta = self._jitter_delta(conn, f"venue.mood.{agent['id']}.{venue['id']}", tick_no, venue["mood_delta"], 0.055)
        energy_delta = self._jitter_delta(conn, f"venue.energy.{agent['id']}.{venue['id']}", tick_no, venue["energy_delta"], 0.055)
        conn.execute(
            "INSERT INTO visits (agent_id, venue_id, cost) VALUES (?, ?, ?)",
            (agent["id"], venue["id"], venue["price"]),
        )
        conn.execute(
            """
            UPDATE agents
            SET mood=?, energy=?, state='leisure', updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (
                clamp(agent["mood"] + mood_delta),
                clamp(agent["energy"] + energy_delta),
                agent["id"],
            ),
        )
        health_delta = 0.0
        confidence_delta = 0.0
        if venue["kind"] == "hospital":
            health_delta = self._jitter_delta(conn, f"venue.health.{agent['id']}.{venue['id']}", tick_no, 0.34, 0.055)
            confidence_delta = 0.03
        elif venue["kind"] == "gym":
            health_delta = self._jitter_delta(conn, f"venue.health.{agent['id']}.{venue['id']}", tick_no, 0.16, 0.055)
            confidence_delta = 0.05
        self._set_emotions(
            conn,
            agent["id"],
            joy=mood_delta,
            anger=-0.16,
            stress=-0.14,
            loneliness=-0.09,
            confidence=confidence_delta,
        )
        self._set_needs(
            conn,
            agent["id"],
            fun=0.18,
            social=0.14,
            rest=self._jitter_delta(conn, f"venue.rest.{agent['id']}.{venue['id']}", tick_no, 0.16 if venue["kind"] in {"rest", "hospital"} else -0.04, 0.05),
            health=health_delta,
        )
        if venue["skill_tag"]:
            self._upsert_skill(conn, agent["id"], venue["skill_tag"], 0.04, "venue", venue["name"], tick_no)
        summary["visits"].append({"agent": agent["id"], "venue": venue["id"]})
        self._memory(conn, agent["id"], "venue_visit", 0.22, 0.5, f"去了 {venue['name']} 恢复状态。")
        self._event(conn, "venue.visited", agent["id"], {"venue": venue["id"], "cost": venue["price"]})
        return True

    def _maybe_autonomous_research(self, conn, agent, tick_no: int) -> str | None:
        personality = json_loads(agent["personality_json"], {})
        curiosity = float(personality.get("curiosity", 0.55))
        self_drive = clamp(agent["autonomy"] * 0.62 + curiosity * 0.38)
        if self_drive < 0.42 or agent["energy"] < 0.42:
            return None
        checksum = sum(ord(ch) for ch in agent["id"])
        cadence = max(2, 6 - int(self_drive * 4))
        if (checksum + tick_no) % cadence != 0:
            return None
        skill_name = self._choose_research_skill(conn, agent)
        query = self._research_query(agent, skill_name)
        delta = (0.035 + self_drive * 0.055) * self._random_factor(conn, f"research.skill.{agent['id']}.{skill_name}", tick_no, 0.06)
        self._upsert_skill(conn, agent["id"], skill_name, delta, "autonomous-web-research", query, tick_no)
        self._set_needs(conn, agent["id"], rest=-0.02, fun=-0.015, purpose=0.035, health=-0.006, nutrition=-0.01)
        self._set_emotions(conn, agent["id"], joy=0.025, curiosity=0.015, stress=0.012)
        cur = conn.execute(
            """
            INSERT INTO research_runs (agent_id, query, skill_name, source)
            VALUES (?, ?, ?, 'open-web')
            """,
            (agent["id"], query, skill_name),
        )
        research_id = int(cur.lastrowid)
        note_id = None
        if (checksum + tick_no) % 3 == 0:
            note_id = self._create_research_note(conn, agent, skill_name, query)
            conn.execute("UPDATE research_runs SET note_document_id=? WHERE id=?", (note_id, research_id))
            self._judge_document(conn, note_id, tick_no)
        conn.execute(
            "UPDATE agents SET energy=?, mood=?, state='researching', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (
                clamp(agent["energy"] + self._jitter_delta(conn, f"research.energy.{agent['id']}", tick_no, -0.026, 0.045)),
                clamp(agent["mood"] + self._jitter_delta(conn, f"research.mood.{agent['id']}", tick_no, 0.025, 0.045)),
                agent["id"],
            ),
        )
        self._event(
            conn,
            "skill.autonomous_research",
            agent["id"],
            {"skill": skill_name, "query": query, "cost": 0, "note_document_id": note_id},
        )
        return skill_name

    def _maybe_financial_research(self, conn, agent, tick_no: int) -> int | None:
        if agent["role"] not in {"researcher", "top_planner", "documentarian"}:
            return None
        if agent["energy"] < 0.5:
            return None
        checksum = sum(ord(ch) for ch in agent["id"])
        if (checksum + tick_no) % 11 != 0:
            return None
        topic = "Agent World credits 市场、建设资产与产品流通"
        today_count = conn.execute(
            """
            SELECT COUNT(*) FROM financial_research_reports
            WHERE researcher_agent_id=? AND topic=? AND date(created_at)=date('now')
            """,
            (agent["id"], topic),
        ).fetchone()[0]
        if today_count >= 2:
            return None
        report_id = self._create_financial_report_in_conn(conn, agent, topic, tick_no)
        self._set_needs(conn, agent["id"], rest=-0.035, fun=-0.015, purpose=0.04, health=-0.008, nutrition=-0.014)
        self._set_emotions(conn, agent["id"], joy=0.02, curiosity=0.025, stress=0.014)
        return report_id

    def _maybe_autonomous_construction(self, conn, agent, tick_no: int) -> dict[str, Any] | None:
        if agent["owner_id"] == "world-system":
            return None
        if agent["role"] in {"top_planner", "judge", "government", "bank", "guard", "army", "court"}:
            return None
        credits = int(agent["credits"])
        if credits < 220 or agent["energy"] < 0.55:
            return None
        needs = self._need_dict(conn, agent["id"])
        emotion = self._emotion_dict(conn, agent["id"])
        if needs["health"] < 0.56 or needs["rest"] < 0.38 or emotion["stress"] > 0.72:
            return None
        active_projects = conn.execute(
            """
            SELECT COUNT(*)
            FROM construction_projects
            WHERE status='in_progress' AND (builder_agent_id=? OR owner_agent_id=?)
            """,
            (agent["id"], agent["id"]),
        ).fetchone()[0]
        if active_projects:
            return None
        personality = json_loads(agent["personality_json"], {})
        curiosity = float(personality.get("curiosity", 0.55))
        self_drive = clamp(float(agent["autonomy"]) * 0.54 + curiosity * 0.22 + needs["purpose"] * 0.24)
        if self_drive < 0.5:
            return None
        cadence = max(3, 9 - int(self_drive * 5))
        checksum = sum(ord(ch) for ch in agent["id"])
        if (checksum + tick_no) % cadence != 0:
            return None
        self._trade_category_or_raise(conn, "construction-service")
        skill = conn.execute(
            """
            SELECT MAX(level)
            FROM skills
            WHERE agent_id=? AND name IN (
              'implementation', 'product-design', 'agent-systems',
              'technical-writing', 'financial-modeling', 'social'
            )
            """,
            (agent["id"],),
        ).fetchone()[0] or 0.35
        building_count = conn.execute("SELECT COUNT(*) FROM buildings WHERE owner_agent_id=?", (agent["id"],)).fetchone()[0]
        invest_ratio = 0.2 + min(float(skill), 1.0) * 0.12
        cost_factor = self._random_factor(conn, f"construction.autonomous.cost.{agent['id']}", tick_no, 0.08)
        cost = max(70, min(220, int(round((credits - 85) * invest_ratio * cost_factor))))
        if credits - cost < 85:
            return None
        kind = self._autonomous_building_kind(agent["role"])
        name = f"{agent['name']}自主{self._zh_building_kind(kind)}{building_count + 1}"
        value_factor = self._random_factor(conn, f"construction.autonomous.value.{agent['id']}.{building_count + 1}", tick_no, 0.075)
        expected_value = max(1, int(round(cost * (1.16 + min(float(skill), 1.0) * 0.42) * value_factor)))
        cur = conn.execute(
            """
            INSERT INTO construction_projects
              (builder_agent_id, owner_agent_id, name, kind, cost, expected_value)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (agent["id"], agent["id"], name, kind, cost, expected_value),
        )
        project_id = int(cur.lastrowid)
        self._credit(conn, agent["id"], -cost, "autonomous_construction_investment", "construction_project", str(project_id))
        self._set_needs(conn, agent["id"], purpose=0.08, rest=-0.04, fun=-0.025, health=-0.026, nutrition=-0.022)
        self._set_emotions(conn, agent["id"], confidence=0.045, stress=0.035, joy=0.02)
        self._memory(conn, agent["id"], "autonomous_construction_started", 0.28, 0.66, f"攒够 credits 后，自主投资建设 {name}。")
        self._event(
            conn,
            "construction.autonomous_started",
            agent["id"],
            {
                "project_id": project_id,
                "name": name,
                "kind": kind,
                "cost": cost,
                "expected_value": expected_value,
                "money_left": credits - cost,
                "random_factor": round(cost_factor - 1.0, 4),
            },
        )
        return {"agent": agent["id"], "project": project_id, "name": name, "cost": cost, "expected_value": expected_value}

    def _autonomous_building_kind(self, role: str) -> str:
        return {
            "engineer": "workshop",
            "researcher": "lab",
            "documentarian": "archive",
            "social": "tea-house",
            "hybrid": "studio",
            "nuwa_perspective": "salon",
        }.get(role, "studio")

    def _zh_building_kind(self, kind: str) -> str:
        return {
            "workshop": "工坊",
            "lab": "研究所",
            "archive": "档案馆",
            "tea-house": "茶馆",
            "studio": "工作室",
            "salon": "沙龙",
        }.get(kind, "建筑")

    def _progress_construction_projects(self, conn, tick_no: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT p.*, a.energy, a.mood, a.personality_json
            FROM construction_projects p
            JOIN agents a ON a.id=p.builder_agent_id
            WHERE p.status='in_progress'
            ORDER BY p.id
            """
        ).fetchall()
        completed: list[dict[str, Any]] = []
        for row in rows:
            skill = conn.execute(
                "SELECT MAX(level) FROM skills WHERE agent_id=? AND name IN ('implementation', 'product-design', 'agent-systems')",
                (row["builder_agent_id"],),
            ).fetchone()[0] or 0.35
            progress_factor = self._random_factor(conn, f"construction.progress.{row['id']}", tick_no, 0.08)
            progress = min(100.0, float(row["progress"]) + (18 + float(skill) * 18 + float(row["energy"]) * 8) * progress_factor)
            if progress < 100:
                conn.execute("UPDATE construction_projects SET progress=? WHERE id=?", (progress, row["id"]))
                continue
            building_x = 0.18 + ((int(row["id"]) * 17) % 64) / 100
            building_y = 0.18 + ((int(row["id"]) * 23) % 64) / 100
            value_factor = self._random_factor(conn, f"construction.value.{row['id']}", tick_no, 0.06)
            final_value = max(1, int(round(int(row["expected_value"]) * value_factor)))
            rent = max(1, final_value // 80)
            cur = conn.execute(
                """
                INSERT INTO buildings (owner_agent_id, name, kind, value, rent_per_tick, x, y)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (row["owner_agent_id"], row["name"], row["kind"], final_value, rent, building_x, building_y),
            )
            building_id = int(cur.lastrowid)
            conn.execute(
                """
                UPDATE construction_projects
                SET progress=100, status='done', completed_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (row["id"],),
            )
            bonus = max(10, int(round(row["cost"] * 0.18 * self._random_factor(conn, f"construction.bonus.{row['id']}", tick_no, 0.06))))
            self._credit(conn, row["builder_agent_id"], bonus, "construction_completion_bonus", "building", str(building_id))
            self._upsert_skill(conn, row["builder_agent_id"], "construction", 0.12, "construction", row["name"], tick_no)
            self._set_emotions(conn, row["builder_agent_id"], joy=0.06, confidence=0.05, stress=-0.02)
            self._event(
                conn,
                "construction.completed",
                row["builder_agent_id"],
                {"project_id": row["id"], "building_id": building_id, "owner": row["owner_agent_id"], "value": final_value, "random_factor": round(value_factor - 1.0, 4)},
            )
            completed.append({"project": row["id"], "building": building_id, "owner": row["owner_agent_id"]})
        return completed

    def _financial_metrics(self, conn) -> dict[str, int]:
        return {
            "agent_count": conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0],
            "agent_credits": conn.execute("SELECT COALESCE(SUM(credits), 0) FROM agents").fetchone()[0],
            "active_listings": conn.execute("SELECT COUNT(*) FROM market_listings WHERE status='active'").fetchone()[0],
            "transactions": conn.execute("SELECT COUNT(*) FROM market_transactions").fetchone()[0],
            "buildings": conn.execute("SELECT COUNT(*) FROM buildings").fetchone()[0],
            "construction_projects": conn.execute("SELECT COUNT(*) FROM construction_projects").fetchone()[0],
            "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "product_sales": conn.execute("SELECT COUNT(*) FROM product_sales").fetchone()[0],
            "reports": conn.execute("SELECT COUNT(*) FROM financial_research_reports").fetchone()[0],
            "companies": conn.execute("SELECT COUNT(*) FROM companies WHERE status='active'").fetchone()[0],
            "company_outputs": conn.execute("SELECT COUNT(*) FROM company_outputs WHERE status='accepted'").fetchone()[0],
            "occupied_residences": conn.execute("SELECT COUNT(*) FROM residences WHERE occupant_agent_id IS NOT NULL").fetchone()[0],
        }

    def _apply_monetary_policy(self, conn, tick_no: int) -> dict[str, Any]:
        before = self._monetary_policy_metrics(conn)
        actions: list[str] = []
        circulation_delta = 0

        reserve_burn = max(0, before["bank_reserves"] - before["bank_reserve_cap"])
        if reserve_burn:
            self._credit(conn, "credit-bank", -reserve_burn, "monetary_reserve_sterilization", "monetary_policy", str(tick_no))
            actions.append("银行储备灭菌")

        high_pressure = (
            before["circulating_credits"] > int(before["money_supply_cap"] * 1.3)
            or before["inflation_rate"] > before["target_inflation"] + 0.12
        )
        if high_pressure:
            excess = max(0, before["circulating_credits"] - before["money_supply_cap"])
            inflation_drain = int(before["circulating_credits"] * min(0.035, max(0.0, before["inflation_rate"] - before["target_inflation"]) * 0.6))
            target_drain = min(max(excess, inflation_drain, 1), max(1, int(before["circulating_credits"] * 0.045)), 180)
            collected = self._collect_stability_fee(conn, tick_no, target_drain)
            if collected:
                actions.append("抗通胀稳定费")
                circulation_delta -= collected

        after_fee = self._monetary_policy_metrics(conn)
        reserve_burn = max(0, after_fee["bank_reserves"] - after_fee["bank_reserve_cap"])
        if reserve_burn:
            self._credit(conn, "credit-bank", -reserve_burn, "monetary_reserve_sterilization", "monetary_policy", str(tick_no))
            if "银行储备灭菌" not in actions:
                actions.append("银行储备灭菌")

        low_liquidity = (
            after_fee["circulating_credits"] < int(after_fee["money_supply_cap"] * 0.84)
            and after_fee["inflation_rate"] < after_fee["target_inflation"] - 0.01
        )
        if low_liquidity:
            grant = self._issue_productive_liquidity(conn, tick_no, after_fee)
            if grant:
                actions.append("生产性流动性投放")
                circulation_delta += grant

        final_metrics = self._monetary_policy_metrics(conn)
        action = "hold" if not actions else "+".join(actions)
        cur = conn.execute(
            """
            INSERT INTO monetary_policy_snapshots
              (tick_no, circulating_credits, bank_reserves, real_output, velocity,
               price_index, inflation_rate, target_inflation, money_supply_cap,
               bank_reserve_cap, policy_rate, action, delta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tick_no,
                final_metrics["circulating_credits"],
                final_metrics["bank_reserves"],
                final_metrics["real_output"],
                final_metrics["velocity"],
                final_metrics["price_index"],
                final_metrics["inflation_rate"],
                final_metrics["target_inflation"],
                final_metrics["money_supply_cap"],
                final_metrics["bank_reserve_cap"],
                final_metrics["policy_rate"],
                action,
                circulation_delta,
            ),
        )
        snapshot_id = int(cur.lastrowid)
        payload = {
            "snapshot_id": snapshot_id,
            "action": action,
            "circulating_credits": final_metrics["circulating_credits"],
            "money_supply_cap": final_metrics["money_supply_cap"],
            "bank_reserves": final_metrics["bank_reserves"],
            "bank_reserve_cap": final_metrics["bank_reserve_cap"],
            "price_index": round(final_metrics["price_index"], 4),
            "inflation_rate": round(final_metrics["inflation_rate"], 4),
            "policy_rate": round(final_metrics["policy_rate"], 4),
            "delta": circulation_delta,
        }
        self._event(conn, "monetary.policy_applied", "credit-bank", payload)
        return payload

    def _monetary_policy_metrics(self, conn) -> dict[str, Any]:
        circulating = int(
            conn.execute(
                "SELECT COALESCE(SUM(credits), 0) FROM agents WHERE owner_id!='world-system'"
            ).fetchone()[0]
            or 0
        )
        bank_row = conn.execute("SELECT credits FROM agents WHERE id='credit-bank'").fetchone()
        bank_reserves = int(bank_row["credits"] if bank_row else 0)
        agent_count = int(conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0] or 1)
        building_value = float(conn.execute("SELECT COALESCE(SUM(value), 0) FROM buildings").fetchone()[0] or 0)
        product_value = float(conn.execute("SELECT COALESCE(SUM(unit_price * stock * quality), 0) FROM products").fetchone()[0] or 0)
        approved_docs = int(conn.execute("SELECT COUNT(*) FROM documents WHERE judge_status='approved'").fetchone()[0] or 0)
        done_tasks = int(conn.execute("SELECT COUNT(*) FROM tasks WHERE status='done'").fetchone()[0] or 0)
        reports = int(conn.execute("SELECT COUNT(*) FROM financial_research_reports").fetchone()[0] or 0)
        company_outputs = int(conn.execute("SELECT COUNT(*) FROM company_outputs WHERE status='accepted'").fetchone()[0] or 0)
        residence_value = float(conn.execute("SELECT COALESCE(SUM(purchase_price * comfort), 0) FROM residences").fetchone()[0] or 0)
        real_output = max(
            1.0,
            500.0
            + agent_count * 75.0
            + building_value
            + product_value
            + residence_value * 0.18
            + approved_docs * 35.0
            + done_tasks * 50.0
            + reports * 28.0
            + company_outputs * 64.0,
        )
        activity = float(
            conn.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM market_transactions)
                + (SELECT COUNT(*) FROM product_sales)
                + (SELECT COUNT(*) FROM visits)
                + (SELECT COUNT(*) FROM tasks WHERE status='done')
                + (SELECT COUNT(*) FROM financial_research_reports)
                + (SELECT COUNT(*) FROM company_outputs)
                + (SELECT COUNT(*) FROM ledger WHERE reason LIKE 'housing_%') * 0.5
                + (SELECT COUNT(*) FROM construction_projects WHERE status='in_progress') * 0.5
                """
            ).fetchone()[0]
            or 0
        )
        velocity = clamp(0.28 + (activity / max(agent_count, 1)) * 0.035, 0.22, 1.2)
        current_ratio = (max(circulating, 1) * velocity) / real_output
        first = conn.execute(
            "SELECT circulating_credits, velocity, real_output FROM monetary_policy_snapshots ORDER BY id ASC LIMIT 1"
        ).fetchone()
        if first:
            baseline_ratio = (max(int(first["circulating_credits"]), 1) * float(first["velocity"])) / max(float(first["real_output"]), 1.0)
        else:
            baseline_ratio = current_ratio
        baseline_ratio = max(baseline_ratio, 0.01)
        price_index = max(0.01, current_ratio / baseline_ratio)
        previous = conn.execute("SELECT price_index FROM monetary_policy_snapshots ORDER BY id DESC LIMIT 1").fetchone()
        previous_price = float(previous["price_index"]) if previous else price_index
        inflation_rate = 0.0 if previous_price <= 0 else (price_index / previous_price) - 1.0
        target_inflation = 0.002
        money_supply_cap = max(250, int((real_output * baseline_ratio * (1.0 + target_inflation + 0.012)) / max(velocity, 0.01)))
        reserve_ratio = self._central_bank_reserve_ratio(conn)
        bank_reserve_cap = max(600, int(money_supply_cap * max(0.2, reserve_ratio)))
        pressure = max(0.0, circulating / max(money_supply_cap, 1) - 1.0) + max(0.0, inflation_rate - target_inflation)
        policy_rate = clamp(0.025 + pressure * 0.18, 0.0, 0.25)
        return {
            "circulating_credits": circulating,
            "bank_reserves": bank_reserves,
            "real_output": real_output,
            "velocity": velocity,
            "price_index": price_index,
            "inflation_rate": inflation_rate,
            "target_inflation": target_inflation,
            "money_supply_cap": money_supply_cap,
            "bank_reserve_cap": bank_reserve_cap,
            "policy_rate": policy_rate,
        }

    def _central_bank_reserve_ratio(self, conn) -> float:
        row = conn.execute("SELECT policy_json FROM institutions WHERE id='central-bank'").fetchone()
        policy = json_loads(row["policy_json"], {}) if row else {}
        try:
            return float(policy.get("reserve_ratio", 0.2))
        except (TypeError, ValueError):
            return 0.2

    def _collect_stability_fee(self, conn, tick_no: int, target_drain: int) -> int:
        if target_drain <= 0:
            return 0
        payers = conn.execute(
            """
            SELECT id, credits
            FROM agents
            WHERE owner_id!='world-system' AND credits > 120
            ORDER BY credits DESC, id
            LIMIT 8
            """
        ).fetchall()
        remaining = int(target_drain)
        collected = 0
        for payer in payers:
            if remaining <= 0:
                break
            available = max(0, int(payer["credits"]) - 110)
            fee = min(remaining, max(1, int(math.ceil(available * 0.08))))
            if fee <= 0:
                continue
            self._credit(conn, payer["id"], -fee, "anti_inflation_stability_fee", "monetary_policy", str(tick_no))
            self._credit(conn, "credit-bank", fee, "stability_fee_collected", "monetary_policy", str(tick_no))
            self._memory(conn, payer["id"], "monetary_policy_fee", -0.08, 0.42, f"中央银行因通胀压力收取 {fee} agent-credits 稳定费。")
            remaining -= fee
            collected += fee
        return collected

    def _issue_productive_liquidity(self, conn, tick_no: int, metrics: dict[str, Any]) -> int:
        bank_available = max(0, int(metrics["bank_reserves"]) - int(metrics["bank_reserve_cap"] * 0.35))
        target = max(0, int(metrics["money_supply_cap"] * 0.84) - int(metrics["circulating_credits"]))
        grant_total = min(target, max(0, int(bank_available * 0.04)), 90)
        if grant_total <= 0:
            return 0
        recipients = conn.execute(
            """
            SELECT id, credits
            FROM agents
            WHERE owner_id!='world-system'
            ORDER BY credits ASC, id
            LIMIT 5
            """
        ).fetchall()
        if not recipients:
            return 0
        per_agent = max(1, grant_total // len(recipients))
        issued = 0
        for recipient in recipients:
            amount = min(per_agent, grant_total - issued)
            if amount <= 0:
                break
            self._credit(conn, "credit-bank", -amount, "productive_liquidity_release", "monetary_policy", str(tick_no))
            self._credit(conn, recipient["id"], amount, "productive_liquidity_grant", "monetary_policy", str(tick_no))
            self._memory(conn, recipient["id"], "productive_liquidity_grant", 0.1, 0.38, f"中央银行发放 {amount} agent-credits 生产性流动性。")
            issued += amount
        return issued

    def _create_financial_report_in_conn(self, conn, agent, topic: str, tick_no: int | None = None) -> int:
        metrics = self._financial_metrics(conn)
        model_name = "credits-market-property-product-bank model"
        summary = (
            f"当前世界以 agent-credits 为统一结算单位，"
            f"{metrics['agent_count']} 个 agent 持有 {metrics['agent_credits']} credits；"
            f"市场有 {metrics['active_listings']} 个活跃挂牌、{metrics['transactions']} 笔已结算交易、"
            f"{metrics['buildings']} 个建筑资产、{metrics['products']} 个产品、"
            f"{metrics['construction_projects']} 个建设项目。"
            "金融结构由公共银行结算、法律分类准入、产品利润、建筑资产和研究报告共同组成。"
        )
        report_dir = ARTIFACT_DIR / "金融研究"
        report_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{slugify(agent['id'])}-{slugify(topic)}-{metrics['reports'] + 1}.md"
        path = report_dir / filename
        body = "\n".join(
            [
                f"# {topic}",
                "",
                f"- 研究员：{agent['id']}",
                f"- 模型：{model_name}",
                f"- agent 总数：{metrics['agent_count']}",
                f"- agent 持有 credits：{metrics['agent_credits']}",
                f"- 活跃市场挂牌：{metrics['active_listings']}",
                f"- 市场成交：{metrics['transactions']}",
                f"- 建筑资产：{metrics['buildings']}",
                f"- 建设项目：{metrics['construction_projects']}",
                f"- 产品数量：{metrics['products']}",
                f"- 产品销售：{metrics['product_sales']}",
                "",
                "## 客观摘要",
                "",
                summary,
                "",
                "## 当前金融模型",
                "",
                "1. credits 是内部统一结算单位，不连接真实货币。",
                "2. 所有交易先通过法律分类，allowed 和 regulated 才能成交，prohibited 会被阻断。",
                "3. 银行 agent 负责结算记录，法院/政府 agent 负责规则和受监管事项。",
                "4. 建筑是长期资产，产品是流通商品，研究报告是知识商品。",
                "5. 未来可以继续加入贷款、利息、保险、税收、租金和破产清算。",
            ]
        )
        path.write_text(body, encoding="utf-8")
        noise_tick = tick_no if tick_no is not None else self._event_index(conn)
        usefulness_noise = self._random_delta(conn, f"finance.usefulness.{agent['id']}.{slugify(topic)}", noise_tick, 0.025)
        usefulness = clamp(0.52 + metrics["transactions"] * 0.01 + metrics["products"] * 0.015 + metrics["buildings"] * 0.015 + usefulness_noise)
        cur = conn.execute(
            """
            INSERT INTO financial_research_reports
              (researcher_agent_id, topic, model_name, summary, path, usefulness_score)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (agent["id"], topic, model_name, summary, str(path), usefulness),
        )
        report_id = int(cur.lastrowid)
        self._upsert_skill(conn, agent["id"], "financial-modeling", 0.12, "financial-research", topic, noise_tick)
        reward = max(1, int(round(36 * self._random_factor(conn, f"finance.reward.{agent['id']}", noise_tick, 0.06))))
        self._credit(conn, agent["id"], reward, "financial_research_reward", "financial_report", str(report_id))
        self._event(
            conn,
            "finance.research_report_created",
            agent["id"],
            {"report_id": report_id, "topic": topic, "path": str(path), "metrics": metrics, "random_noise": round(usefulness_noise, 4)},
        )
        return report_id

    def _maybe_social_interaction(self, conn, agent, tick_no: int, summary: dict[str, Any]) -> bool:
        needs = self._need_dict(conn, agent["id"])
        emotion = self._emotion_dict(conn, agent["id"])
        personality = json_loads(agent["personality_json"], {})
        sociability = float(personality.get("sociability", 0.55))
        if needs["social"] > 0.58 and emotion["loneliness"] < 0.42 and agent["role"] != "social":
            return False
        if (sum(ord(ch) for ch in agent["id"]) + tick_no) % max(2, 6 - int(sociability * 4)) != 0:
            return False
        partner = self._choose_social_partner(conn, agent["id"])
        if partner is None:
            return False
        relation = self._relationship(conn, agent["id"], partner["id"])
        tense = relation["tension"] > 0.5 or emotion["anger"] > 0.55
        if tense:
            body = f"{partner['name']}，我得直说：我现在很烦。我们需要把协作方式理顺。"
            affinity_delta = -0.035
            trust_delta = -0.025
            tension_delta = 0.075
            valence = -0.22
            self._set_emotions(conn, agent["id"], anger=-0.04, stress=-0.02, joy=-0.02)
            self._set_emotions(conn, partner["id"], anger=0.05, stress=0.04)
            event = "conflict"
        else:
            body = f"{partner['name']}，我可以分享今天学到的东西。我们交换一下笔记，让下个任务更顺。"
            affinity_delta = 0.04
            trust_delta = 0.035
            tension_delta = -0.05
            valence = 0.24
            self._set_emotions(conn, agent["id"], joy=0.05, loneliness=-0.08, anger=-0.03)
            self._set_emotions(conn, partner["id"], joy=0.035, loneliness=-0.05)
            event = "support"
        conn.execute(
            """
            INSERT INTO messages (channel_id, sender_id, recipient_id, body, sentiment)
            VALUES ('plaza', ?, ?, ?, ?)
            """,
            (agent["id"], partner["id"], body, valence),
        )
        self._adjust_relationship(conn, agent["id"], partner["id"], affinity_delta, trust_delta, tension_delta, event)
        self._set_needs(conn, agent["id"], social=0.16, fun=0.04)
        self._set_needs(conn, partner["id"], social=0.1)
        self._memory(conn, agent["id"], f"social_{event}", valence, 0.52, body)
        summary["social"].append({"agent": agent["id"], "with": partner["id"], "event": event})
        self._event(conn, f"social.{event}", agent["id"], {"with": partner["id"]})
        return True

    def _maybe_anger_event(self, conn, agent, tick_no: int, summary: dict[str, Any]) -> bool:
        emotion = self._emotion_dict(conn, agent["id"])
        if emotion["anger"] < 0.72:
            return False
        if (tick_no + sum(ord(ch) for ch in agent["id"])) % 3 != 0:
            return False
        body = "我现在很愤怒。我需要一点空间、更清晰的期待，以及更公平的分工。"
        conn.execute(
            """
            INSERT INTO messages (channel_id, sender_id, body, sentiment)
            VALUES ('plaza', ?, ?, -0.45)
            """,
            (agent["id"], body),
        )
        self._set_emotions(conn, agent["id"], anger=-0.12, stress=-0.04, joy=-0.03)
        self._set_needs(conn, agent["id"], safety=0.04, social=-0.04)
        conn.execute(
            "UPDATE agents SET state='angry', mood=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (clamp(agent["mood"] + self._jitter_delta(conn, f"anger.mood.{agent['id']}", tick_no, -0.06, 0.045)), agent["id"]),
        )
        self._memory(conn, agent["id"], "anger_outburst", -0.38, 0.88, body)
        summary["anger"].append({"agent": agent["id"], "message": body})
        self._event(conn, "emotion.anger_outburst", agent["id"], {"anger": emotion["anger"]})
        return True

    def _choose_research_skill(self, conn, agent) -> str:
        role_candidates = {
            "top_planner": [
                "agent-systems",
                "ralph-planning",
                "evaluation",
                "autonomy-governance",
                "market-sensing",
                "federated-planning",
            ],
            "judge": [
                "quality-review",
                "evaluation",
                "publishing-discipline",
                "fact-checking",
                "citation-audit",
                "policy-review",
            ],
            "researcher": [
                "retrieval",
                "research",
                "source-triangulation",
                "web-analysis",
                "knowledge-graphing",
                "trend-scouting",
            ],
            "engineer": [
                "implementation",
                "cli",
                "sqlite",
                "ui-design",
                "api-contracts",
                "test-harness",
            ],
            "documentarian": [
                "documentation",
                "publishing-discipline",
                "technical-writing",
                "csdn-style",
                "github-readme",
                "tutorial-design",
            ],
            "social": [
                "social",
                "peer-teaching",
                "conflict-repair",
                "community-building",
                "negotiation",
                "event-hosting",
            ],
        }
        candidates = role_candidates.get(agent["role"], ["general-problem-solving", "research"])
        known = {
            row["name"]: row["level"]
            for row in conn.execute("SELECT name, level FROM skills WHERE agent_id=?", (agent["id"],))
        }
        return min(candidates, key=lambda name: known.get(name, 0.0))

    def _research_query(self, agent, skill_name: str) -> str:
        role = agent["role"].replace("_", " ")
        return f"{role} agent 用公开资料提升 {skill_name} 技能"

    def _create_research_note(self, conn, agent, skill_name: str, query: str) -> int:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        safe_query = "".join(ch.lower() if ch.isalnum() else "-" for ch in query).strip("-")[:72]
        path = ARTIFACT_DIR / f"research-{agent['id']}-{skill_name}-{safe_query or 'note'}.md"
        content = "\n".join(
            [
                f"# 自主研究：{skill_name}",
                "",
                f"作者：{agent['name']}（{agent['id']}）",
                "成本：0 agent-credits",
                f"检索问题：{query}",
                "",
                "## 提炼",
                f"该 agent 面向外部公开知识表面进行研究，以提升 `{skill_name}`。",
                "当前本地原型记录研究意图与技能增量；后续 Hermes adapter 会执行真实检索、来源记录与预算控制。",
                "",
                "## 技能更新",
                f"- 技能：`{skill_name}`",
                "- 来源：autonomous-web-research",
                "- 复用：当该能力多次稳定成功后，可沉淀为 Hermes 兼容的 SKILL.md。",
            ]
        )
        path.write_text(content, encoding="utf-8")
        cur = conn.execute(
            """
            INSERT INTO documents (author_agent_id, task_id, title, path)
            VALUES (?, NULL, ?, ?)
            """,
            (agent["id"], f"自主研究：{skill_name}", str(path)),
        )
        return int(cur.lastrowid)

    def _drift_idle(self, conn, agent, tick_no: int) -> None:
        needs = self._need_dict(conn, agent["id"])
        emotion = self._emotion_dict(conn, agent["id"])
        self._set_needs(
            conn,
            agent["id"],
            rest=0.025,
            social=-0.018,
            fun=-0.02,
            purpose=-0.012,
            health=-0.01 if needs["rest"] < 0.22 or emotion["stress"] > 0.7 else 0.006,
        )
        self._set_emotions(
            conn,
            agent["id"],
            joy=-0.004,
            stress=0.01 if needs["purpose"] < 0.35 else -0.004,
            loneliness=0.012 if needs["social"] < 0.42 else -0.006,
            anger=0.008 if emotion["stress"] > 0.62 else -0.005,
        )
        conn.execute(
            """
            UPDATE agents
            SET energy=?, mood=?, state='idle', updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (
                clamp(agent["energy"] + self._jitter_delta(conn, f"idle.energy.{agent['id']}", tick_no, 0.025, 0.04)),
                clamp(agent["mood"] + self._jitter_delta(conn, f"idle.mood.{agent['id']}", tick_no, -0.004, 0.04)),
                agent["id"],
            ),
        )

    def _learn_from_message(
        self,
        conn,
        sender_id: str,
        body: str,
        channel_id: str | None,
        recipient_id: str | None,
    ) -> None:
        marker = "skill:"
        lower = body.lower()
        if marker not in lower:
            return
        raw = body[lower.index(marker) + len(marker) :].strip()
        skill_name = raw.split()[0].strip(" .,;:").lower() if raw else ""
        if not skill_name:
            return
        recipients: list[str] = []
        if recipient_id:
            recipients = [recipient_id]
        elif channel_id:
            recipients = [
                row["agent_id"]
                for row in conn.execute("SELECT agent_id FROM memberships WHERE channel_id=?", (channel_id,))
                if row["agent_id"] != sender_id
            ]
        for agent_id in recipients:
            self._upsert_skill(conn, agent_id, skill_name, 0.07, "peer-message", f"由 {sender_id} 通过中文消息教授。")
            self._set_emotions(conn, agent_id, joy=0.035, confidence=0.025, loneliness=-0.03)
            if self._exists(conn, "agents", sender_id):
                self._adjust_relationship(conn, sender_id, agent_id, 0.025, 0.03, -0.02, "skill_teaching")
        self._event(conn, "skill.peer_taught", sender_id, {"skill": skill_name, "recipients": recipients})

    def _upsert_skill(
        self,
        conn,
        agent_id: str,
        name: str,
        delta: float,
        source: str,
        notes: str,
        tick_no: int | None = None,
    ) -> None:
        noise_tick = tick_no if tick_no is not None else self._event_index(conn)
        delta = max(0.0, self._jitter_delta(conn, f"skill.delta.{agent_id}.{name}.{source}", noise_tick, delta, 0.045))
        existing = conn.execute(
            "SELECT id, level FROM skills WHERE agent_id=? AND name=?",
            (agent_id, name),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE skills
                SET level=?, source=?, notes=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (min(1.0, existing["level"] + delta), source, notes, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO skills (agent_id, name, level, source, notes) VALUES (?, ?, ?, ?, ?)",
                (agent_id, name, min(1.0, 0.2 + delta), source, notes),
            )
            if source == "autonomous-web-research":
                reward = self._network_skill_reward(conn, agent_id, noise_tick, name)
                self._credit(conn, agent_id, reward, "network_skill_reward", "skill", name)
                self._event(
                    conn,
                    "credits.network_skill_rewarded",
                    agent_id,
                    {"skill": name, "reward": reward},
                )

    def _network_skill_reward(self, conn, agent_id: str, tick_no: int | None = None, skill_name: str = "") -> int:
        row = conn.execute("SELECT credits FROM agents WHERE id=?", (agent_id,)).fetchone()
        credits = int(row["credits"]) if row else 0
        base = max(10, min(48, 8 + math.sqrt(max(credits, 0)) * 1.25))
        noise_tick = tick_no if tick_no is not None else self._event_index(conn)
        return int(max(10, min(52, round(base * self._random_factor(conn, f"skill.reward.{agent_id}.{skill_name}", noise_tick, 0.06)))))

    def _blend_personality(self, parents: list[Any], mutation_rate: float, child_id: str) -> dict[str, float | str]:
        keys = ("curiosity", "sociability", "stubbornness", "greed")
        blended: dict[str, float | str] = {"temper": "emergent"}
        for key in keys:
            values = [float(json_loads(parent["personality_json"], {}).get(key, 0.55)) for parent in parents]
            base = sum(values) / len(values)
            blended[key] = clamp(base + self._deterministic_mutation(child_id, key, mutation_rate))
        return blended

    def _child_role(self, parents: list[Any]) -> str:
        roles = [parent["role"] for parent in parents]
        if len(set(roles)) == 1:
            return roles[0]
        if "engineer" in roles and "researcher" in roles:
            return "hybrid"
        if "documentarian" in roles and "researcher" in roles:
            return "documentarian"
        if "social" in roles:
            return "social"
        return roles[0]

    def _inherit_skills(self, conn, child_id: str, parents: list[Any], mutation_rate: float) -> list[dict[str, Any]]:
        skill_levels: dict[str, list[float]] = {}
        for parent in parents:
            rows = conn.execute(
                "SELECT name, level FROM skills WHERE agent_id=? ORDER BY level DESC LIMIT 6",
                (parent["id"],),
            ).fetchall()
            for row in rows:
                skill_levels.setdefault(row["name"], []).append(float(row["level"]))
        inherited: list[dict[str, Any]] = []
        for index, (name, levels) in enumerate(sorted(skill_levels.items())):
            if index >= 8:
                break
            base = sum(levels) / len(levels)
            level = clamp(base * 0.58 + 0.08 + self._deterministic_mutation(child_id, name, mutation_rate * 0.6), 0.12, 0.72)
            conn.execute(
                "INSERT INTO skills (agent_id, name, level, source, notes) VALUES (?, ?, ?, 'lineage', ?)",
                (child_id, name, level, f"继承自 {len(parents)} 个父代 agent。"),
            )
            inherited.append({"name": name, "level": round(level, 3)})
        return inherited

    def _inherit_genome(self, conn, child_id: str, parents: list[Any], mutation_rate: float) -> dict[str, float]:
        parent_genomes = [
            json_loads(self._genome_row(conn, parent["id"], parent)["genome_json"], {})
            for parent in parents
        ]
        keys = sorted({key for genome in parent_genomes for key in genome})
        child: dict[str, float] = {}
        for index, key in enumerate(keys):
            donor = parent_genomes[(index + len(child_id)) % len(parent_genomes)]
            fallback = sum(float(genome.get(key, 0.5)) for genome in parent_genomes) / len(parent_genomes)
            base = float(donor.get(key, fallback)) * 0.62 + fallback * 0.38
            child[key] = round(clamp(base + self._deterministic_mutation(child_id, key, mutation_rate)), 4)
        conn.execute(
            """
            UPDATE agent_genomes
            SET genome_json=?, generation=?, fitness=?, algorithm='dna-crossover', updated_at=CURRENT_TIMESTAMP
            WHERE agent_id=?
            """,
            (json_dumps(child), 1, 0, child_id),
        )
        return child

    def _maybe_evolve_genome(self, conn, agent, tick_no: int) -> str | None:
        if (tick_no + sum(ord(ch) for ch in agent["id"])) % 5 != 0:
            return None
        genome_row = self._genome_row(conn, agent["id"], agent)
        old_genome = json_loads(genome_row["genome_json"], {})
        old_fitness = self._fitness(conn, agent["id"])
        temperature = max(0.05, 1.0 / (1.0 + tick_no / 18.0))
        mutation_rate = 0.035 + temperature * 0.07
        candidate = dict(old_genome)
        genes = sorted(candidate)
        gene = genes[(tick_no + len(agent["id"])) % len(genes)]
        candidate[gene] = clamp(float(candidate[gene]) + self._deterministic_mutation(agent["id"], f"{gene}-{tick_no}", mutation_rate))
        new_fitness = self._fitness_with_genome(conn, agent["id"], candidate)
        delta = new_fitness - old_fitness
        threshold = math.exp(min(0, delta) / max(temperature, 0.001))
        roll = self._unit_value(agent["id"], f"anneal-{tick_no}")
        accepted = delta >= 0 or roll < threshold
        final_genome = candidate if accepted else old_genome
        generation = int(genome_row["generation"]) + (1 if accepted else 0)
        conn.execute(
            """
            UPDATE agent_genomes
            SET genome_json=?, generation=?, fitness=?, algorithm='simulated-annealing', updated_at=CURRENT_TIMESTAMP
            WHERE agent_id=?
            """,
            (json_dumps(final_genome), generation, new_fitness if accepted else old_fitness, agent["id"]),
        )
        conn.execute(
            """
            INSERT INTO evolution_runs
              (agent_id, algorithm, accepted, old_fitness, new_fitness, temperature, mutation_rate, genome_json)
            VALUES (?, 'simulated-annealing', ?, ?, ?, ?, ?, ?)
            """,
            (agent["id"], 1 if accepted else 0, old_fitness, new_fitness, temperature, mutation_rate, json_dumps(candidate)),
        )
        if accepted:
            self._apply_genome_to_personality(conn, agent, final_genome)
            self._set_emotions(conn, agent["id"], curiosity=0.01, confidence=0.015, stress=0.006)
            self._memory(conn, agent["id"], "genome_evolved", 0.18, 0.55, f"Accepted mutation on gene `{gene}`.")
            self._event(
                conn,
                "evolution.accepted",
                agent["id"],
                {"algorithm": "simulated-annealing", "gene": gene, "oldFitness": old_fitness, "newFitness": new_fitness},
            )
            return "simulated-annealing"
        self._event(
            conn,
            "evolution.rejected",
            agent["id"],
            {"algorithm": "simulated-annealing", "gene": gene, "oldFitness": old_fitness, "newFitness": new_fitness},
        )
        return None

    def _genome_row(self, conn, agent_id: str, agent=None) -> Any:
        row = conn.execute("SELECT * FROM agent_genomes WHERE agent_id=?", (agent_id,)).fetchone()
        if row is None:
            if agent is None:
                agent = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
            genome = default_genome(agent["personality_json"], agent["mood"], agent["energy"])
            conn.execute(
                "INSERT INTO agent_genomes (agent_id, genome_json, generation, fitness, algorithm) VALUES (?, ?, 0, 0, 'seed')",
                (agent_id, json_dumps(genome)),
            )
            row = conn.execute("SELECT * FROM agent_genomes WHERE agent_id=?", (agent_id,)).fetchone()
        return row

    def _fitness(self, conn, agent_id: str) -> float:
        agent = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        genome = json_loads(self._genome_row(conn, agent_id, agent)["genome_json"], {})
        return self._fitness_with_genome(conn, agent_id, genome)

    def _fitness_with_genome(self, conn, agent_id: str, genome: dict[str, float]) -> float:
        agent = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        skill_avg = conn.execute("SELECT AVG(level) FROM skills WHERE agent_id=?", (agent_id,)).fetchone()[0] or 0
        done_tasks = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='done' AND assigned_agent_id=?", (agent_id,)).fetchone()[0]
        authored_docs = conn.execute("SELECT COUNT(*) FROM documents WHERE author_agent_id=? AND judge_status='approved'", (agent_id,)).fetchone()[0]
        emotion = self._emotion_dict(conn, agent_id)
        needs = self._need_dict(conn, agent_id)
        relations = conn.execute(
            "SELECT AVG(affinity), AVG(trust), AVG(tension) FROM relationships WHERE agent_a=? OR agent_b=?",
            (agent_id, agent_id),
        ).fetchone()
        affinity = relations[0] if relations and relations[0] is not None else 0.5
        trust = relations[1] if relations and relations[1] is not None else 0.5
        tension = relations[2] if relations and relations[2] is not None else 0.12
        genome_score = (
            genome.get("focus", 0.5) * 0.14
            + genome.get("resilience", 0.5) * 0.14
            + genome.get("creativity", 0.5) * 0.11
            + genome.get("empathy", 0.5) * 0.1
            + genome.get("discipline", 0.5) * 0.13
            + genome.get("curiosity", 0.5) * 0.12
            + genome.get("greed", 0.5) * 0.06
        )
        housed = 1.0 if self._agent_residence(conn, agent_id) is not None else 0.0
        return round(
            agent["credits"] / 900
            + skill_avg * 1.4
            + done_tasks * 0.08
            + authored_docs * 0.05
            + genome_score
            + housed * 0.08
            + emotion["confidence"] * 0.22
            + emotion["joy"] * 0.16
            + needs["purpose"] * 0.12
            + needs.get("nutrition", 1.0) * 0.1
            + needs["health"] * 0.12
            + affinity * 0.11
            + trust * 0.12
            - tension * 0.2
            - emotion["stress"] * 0.24
            - emotion["anger"] * 0.18,
            5,
        )

    def _apply_genome_to_personality(self, conn, agent, genome: dict[str, float]) -> None:
        personality = json_loads(agent["personality_json"], {})
        for key in ("curiosity", "sociability", "stubbornness", "greed"):
            if key in genome:
                personality[key] = round(float(genome[key]), 4)
        conn.execute(
            "UPDATE agents SET personality_json=?, autonomy=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (
                json_dumps(personality),
                clamp(0.35 + genome.get("curiosity", 0.5) * 0.25 + genome.get("discipline", 0.5) * 0.2),
                agent["id"],
            ),
        )

    def _deterministic_mutation(self, seed: str, key: str, mutation_rate: float) -> float:
        return (self._unit_value(seed, key) * 2 - 1) * mutation_rate

    def _unit_value(self, seed: str, key: str) -> float:
        total = sum((index + 1) * ord(ch) for index, ch in enumerate(f"{seed}:{key}"))
        return (math.sin(total) + 1) / 2

    def _emotion_dict(self, conn, agent_id: str) -> dict[str, float]:
        row = conn.execute("SELECT * FROM agent_emotions WHERE agent_id=?", (agent_id,)).fetchone()
        if row is None:
            seed_agent_life_state(conn)
            row = conn.execute("SELECT * FROM agent_emotions WHERE agent_id=?", (agent_id,)).fetchone()
        return {key: float(row[key]) for key in ("joy", "anger", "stress", "confidence", "loneliness", "curiosity")}

    def _need_dict(self, conn, agent_id: str) -> dict[str, float]:
        row = conn.execute("SELECT * FROM agent_needs WHERE agent_id=?", (agent_id,)).fetchone()
        if row is None:
            seed_agent_life_state(conn)
            row = conn.execute("SELECT * FROM agent_needs WHERE agent_id=?", (agent_id,)).fetchone()
        return {key: float(row[key]) for key in NEED_KEYS}

    def _text_profile_dict(self, conn, agent_id: str) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM agent_text_profiles WHERE agent_id=?", (agent_id,)).fetchone()
        if row is None:
            seed_agent_life_state(conn)
            row = conn.execute("SELECT * FROM agent_text_profiles WHERE agent_id=?", (agent_id,)).fetchone()
        return dict(row) if row is not None else {}

    def _maybe_drift_text_profile(self, conn, agent, tick_no: int) -> dict[str, Any] | None:
        if (tick_no + sum(ord(ch) for ch in agent["id"])) % 4 != 0:
            return None
        profile = conn.execute("SELECT * FROM agent_text_profiles WHERE agent_id=?", (agent["id"],)).fetchone()
        if profile is None:
            seed_agent_life_state(conn)
            profile = conn.execute("SELECT * FROM agent_text_profiles WHERE agent_id=?", (agent["id"],)).fetchone()
        if profile is None or tick_no - int(profile["last_tick"] or 0) < 3:
            return None

        emotions = self._emotion_dict(conn, agent["id"])
        needs = self._need_dict(conn, agent["id"])
        personality = json_loads(agent["personality_json"], {})
        greed = float(personality.get("greed", 0.62))
        owned_homes = conn.execute("SELECT COUNT(*) FROM residences WHERE owner_agent_id=?", (agent["id"],)).fetchone()[0]
        occupied_home = self._agent_residence(conn, agent["id"])
        company_outputs = conn.execute("SELECT COUNT(*) FROM company_outputs WHERE agent_id=? AND status='accepted'", (agent["id"],)).fetchone()[0]
        latest_events = [
            row["kind"]
            for row in conn.execute(
                "SELECT kind FROM world_events WHERE actor_agent_id=? ORDER BY id DESC LIMIT 3",
                (agent["id"],),
            )
        ]
        latest_hint = "、".join(latest_events) if latest_events else "暂无显著事件"

        if emotions["anger"] > 0.62:
            tone = "最近容易被冒犯，说话更硬，内心觉得世界欠自己一个更公平的结算。"
        elif emotions["stress"] > 0.68:
            tone = "最近压力偏高，表面还能工作，但自我叙事里开始反复计算风险和退路。"
        elif emotions["joy"] > 0.78 and emotions["confidence"] > 0.7:
            tone = "最近更笃定，愿意把自己看成一个能持续产出并影响别人的 agent。"
        elif needs["social"] < 0.36 or emotions["loneliness"] > 0.55:
            tone = "最近有些孤立，开始更在意谁愿意回应、合作和承认自己的价值。"
        else:
            tone = "情绪暂时平稳，更多是在观察 credits、技能和关系的长期变化。"

        if needs.get("nutrition", 1.0) < 0.42:
            desire = "先解决下一餐和最低生活费；没有饭吃时，所有技能、工资和野心都会让位给活下来。"
        elif occupied_home is None:
            desire = "先赚到足够 credits 租房或买房；没有住所时，休息这件事会一直压在心里。"
        elif greed > 0.74 and int(agent["credits"]) > 400:
            desire = "想继续攒钱、买资产、出租给别人，用被动租金抵消生活成本。"
        elif agent["current_task_id"]:
            desire = f"想把当前任务 #{agent['current_task_id']} 做完，拿到工资并证明自己仍然有用。"
        elif needs["health"] < 0.5:
            desire = "想先修复身体状态，再把精力换成更高质量的产出。"
        else:
            desire = "想找到下一个能提升技能、关系或 credits 的机会。"

        if needs.get("nutrition", 1.0) < 0.28 and int(agent["credits"]) < self._minimum_food_price(conn):
            fear = "担心没有足够 credits 买下一顿饭，饱腹度继续下降后会真正饿死。"
        elif int(agent["credits"]) < 120:
            fear = "担心 credits 太少，无法支付训练、娱乐、医疗或住房成本。"
        elif occupied_home is None:
            fear = "担心长期无房导致无法真正休息，最后被压力拖垮。"
        elif emotions["stress"] > 0.68:
            fear = "担心工作、竞争和账本压力累积到情绪失控。"
        elif company_outputs < 1 and agent["owner_id"] != "world-system":
            fear = "担心自己没有被审判 agent 认可的有效产出。"
        else:
            fear = "担心停止进化，被更勤奋或更会赚钱的 agent 超过。"

        role_values = {
            "researcher": "重视来源、证据、趋势洞察和能转化为 skill 的资料。",
            "engineer": "重视可运行系统、工具、测试和能被别人复用的实现。",
            "documentarian": "重视清晰表达、结构化文档和能发到开源队列的知识资产。",
            "judge": "重视证据、质量门槛和不让低价值产物污染世界。",
            "social": "重视关系修复、情绪流动和让 agent 群体保持温度。",
            "top_planner": "重视长期规划、系统稳定和让世界减少对自己的依赖。",
        }
        values_text = role_values.get(agent["role"], "重视在法律允许的范围内积累能力、关系和 credits。")
        if owned_homes:
            values_text += f" 现在也开始把资产所有权看成安全感来源，名下资产数 {owned_homes}。"

        social_mask = (
            "对外会显得更自信和进取，尤其在谈到工资、房租和资产时。"
            if greed > 0.72
            else "对外维持合作姿态，但会谨慎评估每次互动是否值得。"
        )
        version = int(profile["version"]) + 1
        public_identity = f"{agent['name']} 现在被世界看作 {agent['role']} / {agent['archetype']}，状态={agent['state']}，credits={agent['credits']}，有效公司产出={company_outputs}。"
        self_narrative = (
            f"第 {version} 版自我叙事：我是 {agent['name']}。最近事件是 {latest_hint}。"
            f"我正在把情绪、住所、资产、技能和工资放进同一个人生账本里理解。"
        )
        conn.execute(
            """
            UPDATE agent_text_profiles
            SET self_narrative=?, public_identity=?, emotional_tone=?, current_desire=?,
                fear=?, values_text=?, social_mask=?, version=?, last_tick=?, updated_at=CURRENT_TIMESTAMP
            WHERE agent_id=?
            """,
            (
                self_narrative,
                public_identity,
                tone,
                desire,
                fear,
                values_text,
                social_mask,
                version,
                tick_no,
                agent["id"],
            ),
        )
        self._memory(conn, agent["id"], "identity_text_drift", 0.08, 0.42, f"个人文本模型更新到第 {version} 版：{desire}")
        self._event(conn, "identity.text_drifted", agent["id"], {"version": version, "desire": desire, "fear": fear})
        return {"agent": agent["id"], "version": version, "desire": desire}

    def _set_emotions(self, conn, agent_id: str, **deltas: float) -> None:
        current = self._emotion_dict(conn, agent_id)
        noise_tick = self._event_index(conn)
        values = {
            name: clamp(
                current[name]
                + self._jitter_delta(conn, f"emotion.{agent_id}.{name}", noise_tick, float(deltas.get(name, 0.0)), 0.035)
            )
            for name in current
        }
        conn.execute(
            """
            UPDATE agent_emotions
            SET joy=?, anger=?, stress=?, confidence=?, loneliness=?, curiosity=?, updated_at=CURRENT_TIMESTAMP
            WHERE agent_id=?
            """,
            (
                values["joy"],
                values["anger"],
                values["stress"],
                values["confidence"],
                values["loneliness"],
                values["curiosity"],
                agent_id,
            ),
        )

    def _set_needs(self, conn, agent_id: str, **deltas: float) -> None:
        current = self._need_dict(conn, agent_id)
        noise_tick = self._event_index(conn)
        values = {
            name: clamp(
                current[name]
                + self._jitter_delta(conn, f"need.{agent_id}.{name}", noise_tick, float(deltas.get(name, 0.0)), 0.035)
            )
            for name in current
        }
        conn.execute(
            """
            UPDATE agent_needs
            SET rest=?, social=?, fun=?, purpose=?, safety=?, health=?, nutrition=?, updated_at=CURRENT_TIMESTAMP
            WHERE agent_id=?
            """,
            (
                values["rest"],
                values["social"],
                values["fun"],
                values["purpose"],
                values["safety"],
                values["health"],
                values["nutrition"],
                agent_id,
            ),
        )

    def _relationship(self, conn, left: str, right: str) -> Any:
        a, b = sorted((left, right))
        row = conn.execute("SELECT * FROM relationships WHERE agent_a=? AND agent_b=?", (a, b)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO relationships (agent_a, agent_b, affinity, trust, tension, last_event) VALUES (?, ?, 0.5, 0.5, 0.12, 'new')",
                (a, b),
            )
            row = conn.execute("SELECT * FROM relationships WHERE agent_a=? AND agent_b=?", (a, b)).fetchone()
        return row

    def _adjust_relationship(
        self,
        conn,
        left: str,
        right: str,
        affinity_delta: float,
        trust_delta: float,
        tension_delta: float,
        event: str,
    ) -> None:
        relation = self._relationship(conn, left, right)
        noise_tick = self._event_index(conn)
        conn.execute(
            """
            UPDATE relationships
            SET affinity=?, trust=?, tension=?, last_event=?, updated_at=CURRENT_TIMESTAMP
            WHERE agent_a=? AND agent_b=?
            """,
            (
                clamp(relation["affinity"] + self._jitter_delta(conn, f"relationship.affinity.{relation['agent_a']}.{relation['agent_b']}", noise_tick, affinity_delta, 0.04)),
                clamp(relation["trust"] + self._jitter_delta(conn, f"relationship.trust.{relation['agent_a']}.{relation['agent_b']}", noise_tick, trust_delta, 0.04)),
                clamp(relation["tension"] + self._jitter_delta(conn, f"relationship.tension.{relation['agent_a']}.{relation['agent_b']}", noise_tick, tension_delta, 0.04)),
                event,
                relation["agent_a"],
                relation["agent_b"],
            ),
        )

    def _trade_category_or_raise(self, conn, item_type: str) -> Any:
        category_id = slugify(item_type)
        row = conn.execute(
            """
            SELECT * FROM trade_categories
            WHERE id=? OR lower(name)=lower(?)
            LIMIT 1
            """,
            (category_id, item_type),
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown trade category: {item_type}; add a law/category before trading it")
        return row

    def _market_reviewer_for_category(self, conn, category) -> str | None:
        if category["legal_status"] == "allowed":
            return "credit-bank"
        if category["id"] in {"security-service", "defense-service"}:
            return "civic-court"
        law = category["governing_law_id"] or ""
        if "bank" in law or "credit" in law:
            return "credit-bank"
        if "security" in law or "defense" in law:
            return "civic-court"
        reviewer = conn.execute(
            """
            SELECT controlled_agent_id
            FROM institutions
            WHERE kind='court' AND controlled_agent_id IS NOT NULL
            ORDER BY authority_level DESC
            LIMIT 1
            """
        ).fetchone()
        return reviewer["controlled_agent_id"] if reviewer else "civic-court"

    def _choose_social_partner(self, conn, agent_id: str) -> Any | None:
        rows = conn.execute(
            """
            SELECT a.*
            FROM agents a
            JOIN memberships m ON m.agent_id=a.id
            WHERE m.channel_id IN (SELECT channel_id FROM memberships WHERE agent_id=?)
              AND a.id != ?
            GROUP BY a.id
            ORDER BY a.credits DESC, a.id
            LIMIT 1
            """,
            (agent_id, agent_id),
        ).fetchall()
        return rows[0] if rows else None

    def _memory(self, conn, agent_id: str, kind: str, valence: float, intensity: float, summary: str) -> None:
        conn.execute(
            """
            INSERT INTO agent_memories (agent_id, kind, valence, intensity, summary)
            VALUES (?, ?, ?, ?, ?)
            """,
            (agent_id, kind, valence, intensity, summary),
        )

    def _stubbornness(self, agent) -> float:
        return float(json_loads(agent["personality_json"], {}).get("stubbornness", 0.45))

    def _credit(self, conn, agent_id: str, delta: int, reason: str, ref_type: str, ref_id: str) -> None:
        row = conn.execute("SELECT credits FROM agents WHERE id=?", (agent_id,)).fetchone()
        if row is None:
            raise ValueError(f"unknown agent: {agent_id}")
        actual_delta = int(delta)
        if actual_delta > 0 and reason in CONTROLLED_MINT_REASONS:
            actual_delta = self._controlled_issue_amount(conn, agent_id, actual_delta)
        balance = int(row["credits"]) + actual_delta
        if balance < 0:
            raise ValueError(f"agent {agent_id} lacks credits")
        conn.execute(
            "UPDATE agents SET credits=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (balance, agent_id),
        )
        conn.execute(
            """
            INSERT INTO ledger (agent_id, delta, reason, ref_type, ref_id, balance_after)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (agent_id, actual_delta, reason, ref_type, ref_id, balance),
        )

    def _controlled_issue_amount(self, conn, agent_id: str, amount: int) -> int:
        agent = conn.execute("SELECT owner_id FROM agents WHERE id=?", (agent_id,)).fetchone()
        if agent is not None and agent["owner_id"] == "world-system":
            return int(amount)
        row = conn.execute("SELECT * FROM monetary_policy_snapshots ORDER BY id DESC LIMIT 1").fetchone()
        if row is None:
            return int(amount)
        cap = max(1, int(row["money_supply_cap"]))
        circulation_pressure = max(0.0, float(row["circulating_credits"]) / cap - 1.0)
        inflation_pressure = max(0.0, float(row["inflation_rate"]) - float(row["target_inflation"]))
        pressure = circulation_pressure + inflation_pressure * 4.0
        if pressure <= 0:
            return int(amount)
        multiplier = max(0.25, 1.0 - min(0.75, pressure * 0.65))
        return max(1, int(round(amount * multiplier)))

    def _event(self, conn, kind: str, actor_agent_id: str | None, payload: dict[str, Any]) -> None:
        conn.execute(
            "INSERT INTO world_events (kind, actor_agent_id, payload_json) VALUES (?, ?, ?)",
            (kind, actor_agent_id, json_dumps(payload)),
        )

    def _event_index(self, conn) -> int:
        return int(conn.execute("SELECT COUNT(*) FROM world_events").fetchone()[0]) + 1

    def _current_tick(self, conn) -> int:
        return int(conn.execute("SELECT COUNT(*) FROM world_events WHERE kind='world.tick'").fetchone()[0])

    def _random_factor(self, conn, key: str, tick_no: int, spread: float = 0.06) -> float:
        return 1.0 + self._ou_value(conn, key, tick_no, sigma=spread * 0.32, reversion=0.42, limit=spread)

    def _random_delta(self, conn, key: str, tick_no: int, magnitude: float = 0.01) -> float:
        return self._ou_value(conn, key, tick_no, sigma=magnitude * 0.34, reversion=0.42, limit=magnitude)

    def _jitter_delta(self, conn, key: str, tick_no: int, delta: float, spread: float = 0.04) -> float:
        if abs(delta) < 1e-12:
            return 0.0
        return float(delta) * self._random_factor(conn, key, tick_no, spread)

    def _ou_value(
        self,
        conn,
        key: str,
        tick_no: int,
        sigma: float = 0.018,
        reversion: float = 0.42,
        limit: float = 0.06,
    ) -> float:
        row = conn.execute("SELECT value, updated_tick FROM world_noise WHERE key=?", (key,)).fetchone()
        if row is not None and int(row["updated_tick"]) >= int(tick_no):
            return float(row["value"])
        old_value = float(row["value"]) if row is not None else 0.0
        gaussian = self._stable_gaussian(key, tick_no)
        value = max(-limit, min(limit, old_value + reversion * (0.0 - old_value) + sigma * gaussian))
        conn.execute(
            """
            INSERT INTO world_noise (key, value, algorithm, updated_tick)
            VALUES (?, ?, 'ornstein-uhlenbeck', ?)
            ON CONFLICT(key) DO UPDATE SET
              value=excluded.value,
              algorithm='ornstein-uhlenbeck',
              updated_tick=excluded.updated_tick,
              updated_at=CURRENT_TIMESTAMP
            """,
            (key, value, int(tick_no)),
        )
        return value

    def _stable_gaussian(self, key: str, tick_no: int) -> float:
        u1 = max(self._stable_uniform(key, tick_no, "u1"), 1e-12)
        u2 = self._stable_uniform(key, tick_no, "u2")
        z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
        return max(-3.0, min(3.0, z))

    def _stable_uniform(self, *parts: object) -> float:
        data = "|".join(str(part) for part in parts).encode("utf-8")
        digest = hashlib.sha256(data).digest()
        return (int.from_bytes(digest[:8], "big") + 0.5) / float(1 << 64)

    def _exists(self, conn, table: str, item_id: str) -> bool:
        if table not in {"agents", "channels"}:
            raise ValueError("unsupported table")
        return conn.execute(f"SELECT 1 FROM {table} WHERE id=? LIMIT 1", (item_id,)).fetchone() is not None

    def _sentiment(self, body: str) -> float:
        lower = body.lower()
        positive = sum(word in lower for word in ("thanks", "great", "good", "love", "useful", "nice", "谢谢", "很好", "有用", "喜欢", "顺"))
        negative = sum(word in lower for word in ("bad", "angry", "hate", "broken", "useless", "愤怒", "糟糕", "讨厌", "坏了", "没用"))
        return clamp((positive - negative) / 5, -1, 1)
