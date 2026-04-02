# Transight Claude Hooks

This project uses lightweight Claude Code hooks for three jobs:

- inject a small amount of startup context on `SessionStart`
- guard destructive reseeding attempts on `PreToolUse`
- log and optionally beep on `Stop` and `SubagentStop`

## Files

- `.claude/settings.json`: registers the hooks
- `.claude/hooks/scripts/hooks.py`: hook handler
- `.claude/hooks/config/hooks-config.json`: shared defaults
- `.claude/hooks/config/hooks-config.local.json`: optional personal overrides, kept out of git

## Shared Behavior

- `SessionStart`: prints branch, working tree status, and a reminder that `seed.py` is destructive
- `PreToolUse`: returns an `ask` decision if the Bash command looks like `python seed.py` or `python server/seed.py`
- `Stop` / `SubagentStop`: log the event and optionally play a system beep

## Local Overrides

Create `.claude/hooks/config/hooks-config.local.json` to override the shared defaults. Example:

```json
{
  "disableSound": true,
  "disableLogging": true
}
```

## Notes

- No large audio assets are committed. On Windows the script uses `winsound.MessageBeep`; elsewhere it falls back to the terminal bell.
- The shared config uses `py -3` for hook execution on Windows. If your machine exposes Python differently, adjust the command in `.claude/settings.json`.
- The hook script always exits successfully so it does not block normal Claude usage.
