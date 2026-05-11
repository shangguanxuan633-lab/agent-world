from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .db import DEFAULT_DB_PATH, seed_world
from .engine import WorldEngine
from .ralph_planner import write_planning_packet
from .recorder import export_agent_behavior_records
from .summary import export_world_summary


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = PROJECT_ROOT / "static"


class AgentWorldHandler(SimpleHTTPRequestHandler):
    engine: WorldEngine

    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        clean = parsed.path
        if clean == "/":
            return str(STATIC_ROOT / "index.html")
        if clean.startswith("/static/"):
            return str(STATIC_ROOT / clean.removeprefix("/static/"))
        return str(STATIC_ROOT / clean.lstrip("/"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            self._json(self.engine.snapshot())
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            if parsed.path == "/api/tick":
                self._json({"summaries": self.engine.tick(int(payload.get("steps", 1))), "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/tasks":
                task_id = self.engine.create_task(
                    title=str(payload["title"]),
                    description=str(payload.get("description", "")),
                    reward=int(payload["reward"]),
                    assigned_agent_id=payload.get("agent") or None,
                    assigned_channel_id=payload.get("group") or None,
                    assigned_role=payload.get("role") or None,
                )
                self._json({"taskId": task_id, "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/messages":
                msg_id = self.engine.send_message(
                    sender_id=str(payload.get("sender", "owner")),
                    body=str(payload["body"]),
                    channel_id=payload.get("group") or None,
                    recipient_id=payload.get("agent") or None,
                )
                self._json({"messageId": msg_id, "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/agents":
                agent_id = self.engine.create_agent(
                    name=str(payload["name"]),
                    blueprint_id=str(payload.get("blueprint", "researcher")),
                    owner_id=str(payload.get("owner", "local-owner")),
                    credits=int(payload.get("credits", 80)),
                )
                self._json({"agentId": agent_id, "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/training":
                training_id = self.engine.start_training(
                    agent_id=str(payload["agent"]),
                    program_id=str(payload["program"]),
                    created_by=str(payload.get("createdBy", "owner")),
                )
                self._json({"trainingId": training_id, "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/reproduce":
                parent_ids = payload.get("parents", [])
                if isinstance(parent_ids, str):
                    parent_ids = [item.strip() for item in parent_ids.split(",")]
                child_id = self.engine.reproduce_agents(
                    parent_ids=list(parent_ids),
                    child_name=str(payload["name"]),
                    owner_id=str(payload.get("owner", "local-owner")),
                    mutation_rate=float(payload.get("mutationRate", 0.08)),
                )
                self._json({"childId": child_id, "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/nuwa-agents":
                agent_id = self.engine.create_nuwa_agent(
                    distillation_id=str(payload["figure"]),
                    name=payload.get("name") or None,
                    owner_id=str(payload.get("owner", "local-owner")),
                    credits=int(payload.get("credits", 120)),
                )
                self._json({"agentId": agent_id, "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/market-listings":
                listing_id = self.engine.create_market_listing(
                    seller_agent_id=str(payload["seller"]),
                    item_type=str(payload["itemType"]),
                    item_name=str(payload["name"]),
                    description=str(payload.get("description", "")),
                    price=int(payload["price"]),
                )
                self._json({"listingId": listing_id, "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/market-buy":
                transaction_id = self.engine.buy_market_listing(
                    buyer_agent_id=str(payload["buyer"]),
                    listing_id=int(payload["listing"]),
                )
                self._json({"transactionId": transaction_id, "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/construction":
                project_id = self.engine.create_construction_project(
                    builder_agent_id=str(payload["builder"]),
                    owner_agent_id=payload.get("owner") or None,
                    name=str(payload["name"]),
                    kind=str(payload.get("kind", "workshop")),
                    cost=int(payload["cost"]),
                    expected_value=int(payload["expectedValue"]) if payload.get("expectedValue") else None,
                )
                self._json({"projectId": project_id, "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/products":
                product_id = self.engine.design_product(
                    designer_agent_id=str(payload["designer"]),
                    name=str(payload["name"]),
                    category=str(payload.get("category", "tool")),
                    unit_price=int(payload["price"]),
                    build_cost=int(payload.get("buildCost", 0)),
                    stock=int(payload.get("stock", 1)),
                )
                self._json({"productId": product_id, "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/product-buy":
                sale_id = self.engine.buy_product(
                    buyer_agent_id=str(payload["buyer"]),
                    product_id=int(payload["product"]),
                    quantity=int(payload.get("quantity", 1)),
                )
                self._json({"saleId": sale_id, "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/housing-rent":
                residence_id = self.engine.rent_residence(
                    agent_id=str(payload["agent"]),
                    residence_id=int(payload["residence"]),
                )
                self._json({"residenceId": residence_id, "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/housing-buy":
                residence_id = self.engine.buy_residence(
                    agent_id=str(payload["agent"]),
                    residence_id=int(payload["residence"]),
                )
                self._json({"residenceId": residence_id, "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/housing-invest":
                residence_id = self.engine.buy_residence_for_rent(
                    agent_id=str(payload["agent"]),
                    residence_id=int(payload["residence"]),
                    monthly_rent=int(payload["rent"]) if payload.get("rent") else None,
                )
                self._json({"residenceId": residence_id, "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/finance-research":
                report_id = self.engine.research_financial_model(
                    researcher_agent_id=str(payload["agent"]),
                    topic=str(payload.get("topic", "agent-world financial model")),
                )
                self._json({"reportId": report_id, "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/records/export":
                written = export_agent_behavior_records(db_path=self.engine.db_path)
                self._json({"count": len(written), "paths": [str(path) for path in written], "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/summary/export":
                path = export_world_summary(db_path=self.engine.db_path)
                self._json({"path": str(path), "state": self.engine.snapshot()})
                return
            if parsed.path == "/api/ralph-plan":
                packet = write_planning_packet(db_path=self.engine.db_path)
                self._json({"path": str(packet), "state": self.engine.snapshot()})
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")
        except Exception as exc:  # noqa: BLE001 - API boundary returns JSON error
            self._json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args) -> None:  # noqa: A003 - stdlib signature
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _json(self, payload, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve Hermes Agent World UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args(argv)

    seed_world(args.db)
    AgentWorldHandler.engine = WorldEngine(args.db)
    server = ThreadingHTTPServer((args.host, args.port), AgentWorldHandler)
    print(f"Hermes Agent World UI: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
