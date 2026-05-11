from __future__ import annotations

from pathlib import Path
from typing import Any

from .db import DEFAULT_DB_PATH, connect, json_loads, rows_to_dicts


DEFAULT_RECORD_DIR = Path(__file__).resolve().parents[1] / "中文记录" / "agent行为"


def export_agent_behavior_records(
    db_path: Path | str = DEFAULT_DB_PATH,
    output_dir: Path | str = DEFAULT_RECORD_DIR,
) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with connect(db_path) as conn:
        agents = rows_to_dicts(conn.execute("SELECT * FROM agents ORDER BY id"))
        index_lines = ["# Agent 行为客观记录索引", ""]
        for agent in agents:
            path = out / f"{agent['id']}.md"
            path.write_text(_agent_record(conn, agent), encoding="utf-8")
            written.append(path)
            index_lines.append(f"- [{agent['id']}]({agent['id']}.md)：{agent['name']} / {agent['role']}")
        index = out / "README.md"
        index.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
        written.append(index)
    return written


def _agent_record(conn, agent: dict[str, Any]) -> str:
    agent_id = agent["id"]
    personality = json_loads(agent.get("personality_json"), {})
    text_profile = conn.execute("SELECT * FROM agent_text_profiles WHERE agent_id=?", (agent_id,)).fetchone()
    lines = [
        f"# {agent['name']} 行为客观记录",
        "",
        "## 基本信息",
        "",
        f"- 智能体 ID：{agent_id}",
        f"- 名称：{agent['name']}",
        f"- 角色：{agent['role']}",
        f"- 原型：{agent['archetype']}",
        f"- 归属：{agent.get('owner_id', 'local-owner')}",
        f"- agent-credits：{agent['credits']}",
        f"- 心情：{agent['mood']}",
        f"- 精力：{agent['energy']}",
        f"- 状态：{agent['state']}",
        f"- 性格参数：{personality}",
        "",
    ]
    if text_profile is not None:
        lines.extend(
            [
                "## 个人文本模型",
                "",
                f"- 版本：{text_profile['version']}",
                f"- 自我叙事：{text_profile['self_narrative']}",
                f"- 公共身份：{text_profile['public_identity']}",
                f"- 情绪叙事：{text_profile['emotional_tone']}",
                f"- 当前欲望：{text_profile['current_desire']}",
                f"- 当前恐惧：{text_profile['fear']}",
                f"- 价值观：{text_profile['values_text']}",
                f"- 社交面具：{text_profile['social_mask']}",
                "",
            ]
        )
    sections = [
        (
            "世界事件",
            "SELECT id, kind, payload_json, created_at FROM world_events WHERE actor_agent_id=? ORDER BY id",
            (agent_id,),
            lambda r: f"- #{r['id']} {r['created_at']} 事件={r['kind']} 载荷={r['payload_json']}",
        ),
        (
            "消息",
            """
            SELECT id, channel_id, sender_id, recipient_id, body, sentiment, created_at
            FROM messages
            WHERE sender_id=? OR recipient_id=?
            ORDER BY id
            """,
            (agent_id, agent_id),
            lambda r: f"- #{r['id']} {r['created_at']} {r['sender_id']} -> {r['recipient_id'] or r['channel_id']} 情绪值={r['sentiment']}：{r['body']}",
        ),
        (
            "任务",
            """
            SELECT id, title, reward, status, progress, created_at, updated_at
            FROM tasks
            WHERE assigned_agent_id=? OR artifact_id IN (SELECT id FROM documents WHERE author_agent_id=?)
            ORDER BY id
            """,
            (agent_id, agent_id),
            lambda r: f"- #{r['id']} 状态={r['status']} 报酬={r['reward']} 进度={r['progress']}：{r['title']}",
        ),
        (
            "账本",
            "SELECT id, delta, reason, ref_type, ref_id, balance_after, created_at FROM ledger WHERE agent_id=? ORDER BY id",
            (agent_id,),
            lambda r: f"- #{r['id']} {r['created_at']} 变动={r['delta']} 余额={r['balance_after']} 原因={r['reason']} 引用={r['ref_type']}:{r['ref_id']}",
        ),
        (
            "场所访问",
            "SELECT id, venue_id, cost, created_at FROM visits WHERE agent_id=? ORDER BY id",
            (agent_id,),
            lambda r: f"- #{r['id']} {r['created_at']} 场所={r['venue_id']} 花费={r['cost']}",
        ),
        (
            "住房与出租资产",
            "SELECT id, name, status, owner_agent_id, occupant_agent_id, purchase_price, monthly_rent, updated_at FROM residences WHERE owner_agent_id=? OR occupant_agent_id=? ORDER BY id",
            (agent_id, agent_id),
            lambda r: f"- 住所 #{r['id']} {r['name']} 状态={r['status']} 所有者={r['owner_agent_id']} 居住者={r['occupant_agent_id']} 买价={r['purchase_price']} 月租={r['monthly_rent']}",
        ),
        (
            "技能",
            "SELECT name, level, source, notes, updated_at FROM skills WHERE agent_id=? ORDER BY level DESC, name",
            (agent_id,),
            lambda r: f"- {r['name']} 等级={r['level']} 来源={r['source']} 更新时间={r['updated_at']} 备注={r['notes']}",
        ),
        (
            "研究",
            "SELECT id, query, skill_name, source, note_document_id, created_at FROM research_runs WHERE agent_id=? ORDER BY id",
            (agent_id,),
            lambda r: f"- #{r['id']} {r['created_at']} 技能={r['skill_name']} 来源={r['source']} 笔记={r['note_document_id']} 查询={r['query']}",
        ),
        (
            "金融研究",
            "SELECT id, topic, model_name, usefulness_score, path, created_at FROM financial_research_reports WHERE researcher_agent_id=? ORDER BY id",
            (agent_id,),
            lambda r: f"- #{r['id']} {r['created_at']} 模型={r['model_name']} 有用度={r['usefulness_score']} 路径={r['path']} 主题={r['topic']}",
        ),
        (
            "文档",
            "SELECT id, title, path, usefulness_score, judge_status, created_at FROM documents WHERE author_agent_id=? ORDER BY id",
            (agent_id,),
            lambda r: f"- #{r['id']} 审判状态={r['judge_status']} 有用度={r['usefulness_score']} 路径={r['path']} 标题={r['title']}",
        ),
        (
            "训练",
            "SELECT id, program_id, status, progress, cost, created_at, completed_at FROM training_sessions WHERE agent_id=? ORDER BY id",
            (agent_id,),
            lambda r: f"- #{r['id']} 状态={r['status']} 项目={r['program_id']} 进度={r['progress']} 成本={r['cost']} 完成时间={r['completed_at']}",
        ),
        (
            "进化",
            "SELECT id, algorithm, accepted, old_fitness, new_fitness, temperature, created_at FROM evolution_runs WHERE agent_id=? ORDER BY id",
            (agent_id,),
            lambda r: f"- #{r['id']} {r['created_at']} 算法={r['algorithm']} 是否接受={r['accepted']} 适应度={r['old_fitness']}->{r['new_fitness']} 温度={r['temperature']}",
        ),
        (
            "市场挂牌",
            "SELECT id, item_type, item_name, price, legality_status, status, created_at FROM market_listings WHERE seller_agent_id=? ORDER BY id",
            (agent_id,),
            lambda r: f"- #{r['id']} 状态={r['status']} 类型={r['item_type']} 名称={r['item_name']} 价格={r['price']} 合法性={r['legality_status']}",
        ),
        (
            "市场成交",
            """
            SELECT id, listing_id, buyer_agent_id, seller_agent_id, price, legal_basis, created_at
            FROM market_transactions
            WHERE buyer_agent_id=? OR seller_agent_id=?
            ORDER BY id
            """,
            (agent_id, agent_id),
            lambda r: f"- #{r['id']} {r['created_at']} 挂牌={r['listing_id']} 买家={r['buyer_agent_id']} 卖家={r['seller_agent_id']} 价格={r['price']} 法律依据={r['legal_basis']}",
        ),
        (
            "建设项目",
            """
            SELECT id, builder_agent_id, owner_agent_id, name, kind, cost, expected_value, progress, status, completed_at
            FROM construction_projects
            WHERE builder_agent_id=? OR owner_agent_id=?
            ORDER BY id
            """,
            (agent_id, agent_id),
            lambda r: f"- #{r['id']} 状态={r['status']} 名称={r['name']} 类型={r['kind']} 建设者={r['builder_agent_id']} 所有者={r['owner_agent_id']} 成本={r['cost']} 预期价值={r['expected_value']} 进度={r['progress']}",
        ),
        (
            "建筑资产",
            "SELECT id, name, kind, value, rent_per_tick, status, created_at FROM buildings WHERE owner_agent_id=? ORDER BY id",
            (agent_id,),
            lambda r: f"- #{r['id']} 状态={r['status']} 名称={r['name']} 类型={r['kind']} 价值={r['value']} 每轮租金={r['rent_per_tick']}",
        ),
        (
            "产品",
            "SELECT id, name, category, unit_price, build_cost, stock, quality, status, created_at FROM products WHERE designer_agent_id=? ORDER BY id",
            (agent_id,),
            lambda r: f"- #{r['id']} 状态={r['status']} 名称={r['name']} 分类={r['category']} 价格={r['unit_price']} 库存={r['stock']} 质量={r['quality']}",
        ),
        (
            "产品销售",
            """
            SELECT id, product_id, buyer_agent_id, seller_agent_id, quantity, total_price, created_at
            FROM product_sales
            WHERE buyer_agent_id=? OR seller_agent_id=?
            ORDER BY id
            """,
            (agent_id, agent_id),
            lambda r: f"- #{r['id']} {r['created_at']} 产品={r['product_id']} 买家={r['buyer_agent_id']} 卖家={r['seller_agent_id']} 数量={r['quantity']} 总价={r['total_price']}",
        ),
        (
            "记忆",
            "SELECT id, kind, valence, intensity, summary, created_at FROM agent_memories WHERE agent_id=? ORDER BY id",
            (agent_id,),
            lambda r: f"- #{r['id']} {r['created_at']} 类型={r['kind']} 情绪正负={r['valence']} 强度={r['intensity']}：{r['summary']}",
        ),
    ]
    for title, sql, params, formatter in sections:
        rows = rows_to_dicts(conn.execute(sql, params))
        lines.extend([f"## {title}", ""])
        if rows:
            lines.extend(formatter(row) for row in rows)
        else:
            lines.append("- 暂无记录。")
        lines.append("")
    return "\n".join(lines)
