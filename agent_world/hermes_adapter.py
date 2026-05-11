from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HermesTaskPrompt:
    agent_id: str
    system_prompt: str
    user_prompt: str
    allowed_toolsets: tuple[str, ...]


class HermesCommandAdapter:
    """Boundary for future Hermes-backed task execution.

    The local world is useful without API keys, so this adapter does not run
    Hermes yet. It composes the contract that a real integration should pass to
    `hermes chat` or the Python AIAgent API once budgets and approvals exist.
    """

    def is_available(self) -> bool:
        return shutil.which("hermes") is not None

    def compose_prompt(self, agent: dict[str, Any], task: dict[str, Any]) -> HermesTaskPrompt:
        skills = ", ".join(skill["name"] for skill in agent.get("skills", [])[:8]) or "暂时没有技能"
        traits = agent.get("personality", {})
        system_prompt = "\n".join(
            [
                f"你是 {agent['name']}（{agent['id']}），角色是 {agent['role']}，生活在 Agent World 小世界中。",
                f"原型：{agent.get('archetype', '未知')}。",
                f"性格参数：{traits}。",
                f"已掌握技能：{skills}。",
                "你的母语是中文。请用中文思考、沟通和产出。",
                "保持可追溯、重视来源，不要直接对外发布任何内容。",
                "产出一个简洁、可被审判 agent 评估有用性的成果。",
            ]
        )
        user_prompt = "\n".join(
            [
                f"任务：{task['title']}",
                "",
                task["description"],
                "",
                f"报酬：{task['reward']} agent-credits。",
                "输出结构：摘要、实现/研究笔记、可复用技能笔记、风险。",
            ]
        )
        return HermesTaskPrompt(
            agent_id=agent["id"],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            allowed_toolsets=("file", "terminal", "web", "skills", "memory"),
        )
