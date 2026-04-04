# First Bus-Style UI Retheme

**Date:** 2026-04-01
**Status:** Approved
**Approach:** CSS-Only Retheme (Approach A)

## Overview

Transform Transight AI's frontend to match the First Bus app's visual language while keeping the existing sidebar + map grid layout and all current functionality. The changes are primarily CSS-driven with minimal JSX modifications.

## Requirements

- Auto dark/light theme with toggle (system preference detection + manual override)
- Color-coded bus markers by delay status (green/amber/red)
- Themed map tiles (CartoDB Positron for light, Dark Matter for dark)
- Restyled cards that adapt to theme via CSS variables
- All existing cards and data preserved (journey, ETA, passengers, traffic, bus position)
- Stop info remains in map popups only (no sidebar stop list)
- Stop dots stay uniform blue

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Layout | Keep sidebar + map grid | Working layout, minimal risk |
| Theme | Auto dark/light with toggle | Flexibility, matches First Bus light style while preserving existing dark mode |
| Stop display | Map popups only | Current approach works, no need for sidebar stop list |
| Bus markers | Color-coded by delay | Visual status at a glance, like First Bus |
| Stop dots | Uniform blue | Simplicity, stops don't need status colors |
| Cards | Keep all, restyle | University project — technical details are valuable |
| Map tiles | CartoDB (themed) | Free, no API key, matches theme |

## Section 1: Theme System

### Implementation

A `data-theme` attribute on `<html>` controls the active theme. CSS custom properties swap per theme. Tailwind classes already reference these variables, so most of the UI flips automatically.

### Light Palette (First Bus-inspired)

| Variable | Value | Usage |
|----------|-------|-------|
| `--color-bg-primary` | `#f8fafc` | Page background |
| `--color-bg-card` | `#ffffff` | Card backgrounds |
| `--color-bg-card-hover` | `#f1f5f9` | Card hover states |
| `--color-text-primary` | `#1e293b` | Primary text |
| `--color-text-secondary` | `#64748b` | Secondary/muted text |
| `--color-border` | `#e2e8f0` | Card and section borders |
| `--color-accent` | `#1d4ed8` | First Bus blue accent |
| `--color-accent-glow` | `#2563eb` | Accent glow effects |

### Dark Palette (existing, preserved)

| Variable | Value | Usage |
|----------|-------|-------|
| `--color-bg-primary` | `#0b0f19` | Page background |
| `--color-bg-card` | `#111827` | Card backgrounds |
| `--color-bg-card-hover` | `#1f2937` | Card hover states |
| `--color-text-primary` | `#f9fafb` | Primary text |
| `--color-text-secondary` | `#9ca3af` | Secondary/muted text |
| `--color-border` | `#1e293b` | Card and section borders |
| `--color-accent` | `#3b82f6` | Blue accent |
| `--color-accent-glow` | `#2563eb` | Accent glow effects |

### Theme Detection & Persistence

1. On first load: check `localStorage("transight-theme")` for saved preference
2. If no saved preference: use `window.matchMedia("(prefers-color-scheme: dark)")` 
3. Set `document.documentElement.dataset.theme` to `"light"` or `"dark"`
4. On toggle click: flip theme, save to `localStorage`, update `data-theme`
5. If `localStorage` is unavailable: fall back to system preference silently

### CSS Structure — Tailwind v4 `@theme` Compatibility

The current `@theme` block in `index.css` registers CSS custom properties at `:root` level for the Tailwind compiler. To avoid specificity conflicts between `@theme` output and manual variable overrides:

**Strategy:** Keep the `@theme` block for non-color variables only (`--font-sans`). Move all color variables out of `@theme` and into explicit `[data-theme]` selector blocks. This avoids `:root`-level specificity fights between `@theme` output and theme overrides.

```css
@theme {
  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
  /* Color variables REMOVED from @theme — moved to [data-theme] blocks */
}

/* Light mode */
[data-theme="light"] {
  --color-bg-primary: #f8fafc;
  --color-bg-card: #ffffff;
  --color-bg-card-hover: #f1f5f9;
  --color-text-primary: #1e293b;
  --color-text-secondary: #64748b;
  --color-border: #e2e8f0;
  --color-accent: #1d4ed8;
  --color-accent-glow: #2563eb;
  --color-danger: #ef4444;
  --color-warning: #f59e0b;
  --color-success: #10b981;
}

/* Dark mode */
[data-theme="dark"] {
  --color-bg-primary: #0b0f19;
  --color-bg-card: #111827;
  --color-bg-card-hover: #1f2937;
  --color-text-primary: #f9fafb;
  --color-text-secondary: #9ca3af;
  --color-border: #1e293b;
  --color-accent: #3b82f6;
  --color-accent-glow: #2563eb;
  --color-danger: #ef4444;
  --color-warning: #f59e0b;
  --color-success: #10b981;
}
```

**Important:** Tailwind v4 utility classes like `bg-bg-card` resolve via the `@theme` registration. Since we're moving colors out of `@theme`, we must ensure Tailwind still recognizes them. The `[data-theme]` variables will still work as long as the variable names match what Tailwind expects. If Tailwind v4 requires `@theme` for utility class generation, keep the dark-mode values in `@theme` as defaults and add `[data-theme="light"]` overrides with higher specificity.

## Section 2: Color-Coded Bus Markers

### Delay Thresholds

| Delay Status | Condition | Marker Color | Glow Color |
|--------------|-----------|-------------|------------|
| On time | `delay_minutes <= 1` | Green `#10b981` | `rgba(16, 185, 129, 0.7)` |
| Slightly late | `1 < delay_minutes <= 5` | Amber `#f59e0b` | `rgba(245, 158, 11, 0.7)` |
| Very late | `delay_minutes > 5` | Red `#ef4444` | `rgba(239, 68, 68, 0.7)` |
| No data | `delay_minutes` is null/undefined | Blue `#3b82f6` | `rgba(37, 99, 235, 0.7)` (current) |

### Implementation

A helper function `getBusMarkerColors(delayMinutes)` returns `{ background, glow }` based on the thresholds above. The `busIcon` creation moves from a module-level constant to a per-bus dynamic `DivIcon` constructed inside the map render loop using the bus's `delay_minutes` value.

**Data pipeline fix:** The existing `allBusPositions` mapping must include `delay_minutes` for marker coloring to work. Update the mapping:

```jsx
const allBusPositions = buses.map((b, index) => ({
  key: getBusKey(b, index),
  vehicle_id: b.vehicle_id,
  operator: b.operator,
  position: [b.position.lat, b.position.lng],
  eta: b.eta,
  passengers: b.passenger_count,
  delay_minutes: b.delay_minutes,  // ADDED — required for color-coded markers
}));
```

Helper function:

```jsx
function getBusMarkerColors(delayMinutes) {
  if (delayMinutes == null) return { bg: '#2563eb,#1d4ed8', glow: 'rgba(37,99,235,.7)' };
  if (delayMinutes <= 1) return { bg: '#10b981,#059669', glow: 'rgba(16,185,129,.7)' };
  if (delayMinutes <= 5) return { bg: '#f59e0b,#d97706', glow: 'rgba(245,158,11,.7)' };
  return { bg: '#ef4444,#dc2626', glow: 'rgba(239,68,68,.7)' };
}
```

The bus marker HTML template uses these values in the inline `background` gradient and `box-shadow`.

### Stop Dots

Stop dots remain uniform blue (`#3b82f6`) with white border. No changes.

## Section 3: Themed Map Tiles

### Tile Providers

| Theme | Provider | URL |
|-------|----------|-----|
| Light | CartoDB Positron | `https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png` |
| Dark | CartoDB Dark Matter | `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png` |

Both are free, require no API key, and support retina (`{r}`) tiles.

### Attribution

```
&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>
```

### Route Polyline

The polyline color adjusts for contrast (this is a JSX prop change, not CSS):
- Light mode: `#1d4ed8` (deeper blue on light background)
- Dark mode: `#3b82f6` (brighter blue on dark background)

Implementation: `color={theme === 'dark' ? '#3b82f6' : '#1d4ed8'}` on the `<Polyline>` component.

Polyline weight and dash pattern remain the same (weight 4, dash `10, 10`).

### Reactivity

The `TileLayer` `url` prop is driven by the current theme state. When the theme toggles, the tile URL changes and Leaflet reloads tiles. Leaflet needs a `key` prop on `TileLayer` to force a re-mount when the URL changes (e.g., `key={theme}`).

**Note:** `MapContainer` center behavior is a separate pre-existing issue — it does not re-render on `center` prop changes after initial mount. This is out of scope for this retheme.

## Section 4: Card Restyling

### Light Mode Cards

- Background: `#ffffff` (via `--color-bg-card`)
- Border: `#e2e8f0` (via `--color-border`)
- Shadow: `0 1px 3px rgba(0,0,0,0.1)` (subtle elevation)
- Text colors flip via CSS variables

### Dark Mode Cards

- No change from current styling

### ETA Card Special Treatment

- Dark mode: Keep current `card-glow` animation (blue pulsing box-shadow)
- Light mode: Replace glow with a `4px` solid blue top border (`border-top: 4px solid var(--color-accent)`) for a clean accent without the glowing effect

### Light Mode Leaflet Overrides

Current CSS has Leaflet overrides for light-themed controls. These remain appropriate for light mode. For dark mode, add overrides:

```css
[data-theme="dark"] .leaflet-control-zoom a {
  background: #1f2937 !important;
  color: #f9fafb !important;
  border-color: #374151 !important;
}
```

## Section 5: Header & Theme Toggle

### Toggle Button

A sun/moon icon button placed next to the route selector in the header. Uses inline SVG or Unicode characters for zero dependencies:
- Light mode active: Show moon icon (click to switch to dark)
- Dark mode active: Show sun icon (click to switch to light)
- Icon-only button (no text label) — fits at all breakpoints including mobile

### Header Adaptation

- Light mode: `background: rgba(255,255,255,0.8)` with `backdrop-blur` and subtle bottom `box-shadow`
- Dark mode: Current `bg-bg-card/60` with `backdrop-blur` (no change)

### State Management

A `useTheme` custom hook or inline `useState` + `useEffect` in `App.jsx`:
- `const [theme, setTheme] = useState(() => { /* check localStorage, then prefers-color-scheme */ })`
- `useEffect` syncs `data-theme` attribute on `<html>` when `theme` changes
- `useEffect` also registers a `matchMedia("(prefers-color-scheme: dark)")` change listener so the theme follows system changes in real-time when no manual override is saved. Cleanup the listener on unmount.
- Toggle function flips state and writes to `localStorage`
- Approximately 20 lines of code

## Section 6: Testing & Error Handling

### Visual Testing Checklist

- [ ] Light mode renders correctly (cards, header, footer, map)
- [ ] Dark mode renders correctly (matches current appearance)
- [ ] Toggle switches theme smoothly
- [ ] Theme persists across page refreshes
- [ ] Bus markers show green for on-time buses
- [ ] Bus markers show amber for slightly late buses (1-5 min)
- [ ] Bus markers show red for very late buses (> 5 min)
- [ ] Bus markers show blue when no delay data available
- [ ] Map tiles swap between Positron and Dark Matter on theme change
- [ ] Leaflet popups are readable in both themes
- [ ] Route polyline visible on both light and dark tiles
- [ ] No style conflicts in Leaflet controls between themes

### Error Handling

| Scenario | Behavior |
|----------|----------|
| `localStorage` unavailable | Fall back to system preference, no crash |
| CartoDB CDN down | Gray/missing tiles (Leaflet default), no code change needed |
| `delay_minutes` null/undefined | Bus marker defaults to blue (current style) |
| System preference changes while app is open | If no manual override saved, theme follows system |

## Files Modified

| File | Changes |
|------|---------|
| `client/src/index.css` | Add light/dark theme variable blocks, dark-mode Leaflet overrides, light-mode card shadow, ETA card light-mode accent |
| `client/src/App.jsx` | Add theme state + toggle + matchMedia listener, dynamic bus marker colors, add `delay_minutes` to `allBusPositions`, themed tile URL, themed polyline color (`color` prop), toggle button in header, replace hardcoded `text-white` with `text-text-primary` and `bg-white` with `bg-bg-card` on map container |

## Out of Scope

- Sidebar stop list (stays as map popups)
- Component extraction / file splitting
- New data or API changes
- Mobile-specific bottom sheet layout
- Animated bus movement between positions
