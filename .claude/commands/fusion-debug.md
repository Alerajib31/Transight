---
description: Diagnose a Fusion Engine, ETA, or live-data issue using Transight's specialized agents
model: sonnet
---

# Fusion Debug

Use the Transight agents to diagnose a backend, ETA, or dashboard issue without bloating the main context.

## Workflow

1. Restate the reported symptom and decide whether the issue is backend/data, frontend/dashboard, or both.
2. Use the Task tool to invoke `transight-backend-agent` for anything involving:
   - `server/`
   - BODS, TomTom, GTFS, or YOLO inputs
   - ETA calculation
   - database reads and writes
3. If the symptom includes route selector, map markers, polling, or cards, also invoke `transight-frontend-agent`.
4. After investigation or edits, use `transight-verifier-agent` to run the smallest relevant checks.
5. Do not reseed unless the user explicitly approves a destructive reset.

## Output

Return:

- likely root cause
- files inspected or changed
- verification performed
- remaining risk, missing data, or follow-up
