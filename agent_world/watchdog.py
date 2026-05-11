from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from .db import DEFAULT_DB_PATH, seed_world
from .engine import WorldEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = PROJECT_ROOT / "runtime"


def healthy(url: str) -> bool:
    try:
        with urlopen(url, timeout=3) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Keep Agent World running and ticking.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8777)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--tick-seconds", type=int, default=60)
    parser.add_argument("--health-seconds", type=int, default=15)
    args = parser.parse_args(argv)

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    seed_world(args.db)
    engine = WorldEngine(args.db)
    server_proc: subprocess.Popen | None = None
    health_url = f"http://{args.host}:{args.port}/api/state"
    last_tick = 0.0

    while True:
        if not healthy(health_url):
            if server_proc and server_proc.poll() is None:
                server_proc.terminate()
                try:
                    server_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server_proc.kill()
            out = open(RUNTIME_DIR / "server.out.log", "ab")
            err = open(RUNTIME_DIR / "server.err.log", "ab")
            server_proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "agent_world.server",
                    "--host",
                    args.host,
                    "--port",
                    str(args.port),
                    "--db",
                    str(args.db),
                ],
                cwd=PROJECT_ROOT,
                stdout=out,
                stderr=err,
            )
            write_status(args, "server_started")

        now = time.time()
        if now - last_tick >= args.tick_seconds:
            summaries = engine.tick(1)
            write_status(args, "tick", summaries[-1])
            last_tick = now

        time.sleep(max(3, args.health_seconds))


def write_status(args, event: str, payload=None) -> None:
    status_path = RUNTIME_DIR / "watchdog-status.json"
    data = {
        "event": event,
        "port": args.port,
        "db": str(args.db),
        "tickSeconds": args.tick_seconds,
        "updatedAt": time.time(),
        "payload": payload or {},
    }
    status_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

