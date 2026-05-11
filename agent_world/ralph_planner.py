from __future__ import annotations

from pathlib import Path
from typing import Any

from .db import DEFAULT_DB_PATH
from .engine import WorldEngine


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def write_planning_packet(
    db_path: Path | str = DEFAULT_DB_PATH,
    workspace_root: Path | str = WORKSPACE_ROOT,
) -> Path:
    root = Path(workspace_root)
    engine = WorldEngine(db_path)
    state = engine.snapshot()
    ralph_dir = root / ".ralph"
    ralph_dir.mkdir(parents=True, exist_ok=True)
    packet_path = ralph_dir / "hermes-agent-world-plan.md"

    agents = state["agents"]
    tasks = state["tasks"]
    queue = state["publicationQueue"]
    low_energy = [a for a in agents if a["energy"] < 0.45]
    open_tasks = [t for t in tasks if t["status"] in ("open", "in_progress")]
    approved_docs = [q for q in queue if q["status"] == "queued"]

    lines: list[str] = [
        "# Hermes Agent World Ralph Planning Packet",
        "",
        "Owner goal: grow a Hermes-inspired agent society with work, credits, skills, venues, judging, and explicit publishing adapters.",
        "",
        "## World Snapshot",
        "",
        f"- Agents: {len(agents)}",
        f"- Open/in-progress tasks: {len(open_tasks)}",
        f"- Queued publication items: {len(approved_docs)}",
        f"- Low-energy agents: {', '.join(a['id'] for a in low_energy) or 'none'}",
        "",
        "## Highest-Value Work",
    ]
    for task in sorted(open_tasks, key=lambda t: t["reward"], reverse=True)[:8]:
        lines.append(f"- #{task['id']} {task['title']} [{task['status']}] reward={task['reward']}")

    lines.extend(
        [
            "",
            "## Suggested Next Stories",
            "",
            "1. Add real Hermes execution with per-agent prompt assembly, budgets, and trace capture.",
            "2. Add a manual publishing adapter that drafts GitHub repo content from approved documents.",
            "3. Add richer social dynamics: affinity, conflict, reputation, and collaboration bonuses.",
            "4. Add evaluation rubrics for judge decisions and skill quality.",
            "",
            "## Verification Checklist",
            "",
            "- Run `python -m unittest discover -s tests`.",
            "- Run CLI init/task/tick/status smoke commands.",
            "- Open the 2D UI and confirm agents, tasks, messages, credits, documents, and queue render.",
            "- Confirm no external publishing happens automatically.",
        ]
    )
    packet_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return packet_path

