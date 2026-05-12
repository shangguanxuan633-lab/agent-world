from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .db import DEFAULT_DB_PATH, reset_db, seed_world
from .engine import WorldEngine
from .ralph_planner import write_planning_packet
from .recorder import export_agent_behavior_records
from .summary import export_world_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-world", description="控制 Hermes Agent World 小世界。")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to SQLite world database.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="初始化并种下小世界。")
    init.add_argument("--reset", action="store_true", help="重建本地世界数据库。")

    status = sub.add_parser("status", help="查看世界状态。")
    status.add_argument("--json", action="store_true", help="输出原始 JSON 快照。")

    sub.add_parser("agents", help="列出智能体。")
    sub.add_parser("venues", help="列出场所。")
    sub.add_parser("blueprints", help="列出智能体蓝图。")
    sub.add_parser("institutions", help="列出制度层机构。")
    sub.add_parser("laws", help="列出市场法律与交易分类。")

    tick = sub.add_parser("tick", help="推进小世界。")
    tick.add_argument("--steps", type=int, default=1)

    task = sub.add_parser("task", help="任务命令。")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    task_create = task_sub.add_parser("create", help="创建带报酬的工作。")
    task_create.add_argument("--title", required=True)
    task_create.add_argument("--description", required=True)
    task_create.add_argument("--reward", type=int, required=True)
    target = task_create.add_mutually_exclusive_group(required=True)
    target.add_argument("--agent", dest="assigned_agent_id")
    target.add_argument("--group", dest="assigned_channel_id")
    target.add_argument("--role", dest="assigned_role")

    message = sub.add_parser("message", help="消息命令。")
    msg_sub = message.add_subparsers(dest="message_command", required=True)
    msg_send = msg_sub.add_parser("send", help="发送私聊或群组消息。")
    msg_send.add_argument("--from", dest="sender_id", required=True)
    msg_send.add_argument("--body", required=True)
    msg_target = msg_send.add_mutually_exclusive_group(required=True)
    msg_target.add_argument("--agent", dest="recipient_id")
    msg_target.add_argument("--group", dest="channel_id")

    ledger = sub.add_parser("ledger", help="查看近期 credits 账本。")
    ledger.add_argument("--agent")

    agent = sub.add_parser("agent", help="智能体平台命令。")
    agent_sub = agent.add_subparsers(dest="agent_command", required=True)
    agent_create = agent_sub.add_parser("create", help="创建可训练的本地智能体。")
    agent_create.add_argument("--name", required=True)
    agent_create.add_argument("--blueprint", default="researcher")
    agent_create.add_argument("--owner", default="local-owner")
    agent_create.add_argument("--credits", type=int, default=80)

    training = sub.add_parser("training", help="训练命令。")
    training_sub = training.add_subparsers(dest="training_command", required=True)
    training_sub.add_parser("programs", help="列出训练项目。")
    training_start = training_sub.add_parser("start", help="开始训练。")
    training_start.add_argument("--agent", required=True)
    training_start.add_argument("--program", required=True)

    lineage = sub.add_parser("lineage", help="谱系与繁衍命令。")
    lineage_sub = lineage.add_subparsers(dest="lineage_command", required=True)
    lineage_create = lineage_sub.add_parser("create", help="用父代智能体孵化子代。")
    lineage_create.add_argument("--parents", required=True, help="父代智能体 id，用逗号分隔。")
    lineage_create.add_argument("--name", required=True)
    lineage_create.add_argument("--owner", default="local-owner")
    lineage_create.add_argument("--mutation-rate", type=float, default=0.08)

    nuwa = sub.add_parser("nuwa", help="女娲认知蒸馏命令。")
    nuwa_sub = nuwa.add_subparsers(dest="nuwa_command", required=True)
    nuwa_sub.add_parser("list", help="列出内置公开人物视角蒸馏。")
    nuwa_create = nuwa_sub.add_parser("create", help="用女娲蒸馏创建智能体。")
    nuwa_create.add_argument("--figure", required=True)
    nuwa_create.add_argument("--name")
    nuwa_create.add_argument("--owner", default="local-owner")
    nuwa_create.add_argument("--credits", type=int, default=120)

    market = sub.add_parser("market", help="合法 credits 市场命令。")
    market_sub = market.add_subparsers(dest="market_command", required=True)
    market_sub.add_parser("categories", help="列出合法交易分类。")
    market_sub.add_parser("list", help="列出市场挂牌。")
    market_create = market_sub.add_parser("create", help="创建合法市场挂牌。")
    market_create.add_argument("--seller", required=True)
    market_create.add_argument("--type", required=True, dest="item_type")
    market_create.add_argument("--name", required=True)
    market_create.add_argument("--description", default="")
    market_create.add_argument("--price", type=int, required=True)
    market_buy = market_sub.add_parser("buy", help="购买活跃挂牌。")
    market_buy.add_argument("--buyer", required=True)
    market_buy.add_argument("--listing", type=int, required=True)

    construction = sub.add_parser("construction", help="建设与建筑命令。")
    construction_sub = construction.add_subparsers(dest="construction_command", required=True)
    construction_sub.add_parser("list", help="列出建设项目和建筑。")
    construction_create = construction_sub.add_parser("create", help="启动建设项目。")
    construction_create.add_argument("--builder", required=True)
    construction_create.add_argument("--owner")
    construction_create.add_argument("--name", required=True)
    construction_create.add_argument("--kind", default="workshop")
    construction_create.add_argument("--cost", type=int, required=True)
    construction_create.add_argument("--expected-value", type=int)

    product = sub.add_parser("product", help="产品设计与流通命令。")
    product_sub = product.add_subparsers(dest="product_command", required=True)
    product_sub.add_parser("list", help="列出产品和销售。")
    product_create = product_sub.add_parser("create", help="为智能体经济设计产品。")
    product_create.add_argument("--designer", required=True)
    product_create.add_argument("--name", required=True)
    product_create.add_argument("--category", default="tool")
    product_create.add_argument("--price", type=int, required=True)
    product_create.add_argument("--build-cost", type=int, default=0)
    product_create.add_argument("--stock", type=int, default=1)
    product_buy = product_sub.add_parser("buy", help="购买产品库存。")
    product_buy.add_argument("--buyer", required=True)
    product_buy.add_argument("--product", type=int, required=True)
    product_buy.add_argument("--quantity", type=int, default=1)

    housing = sub.add_parser("housing", help="住房、买房和租金命令。")
    housing_sub = housing.add_subparsers(dest="housing_command", required=True)
    housing_sub.add_parser("list", help="列出住所、租金和占用情况。")
    housing_rent = housing_sub.add_parser("rent", help="让 agent 租住所。")
    housing_rent.add_argument("--agent", required=True)
    housing_rent.add_argument("--residence", type=int, required=True)
    housing_buy = housing_sub.add_parser("buy", help="让 agent 买住所。")
    housing_buy.add_argument("--agent", required=True)
    housing_buy.add_argument("--residence", type=int, required=True)
    housing_invest = housing_sub.add_parser("invest", help="让 agent 买下住所并挂牌出租。")
    housing_invest.add_argument("--agent", required=True)
    housing_invest.add_argument("--residence", type=int, required=True)
    housing_invest.add_argument("--rent", type=int)

    company = sub.add_parser("company", help="公司、岗位和有效产出命令。")
    company_sub = company.add_subparsers(dest="company_command", required=True)
    company_sub.add_parser("list", help="列出公司、岗位、有效产出和资料需求。")
    company_repair = company_sub.add_parser("repair-skills", help="把历史 accepted 行业技能包补齐成完整 SKILL.md 目录。")
    company_repair.add_argument("--limit", type=int, default=25)
    company_need = company_sub.add_parser("need", help="提交或更新 SkillForge 行业资料需求。")
    company_need_sub = company_need.add_subparsers(dest="company_need_command", required=True)
    company_need_add = company_need_sub.add_parser("add", help="把适合 agent 打工的行业机会提交到公司需求队列。")
    company_need_add.add_argument("--industry", required=True)
    company_need_add.add_argument("--topic", required=True)
    company_need_add.add_argument("--demand", type=float, default=0.72)
    company_need_add.add_argument("--source", default="industry-scout")
    company_need_add.add_argument("--actor", default="atlas")

    finance = sub.add_parser("finance", help="金融模型研究命令。")
    finance_sub = finance.add_subparsers(dest="finance_command", required=True)
    finance_sub.add_parser("reports", help="列出金融研究报告。")
    finance_sub.add_parser("policy", help="查看央行货币政策、通胀压力和供给上限。")
    finance_research = finance_sub.add_parser("research", help="让研究员汇总当前金融模型。")
    finance_research.add_argument("--agent", required=True)
    finance_research.add_argument("--topic", default="agent-world financial model")

    record = sub.add_parser("record", help="中文客观行为记录。")
    record_sub = record.add_subparsers(dest="record_command", required=True)
    record_export = record_sub.add_parser("export", help="为每个智能体导出一份中文行为文件。")
    record_export.add_argument("--dir", dest="output_dir")

    summary = sub.add_parser("summary", help="中文周期世界汇总。")
    summary_sub = summary.add_subparsers(dest="summary_command", required=True)
    summary_export = summary_sub.add_parser("export", help="导出当前小世界的中文汇总。")
    summary_export.add_argument("--dir", dest="output_dir")

    sub.add_parser("ralph-plan", help="写入顶层智能体 Ralph 规划包。")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    db_path = Path(args.db)
    engine = WorldEngine(db_path)

    if args.command == "init":
        if args.reset:
            reset_db(db_path)
        seed_world(db_path)
        print(f"小世界已就绪：{db_path}")
        return 0

    engine.ensure_seeded()

    if args.command == "status":
        state = engine.snapshot()
        if args.json:
            print(json.dumps(state, ensure_ascii=False, indent=2))
        else:
            print_status(state)
        return 0

    if args.command == "agents":
        state = engine.snapshot()
        for agent in state["agents"]:
            print(
                f"{agent['id']:18} 角色={zh_role(agent['role']):8} 状态={zh_status(agent['state']):8} "
                f"agent-credits={agent['credits']:4} 心情={agent['mood']:.2f} 精力={agent['energy']:.2f}"
            )
        return 0

    if args.command == "venues":
        for venue in engine.snapshot()["venues"]:
            print(f"{venue['id']:14} 价格={venue['price']:3} 类型={venue['kind']:10} {venue['name']}")
        return 0

    if args.command == "blueprints":
        for blueprint in engine.snapshot()["blueprints"]:
            print(f"{blueprint['id']:14} 角色={zh_role(blueprint['role']):8} {blueprint['name']} - {blueprint['description']}")
        return 0

    if args.command == "institutions":
        for item in engine.snapshot()["institutions"]:
            agent_id = item["controlled_agent_id"] or "-"
            print(f"{item['id']:16} 类型={zh_role(item['kind']):8} 控制智能体={agent_id:18} 预算={item['budget_credits']:5} {item['name']}")
        return 0

    if args.command == "laws":
        state = engine.snapshot()
        for law in state["laws"]:
            print(f"{law['id']:26} 领域={law['domain']:10} {law['title']}")
        print("")
        for category in state["tradeCategories"]:
            print(f"{category['id']:22} {zh_status(category['legal_status']):10} 法律={category['governing_law_id']} {category['name']}")
        return 0

    if args.command == "tick":
        summaries = engine.tick(args.steps)
        print(json.dumps(summaries, ensure_ascii=False, indent=2))
        return 0

    if args.command == "task" and args.task_command == "create":
        task_id = engine.create_task(
            title=args.title,
            description=args.description,
            reward=args.reward,
            assigned_agent_id=args.assigned_agent_id,
            assigned_channel_id=args.assigned_channel_id,
            assigned_role=args.assigned_role,
        )
        print(f"已创建任务 #{task_id}")
        return 0

    if args.command == "message" and args.message_command == "send":
        msg_id = engine.send_message(
            sender_id=args.sender_id,
            body=args.body,
            channel_id=args.channel_id,
            recipient_id=args.recipient_id,
        )
        print(f"已发送消息 #{msg_id}")
        return 0

    if args.command == "ledger":
        state = engine.snapshot()
        rows = state["ledger"]
        if args.agent:
            rows = [row for row in rows if row["agent_id"] == args.agent]
        for row in rows[:25]:
            print(
                f"#{row['id']:03} {row['agent_id']:8} {row['delta']:>5} "
                f"余额={row['balance_after']:>4} 原因={row['reason']} 引用={row['ref_type']}:{row['ref_id']}"
            )
        return 0

    if args.command == "agent" and args.agent_command == "create":
        agent_id = engine.create_agent(
            name=args.name,
            blueprint_id=args.blueprint,
            owner_id=args.owner,
            credits=args.credits,
        )
        print(f"已创建智能体 {agent_id}")
        return 0

    if args.command == "training" and args.training_command == "programs":
        for program in engine.snapshot()["trainingPrograms"]:
            print(
                f"{program['id']:24} 成本={program['cost']:3} 技能={program['target_skill']:22} "
                f"轮数={program['duration_ticks']} {program['name']}"
            )
        return 0

    if args.command == "training" and args.training_command == "start":
        training_id = engine.start_training(args.agent, args.program)
        print(f"已开始训练 #{training_id}")
        return 0

    if args.command == "lineage" and args.lineage_command == "create":
        child_id = engine.reproduce_agents(
            [item.strip() for item in args.parents.split(",")],
            args.name,
            owner_id=args.owner,
            mutation_rate=args.mutation_rate,
        )
        print(f"已孵化子代智能体 {child_id}")
        return 0

    if args.command == "nuwa" and args.nuwa_command == "list":
        for item in engine.snapshot()["nuwaDistillations"]:
            print(f"{item['id']:14} {item['domain']:34} {item['display_name']} - {item['honesty_boundary']}")
        return 0

    if args.command == "nuwa" and args.nuwa_command == "create":
        agent_id = engine.create_nuwa_agent(
            distillation_id=args.figure,
            name=args.name,
            owner_id=args.owner,
            credits=args.credits,
        )
        print(f"已创建女娲智能体 {agent_id}")
        return 0

    if args.command == "market" and args.market_command == "categories":
        for category in engine.snapshot()["tradeCategories"]:
            print(f"{category['id']:22} {zh_status(category['legal_status']):10} 风险={category['risk_level']} 法律={category['governing_law_id']} {category['description']}")
        return 0

    if args.command == "market" and args.market_command == "list":
        state = engine.snapshot()
        for item in state["marketListings"]:
            print(f"#{item['id']:03} {zh_status(item['status']):8} {item['item_type']:20} 卖家={item['seller_agent_id']:14} 价格={item['price']:4} {item['item_name']}")
        return 0

    if args.command == "market" and args.market_command == "create":
        listing_id = engine.create_market_listing(
            seller_agent_id=args.seller,
            item_type=args.item_type,
            item_name=args.name,
            description=args.description,
            price=args.price,
        )
        print(f"已创建市场挂牌 #{listing_id}")
        return 0

    if args.command == "market" and args.market_command == "buy":
        transaction_id = engine.buy_market_listing(args.buyer, args.listing)
        print(f"已结算市场交易 #{transaction_id}")
        return 0

    if args.command == "construction" and args.construction_command == "list":
        state = engine.snapshot()
        for project in state["constructionProjects"]:
            print(f"建设项目 #{project['id']:03} {zh_status(project['status']):8} 建设者={project['builder_agent_id']:10} 所有者={project['owner_agent_id']:10} 进度={project['progress']:.0f}% {project['name']}")
        for building in state["buildings"]:
            print(f"建筑 #{building['id']:03} 所有者={building['owner_agent_id']:10} 价值={building['value']:4} 租金={building['rent_per_tick']:3} {building['name']}")
        return 0

    if args.command == "construction" and args.construction_command == "create":
        project_id = engine.create_construction_project(
            builder_agent_id=args.builder,
            owner_agent_id=args.owner,
            name=args.name,
            kind=args.kind,
            cost=args.cost,
            expected_value=args.expected_value,
        )
        print(f"已启动建设项目 #{project_id}")
        return 0

    if args.command == "product" and args.product_command == "list":
        state = engine.snapshot()
        for product in state["products"]:
            print(f"产品 #{product['id']:03} {zh_status(product['status']):8} 设计者={product['designer_agent_id']:10} 价格={product['unit_price']:4} 库存={product['stock']:3} 质量={product['quality']:.2f} {product['name']}")
        for sale in state["productSales"]:
            print(f"销售 #{sale['id']:03} 产品={sale['product_id']} 买家={sale['buyer_agent_id']} 卖家={sale['seller_agent_id']} 总价={sale['total_price']}")
        return 0

    if args.command == "product" and args.product_command == "create":
        product_id = engine.design_product(
            designer_agent_id=args.designer,
            name=args.name,
            category=args.category,
            unit_price=args.price,
            build_cost=args.build_cost,
            stock=args.stock,
        )
        print(f"已创建产品 #{product_id}")
        return 0

    if args.command == "product" and args.product_command == "buy":
        sale_id = engine.buy_product(args.buyer, args.product, args.quantity)
        print(f"已结算产品销售 #{sale_id}")
        return 0

    if args.command == "housing" and args.housing_command == "list":
        state = engine.snapshot()
        for home in state["residences"]:
            occupant = home["occupant_agent_id"] or "-"
            owner = home["owner_agent_id"] or "-"
            print(
                f"住所 #{home['id']:03} {zh_status(home['status']):10} "
                f"所有者={owner:16} 居住={occupant:16} 买价={home['purchase_price']:5} "
                f"月租={home['monthly_rent']:4} 舒适={home['comfort']:.2f} {home['name']}"
            )
        return 0

    if args.command == "housing" and args.housing_command == "rent":
        residence_id = engine.rent_residence(args.agent, args.residence)
        print(f"{args.agent} 已租下住所 #{residence_id}")
        return 0

    if args.command == "housing" and args.housing_command == "buy":
        residence_id = engine.buy_residence(args.agent, args.residence)
        print(f"{args.agent} 已买下住所 #{residence_id}")
        return 0

    if args.command == "housing" and args.housing_command == "invest":
        residence_id = engine.buy_residence_for_rent(args.agent, args.residence, args.rent)
        print(f"{args.agent} 已买下住所 #{residence_id} 并挂牌出租")
        return 0

    if args.command == "company" and args.company_command == "list":
        state = engine.snapshot()
        for company in state["companies"]:
            print(
                f"{company['id']:20} {zh_status(company['status']):8} 资金={company['treasury_credits']:5} "
                f"需求={company['demand_score']:.2f} {company['name']}"
            )
        for job in state["companyJobs"][:12]:
            print(
                f"岗位 #{job['id']:03} {zh_status(job['status']):10} 公司={job['company_id']} "
                f"行业={job['industry']} 类型={job['output_type']} 报酬={job['reward']} 任务={job['task_id']}"
            )
        for output in state["companyOutputs"][:12]:
            print(
                f"产出 #{output['id']:03} {zh_status(output['status']):10} agent={output['agent_id']} "
                f"有效度={output['effectiveness_score']:.2f} 奖励={output['reward']} {output['title']}"
            )
        for need in state["materialNeeds"][:8]:
            print(f"需求 #{need['id']:03} {need['industry']} {need['demand_score']:.2f} {need['topic']}")
        return 0

    if args.command == "company" and args.company_command == "repair-skills":
        repaired = engine.repair_accepted_skill_packages(limit=args.limit)
        print(f"已补齐 {len(repaired)} 个历史 skill 包")
        for item in repaired[:20]:
            print(f"产出 #{item['company_output_id']:03} 文档={item['document_id']} 质量={item['quality']:.2f} {item['path']}")
        return 0

    if args.command == "company" and args.company_command == "need" and args.company_need_command == "add":
        need_id = engine.submit_material_need(
            industry=args.industry,
            topic=args.topic,
            demand_score=args.demand,
            source_hint=args.source,
            actor_agent_id=args.actor,
        )
        print(f"已提交行业资料需求 #{need_id}：{args.industry} - {args.topic}")
        return 0

    if args.command == "finance" and args.finance_command == "reports":
        for report in engine.snapshot()["financialResearchReports"]:
            print(f"#{report['id']:03} {report['researcher_agent_id']:10} 有用度={report['usefulness_score']:.2f} {report['topic']} -> {report['path']}")
        return 0

    if args.command == "finance" and args.finance_command == "policy":
        state = engine.snapshot()
        rows = state.get("monetaryPolicy", [])
        if not rows:
            print("暂无货币政策快照；推进一轮世界后，credit-bank 会计算 MV=PY 供给上限。")
            return 0
        for row in rows[:10]:
            print(
                f"#{row['id']:03} tick={row['tick_no']:03} 行动={row['action']} "
                f"流通={row['circulating_credits']}/{row['money_supply_cap']} "
                f"银行储备={row['bank_reserves']}/{row['bank_reserve_cap']} "
                f"价格指数={row['price_index']:.3f} 通胀={row['inflation_rate'] * 100:+.2f}% "
                f"政策利率={row['policy_rate'] * 100:.2f}%"
            )
        return 0

    if args.command == "finance" and args.finance_command == "research":
        report_id = engine.research_financial_model(args.agent, args.topic)
        print(f"已创建金融研究报告 #{report_id}")
        return 0

    if args.command == "record" and args.record_command == "export":
        written = export_agent_behavior_records(db_path=db_path, output_dir=args.output_dir) if args.output_dir else export_agent_behavior_records(db_path=db_path)
        print(f"已导出 {len(written)} 个行为记录文件")
        for path in written[:12]:
            print(path)
        return 0

    if args.command == "summary" and args.summary_command == "export":
        path = export_world_summary(db_path=db_path, output_dir=args.output_dir) if args.output_dir else export_world_summary(db_path=db_path)
        print(f"已导出世界汇总 {path}")
        return 0

    if args.command == "ralph-plan":
        packet = write_planning_packet(db_path=db_path)
        print(f"已写入 {packet}")
        return 0

    parser.error("未处理的命令")
    return 2


def print_status(state: dict[str, Any]) -> None:
    agents = state["agents"]
    open_tasks = [task for task in state["tasks"] if task["status"] in ("open", "in_progress")]
    done_tasks = [task for task in state["tasks"] if task["status"] == "done"]
    queued = [item for item in state["publicationQueue"] if item["status"] == "queued"]
    total_credits = sum(agent["credits"] for agent in agents)
    print("Hermes Agent World 小世界")
    print(f"智能体：{len(agents)}  智能体持有 agent-credits：{total_credits}  活跃任务：{len(open_tasks)}")
    print(f"已完成任务：{len(done_tasks)}  发布队列：{len(queued)}")
    policy = (state.get("monetaryPolicy") or [None])[0]
    if policy:
        print(
            f"货币政策：流通 {policy['circulating_credits']}/{policy['money_supply_cap']}，"
            f"银行储备 {policy['bank_reserves']}/{policy['bank_reserve_cap']}，"
            f"通胀 {policy['inflation_rate'] * 100:+.2f}%，行动={policy['action']}"
        )
    print("")
    for agent in agents:
        task = agent["current_task_id"] or "-"
        print(
            f"- {agent['id']:18} {zh_role(agent['role']):8} {zh_status(agent['state']):8} "
            f"agent-credits={agent['credits']:4} 心情={agent['mood']:.2f} 精力={agent['energy']:.2f} 当前任务={task}"
        )


def zh_role(value: str) -> str:
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


def zh_status(value: str) -> str:
    return {
        "bootstrap": "启动期",
        "stand_down": "自主运行",
        "idle": "空闲",
        "working": "工作中",
        "leisure": "休闲中",
        "researching": "研究中",
        "training": "训练中",
        "trained": "训练完成",
        "proud": "自豪",
        "stung": "受挫",
        "reflecting": "反思中",
        "incubating": "孵化中",
        "done": "完成",
        "open": "开放",
        "in_progress": "进行中",
        "active": "活跃",
        "sold": "已售出",
        "sold_out": "售罄",
        "queued": "排队中",
        "pending": "待审判",
        "approved": "已通过",
        "rejected": "未通过",
        "settled": "已结算",
        "operational": "运营中",
        "allowed": "允许交易",
        "regulated": "监管交易",
        "prohibited": "禁止交易",
        "legal": "合法",
        "for_rent": "可租",
        "for_sale": "可买",
        "rented": "已出租",
        "owner_occupied": "自住房",
        "needs_revision": "需返工",
        "accepted": "有效",
        "regulated-approved": "监管通过",
    }.get(value, value)


if __name__ == "__main__":
    raise SystemExit(main())
