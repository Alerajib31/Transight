---
description: Review local changes, run the right verification, and decide whether Transight is ready to ship
model: sonnet
---

# Ship Readiness

Perform a final Transight-specific ship check.

## Instructions

1. Inspect the current diff and group the changes by backend, frontend, data, or documentation.
2. Use `transight-verifier-agent` to run the smallest high-signal checks for the changed areas.
3. Call out any destructive steps, missing environment variables, external API dependencies, or manual QA still required.
4. If a change touches live data or ETA logic, include a note about fallback-path coverage.
5. Keep the final recommendation binary: ready to ship, or blocked.

## Output

Return:

- ship decision
- checks run
- blockers or residual risks
- recommended next step
