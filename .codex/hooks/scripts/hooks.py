#!/usr/bin/env python3
"""Lightweight hook handler for Transight's Codex workflow."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import winsound
except ImportError:  # pragma: no cover - only unavailable off Windows
    winsound = None


SCRIPT_DIR = Path(__file__).resolve().parent
HOOKS_DIR = SCRIPT_DIR.parent
CONFIG_DIR = HOOKS_DIR / "config"
LOGS_DIR = HOOKS_DIR / "logs"
LOCAL_CONFIG_PATH = CONFIG_DIR / "hooks-config.local.json"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "hooks-config.json"
HOOK_CONFIG_MAP = {
    "agent-turn-complete": "disableAgentTurnCompleteHook",
    "SessionStart": "disableSessionStartHook",
    "Stop": "disableStopHook",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", nargs="?")
    parser.add_argument("--hook", dest="hook_name")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_config(key: str, default: Any = False) -> Any:
    local_config = load_json(LOCAL_CONFIG_PATH)
    if key in local_config:
        return local_config[key]

    default_config = load_json(DEFAULT_CONFIG_PATH)
    if key in default_config:
        return default_config[key]

    return default


def is_disabled(hook_name: str) -> bool:
    config_key = HOOK_CONFIG_MAP.get(hook_name, "disableStopHook")
    return bool(get_config(config_key, False))


def logging_disabled() -> bool:
    return bool(get_config("disableLogging", False))


def sound_disabled() -> bool:
    return bool(get_config("disableSound", False))


def play_notification() -> None:
    if sound_disabled():
        return

    try:
        if winsound is not None and os.name == "nt":
            winsound.MessageBeep()
        else:
            sys.stderr.write("\a")
            sys.stderr.flush()
    except Exception:
        pass


def run_git(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=HOOKS_DIR.parent.parent,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        return completed.stdout.strip()
    except Exception:
        return ""


def log_event(hook_name: str) -> None:
    if logging_disabled():
        return

    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hook": hook_name,
        }
        with (LOGS_DIR / "hooks-log.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def build_session_context() -> str:
    branch = run_git("branch", "--show-current") or "unknown"
    status = run_git("status", "--short")
    dirty = "dirty" if status else "clean"
    return "\n".join(
        [
            "Transight Codex session context:",
            f"- branch: {branch}",
            f"- working tree: {dirty}",
            "- backend dev: `cd server && python app.py`",
            "- frontend dev: `cd client && npm run dev`",
            "- destructive command reminder: `python seed.py` drops tables",
        ]
    )


def main() -> None:
    args = parse_args()
    hook_name = ""

    if args.hook_name:
        hook_name = args.hook_name
    elif args.payload:
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError:
            return
        hook_name = str(payload.get("type", ""))

    if not hook_name or is_disabled(hook_name):
        return

    log_event(hook_name)

    if hook_name == "SessionStart":
        print(build_session_context())
        return

    if hook_name in {"agent-turn-complete", "Stop"}:
        play_notification()


if __name__ == "__main__":
    main()
