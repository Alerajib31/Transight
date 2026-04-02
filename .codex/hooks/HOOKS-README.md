# Transight Codex Hooks

This project adds a small Codex hook setup so Codex sessions pick up Transight context automatically.

## Files

- `.codex/config.toml`: registers the `notify` hook used after each agent turn
- `.codex/hooks.json`: registers `SessionStart` and `Stop`
- `.codex/hooks/scripts/hooks.py`: shared handler
- `.codex/hooks/config/hooks-config.json`: shared defaults
- `.codex/hooks/config/hooks-config.local.json`: optional personal overrides

## Behavior

- `SessionStart`: injects branch and workspace status into the session context
- `agent-turn-complete`: logs the event and optionally plays a system beep
- `Stop`: logs the event and optionally plays a system beep
- The shared Windows setup uses `py -3` to launch the hook script.

## Local Overrides

Create `.codex/hooks/config/hooks-config.local.json` if you want to silence or disable logging:

```json
{
  "disableSound": true,
  "disableLogging": true
}
```
