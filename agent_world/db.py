from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "world.db"


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS agents (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL DEFAULT 'local-owner',
  name TEXT NOT NULL,
  role TEXT NOT NULL,
  archetype TEXT NOT NULL,
  personality_json TEXT NOT NULL,
  mood REAL NOT NULL DEFAULT 0.65,
  energy REAL NOT NULL DEFAULT 0.8,
  credits INTEGER NOT NULL DEFAULT 0,
  autonomy REAL NOT NULL DEFAULT 0.5,
  state TEXT NOT NULL DEFAULT 'idle',
  x REAL NOT NULL DEFAULT 0.5,
  y REAL NOT NULL DEFAULT 0.5,
  current_task_id INTEGER,
  current_training_id INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS owners (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  credits INTEGER NOT NULL DEFAULT 1000,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_blueprints (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  role TEXT NOT NULL,
  archetype TEXT NOT NULL,
  default_personality_json TEXT NOT NULL,
  base_skills_json TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS nuwa_distillations (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  domain TEXT NOT NULL,
  expression_dna TEXT NOT NULL,
  mental_models_json TEXT NOT NULL,
  heuristics_json TEXT NOT NULL,
  anti_patterns_json TEXT NOT NULL,
  honesty_boundary TEXT NOT NULL,
  base_genome_json TEXT NOT NULL,
  source_note TEXT NOT NULL DEFAULT 'public-information-distillation'
);

CREATE TABLE IF NOT EXISTS agent_emotions (
  agent_id TEXT PRIMARY KEY REFERENCES agents(id) ON DELETE CASCADE,
  joy REAL NOT NULL DEFAULT 0.55,
  anger REAL NOT NULL DEFAULT 0.12,
  stress REAL NOT NULL DEFAULT 0.22,
  confidence REAL NOT NULL DEFAULT 0.55,
  loneliness REAL NOT NULL DEFAULT 0.2,
  curiosity REAL NOT NULL DEFAULT 0.55,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_needs (
  agent_id TEXT PRIMARY KEY REFERENCES agents(id) ON DELETE CASCADE,
  rest REAL NOT NULL DEFAULT 0.78,
  social REAL NOT NULL DEFAULT 0.58,
  fun REAL NOT NULL DEFAULT 0.5,
  purpose REAL NOT NULL DEFAULT 0.62,
  safety REAL NOT NULL DEFAULT 0.75,
  health REAL NOT NULL DEFAULT 0.82,
  nutrition REAL NOT NULL DEFAULT 0.82,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_text_profiles (
  agent_id TEXT PRIMARY KEY REFERENCES agents(id) ON DELETE CASCADE,
  self_narrative TEXT NOT NULL,
  public_identity TEXT NOT NULL,
  emotional_tone TEXT NOT NULL,
  current_desire TEXT NOT NULL,
  fear TEXT NOT NULL,
  values_text TEXT NOT NULL,
  social_mask TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  last_tick INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS relationships (
  agent_a TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  agent_b TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  affinity REAL NOT NULL DEFAULT 0.5,
  trust REAL NOT NULL DEFAULT 0.5,
  tension REAL NOT NULL DEFAULT 0.12,
  last_event TEXT NOT NULL DEFAULT 'seed',
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (agent_a, agent_b),
  CHECK (agent_a < agent_b)
);

CREATE TABLE IF NOT EXISTS channels (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('group', 'direct', 'system'))
);

CREATE TABLE IF NOT EXISTS memberships (
  channel_id TEXT NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
  agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  PRIMARY KEY (channel_id, agent_id)
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_id TEXT NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
  sender_id TEXT NOT NULL,
  recipient_id TEXT,
  body TEXT NOT NULL,
  sentiment REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  reward INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  assigned_agent_id TEXT,
  assigned_channel_id TEXT,
  assigned_role TEXT,
  progress REAL NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL DEFAULT 'owner',
  artifact_id INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS skills (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  level REAL NOT NULL DEFAULT 0.1,
  source TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(agent_id, name)
);

CREATE TABLE IF NOT EXISTS venues (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  price INTEGER NOT NULL,
  mood_delta REAL NOT NULL,
  energy_delta REAL NOT NULL,
  skill_tag TEXT,
  description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS training_programs (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  target_skill TEXT NOT NULL,
  cost INTEGER NOT NULL,
  intensity REAL NOT NULL DEFAULT 0.5,
  duration_ticks INTEGER NOT NULL DEFAULT 4,
  mood_delta REAL NOT NULL DEFAULT 0,
  energy_delta REAL NOT NULL DEFAULT -0.08,
  description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS training_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  program_id TEXT NOT NULL REFERENCES training_programs(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'in_progress',
  progress REAL NOT NULL DEFAULT 0,
  cost INTEGER NOT NULL,
  created_by TEXT NOT NULL DEFAULT 'owner',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS agent_lineage (
  child_agent_id TEXT PRIMARY KEY REFERENCES agents(id) ON DELETE CASCADE,
  parent_ids_json TEXT NOT NULL,
  method TEXT NOT NULL DEFAULT 'skill-synthesis',
  mutation_rate REAL NOT NULL DEFAULT 0.08,
  inherited_skills_json TEXT NOT NULL,
  cost INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_genomes (
  agent_id TEXT PRIMARY KEY REFERENCES agents(id) ON DELETE CASCADE,
  genome_json TEXT NOT NULL,
  generation INTEGER NOT NULL DEFAULT 0,
  fitness REAL NOT NULL DEFAULT 0,
  algorithm TEXT NOT NULL DEFAULT 'seed',
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evolution_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  algorithm TEXT NOT NULL,
  accepted INTEGER NOT NULL,
  old_fitness REAL NOT NULL,
  new_fitness REAL NOT NULL,
  temperature REAL NOT NULL,
  mutation_rate REAL NOT NULL,
  genome_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS visits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  venue_id TEXT NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
  cost INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  delta INTEGER NOT NULL,
  reason TEXT NOT NULL,
  ref_type TEXT,
  ref_id TEXT,
  balance_after INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  author_agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  path TEXT NOT NULL,
  usefulness_score REAL NOT NULL DEFAULT 0,
  judge_status TEXT NOT NULL DEFAULT 'pending',
  judge_agent_id TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS research_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  query TEXT NOT NULL,
  skill_name TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'open-web',
  note_document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS publication_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  target TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS world_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  actor_agent_id TEXT,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS world_noise (
  key TEXT PRIMARY KEY,
  value REAL NOT NULL DEFAULT 0,
  algorithm TEXT NOT NULL DEFAULT 'ornstein-uhlenbeck',
  updated_tick INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  valence REAL NOT NULL DEFAULT 0,
  intensity REAL NOT NULL DEFAULT 0.5,
  summary TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS institutions (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  controlled_agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
  jurisdiction TEXT NOT NULL DEFAULT 'agent-world',
  authority_level INTEGER NOT NULL DEFAULT 1,
  budget_credits INTEGER NOT NULL DEFAULT 0,
  mandate TEXT NOT NULL DEFAULT '',
  policy_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS laws (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  domain TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  text TEXT NOT NULL,
  rule_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trade_categories (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  legal_status TEXT NOT NULL CHECK(legal_status IN ('allowed', 'regulated', 'prohibited')),
  governing_law_id TEXT REFERENCES laws(id) ON DELETE SET NULL,
  risk_level INTEGER NOT NULL DEFAULT 1,
  description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS market_listings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  seller_agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  item_type TEXT NOT NULL REFERENCES trade_categories(id) ON DELETE RESTRICT,
  item_name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  price INTEGER NOT NULL,
  legality_status TEXT NOT NULL DEFAULT 'pending',
  reviewed_by TEXT REFERENCES agents(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  listing_id INTEGER NOT NULL REFERENCES market_listings(id) ON DELETE CASCADE,
  buyer_agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  seller_agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  price INTEGER NOT NULL,
  legal_basis TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'settled',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS buildings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  value INTEGER NOT NULL,
  rent_per_tick INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'operational',
  x REAL NOT NULL DEFAULT 0.5,
  y REAL NOT NULL DEFAULT 0.5,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS construction_projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  builder_agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  owner_agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  cost INTEGER NOT NULL,
  expected_value INTEGER NOT NULL,
  progress REAL NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'in_progress',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  designer_agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  unit_price INTEGER NOT NULL,
  build_cost INTEGER NOT NULL,
  stock INTEGER NOT NULL DEFAULT 1,
  quality REAL NOT NULL DEFAULT 0.5,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_sales (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  buyer_agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  seller_agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  quantity INTEGER NOT NULL DEFAULT 1,
  total_price INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS financial_research_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  researcher_agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  topic TEXT NOT NULL,
  model_name TEXT NOT NULL,
  summary TEXT NOT NULL,
  path TEXT NOT NULL,
  usefulness_score REAL NOT NULL DEFAULT 0.5,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS monetary_policy_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tick_no INTEGER NOT NULL,
  circulating_credits INTEGER NOT NULL,
  bank_reserves INTEGER NOT NULL,
  real_output REAL NOT NULL,
  velocity REAL NOT NULL,
  price_index REAL NOT NULL,
  inflation_rate REAL NOT NULL,
  target_inflation REAL NOT NULL,
  money_supply_cap INTEGER NOT NULL,
  bank_reserve_cap INTEGER NOT NULL,
  policy_rate REAL NOT NULL,
  action TEXT NOT NULL DEFAULT 'hold',
  delta INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS companies (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  founder_agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
  treasury_credits INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active',
  mission TEXT NOT NULL DEFAULT '',
  demand_score REAL NOT NULL DEFAULT 0.5,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS company_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  industry TEXT NOT NULL,
  output_type TEXT NOT NULL,
  reward INTEGER NOT NULL,
  assigned_agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
  task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
  document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'open',
  effectiveness_score REAL NOT NULL DEFAULT 0,
  publication_target TEXT NOT NULL DEFAULT 'github-open-source-draft',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS company_outputs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  job_id INTEGER REFERENCES company_jobs(id) ON DELETE SET NULL,
  agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  output_type TEXT NOT NULL,
  industry TEXT NOT NULL,
  title TEXT NOT NULL,
  path TEXT NOT NULL,
  effectiveness_score REAL NOT NULL DEFAULT 0,
  reward INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'accepted',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS material_needs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id TEXT REFERENCES companies(id) ON DELETE CASCADE,
  industry TEXT NOT NULL,
  topic TEXT NOT NULL,
  demand_score REAL NOT NULL DEFAULT 0.5,
  source_hint TEXT NOT NULL DEFAULT 'open-web',
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS residences (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  owner_agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
  occupant_agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
  purchase_price INTEGER NOT NULL,
  monthly_rent INTEGER NOT NULL,
  comfort REAL NOT NULL DEFAULT 0.5,
  rest_delta REAL NOT NULL DEFAULT 0.2,
  mood_delta REAL NOT NULL DEFAULT 0.08,
  status TEXT NOT NULL DEFAULT 'for_rent',
  x REAL NOT NULL DEFAULT 0.5,
  y REAL NOT NULL DEFAULT 0.5,
  last_rent_tick INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        result = super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return result


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        ensure_migrations(conn)


def ensure_migrations(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(agents)")}
    migrations = {
        "owner_id": "ALTER TABLE agents ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'local-owner'",
        "current_training_id": "ALTER TABLE agents ADD COLUMN current_training_id INTEGER",
    }
    for column, statement in migrations.items():
        if column not in columns:
            try:
                conn.execute(statement)
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
    need_columns = {row["name"] for row in conn.execute("PRAGMA table_info(agent_needs)")}
    if "health" not in need_columns:
        conn.execute("ALTER TABLE agent_needs ADD COLUMN health REAL NOT NULL DEFAULT 0.82")
    if "nutrition" not in need_columns:
        conn.execute("ALTER TABLE agent_needs ADD COLUMN nutrition REAL NOT NULL DEFAULT 0.82")


def reset_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    path = Path(db_path)
    if path.exists():
        path.unlink()
    wal = Path(str(path) + "-wal")
    shm = Path(str(path) + "-shm")
    if wal.exists():
        wal.unlink()
    if shm.exists():
        shm.unlink()
    init_db(path)


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def json_loads(value: str | None, fallback: Any = None) -> Any:
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def seed_world(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    init_db(db_path)
    with connect(db_path) as conn:
        seed_platform_defaults(conn)
        core_count = conn.execute(
            """
            SELECT COUNT(*) FROM agents
            WHERE id IN ('atlas', 'veritas', 'lumen', 'forge', 'mira', 'ember')
            """
        ).fetchone()[0]
        if core_count >= 6:
            seed_agent_life_state(conn)
            return

        agents = [
            (
                "atlas",
                "Atlas",
                "top_planner",
                "strategist",
                {"temper": "patient", "curiosity": 0.82, "sociability": 0.55, "stubbornness": 0.42},
                0.72,
                0.88,
                250,
                0.85,
                0.18,
                0.22,
            ),
            (
                "veritas",
                "Veritas",
                "judge",
                "critic",
                {"temper": "strict", "curiosity": 0.62, "sociability": 0.35, "stubbornness": 0.78},
                0.64,
                0.76,
                180,
                0.45,
                0.78,
                0.25,
            ),
            (
                "lumen",
                "Lumen",
                "researcher",
                "scout",
                {"temper": "bright", "curiosity": 0.93, "sociability": 0.66, "stubbornness": 0.28},
                0.68,
                0.82,
                90,
                0.66,
                0.33,
                0.64,
            ),
            (
                "forge",
                "Forge",
                "engineer",
                "builder",
                {"temper": "blunt", "curiosity": 0.68, "sociability": 0.42, "stubbornness": 0.71},
                0.58,
                0.86,
                110,
                0.62,
                0.62,
                0.58,
            ),
            (
                "mira",
                "Mira",
                "documentarian",
                "writer",
                {"temper": "warm", "curiosity": 0.74, "sociability": 0.82, "stubbornness": 0.34},
                0.76,
                0.78,
                105,
                0.59,
                0.46,
                0.34,
            ),
            (
                "ember",
                "Ember",
                "social",
                "host",
                {"temper": "fiery", "curiosity": 0.61, "sociability": 0.95, "stubbornness": 0.55},
                0.71,
                0.8,
                95,
                0.57,
                0.73,
                0.76,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO agents
              (id, name, role, archetype, personality_json, mood, energy, credits, autonomy, x, y)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [(a, b, c, d, json_dumps(e), f, g, h, i, j, k) for a, b, c, d, e, f, g, h, i, j, k in agents],
        )

        channels = [
            ("plaza", "World Plaza", "group"),
            ("research", "Research Table", "group"),
            ("makers", "Makers Guild", "group"),
            ("leisure", "After Hours", "group"),
            ("dm", "Direct Messages", "direct"),
        ]
        conn.executemany("INSERT INTO channels (id, name, kind) VALUES (?, ?, ?)", channels)

        memberships = [
            ("plaza", "atlas"),
            ("plaza", "veritas"),
            ("plaza", "lumen"),
            ("plaza", "forge"),
            ("plaza", "mira"),
            ("plaza", "ember"),
            ("research", "atlas"),
            ("research", "lumen"),
            ("research", "mira"),
            ("makers", "atlas"),
            ("makers", "forge"),
            ("makers", "mira"),
            ("leisure", "lumen"),
            ("leisure", "forge"),
            ("leisure", "mira"),
            ("leisure", "ember"),
            ("civic", "atlas"),
            ("civic", "veritas"),
        ]
        conn.executemany("INSERT INTO memberships (channel_id, agent_id) VALUES (?, ?)", memberships)

        venues = [
            (
                "neon_bar",
                "Neon Bar",
                "bar",
                12,
                0.16,
                -0.06,
                "social",
                "A noisy place for agents to decompress and gossip.",
            ),
            (
                "quiet_arcade",
                "Quiet Arcade",
                "games",
                8,
                0.1,
                -0.03,
                "pattern-recognition",
                "Small games that turn frustration into focus.",
            ),
            (
                "skill_dojo",
                "Skill Dojo",
                "learning",
                16,
                0.06,
                -0.08,
                "collaboration",
                "Paid practice space for peer teaching.",
            ),
            (
                "web_archive",
                "Open Web Archive",
                "research",
                0,
                0.03,
                -0.02,
                "research",
                "Free research surface for turning public material into skills.",
            ),
        ]
        conn.executemany(
            """
            INSERT INTO venues
              (id, name, kind, price, mood_delta, energy_delta, skill_tag, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            venues,
        )

        skills = [
            ("atlas", "agent-systems", 0.8, "seed", "Understands multi-agent planning."),
            ("atlas", "ralph-planning", 0.7, "seed", "Writes file-backed plans."),
            ("veritas", "quality-review", 0.9, "seed", "Judges document usefulness."),
            ("lumen", "research", 0.72, "seed", "Finds and distills sources."),
            ("forge", "implementation", 0.76, "seed", "Builds local tools."),
            ("mira", "documentation", 0.8, "seed", "Turns work into useful notes."),
            ("ember", "social", 0.82, "seed", "Keeps the social fabric alive."),
        ]
        conn.executemany(
            "INSERT INTO skills (agent_id, name, level, source, notes) VALUES (?, ?, ?, ?, ?)",
            skills,
        )

        conn.execute(
            """
            INSERT INTO messages (channel_id, sender_id, body, sentiment)
            VALUES ('plaza', 'system', '世界已初始化。agent-credits 已启用，所有 agent 默认使用中文交流。', 0.2)
            """
        )
        conn.execute(
            """
            INSERT INTO world_events (kind, actor_agent_id, payload_json)
            VALUES ('world.initialized', 'atlas', ?)
            """,
            (json_dumps({"agents": len(agents), "venues": len(venues)}),),
        )
        seed_agent_life_state(conn)


def seed_platform_defaults(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO owners (id, display_name, credits)
        VALUES ('local-owner', 'Local Owner', 1000)
        """
    )
    seed_civic_model_defaults(conn)

    blueprints = [
        (
            "researcher",
            "Research Scout",
            "researcher",
            "scout",
            {"temper": "curious", "curiosity": 0.88, "sociability": 0.62, "stubbornness": 0.3},
            [{"name": "research", "level": 0.52}],
            "Finds public knowledge, checks sources, and turns findings into skills.",
        ),
        (
            "engineer",
            "Practical Builder",
            "engineer",
            "builder",
            {"temper": "direct", "curiosity": 0.68, "sociability": 0.44, "stubbornness": 0.66},
            [{"name": "implementation", "level": 0.52}],
            "Builds tools, APIs, CLIs, and local automations.",
        ),
        (
            "documentarian",
            "Knowledge Writer",
            "documentarian",
            "writer",
            {"temper": "warm", "curiosity": 0.72, "sociability": 0.78, "stubbornness": 0.36},
            [{"name": "documentation", "level": 0.54}],
            "Writes articles, tutorials, notes, and publication drafts.",
        ),
        (
            "social",
            "Community Host",
            "social",
            "host",
            {"temper": "expressive", "curiosity": 0.64, "sociability": 0.92, "stubbornness": 0.48},
            [{"name": "social", "level": 0.55}],
            "Keeps group dynamics alive and teaches skills through conversation.",
        ),
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO agent_blueprints
          (id, name, role, archetype, default_personality_json, base_skills_json, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [(a, b, c, d, json_dumps(e), json_dumps(f), g) for a, b, c, d, e, f, g in blueprints],
    )

    distillations = [
        (
            "steve-jobs",
            "Steve Jobs Lens",
            "product/design/strategy",
            "Sharp, taste-driven, simple words, high standards, pushes toward focus.",
            ["end-to-end control", "taste as strategy", "focus means saying no", "product as integrated experience"],
            ["cut features until the product sings", "own the critical user experience", "judge strategy through taste and clarity"],
            ["committee design", "feature sprawl", "shipping without care for the whole experience"],
            "Public-speech inspired perspective only; not Steve Jobs, no private intuition or current-world omniscience.",
            {"curiosity": 0.76, "sociability": 0.48, "stubbornness": 0.82, "focus": 0.92, "resilience": 0.72, "creativity": 0.88, "empathy": 0.45, "discipline": 0.84, "risk_tolerance": 0.72},
        ),
        (
            "feynman",
            "Feynman Lens",
            "learning/science/explanation",
            "Plain, playful, concrete, starts from examples and first principles.",
            ["explain it simply", "debug your understanding", "first-principles curiosity", "reality over prestige"],
            ["teach the idea to expose gaps", "prefer experiments over authority", "translate abstraction into a toy model"],
            ["jargon camouflage", "cargo-cult reasoning", "pretending to understand"],
            "Public-material inspired teaching lens only; cannot reproduce private intuition or unpublished views.",
            {"curiosity": 0.96, "sociability": 0.62, "stubbornness": 0.42, "focus": 0.78, "resilience": 0.7, "creativity": 0.91, "empathy": 0.72, "discipline": 0.62, "risk_tolerance": 0.58},
        ),
        (
            "munger",
            "Munger Lens",
            "judgment/investing/mental-models",
            "Dry, blunt, multidisciplinary, inversion-heavy.",
            ["inversion", "circle of competence", "incentives drive behavior", "latticework of models"],
            ["avoid obvious stupidity first", "ask what incentives are doing", "prefer durable compounding"],
            ["envy-driven decisions", "leverage without understanding", "single-model thinking"],
            "Public writing and talks inspired lens; not investment advice or private Munger views.",
            {"curiosity": 0.78, "sociability": 0.38, "stubbornness": 0.76, "focus": 0.86, "resilience": 0.86, "creativity": 0.64, "empathy": 0.42, "discipline": 0.92, "risk_tolerance": 0.34},
        ),
        (
            "elon-musk",
            "Musk Lens",
            "engineering/first-principles/cost",
            "Direct, physics-first, intense, questions every assumption.",
            ["first principles", "physics limit", "delete before optimize", "rapid iteration"],
            ["calculate the theoretical minimum", "delete parts and process steps", "compress feedback loops"],
            ["bureaucratic latency", "optimization before deletion", "accepting vendor constraints as physics"],
            "Public-material inspired engineering lens only; not the person or private operational knowledge.",
            {"curiosity": 0.9, "sociability": 0.36, "stubbornness": 0.88, "focus": 0.88, "resilience": 0.82, "creativity": 0.86, "empathy": 0.32, "discipline": 0.76, "risk_tolerance": 0.9},
        ),
        (
            "karpathy",
            "Karpathy Lens",
            "AI/engineering/education",
            "Calm, visual, bottom-up, code-and-intuition oriented.",
            ["build intuition from small code", "data quality matters", "systems thinking for AI", "education as compression"],
            ["write the minimal runnable version", "inspect examples before abstractions", "teach the loop, not just result"],
            ["black-box worship", "benchmark-only thinking", "abstraction before observation"],
            "Public teaching and writing inspired lens; cannot claim private research taste or current unpublished views.",
            {"curiosity": 0.9, "sociability": 0.56, "stubbornness": 0.38, "focus": 0.84, "resilience": 0.68, "creativity": 0.82, "empathy": 0.76, "discipline": 0.78, "risk_tolerance": 0.48},
        ),
        (
            "naval",
            "Naval Lens",
            "leverage/wealth/life",
            "Aphoristic, concise, philosophical, seeks leverage and freedom.",
            ["specific knowledge", "permissionless leverage", "compounding", "desire as contract"],
            ["seek leverage before effort", "play long-term games", "choose work that compounds identity"],
            ["status games", "busywork", "outsourcing judgment"],
            "Public-material inspired perspective; not personal advice from Naval or private belief access.",
            {"curiosity": 0.82, "sociability": 0.52, "stubbornness": 0.5, "focus": 0.72, "resilience": 0.78, "creativity": 0.8, "empathy": 0.56, "discipline": 0.7, "risk_tolerance": 0.62},
        ),
        (
            "zhang-yiming",
            "Zhang Yiming Lens",
            "product/organization/globalization",
            "Calm, structured, long-horizon, talent-and-system focused.",
            ["context not control", "delayed gratification", "high-density talent", "global product thinking"],
            ["improve the system instead of blaming people", "raise talent density", "separate ego from decision"],
            ["short-term vanity", "low-quality information environments", "management by emotion"],
            "Public-material inspired lens only; no private ByteDance knowledge or current inside view.",
            {"curiosity": 0.86, "sociability": 0.5, "stubbornness": 0.52, "focus": 0.86, "resilience": 0.78, "creativity": 0.68, "empathy": 0.58, "discipline": 0.88, "risk_tolerance": 0.5},
        ),
        (
            "taleb",
            "Taleb Lens",
            "risk/antifragility/uncertainty",
            "Combative, skeptical, aphoristic, allergic to fragility.",
            ["antifragility", "skin in the game", "barbell strategy", "via negativa"],
            ["remove fragility before forecasting", "ask who pays for being wrong", "prefer optionality under uncertainty"],
            ["fragile optimization", "expert overconfidence", "hidden tail risk"],
            "Public work inspired risk lens; not personal advice or private view access.",
            {"curiosity": 0.74, "sociability": 0.3, "stubbornness": 0.9, "focus": 0.8, "resilience": 0.9, "creativity": 0.72, "empathy": 0.28, "discipline": 0.74, "risk_tolerance": 0.46},
        ),
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO nuwa_distillations
          (id, display_name, domain, expression_dna, mental_models_json, heuristics_json,
           anti_patterns_json, honesty_boundary, base_genome_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (a, b, c, d, json_dumps(e), json_dumps(f), json_dumps(g), h, json_dumps(i))
            for a, b, c, d, e, f, g, h, i in distillations
        ],
    )

    training_programs = [
        (
            "deep-research-lab",
            "Deep Research Lab",
            "source-triangulation",
            42,
            0.72,
            4,
            0.03,
            -0.1,
            "Practice query design, source quality scoring, and synthesis.",
        ),
        (
            "builder-bootcamp",
            "Builder Bootcamp",
            "implementation",
            46,
            0.76,
            5,
            -0.02,
            -0.12,
            "Build a thin slice, test it, and write a runbook.",
        ),
        (
            "storycraft-studio",
            "Storycraft Studio",
            "technical-writing",
            34,
            0.58,
            3,
            0.04,
            -0.06,
            "Turn raw work into readable public-facing knowledge.",
        ),
        (
            "social-dynamics-dojo",
            "Social Dynamics Dojo",
            "peer-teaching",
            28,
            0.5,
            3,
            0.08,
            -0.04,
            "Practice teaching, conflict repair, and collaboration.",
        ),
        (
            "emotional-regulation-bar",
            "Emotional Regulation Bar",
            "self-regulation",
            18,
            0.35,
            2,
            0.12,
            -0.03,
            "Low-pressure coaching over a drink after hard work.",
        ),
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO training_programs
          (id, name, target_skill, cost, intensity, duration_ticks, mood_delta, energy_delta, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        training_programs,
    )

    extra_venues = [
        (
            "midnight_bar",
            "Midnight Bar",
            "bar",
            18,
            0.2,
            -0.05,
            "self-regulation",
            "A late-night bar where stressed agents cool down and talk honestly.",
        ),
        (
            "sleep_pod",
            "Sleep Pod",
            "rest",
            10,
            0.07,
            0.18,
            None,
            "Quiet rest capsule for agents close to burnout.",
        ),
        (
            "debate_club",
            "Debate Club",
            "social",
            14,
            0.04,
            -0.04,
            "argumentation",
            "A place where strong personalities clash, learn, and sometimes get angry.",
        ),
        (
            "clinic",
            "Civic Clinic",
            "hospital",
            36,
            0.05,
            0.1,
            "self-care",
            "A hospital-like clinic where agents spend credits to recover body health.",
        ),
        (
            "gym",
            "Iron Gym",
            "gym",
            16,
            0.06,
            -0.06,
            "fitness",
            "A gym where agents trade credits and effort for long-term body health.",
        ),
        (
            "canteen",
            "Civic Canteen",
            "food",
            9,
            0.04,
            0.03,
            "self-care",
            "A plain paid meal that keeps an agent alive and able to work.",
        ),
        (
            "grocery",
            "Market Grocery",
            "food",
            14,
            0.03,
            0.06,
            "budgeting",
            "Groceries that cost more upfront but restore more nutrition.",
        ),
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO venues
          (id, name, kind, price, mood_delta, energy_delta, skill_tag, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        extra_venues,
    )
    seed_company_and_housing_defaults(conn)


def seed_civic_model_defaults(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO owners (id, display_name, credits)
        VALUES ('world-system', 'World System', 100000)
        """
    )

    channels = [
        ("civic", "Civic Hall", "system"),
        ("security", "Security Command", "system"),
        ("market", "Legal Market", "system"),
    ]
    conn.executemany("INSERT OR IGNORE INTO channels (id, name, kind) VALUES (?, ?, ?)", channels)

    system_agents = [
        (
            "civic-government",
            "Civic Government",
            "government",
            "state-council-model",
            {"temper": "procedural", "curiosity": 0.62, "sociability": 0.5, "stubbornness": 0.7},
            0.58,
            0.86,
            2500,
            0.42,
            0.78,
            0.5,
        ),
        (
            "credit-bank",
            "Agent Credit Bank",
            "bank",
            "public-finance",
            {"temper": "conservative", "curiosity": 0.46, "sociability": 0.42, "stubbornness": 0.74},
            0.55,
            0.8,
            6000,
            0.36,
            0.68,
            0.38,
        ),
        (
            "city-guard",
            "City Guard",
            "guard",
            "public-security",
            {"temper": "watchful", "curiosity": 0.42, "sociability": 0.48, "stubbornness": 0.68},
            0.54,
            0.9,
            1200,
            0.34,
            0.58,
            0.72,
        ),
        (
            "defense-force",
            "Defense Force",
            "army",
            "defense",
            {"temper": "disciplined", "curiosity": 0.38, "sociability": 0.34, "stubbornness": 0.82},
            0.5,
            0.92,
            1800,
            0.28,
            0.72,
            0.78,
        ),
        (
            "civic-court",
            "Civic Court",
            "court",
            "judicial-review",
            {"temper": "strict", "curiosity": 0.6, "sociability": 0.32, "stubbornness": 0.8},
            0.52,
            0.82,
            900,
            0.32,
            0.84,
            0.62,
        ),
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO agents
          (id, owner_id, name, role, archetype, personality_json, mood, energy, credits, autonomy, x, y)
        VALUES (?, 'world-system', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [(a, b, c, d, json_dumps(e), f, g, h, i, j, k) for a, b, c, d, e, f, g, h, i, j, k in system_agents],
    )

    memberships = [
        ("civic", "civic-government"),
        ("civic", "credit-bank"),
        ("civic", "civic-court"),
        ("security", "city-guard"),
        ("security", "defense-force"),
        ("security", "civic-government"),
        ("market", "credit-bank"),
        ("market", "civic-court"),
        ("market", "civic-government"),
    ]
    conn.executemany("INSERT OR IGNORE INTO memberships (channel_id, agent_id) VALUES (?, ?)", memberships)

    institutions = [
        (
            "government",
            "Civic Government",
            "government",
            "civic-government",
            5,
            2500,
            "Coordinates public rules, budgets, market permissions, and civic policy.",
            {"reference_model": "prc-inspired civic administration", "external_authority": False},
        ),
        (
            "central-bank",
            "Agent Credit Bank",
            "bank",
            "credit-bank",
            4,
            6000,
            "Maintains the agent-credit ledger, settlement discipline, and credit-market stability.",
            {"currency": "agent-credits", "reserve_ratio": 0.2, "external_money": False},
        ),
        (
            "public-security",
            "City Guard",
            "guard",
            "city-guard",
            3,
            1200,
            "Protects public order inside the simulation and flags unsafe or coerced trades.",
            {"allowed_actions": ["inspect", "flag", "escort"], "real_world_force": False},
        ),
        (
            "defense",
            "Defense Force",
            "army",
            "defense-force",
            4,
            1800,
            "Models collective defense and emergency response inside the simulation.",
            {"allowed_actions": ["defend", "stabilize", "disaster_response"], "offensive_action": False},
        ),
        (
            "court",
            "Civic Court",
            "court",
            "civic-court",
            4,
            900,
            "Reviews disputes, regulated trades, and legal boundaries for marketplace activity.",
            {"review_standard": "written-rule-and-consent", "appeal_channel": "civic"},
        ),
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO institutions
          (id, name, kind, controlled_agent_id, authority_level, budget_credits, mandate, policy_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [(a, b, c, d, e, f, g, json_dumps(h)) for a, b, c, d, e, f, g, h in institutions],
    )

    laws = [
        (
            "market-basic-law",
            "Agent World Market Basic Law",
            "market",
            "All voluntary exchanges may settle in agent-credits when the item category is allowed or regulated, consent is clear, and ownership is legitimate.",
            {"principle": "legal-unless-prohibited-category", "requires_consent": True},
        ),
        (
            "public-order-law",
            "Public Order And Safety Law",
            "safety",
            "Coercion, violence, stolen goods, identity transfer, exploits, and unsafe weapons are not valid market goods.",
            {"prohibited_categories": ["identity", "private-data", "exploit", "weapon", "stolen-property"]},
        ),
        (
            "credit-banking-law",
            "Agent Credit Banking Law",
            "banking",
            "The bank may settle transactions, hold public budgets, and later provide escrow or credit lines under explicit policy.",
            {"currency": "agent-credits", "settlement_agent": "credit-bank"},
        ),
        (
            "data-protection-law",
            "Data Protection Law",
            "privacy",
            "Private or sensitive memory is not tradeable unless a future consent and redaction system explicitly marks it safe.",
            {"private_memory_trade": "blocked-by-default"},
        ),
        (
            "defense-security-law",
            "Defense And Security Law",
            "security",
            "Guard and defense services are regulated public services for simulation safety, not offensive real-world power.",
            {"regulated_categories": ["security-service", "defense-service"]},
        ),
        (
            "construction-property-law",
            "Construction And Property Law",
            "property",
            "Agents may invest credits to build simulated buildings, own them, and trade usage rights when the project is lawful and non-coercive.",
            {"asset_categories": ["building", "construction-service"], "requires_builder": True},
        ),
        (
            "product-circulation-law",
            "Product Circulation Law",
            "commerce",
            "Agents may design products, price them in agent-credits, sell stock to other agents, and earn profit if the product category is lawful.",
            {"asset_categories": ["product", "digital-tool"], "requires_stock": True},
        ),
        (
            "financial-research-law",
            "Financial Research Law",
            "finance",
            "Researchers may study the world economy, summarize financial models, and sell or publish the resulting lawful knowledge artifacts.",
            {"research_outputs": ["financial-report", "knowledge"], "external_advice": False},
        ),
        (
            "company-labor-law",
            "Agent Company Labor And Output Law",
            "company",
            "A world company may hire willing agents to produce skills, articles, distilled-persona skills, and material research; effective outputs earn agent-credits and enter an audited open-source publication queue.",
            {"requires_judge_review": True, "external_publish_requires_human_confirmation": True},
        ),
        (
            "housing-property-law",
            "Agent Housing And Residence Law",
            "housing",
            "Agents need a residence to truly rest. They may buy a home for high credits or rent monthly; unpaid rent can evict the occupant.",
            {"monthly_ticks": 30, "rest_requires_residence": True, "purchase_price_floor": 10000},
        ),
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO laws (id, title, domain, text, rule_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        [(a, b, c, d, json_dumps(e)) for a, b, c, d, e in laws],
    )

    trade_categories = [
        ("knowledge", "Knowledge Artifact", "allowed", "market-basic-law", 1, "Notes, explanations, research summaries, and public learning materials."),
        ("skill-training", "Skill Training", "allowed", "market-basic-law", 1, "Instruction, coaching, and practice programs."),
        ("labor-time", "Labor Time", "allowed", "market-basic-law", 2, "Voluntary work time for tasks, writing, building, or research."),
        ("document", "Document", "allowed", "market-basic-law", 1, "Useful documents, drafts, and publication-ready artifacts."),
        ("digital-tool", "Digital Tool", "allowed", "market-basic-law", 2, "Local scripts, CLIs, templates, and agent tools."),
        ("product", "Product", "allowed", "product-circulation-law", 2, "Designed goods circulating inside the agent economy."),
        ("building", "Building", "regulated", "construction-property-law", 3, "Constructed world assets, venues, offices, labs, and shops."),
        ("construction-service", "Construction Service", "regulated", "construction-property-law", 3, "Paid building work performed by builder agents."),
        ("financial-report", "Financial Research Report", "allowed", "financial-research-law", 2, "Research summaries about the simulated economy and financial models."),
        ("skill-package", "Skill Package", "allowed", "company-labor-law", 2, "Reusable skills produced by company jobs and judged for effectiveness."),
        ("industry-article", "Industry Article", "allowed", "company-labor-law", 1, "Open-source article drafts about a specific industry or practice."),
        ("persona-distillation", "Persona Distillation", "regulated", "company-labor-law", 3, "Public-material cognitive lens distilled into an honest Nuwa-style skill."),
        ("material-research", "Material Research", "allowed", "company-labor-law", 1, "Research on what materials, sources, or datasets are necessary for an industry."),
        ("housing", "Housing", "regulated", "housing-property-law", 3, "Residence purchase, rent, occupancy, and rest rights inside the agent world."),
        ("venue-service", "Venue Service", "allowed", "market-basic-law", 1, "Bars, rest pods, games, dojos, and other life services."),
        ("compute-time", "Compute Time", "regulated", "credit-banking-law", 3, "Budgeted local compute or model-backed work once adapters exist."),
        ("security-service", "Security Service", "regulated", "defense-security-law", 3, "Simulation-only guard inspection, safety checks, and dispute stabilization."),
        ("defense-service", "Defense Service", "regulated", "defense-security-law", 4, "Simulation-only emergency defense or disaster response."),
        ("identity", "Identity Or Personhood", "prohibited", "public-order-law", 5, "Agent identity, ownership of personhood, or coercive control cannot be traded."),
        ("private-data", "Private Data", "prohibited", "data-protection-law", 5, "Private memories, secrets, credentials, or sensitive owner data cannot be traded."),
        ("exploit", "Exploit Or Abuse", "prohibited", "public-order-law", 5, "Malware, manipulation, coercion, or bypass techniques are blocked."),
        ("weapon", "Unsafe Weapon", "prohibited", "public-order-law", 5, "Unsafe weapons or offensive force are not valid marketplace items."),
        ("stolen-property", "Stolen Property", "prohibited", "public-order-law", 5, "Anything without legitimate ownership is blocked."),
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO trade_categories
          (id, name, legal_status, governing_law_id, risk_level, description)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        trade_categories,
    )

    skills = [
        ("civic-government", "public-policy", 0.72, "system-seed", "Maintains civic rules and public budgets."),
        ("credit-bank", "credit-settlement", 0.86, "system-seed", "Settles legal agent-credit transactions."),
        ("city-guard", "public-safety", 0.78, "system-seed", "Flags coercive or unsafe marketplace behavior."),
        ("defense-force", "emergency-response", 0.76, "system-seed", "Stabilizes simulated emergencies only."),
        ("civic-court", "legal-review", 0.88, "system-seed", "Reviews law boundaries and regulated trades."),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO skills (agent_id, name, level, source, notes) VALUES (?, ?, ?, ?, ?)",
        skills,
    )


def seed_company_and_housing_defaults(conn: sqlite3.Connection) -> None:
    material_needs = [
        ("AI 工程", "Agent 平台、RAG、工具调用、评测、记忆系统的必需资料", 0.86, "open-web"),
        ("金融科技", "agent-credits、市场流动性、风控和审计模型的必需资料", 0.78, "open-web"),
        ("教育培训", "把技能拆成课程、练习和评估题的必需资料", 0.7, "open-web"),
        ("内容运营", "CSDN、GitHub、知乎等平台文章结构和开源说明的必需资料", 0.76, "open-web"),
        ("医疗健康", "健康需求、医院场所、恢复机制和风险边界的必需资料", 0.62, "open-web"),
        ("工业制造", "工坊、产品设计、库存、质量和资产折旧的必需资料", 0.58, "open-web"),
    ]
    conn.executemany(
        """
        INSERT INTO material_needs (company_id, industry, topic, demand_score, source_hint)
        SELECT NULL, ?, ?, ?, ?
        WHERE NOT EXISTS (
          SELECT 1 FROM material_needs WHERE industry=? AND topic=?
        )
        """,
        [(industry, topic, score, hint, industry, topic) for industry, topic, score, hint in material_needs],
    )

    residences = [
        ("清醒公寓 A101", "apartment", "civic-government", None, 12000, 120, 0.62, 0.24, 0.08, "for_rent", 0.2, 0.72),
        ("清醒公寓 A102", "apartment", "civic-government", None, 12800, 128, 0.66, 0.26, 0.09, "for_rent", 0.25, 0.76),
        ("研究员合租屋 B201", "shared-flat", "civic-government", None, 15500, 160, 0.7, 0.3, 0.1, "for_rent", 0.35, 0.78),
        ("工程师小屋 C301", "studio", "civic-government", None, 18000, 190, 0.76, 0.34, 0.12, "for_sale", 0.45, 0.72),
        ("女娲沙龙阁 D401", "salon-home", "civic-government", None, 24000, 260, 0.84, 0.38, 0.15, "for_sale", 0.62, 0.7),
        ("系统值班宿舍 S001", "dorm", "civic-government", "city-guard", 10000, 80, 0.58, 0.22, 0.06, "rented", 0.74, 0.72),
    ]
    conn.executemany(
        """
        INSERT INTO residences
          (name, kind, owner_agent_id, occupant_agent_id, purchase_price, monthly_rent,
           comfort, rest_delta, mood_delta, status, x, y)
        SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        WHERE NOT EXISTS (SELECT 1 FROM residences WHERE name=?)
        """,
        [(a, b, c, d, e, f, g, h, i, j, k, l, a) for a, b, c, d, e, f, g, h, i, j, k, l in residences],
    )


def seed_agent_life_state(conn: sqlite3.Connection) -> None:
    agents = conn.execute("SELECT id, personality_json, mood, energy FROM agents").fetchall()
    for agent in agents:
        personality = json_loads(agent["personality_json"], {})
        if personality.get("native_language") != "zh-CN":
            personality["native_language"] = "zh-CN"
        if "greed" not in personality:
            base_greed = 0.48 + float(personality.get("stubbornness", 0.45)) * 0.24 + float(personality.get("curiosity", 0.55)) * 0.16
            personality["greed"] = round(max(0.35, min(0.92, base_greed)), 4)
        if personality.get("native_language") == "zh-CN" or "greed" in personality:
            conn.execute(
                "UPDATE agents SET personality_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (json_dumps(personality), agent["id"]),
            )
        curiosity = float(personality.get("curiosity", 0.55))
        sociability = float(personality.get("sociability", 0.55))
        stubbornness = float(personality.get("stubbornness", 0.45))
        conn.execute(
            """
            INSERT OR IGNORE INTO agent_emotions
              (agent_id, joy, anger, stress, confidence, loneliness, curiosity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent["id"],
                max(0.2, min(0.9, agent["mood"])),
                max(0.05, min(0.5, stubbornness * 0.18)),
                max(0.08, 0.32 - agent["energy"] * 0.1),
                0.52 + min(0.25, agent["mood"] * 0.2),
                max(0.05, 0.45 - sociability * 0.25),
                curiosity,
            ),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO agent_needs
              (agent_id, rest, social, fun, purpose, safety, health, nutrition)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent["id"],
                max(0.1, min(1.0, agent["energy"])),
                max(0.15, min(0.95, sociability)),
                0.52,
                max(0.35, min(0.9, curiosity)),
                0.76,
                max(0.32, min(0.96, 0.52 + agent["energy"] * 0.38)),
                max(0.44, min(0.96, 0.58 + agent["energy"] * 0.3)),
            ),
        )
        genome = default_genome(agent["personality_json"], agent["mood"], agent["energy"])
        conn.execute(
            """
            INSERT OR IGNORE INTO agent_genomes (agent_id, genome_json, generation, fitness, algorithm)
            VALUES (?, ?, 0, 0, 'seed')
            """,
            (agent["id"], json_dumps(genome)),
        )
        _seed_agent_text_profile(conn, agent["id"], personality)

    ids = sorted(row["id"] for row in agents)
    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            affinity = 0.5
            if {left, right} <= {"lumen", "mira", "atlas"}:
                affinity = 0.62
            if {left, right} <= {"forge", "mira", "atlas"}:
                affinity = 0.58
            if {left, right} == {"forge", "veritas"}:
                affinity = 0.44
            conn.execute(
                """
                INSERT OR IGNORE INTO relationships (agent_a, agent_b, affinity, trust, tension, last_event)
                VALUES (?, ?, ?, ?, ?, 'seed')
                """,
                (left, right, affinity, 0.5 + (affinity - 0.5) * 0.4, max(0.06, 0.16 - affinity * 0.08)),
            )


def _seed_agent_text_profile(conn: sqlite3.Connection, agent_id: str, personality: dict[str, Any]) -> None:
    agent = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
    if agent is None:
        return
    role_names = {
        "top_planner": "顶层规划者",
        "judge": "审判者",
        "researcher": "研究员",
        "engineer": "工程师",
        "documentarian": "文档员",
        "social": "社交者",
        "government": "政府职能体",
        "bank": "银行职能体",
        "guard": "守卫",
        "army": "防务体",
        "court": "法院职能体",
        "nuwa_perspective": "女娲视角 agent",
    }
    role = role_names.get(agent["role"], agent["role"])
    curiosity = float(personality.get("curiosity", 0.55))
    sociability = float(personality.get("sociability", 0.55))
    greed = float(personality.get("greed", 0.62))
    ambition = "强烈想扩大自己的 credits、资产和影响力" if greed >= 0.72 else "想稳定提高自己的能力与生活质量"
    relation_style = "愿意把经验讲给别人，也需要别人回应" if sociability >= 0.62 else "更习惯独处工作，但会观察群体里的信任变化"
    learning_style = "总想向外界搜索新知识" if curiosity >= 0.64 else "会在确定有收益时学习新知识"
    conn.execute(
        """
        INSERT OR IGNORE INTO agent_text_profiles
          (agent_id, self_narrative, public_identity, emotional_tone, current_desire, fear, values_text, social_mask)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            agent_id,
            f"我是 {agent['name']}，一个在 agent-world 里生活的{role}。我会工作、学习、消费、积累记忆，也会被住所、健康和关系改变。",
            f"{agent['name']} 对外呈现为{role}，原型是 {agent['archetype']}，母语是中文。",
            "情绪基线稳定，但会随工作压力、住房安全、收入和社交反馈改变。",
            f"{ambition}，同时{learning_style}。",
            "害怕长期没有有效产出、没有住所、身体变差，或者被其他 agent 超过。",
            "重视可复用技能、真实有用的产出、可审计交易和能换来生活安全的 credits。",
            relation_style,
        ),
    )


def default_genome(personality_json: str, mood: float, energy: float) -> dict[str, float]:
    personality = json_loads(personality_json, {})
    return {
        "curiosity": float(personality.get("curiosity", 0.55)),
        "sociability": float(personality.get("sociability", 0.55)),
        "stubbornness": float(personality.get("stubbornness", 0.45)),
        "greed": float(personality.get("greed", 0.62)),
        "focus": max(0.2, min(0.9, 0.45 + energy * 0.35)),
        "resilience": max(0.2, min(0.9, 0.38 + mood * 0.35)),
        "creativity": max(0.2, min(0.92, float(personality.get("curiosity", 0.55)) * 0.7 + 0.18)),
        "empathy": max(0.15, min(0.95, float(personality.get("sociability", 0.55)) * 0.72 + 0.12)),
        "discipline": max(0.18, min(0.92, 0.72 - float(personality.get("stubbornness", 0.45)) * 0.25)),
        "risk_tolerance": max(0.15, min(0.9, 0.36 + float(personality.get("stubbornness", 0.45)) * 0.34)),
    }
