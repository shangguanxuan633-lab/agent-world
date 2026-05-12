from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_world.db import connect, json_loads, reset_db, seed_world
from agent_world.engine import WorldEngine
from agent_world.ralph_planner import write_planning_packet
from agent_world.recorder import export_agent_behavior_records
from agent_world.summary import export_world_summary


class WorldEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "world.db"
        reset_db(self.db_path)
        seed_world(self.db_path)
        self.engine = WorldEngine(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_task_completion_pays_credits_and_queues_publication(self) -> None:
        state = self.engine.snapshot()
        before = {agent["id"]: agent["credits"] for agent in state["agents"]}
        task_id = self.engine.create_task(
            title="Agent society architecture document",
            description="Write a useful document about Hermes agent society, judging, credits, and publishing.",
            reward=90,
            assigned_agent_id="mira",
        )
        self.engine.tick(steps=8)
        state = self.engine.snapshot()
        task = next(task for task in state["tasks"] if task["id"] == task_id)
        mira = next(agent for agent in state["agents"] if agent["id"] == "mira")
        self.assertEqual(task["status"], "done")
        self.assertGreaterEqual(mira["credits"], before["mira"] + 90)
        self.assertTrue(state["documents"])
        self.assertTrue(state["publicationQueue"])

    def test_peer_message_teaches_skill(self) -> None:
        self.engine.send_message(
            sender_id="lumen",
            channel_id="research",
            body="skill:retrieval Source triage should track provenance and freshness.",
        )
        state = self.engine.snapshot()
        mira = next(agent for agent in state["agents"] if agent["id"] == "mira")
        skills = {skill["name"] for skill in mira["skills"]}
        self.assertIn("retrieval", skills)

    def test_agents_autonomously_research_skills(self) -> None:
        self.engine.tick(steps=8)
        state = self.engine.snapshot()
        self.assertTrue(state["researchRuns"])
        learned_agents = {run["agent_id"] for run in state["researchRuns"]}
        self.assertIn("atlas", learned_agents)
        reward_reasons = {row["reason"] for row in state["ledger"]}
        self.assertIn("network_skill_reward", reward_reasons)

    def test_top_agent_stands_down_after_world_matures(self) -> None:
        self.engine.tick(steps=10)
        state = self.engine.snapshot()
        self.assertEqual(state["governance"]["topAgentMode"], "stand_down")
        task_id = self.engine.create_task(
            title="Makers guild implementation task",
            description="Build a small local improvement for the agent world.",
            reward=50,
            assigned_channel_id="makers",
        )
        self.engine.tick(steps=1)
        state = self.engine.snapshot()
        task = next(task for task in state["tasks"] if task["id"] == task_id)
        atlas = next(agent for agent in state["agents"] if agent["id"] == "atlas")
        self.assertNotEqual(atlas["current_task_id"], task_id)
        self.assertEqual(task["status"], "in_progress")

    def test_ralph_planning_packet_is_written(self) -> None:
        packet = write_planning_packet(self.db_path, workspace_root=Path(self.tmp.name))
        self.assertTrue(packet.exists())
        self.assertIn("Suggested Next Stories", packet.read_text(encoding="utf-8"))

    def test_training_improves_agent_skill(self) -> None:
        training_id = self.engine.start_training("lumen", "deep-research-lab")
        self.engine.tick(steps=8)
        state = self.engine.snapshot()
        session = next(item for item in state["trainingSessions"] if item["id"] == training_id)
        lumen = next(agent for agent in state["agents"] if agent["id"] == "lumen")
        skills = {skill["name"] for skill in lumen["skills"]}
        self.assertEqual(session["status"], "done")
        self.assertIn("source-triangulation", skills)

    def test_reproduction_creates_child_agent_with_lineage(self) -> None:
        child_id = self.engine.reproduce_agents(["lumen", "mira"], "Nova")
        state = self.engine.snapshot()
        self.assertTrue(any(agent["id"] == child_id for agent in state["agents"]))
        self.assertTrue(any(row["child_agent_id"] == child_id for row in state["lineage"]))
        child = next(agent for agent in state["agents"] if agent["id"] == child_id)
        self.assertGreaterEqual(len(child["skills"]), 2)

    def test_simulated_annealing_records_evolution_runs(self) -> None:
        self.engine.tick(steps=12)
        state = self.engine.snapshot()
        self.assertTrue(state["evolutionRuns"])

    def test_nuwa_agent_creation_adds_perspective_agent(self) -> None:
        agent_id = self.engine.create_nuwa_agent("feynman", name="Feynman Lens")
        state = self.engine.snapshot()
        agent = next(item for item in state["agents"] if item["id"] == agent_id)
        self.assertEqual(agent["role"], "nuwa_perspective")
        self.assertIn("honesty_boundary", agent["personality"])
        self.assertGreaterEqual(len(agent["skills"]), 3)

    def test_civic_institutions_and_legal_market_trade(self) -> None:
        state = self.engine.snapshot()
        roles = {agent["role"] for agent in state["agents"]}
        self.assertTrue({"government", "bank", "guard", "army", "court"} <= roles)
        self.assertTrue(state["institutions"])
        listing_id = self.engine.create_market_listing(
            seller_agent_id="mira",
            item_type="knowledge",
            item_name="Publication checklist",
            description="A legal knowledge artifact.",
            price=20,
        )
        transaction_id = self.engine.buy_market_listing("lumen", listing_id)
        state = self.engine.snapshot()
        listing = next(item for item in state["marketListings"] if item["id"] == listing_id)
        self.assertEqual(listing["status"], "sold")
        self.assertTrue(any(item["id"] == transaction_id for item in state["marketTransactions"]))

    def test_prohibited_trade_category_is_blocked(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.create_market_listing(
                seller_agent_id="forge",
                item_type="private-data",
                item_name="Secret memory dump",
                description="Should not be tradeable.",
                price=50,
            )

    def test_construction_product_and_finance_report(self) -> None:
        project_id = self.engine.create_construction_project("forge", "Forge Workshop", "workshop", 70)
        self.engine.tick(steps=4)
        product_id = self.engine.design_product("forge", "Skill Card", "tool", unit_price=18, build_cost=5, stock=2)
        sale_id = self.engine.buy_product("mira", product_id)
        report_id = self.engine.research_financial_model("lumen", "test financial model")
        state = self.engine.snapshot()
        self.assertTrue(any(item["id"] == project_id for item in state["constructionProjects"]))
        self.assertTrue(state["buildings"])
        self.assertTrue(any(item["id"] == sale_id for item in state["productSales"]))
        report = next(item for item in state["financialResearchReports"] if item["id"] == report_id)
        self.assertTrue(Path(report["path"]).exists())

    def test_rich_self_driven_agent_autonomously_builds(self) -> None:
        with connect(self.db_path) as conn:
            conn.execute("UPDATE agents SET credits=520, mood=0.82, energy=0.9, autonomy=0.95, state='idle', current_task_id=NULL WHERE id='forge'")
            conn.execute("UPDATE agent_needs SET rest=0.9, social=0.8, fun=0.8, purpose=0.86, safety=0.8, health=0.9 WHERE agent_id='forge'")
            conn.execute("UPDATE agent_emotions SET joy=0.7, anger=0.04, stress=0.08, confidence=0.75, loneliness=0.1, curiosity=0.7 WHERE agent_id='forge'")
        for _ in range(12):
            self.engine.tick(steps=1)
            state = self.engine.snapshot()
            if any(item["builder_agent_id"] == "forge" for item in state["constructionProjects"]):
                break
        state = self.engine.snapshot()
        self.assertTrue(any(item["builder_agent_id"] == "forge" for item in state["constructionProjects"]))
        self.assertTrue(any(row["agent_id"] == "forge" and row["reason"] == "autonomous_construction_investment" for row in state["ledger"]))

    def test_bank_controls_money_supply_under_inflation_pressure(self) -> None:
        self.engine.tick(steps=1)
        with connect(self.db_path) as conn:
            conn.execute("UPDATE agents SET credits=credits+2000 WHERE owner_id!='world-system'")
        self.engine.tick(steps=1)
        state = self.engine.snapshot()
        policy = state["monetaryPolicy"][0]
        self.assertGreater(policy["inflation_rate"], 0)
        self.assertLessEqual(policy["bank_reserves"], policy["bank_reserve_cap"])
        self.assertIn("抗通胀稳定费", policy["action"])
        self.assertTrue(any(row["reason"] == "anti_inflation_stability_fee" for row in state["ledger"]))

        with connect(self.db_path) as conn:
            before = conn.execute("SELECT credits FROM agents WHERE id='mira'").fetchone()["credits"]
            self.engine._credit(conn, "mira", 40, "judge_bonus", "test", "inflation")
            after = conn.execute("SELECT credits FROM agents WHERE id='mira'").fetchone()["credits"]
        self.assertLess(after - before, 40)

    def test_chinese_behavior_records_export(self) -> None:
        self.engine.send_message(sender_id="lumen", channel_id="research", body="skill:finance-models share notes")
        paths = export_agent_behavior_records(self.db_path, Path(self.tmp.name) / "中文记录" / "agent行为")
        names = {path.name for path in paths}
        self.assertIn("lumen.md", names)
        lumen = next(path for path in paths if path.name == "lumen.md")
        text = lumen.read_text(encoding="utf-8")
        self.assertIn("行为客观记录", text)
        self.assertIn("消息", text)

    def test_agents_have_chinese_native_language_and_health_needs(self) -> None:
        state = self.engine.snapshot()
        atlas = next(agent for agent in state["agents"] if agent["id"] == "atlas")
        self.assertEqual(atlas["personality"]["native_language"], "zh-CN")
        self.assertIn("health", atlas["needs"])

    def test_low_health_agent_spends_credits_at_clinic(self) -> None:
        with connect(self.db_path) as conn:
            conn.execute("UPDATE agent_needs SET health=0.12, fun=0.8, rest=0.8, social=0.8 WHERE agent_id='forge'")
            conn.execute("UPDATE agent_emotions SET anger=0.05, stress=0.1 WHERE agent_id='forge'")
            conn.execute("UPDATE agents SET mood=0.8, energy=0.8, credits=120, state='idle' WHERE id='forge'")
        self.engine.tick(steps=1)
        state = self.engine.snapshot()
        forge = next(agent for agent in state["agents"] if agent["id"] == "forge")
        self.assertGreater(forge["needs"]["health"], 0.12)
        self.assertTrue(any(row["agent_id"] == "forge" and row["ref_id"] == "clinic" for row in state["ledger"]))

    def test_chinese_world_summary_export(self) -> None:
        path = export_world_summary(self.db_path, Path(self.tmp.name) / "中文记录" / "世界汇总")
        text = path.read_text(encoding="utf-8")
        self.assertIn("Agent World 小世界周期汇总", text)
        self.assertIn("制度层", text)
        self.assertIn("身体与情绪", text)

    def test_world_changes_include_bounded_ou_random_factor(self) -> None:
        task_id = self.engine.create_task(
            title="随机扰动验证任务",
            description="让工程师推进一个带小幅 OU 随机因子的世界变化。",
            reward=40,
            assigned_agent_id="forge",
        )
        self.engine.tick(steps=1)
        state = self.engine.snapshot()
        self.assertTrue(state["randomFactors"])
        with connect(self.db_path) as conn:
            rows = list(conn.execute("SELECT key, value, algorithm FROM world_noise"))
        self.assertTrue(any(row["key"] == "world.global" for row in rows))
        self.assertTrue(any(row["key"] == f"task.effort.forge.{task_id}" for row in rows))
        self.assertTrue(all(row["algorithm"] == "ornstein-uhlenbeck" for row in rows))
        self.assertTrue(all(-0.12 <= float(row["value"]) <= 0.12 for row in rows))

    def test_stable_world_forms_company_and_rewards_effective_outputs(self) -> None:
        self.engine.tick(steps=10)
        state = self.engine.snapshot()
        self.assertTrue(state["companies"])
        self.assertTrue(state["companyJobs"])

        for _ in range(24):
            self.engine.tick(steps=1)
            state = self.engine.snapshot()
            if state["companyOutputs"]:
                break

        state = self.engine.snapshot()
        self.assertTrue(state["companyOutputs"])
        self.assertTrue(any(row["reason"] == "company_effective_output_reward" for row in state["ledger"]))
        self.assertTrue(any(item["target"].startswith("github-open-source") or item["target"].startswith("github-nuwa") for item in state["publicationQueue"]))

    def test_skill_package_company_output_is_complete_git_ready_directory(self) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO companies
                  (id, name, kind, founder_agent_id, treasury_credits, status, mission, demand_score)
                VALUES ('skillforge-company', 'SkillForge 开源技能公司', 'skill-lab', 'atlas', 3000, 'active', 'test skill output quality', 0.9)
                """
            )
            conn.execute(
                "UPDATE agents SET credits=1000, mood=0.9, energy=1.0, state='idle', current_task_id=NULL WHERE id='forge'"
            )
            conn.execute(
                "UPDATE agent_needs SET rest=1.0, fun=0.9, health=1.0, purpose=0.9 WHERE agent_id='forge'"
            )
            task_id = self.engine._create_task_in_conn(
                conn,
                title="AI 工程：行业技能包",
                description="公司需求：Agent 平台、RAG、工具调用、评测、记忆系统。请产出完整 SKILL.md、references、examples、scripts 和质量检查表。",
                reward=120,
                assigned_agent_id="forge",
                created_by="company:skillforge-company",
                actor_agent_id="skillforge-company",
            )
            conn.execute(
                """
                INSERT INTO company_jobs
                  (company_id, title, industry, output_type, reward, task_id, status, publication_target)
                VALUES ('skillforge-company', 'AI 工程：行业技能包', 'AI 工程', 'skill-package', 120, ?, 'open', 'github-open-source-skill-draft')
                """,
                (task_id,),
            )

        self.engine.tick(steps=8)
        state = self.engine.snapshot()
        output = next(row for row in state["companyOutputs"] if row["output_type"] == "skill-package")
        self.assertEqual(output["status"], "accepted")
        path = Path(output["path"])
        self.assertTrue(path.is_dir())
        for relative in (
            "SKILL.md",
            "manifest.json",
            "references/quality-checklist.md",
            "references/source-map.md",
            "references/handoff.md",
            "references/validation-procedure.md",
            "examples/handoff.md",
        ):
            self.assertTrue((path / relative).exists(), relative)
        self.assertFalse((path / "scripts" / "quick_validate.py").exists())
        skill_text = (path / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("description: Use when", skill_text)
        self.assertIn("## 质量门槛", skill_text)
        self.assertIn("## 安全边界", skill_text)
        quality = self.engine._artifact_quality_report(path, "skill-package")
        self.assertTrue(quality["passed"], quality)
        self.assertTrue(
            any(
                item["target"] == "github-open-source-skill-draft" and "严格质检通过" in item["notes"]
                for item in state["publicationQueue"]
            )
        )

    def test_industry_scout_can_submit_material_needs(self) -> None:
        self.engine.tick(steps=10)
        need_id = self.engine.submit_material_need(
            industry="智能客服运营",
            topic="客服质检、知识库维护、FAQ 生成和工单摘要的 agent 打工资料需求",
            demand_score=0.93,
            source_hint="https://example.com/customer-support-ai",
            actor_agent_id="atlas",
        )
        state = self.engine.snapshot()
        need = next(row for row in state["materialNeeds"] if row["id"] == need_id)
        self.assertEqual(need["industry"], "智能客服运营")
        self.assertGreaterEqual(need["demand_score"], 0.93)
        self.assertEqual(need["status"], "open")
        self.assertTrue(any(event["kind"] == "company.material_need_submitted" for event in state["events"]))

        same_need_id = self.engine.submit_material_need(
            industry="智能客服运营",
            topic="客服质检、知识库维护、FAQ 生成和工单摘要的 agent 打工资料需求",
            demand_score=0.55,
            source_hint="industry-scout-followup",
            actor_agent_id="atlas",
        )
        self.assertEqual(same_need_id, need_id)
        updated = next(row for row in self.engine.snapshot()["materialNeeds"] if row["id"] == need_id)
        self.assertGreater(updated["demand_score"], need["demand_score"])

    def test_housing_required_for_real_rest_and_monthly_rent(self) -> None:
        with connect(self.db_path) as conn:
            conn.execute("UPDATE agents SET credits=500, energy=0.22, mood=0.42, state='idle', current_task_id=NULL WHERE id='lumen'")
            conn.execute("UPDATE agent_needs SET rest=0.12, safety=0.44, fun=0.6, social=0.6, health=0.8 WHERE agent_id='lumen'")
            conn.execute("UPDATE agent_emotions SET anger=0.04, stress=0.18, joy=0.42 WHERE agent_id='lumen'")

        self.engine.rent_residence("lumen", 1)
        before = next(agent for agent in self.engine.snapshot()["agents"] if agent["id"] == "lumen")["energy"]
        self.engine.tick(steps=1)
        state = self.engine.snapshot()
        lumen = next(agent for agent in state["agents"] if agent["id"] == "lumen")
        self.assertGreater(lumen["energy"], before)
        self.assertTrue(any(event["kind"] == "housing.rested_home" for event in state["events"]))

        with connect(self.db_path) as conn:
            conn.execute("UPDATE residences SET last_rent_tick=-30 WHERE id=1")
        self.engine.tick(steps=1)
        state = self.engine.snapshot()
        self.assertTrue(any(row["agent_id"] == "lumen" and row["reason"] == "housing_monthly_rent" for row in state["ledger"]))

    def test_agent_text_profile_drifts_over_time(self) -> None:
        before = next(agent for agent in self.engine.snapshot()["agents"] if agent["id"] == "lumen")["textProfile"]
        self.engine.tick(steps=12)
        state = self.engine.snapshot()
        after = next(agent for agent in state["agents"] if agent["id"] == "lumen")["textProfile"]
        self.assertGreaterEqual(int(after["version"]), int(before["version"]) + 1)
        self.assertTrue(after["current_desire"])
        self.assertTrue(after["emotional_tone"])
        self.assertTrue(after["fear"])
        self.assertTrue(any(event["kind"] == "identity.text_drifted" for event in state["events"]))

    def test_agent_can_buy_residence_for_rent_and_receive_rent_income(self) -> None:
        with connect(self.db_path) as conn:
            conn.execute("UPDATE agents SET credits=26000, current_task_id=NULL, state='idle' WHERE id='forge'")
            conn.execute("UPDATE agents SET credits=1000, current_task_id=NULL, state='idle' WHERE id='lumen'")
            conn.execute("UPDATE residences SET occupant_agent_id=NULL, owner_agent_id='civic-government', status='for_sale', monthly_rent=190, last_rent_tick=0 WHERE id=4")

        self.engine.buy_residence_for_rent("forge", 4, monthly_rent=260)
        state = self.engine.snapshot()
        home = next(row for row in state["residences"] if row["id"] == 4)
        self.assertEqual(home["owner_agent_id"], "forge")
        self.assertIsNone(home["occupant_agent_id"])
        self.assertEqual(home["status"], "for_rent")

        self.engine.rent_residence("lumen", 4)
        with connect(self.db_path) as conn:
            conn.execute("UPDATE residences SET last_rent_tick=-30 WHERE id=4")
            forge_before = conn.execute("SELECT credits FROM agents WHERE id='forge'").fetchone()[0]
        self.engine.tick(steps=1)
        state = self.engine.snapshot()
        forge_after = next(agent for agent in state["agents"] if agent["id"] == "forge")["credits"]
        self.assertGreaterEqual(forge_after, forge_before + 260)
        self.assertTrue(any(row["agent_id"] == "forge" and row["reason"] == "housing_rent_income" for row in state["ledger"]))

    def test_unhealthy_agent_is_blocked_from_work_and_receives_emergency_care(self) -> None:
        with connect(self.db_path) as conn:
            task_id = self.engine._create_task_in_conn(
                conn,
                "Critical researcher overload",
                "A task that should not keep a sick agent working.",
                80,
                assigned_agent_id="lumen",
                actor_agent_id="owner",
            )
            conn.execute("UPDATE tasks SET status='in_progress', progress=30 WHERE id=?", (task_id,))
            conn.execute(
                "UPDATE agents SET current_task_id=?, credits=1, mood=0.02, energy=0.8, state='working' WHERE id='lumen'",
                (task_id,),
            )
            conn.execute("UPDATE agent_needs SET health=0.05, fun=0.1, rest=0.4 WHERE agent_id='lumen'")
            conn.execute("UPDATE agent_emotions SET stress=0.9, anger=0.2 WHERE agent_id='lumen'")

        self.engine.tick(steps=1)
        state = self.engine.snapshot()
        lumen = next(agent for agent in state["agents"] if agent["id"] == "lumen")
        task = next(task for task in state["tasks"] if task["id"] == task_id)
        self.assertIsNone(lumen["current_task_id"])
        self.assertEqual(lumen["state"], "recovering")
        self.assertGreater(lumen["needs"]["health"], 0.25)
        self.assertEqual(task["status"], "open")
        self.assertTrue(any(event["kind"] == "health.emergency_care" and event["actor_agent_id"] == "lumen" for event in state["events"]))

    def test_researcher_tasks_can_be_claimed_by_compatible_roles_when_lumen_is_unfit(self) -> None:
        with connect(self.db_path) as conn:
            task_id = self.engine._create_task_in_conn(
                conn,
                "医疗健康：人物技能蒸馏",
                "研究型人物技能蒸馏任务，应该允许相关知识角色承接。",
                90,
                assigned_role="researcher",
                created_by="company:skillforge-company",
                actor_agent_id="skillforge-company",
            )
            conn.execute("UPDATE agents SET current_task_id=NULL, state='idle', mood=0.02 WHERE id='lumen'")
            conn.execute("UPDATE agent_needs SET health=0.0, fun=0.0 WHERE agent_id='lumen'")
            conn.execute("UPDATE agent_emotions SET stress=1.0 WHERE agent_id='lumen'")
            conn.execute("UPDATE agents SET current_task_id=NULL, state='idle', mood=0.86, energy=0.9 WHERE role IN ('documentarian', 'nuwa_perspective')")
            conn.execute("UPDATE agent_needs SET health=0.9, fun=0.7, rest=0.8 WHERE agent_id IN (SELECT id FROM agents WHERE role IN ('documentarian', 'nuwa_perspective'))")
            conn.execute("UPDATE agent_emotions SET stress=0.1 WHERE agent_id IN (SELECT id FROM agents WHERE role IN ('documentarian', 'nuwa_perspective'))")

        self.engine.tick(steps=1)
        state = self.engine.snapshot()
        task = next(task for task in state["tasks"] if task["id"] == task_id)
        workers = [agent for agent in state["agents"] if agent["current_task_id"] == task_id]
        self.assertEqual(task["status"], "in_progress")
        self.assertTrue(workers)
        self.assertNotEqual(workers[0]["id"], "lumen")
        self.assertIn(workers[0]["role"], {"documentarian", "nuwa_perspective"})

    def test_company_spawns_researcher_when_research_backlog_outgrows_workforce(self) -> None:
        with connect(self.db_path) as conn:
            for index in range(4):
                conn.execute(
                    """
                    INSERT INTO tasks (title, description, reward, status, created_by)
                    VALUES (?, 'maturity seed', 1, 'done', 'test')
                    """,
                    (f"maturity seed {index}",),
                )
            conn.execute(
                """
                INSERT OR IGNORE INTO companies
                  (id, name, kind, founder_agent_id, treasury_credits, status, mission, demand_score)
                VALUES ('skillforge-company', 'SkillForge', 'skill-lab', 'atlas', 3000, 'active', 'test workforce', 0.9)
                """
            )
            for index in range(2):
                task_id = self.engine._create_task_in_conn(
                    conn,
                    f"研究积压任务 {index}",
                    "研究任务积压时公司应该补充研究员。",
                    88,
                    assigned_role="researcher",
                    created_by="company:skillforge-company",
                    actor_agent_id="skillforge-company",
                )
                conn.execute(
                    """
                    INSERT INTO company_jobs
                      (company_id, title, industry, output_type, reward, task_id, status, publication_target)
                    VALUES ('skillforge-company', ?, 'AI 工程', 'persona-distillation', 88, ?, 'open', 'github-nuwa-persona-draft')
                    """,
                    (f"研究积压任务 {index}", task_id),
                )
            conn.execute("UPDATE agents SET current_task_id=NULL, state='idle', mood=0.02 WHERE id='lumen'")
            conn.execute("UPDATE agent_needs SET health=0.0, fun=0.0 WHERE agent_id='lumen'")
            conn.execute("UPDATE agent_emotions SET stress=1.0 WHERE agent_id='lumen'")

        before = len([agent for agent in self.engine.snapshot()["agents"] if agent["role"] == "researcher"])
        self.engine.tick(steps=1)
        state = self.engine.snapshot()
        after = len([agent for agent in state["agents"] if agent["role"] == "researcher"])
        self.assertGreater(after, before)
        self.assertTrue(any(event["kind"] == "company.researcher_spawned" for event in state["events"]))


if __name__ == "__main__":
    unittest.main()
