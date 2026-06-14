# tailwind-theme-prototype-sync Specification

## Purpose
TBD - created by archiving change admin-web-bootstrap. Update Purpose after archive.
## Requirements
### Requirement: Tailwind CSS 3.4 is configured

The system MUST have `web/admin/tailwind.config.js` + `web/admin/postcss.config.js`. `tailwindcss@^3.4.0` + `postcss` + `autoprefixer` MUST be in `devDependencies`. The `content` array MUST include `./index.html` + `./src/**/*.{ts,tsx}`. The system MUST have `@tailwind base; @tailwind components; @tailwind utilities;` in `src/index.css` (or equivalent entry CSS imported from `main.tsx`).

#### Scenario: Tailwind directives compiled
- **WHEN** developer runs `pnpm build`
- **THEN** the output CSS contains Tailwind base + components + utilities layers (no `@tailwind` directive in dist/)

#### Scenario: Custom ink-* class works
- **WHEN** developer writes `<div class="bg-ink-50">` in `src/App.tsx`
- **THEN** the rendered HTML has background-color set to the ink-50 value (`#f9fafb`)

### Requirement: prototype.html ink palette is mapped

`tailwind.config.js` MUST extend the theme with the `ink` color palette matching `docs/prototype.html` (sampled 2026-06-12):
- `ink-50: '#f9fafb'`
- `ink-100: '#f3f4f6'`
- `ink-200: '#e5e7eb'`
- `ink-300: '#d1d5db'`
- `ink-400: '#9ca3af'`
- `ink-500: '#6b7280'`
- `ink-600: '#4b5563'`
- `ink-700: '#374151'`
- `ink-800: '#1f2937'`
- `ink-900: '#111827'`

#### Scenario: All ink-* shades available
- **WHEN** developer writes `<div class="text-ink-900 bg-ink-50 border-ink-200">`
- **THEN** all three colors compile to the correct hex values

### Requirement: prototype.html brand palette is mapped

`tailwind.config.js` MUST extend the theme with the `brand` color palette:
- `brand-500: '#3b82f6'`
- `brand-600: '#2563eb'`
- `brand-700: '#1d4ed8'`
- `brand-800: '#1e40af'`
- `brand-900: '#1e3a8a'`

#### Scenario: brand-* shades for primary actions
- **WHEN** developer writes `<button class="bg-brand-500 hover:bg-brand-600 text-white">`
- **THEN** button has blue background with darker blue on hover

### Requirement: FontAwesome 6 Solid icons are available

The system MUST have `@fortawesome/fontawesome-free@^6.0.0` in `dependencies`. The system MUST import `@fortawesome/fontawesome-free/css/all.min.css` (or `solid` subset) from `src/main.tsx` so `<i class="fas fa-robot">` etc. render the icon.

#### Scenario: Icon renders
- **WHEN** developer writes `<i class="fas fa-robot">` in JSX
- **THEN** an SVG icon (or web font glyph) appears for the robot icon

#### Scenario: Tree-shaking reduces bundle
- **WHEN** developer runs `pnpm build` and only uses 5 unique `fas fa-*` icons
- **THEN** the final JS bundle is at most 1 MB (font subset tree-shaken)

### Requirement: Tailwind compile does not include unused classes

The `content` array MUST only scan `index.html` + `src/`, NOT `node_modules/`. Unused classes MUST be purged in production build.

#### Scenario: Purge works
- **WHEN** developer runs `pnpm build` and `src/` doesn't use `text-pink-500`
- **THEN** `text-pink-500` rule is NOT in the output CSS

