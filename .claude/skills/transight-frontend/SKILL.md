---
name: transight-frontend
description: Use when editing client/src, Leaflet map behavior, polling, route selection, or Tailwind v4 UI in Transight
---

# Transight Frontend Skill

Use this skill for dashboard and map changes in Transight.

## Key Files

- `client/src/App.jsx`: route selection, polling, stop fetches, bus markers, cards
- `client/src/index.css`: Tailwind v4 theme tokens and custom styles
- `client/vite.config.js`: API proxy to Flask

## Commands

```bash
cd client
npm run dev
npm run build
npm run lint
```

## Gotchas

- Tailwind is v4 and theme tokens live in CSS, not `tailwind.config.js`.
- `App.jsx` handles both the current multi-bus payload and an older single-status fallback path.
- Polling runs every 10 seconds; changing that affects backend load and UI expectations.
- Leaflet icon setup includes a Vite-specific workaround at the top of `App.jsx`.
- Keep route, stops, and status fetch behavior aligned with the Flask endpoints.

## Verification

- Run `npm run build` for any frontend change.
- Run `npm run lint` for JSX or CSS edits.
- If the change touches data rendering, verify loading, error, and no-bus states as well as the happy path.
