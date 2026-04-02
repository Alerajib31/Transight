# Glob: client/src/**/*.{js,jsx,css}

## React Frontend Rules

- Keep the frontend in React function components with hooks.
- Tailwind is v4 and configured in `client/src/index.css`; do not introduce `tailwind.config.js` patterns.
- `client/src/App.jsx` owns polling, route selection, map markers, and multi-bus state; coordinate changes carefully.
- Preserve the 10-second polling cadence unless the backend contract changes too.
- Keep Leaflet icon setup intact unless you are intentionally replacing it with another tested approach.
