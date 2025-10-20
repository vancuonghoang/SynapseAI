import json
from pathlib import Path
from typing import Any, Dict

from apscheduler.schedulers.blocking import BlockingScheduler

from orchestrator.mirror_worker import render_backlog

CONFIG_PATH = Path("config/app.yaml")


def _load_interval_minutes(default: int = 5) -> int:
    try:
        import yaml  # local import to keep dependency optional at runtime
    except ImportError:
        print("[MirrorScheduler] PyYAML not installed; using default cadence.")
        return default

    if not CONFIG_PATH.exists():
        return default

    data: Dict[str, Any] = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    return int(data.get("cadence", {}).get("mirror_renderer_minutes", default))


def start_scheduler():
    interval_minutes = _load_interval_minutes()
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(render_backlog, "interval", minutes=interval_minutes, id="backlog_mirror")
    print(f"[MirrorScheduler] Mirror job scheduled every {interval_minutes} minutes.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("[MirrorScheduler] Shutting down scheduler.")
        scheduler.shutdown()


if __name__ == "__main__":
    start_scheduler()
