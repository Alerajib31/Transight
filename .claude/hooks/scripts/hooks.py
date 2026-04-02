#!/usr/bin/env python3
"""Lightweight hook handler for Transight's Claude Code workflow."""

from __future__ import annotations

import json
import os
import re
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
SEED_PATTERN = re.compile(r"\b(?:python|py)(?:\s+-3)?\s+(?:server[\\/])?seed\.py\b", re.IGNORECASE)


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


def is_disabled(event_name: str) -> bool:
    return bool(get_config(f"disable{event_name}Hook", False))


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


def log_event(payload: dict[str, Any]) -> None:
    if logging_disabled():
        return

    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hook_event_name": payload.get("hook_event_name"),
            "tool_name": payload.get("tool_name"),
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
            "Transight session context:",
            f"- branch: {branch}",
            f"- working tree: {dirty}",
            "- backend dev: `cd server && python app.py`",
            "- frontend dev: `cd client && npm run dev`",
            "- destructive command reminder: `python seed.py` drops tables",
        ]
    )


def maybe_guard_seed(payload: dict[str, Any]) -> bool:
    if payload.get("hook_event_name") != "PreToolUse":
        return False

    if payload.get("tool_name") != "Bash":
        return False

    command = str(payload.get("tool_input", {}).get("command", ""))
    if not SEED_PATTERN.search(command):
        return False

    print(
        json.dumps(
            {
                "decision": "ask",
                "reason": "Transight guard: `seed.py` drops and recreates tables. Confirm before running it.",
            }
        )
    )
    return True


def main() -> None:
    raw = sys.stdin.read().strip()
    if not raw:
        return

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return

    event_name = str(payload.get("hook_event_name", ""))
    if event_name and is_disabled(event_name):
        return

    log_event(payload)

    if maybe_guard_seed(payload):
        return

    if event_name == "SessionStart":
        print(build_session_context())
        return

    if event_name in {"Stop", "SubagentStop"}:
        play_notification()


if __name__ == "__main__":
    main()
