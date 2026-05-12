from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .db import DEFAULT_DB_PATH, json_loads
from .engine import WorldEngine


DEFAULT_SUMMARY_DIR = Path(__file__).resolve().parents[1] / "中文记录" / "世界汇总"


def export_world_summary(
    db_path: Path | str = DEFAULT_DB_PATH,
    output_dir: Path | str = DEFAULT_SUMMARY_DIR,
) -> Path:
    state = WorldEngine(db_path).snapshot()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = out / f"{stamp}-agent-world-summary.md"
    path.write_text(render_world_summary(state), encoding="utf-8")
    _update_index(out)
    return path


def render_world_summary(state: dict[str, Any]) -> str:
    agents = state["agents"]
    active_tasks = [task for task in state["tasks"] if task["status"] in {"open", "in_progress"}]
    done_tasks = [task for task in state["tasks"] if task["status"] == "done"]
    total_credits = sum(int(agent["credits"]) for agent in agents)
    system_agents = [agent for agent in agents if agent["owner_id"] == "world-system"]
    ordinary_agents = [agent for agent in agents if agent["owner_id"] != "world-system"]
    low_health = sorted(agents, key=lambda agent: agent["needs"].get("health", 1.0))[:5]
    low_nutrition = sorted(agents, key=lambda agent: agent["needs"].get("nutrition", 1.0))[:5]
    low_fun = sorted(agents, key=lambda agent: agent["needs"].get("fun", 1.0))[:5]
    rich = sorted(agents, key=lambda agent: int(agent["credits"]), reverse=True)[:5]
    lines = [
        "# Agent World 小世界周期汇总",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- agent 总数：{len(agents)}",
        f"- 普通 agent：{len(ordinary_agents)}",
        f"- 系统 agent：{len(system_agents)}",
        f"- agent 持有 credits：{total_credits}",
        f"- 活跃任务：{len(active_tasks)}",
        f"- 已完成任务：{len(done_tasks)}",
        f"- 发布队列：{len(state['publicationQueue'])}",
        f"- 顶层 agent 状态：{_zh_status(state['governance']['topAgentMode'])}，成熟度 {state['governance']['maturityScore']}/{state['governance']['standDownThreshold']}",
        "",
        "## 制度层",
        "",
    ]
    lines.extend(
        f"- {_zh_institution(item['id'], item['name'])}：{_zh_role(item['kind'])}，控制 agent={item['controlled_agent_id']}，预算={item['budget_credits']}，职责={_zh_mandate(item['id'], item['mandate'])}"
        for item in state.get("institutions", [])
    )
    lines.extend(["", "## 经济与市场", ""])
    lines.extend(
        [
            f"- 法律条目：{len(state.get('laws', []))}",
            f"- 可交易分类：{len([c for c in state.get('tradeCategories', []) if c['legal_status'] != 'prohibited'])}",
            f"- 市场挂牌：{len(state.get('marketListings', []))}",
            f"- 市场成交：{len(state.get('marketTransactions', []))}",
            f"- 建筑资产：{len(state.get('buildings', []))}",
            f"- 建设项目：{len(state.get('constructionProjects', []))}",
            f"- 产品：{len(state.get('products', []))}",
            f"- 产品销售：{len(state.get('productSales', []))}",
            f"- 金融研究报告：{len(state.get('financialResearchReports', []))}",
            f"- 公司：{len(state.get('companies', []))}",
            f"- 公司有效产出：{len([item for item in state.get('companyOutputs', []) if item['status'] == 'accepted'])}",
            f"- 住房：{len(state.get('residences', []))}，已入住 {len([item for item in state.get('residences', []) if item['occupant_agent_id']])}",
        ]
    )
    policy = (state.get("monetaryPolicy") or [None])[0]
    if policy:
        lines.extend(
            [
                "",
                "### 央行货币政策",
                "",
                f"- 流通 agent-credits：{policy['circulating_credits']} / 供给上限 {policy['money_supply_cap']}",
                f"- 银行储备：{policy['bank_reserves']} / 储备上限 {policy['bank_reserve_cap']}",
                f"- 价格指数：{float(policy['price_index']):.3f}",
                f"- 本轮通胀率：{float(policy['inflation_rate']) * 100:+.2f}%",
                f"- 政策利率代理：{float(policy['policy_rate']) * 100:.2f}%",
                f"- 政策动作：{policy['action']}，流通变化 {policy['delta']}",
            ]
        )
    else:
        lines.extend(["", "### 央行货币政策", "", "- 暂无政策快照；推进世界后由 credit-bank 计算。"])
    lines.extend(["", "### agent-credits 前 5", ""])
    lines.extend(f"- {agent['id']}：{agent['credits']} agent-credits，角色={_zh_role(agent['role'])}，状态={_zh_status(agent['state'])}" for agent in rich)
    lines.extend(["", "## 身体与情绪", "", "### 健康最低的 agent", ""])
    lines.extend(
        f"- {agent['id']}：健康={agent['needs'].get('health', 0):.2f}，开心={agent['needs'].get('fun', 0):.2f}，休息={agent['needs'].get('rest', 0):.2f}，agent-credits={agent['credits']}"
        for agent in low_health
    )
    lines.extend(["", "### 开心/娱乐需求最低的 agent", ""])
    lines.extend(
        f"- {agent['id']}：开心={agent['needs'].get('fun', 0):.2f}，愉悦={agent['emotions'].get('joy', 0):.2f}，压力={agent['emotions'].get('stress', 0):.2f}，状态={_zh_status(agent['state'])}"
        for agent in low_fun
    )
    lines.extend(["", "### 饱腹/饮食风险最高的 agent", ""])
    lines.extend(
        f"- {agent['id']}：饱腹 {agent['needs'].get('nutrition', 0):.2f}，健康 {agent['needs'].get('health', 0):.2f}，credits={agent['credits']}，状态 {_zh_status(agent['state'])}"
        for agent in low_nutrition
    )
    lines.extend(["", "## 身份文本模型", ""])
    for agent in agents[:8]:
        profile = agent.get("textProfile") or {}
        if not profile:
            continue
        lines.append(
            f"- {agent['id']}：版本 {profile.get('version', 1)}；欲望={profile.get('current_desire', '-')}；恐惧={profile.get('fear', '-')}"
        )
    lines.extend(["", "## 最新交易、建设与产品", ""])
    lines.extend(_listing_lines(state))
    lines.extend(["", "## 公司与住房", ""])
    lines.extend(_company_housing_lines(state))
    lines.extend(["", "## 随机扰动", ""])
    noise_rows = state.get("randomFactors", [])[:12]
    if noise_rows:
        lines.extend(
            f"- {item['key']}：{float(item['value']):+.4f}，算法={item['algorithm']}，更新时间={item['updated_at']}"
            for item in noise_rows
        )
    else:
        lines.append("- 暂无随机扰动记录。")
    lines.extend(["", "## 最近世界事件", ""])
    for event in state.get("events", [])[:12]:
        payload = json_loads(event.get("payload_json"), {})
        lines.append(f"- #{event['id']} {event['created_at']} 事件={event['kind']} 行为者={event['actor_agent_id']} 载荷={payload}")
    lines.extend(["", "## 当前判断", ""])
    lines.extend(_judgment_lines(state, low_health, low_fun))
    return "\n".join(lines) + "\n"


def _listing_lines(state: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for item in state.get("marketListings", [])[:5]:
        lines.append(f"- 市场挂牌 #{item['id']}：{item['item_name']}，{_zh_status(item['status'])}，价格={item['price']}，卖家={item['seller_agent_id']}")
    for item in state.get("buildings", [])[:5]:
        lines.append(f"- 建筑 #{item['id']}：{item['name']}，所有者={item['owner_agent_id']}，价值={item['value']}，租金={item['rent_per_tick']}")
    for item in state.get("products", [])[:5]:
        lines.append(f"- 产品 #{item['id']}：{item['name']}，状态={_zh_status(item['status'])}，价格={item['unit_price']}，库存={item['stock']}，设计者={item['designer_agent_id']}")
    if not lines:
        lines.append("- 暂无市场、建设或产品活动。")
    return lines


def _company_housing_lines(state: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for item in state.get("companies", [])[:4]:
        lines.append(f"- 公司 {item['name']}：状态={_zh_status(item['status'])}，资金={item['treasury_credits']}，需求={float(item['demand_score']):.2f}")
    for job in state.get("companyJobs", [])[:5]:
        lines.append(f"- 公司岗位 #{job['id']}：{job['industry']} / {job['output_type']}，状态={_zh_status(job['status'])}，报酬={job['reward']}，任务={job['task_id']}")
    for output in state.get("companyOutputs", [])[:5]:
        lines.append(f"- 公司产出 #{output['id']}：agent={output['agent_id']}，有效度={float(output['effectiveness_score']):.2f}，奖励={output['reward']}，状态={_zh_status(output['status'])}")
    for home in state.get("residences", [])[:6]:
        lines.append(f"- 住房 #{home['id']}：{home['name']}，状态={_zh_status(home['status'])}，居住={home['occupant_agent_id'] or '-'}，买价={home['purchase_price']}，月租={home['monthly_rent']}")
    if not lines:
        lines.append("- 暂无公司或住房记录。")
    return lines


def _judgment_lines(state: dict[str, Any], low_health: list[dict[str, Any]], low_fun: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    if low_health and low_health[0]["needs"].get("health", 1.0) < 0.45:
        lines.append(f"- {low_health[0]['id']} 健康偏低，应优先去 clinic 或 gym 花 credits 恢复。")
    if low_fun and low_fun[0]["needs"].get("fun", 1.0) < 0.32:
        lines.append(f"- {low_fun[0]['id']} 开心/娱乐需求偏低，应安排娱乐或社交恢复。")
    if not state.get("marketListings"):
        lines.append("- 市场仍偏空，应鼓励 agent 把知识、工具、产品、训练服务合法挂牌。")
    if not state.get("financialResearchReports"):
        lines.append("- 尚缺金融研究报告，应让 researcher 汇总 credits、资产和产品流通模型。")
    if not state.get("companies") and state["governance"]["topAgentMode"] == "stand_down":
        lines.append("- 世界已经稳定，应成立公司来持续生产 skill、文章、材料研究和人物技能蒸馏。")
    homeless = [agent for agent in state.get("agents", []) if agent["owner_id"] != "world-system" and not any(home["occupant_agent_id"] == agent["id"] for home in state.get("residences", []))]
    if homeless:
        lines.append(f"- {len(homeless)} 个普通 agent 仍无住房；无房不能真正休息，会形成持续赚钱与租房需求。")
    policy = (state.get("monetaryPolicy") or [None])[0]
    if policy and int(policy["circulating_credits"]) > int(policy["money_supply_cap"]):
        lines.append("- 流通 credits 已高于供给上限，中央银行应继续收取稳定费并限制新增奖励。")
    if policy and int(policy["bank_reserves"]) > int(policy["bank_reserve_cap"]):
        lines.append("- 银行储备超过控制上限，应继续执行储备灭菌，避免银行无限扩表。")
    if not lines:
        lines.append("- 小世界当前稳定；下一步可以扩展税收、贷款、保险、租金和公司组织模型。")
    return lines


def _update_index(output_dir: Path) -> None:
    summaries = sorted(output_dir.glob("*-agent-world-summary.md"), reverse=True)
    lines = ["# 世界汇总索引", ""]
    lines.extend(f"- [{path.stem}]({path.name})" for path in summaries)
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _zh_status(value: str) -> str:
    return {
        "bootstrap": "启动期",
        "stand_down": "自主运行",
        "idle": "空闲",
        "working": "工作中",
        "leisure": "休闲中",
        "researching": "研究中",
        "training": "训练中",
        "eating": "吃饭中",
        "starving": "饥饿求生",
        "starved": "饿死失活",
        "recovering": "恢复中",
        "done": "完成",
        "open": "开放",
        "in_progress": "进行中",
        "active": "活跃",
        "sold": "已售出",
        "sold_out": "售罄",
        "queued": "排队中",
        "operational": "运营中",
        "rented": "已出租",
        "for_rent": "可租",
        "for_sale": "可买",
        "owner_occupied": "自住房",
        "resting": "居家休息",
        "needs_revision": "需返工",
        "accepted": "有效",
    }.get(value, value)


def _zh_role(value: str) -> str:
    return {
        "top_planner": "顶层规划",
        "judge": "审判",
        "researcher": "研究员",
        "engineer": "工程师",
        "documentarian": "文档员",
        "social": "社交",
        "hybrid": "混合型",
        "government": "政府",
        "bank": "银行",
        "guard": "守卫",
        "army": "防务",
        "court": "法院",
        "nuwa_perspective": "女娲视角",
    }.get(value, value)


def _zh_institution(institution_id: str, fallback: str) -> str:
    return {
        "government": "小世界政府",
        "central-bank": "Agent Credits 银行",
        "public-security": "城市守卫署",
        "defense": "应急防务部",
        "court": "小世界法院",
    }.get(institution_id, fallback)


def _zh_mandate(institution_id: str, fallback: str) -> str:
    return {
        "government": "协调公共规则、预算、市场许可和公共政策。",
        "central-bank": "维护 agent-credits 账本、结算纪律和信用市场稳定。",
        "public-security": "维护模拟世界公共秩序，标记不安全或被胁迫的交易。",
        "defense": "负责模拟世界的集体防务和应急稳定，不映射现实强制力。",
        "court": "审查争议、监管交易和市场活动的法律边界。",
    }.get(institution_id, fallback)
