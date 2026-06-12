# vite-bootstrap

**Frontend Scope: 含前端**（Vite 5 + React 18 + TypeScript strict 基础脚手架）

**Impact**（被谁消费）：
- 被本 change 其他 capability（tailwind / router / nav）作为依赖
- 被 `mcp-server-management-ui` task 7.x 作为前置（必须有 `web/admin-web/package.json`）
- 未来被所有"前端业务 change"作为前置

## ADDED Requirements

### Requirement: Vite 5 dev server starts on localhost:5173

The system MUST have `web/admin-web/package.json` with `vite@^5.0.0` + `@vitejs/plugin-react@^4.0.0` as devDependencies. Running `pnpm dev` from `web/admin-web/` MUST start a Vite dev server on `http://localhost:5173` within 2 seconds, serving an HTML page with `<div id="root">` and a script tag for `/src/main.tsx`.

#### Scenario: Fresh clone starts
- **WHEN** developer runs `cd web/admin-web && pnpm install && pnpm dev`
- **THEN** Vite reports `ready in Xms` and `http://localhost:5173` is reachable with HTTP 200

#### Scenario: Production build works
- **WHEN** developer runs `pnpm build`
- **THEN** `dist/` is generated with `index.html` + chunked JS bundles and no Vite errors

#### Scenario: TypeScript strict mode
- **WHEN** developer runs `pnpm tsc --noEmit`
- **THEN** exit code is 0 with no type errors

### Requirement: Project layout follows Vite + React convention

The system MUST have the following file structure under `web/admin-web/`:
- `package.json` (with `type: "module"`)
- `vite.config.ts`
- `tsconfig.json` (strict mode)
- `tsconfig.node.json` (for vite.config.ts)
- `index.html` (Vite entry, references `/src/main.tsx`)
- `src/main.tsx` (React root render)
- `src/App.tsx` (top-level component)
- `.gitignore` (excludes `node_modules/`, `dist/`, `.vite/`, `coverage/`, `test-results/`, `playwright-report/`)

#### Scenario: Standard layout exists
- **WHEN** repository is cloned fresh
- **THEN** all the above files exist and `pnpm install` succeeds

### Requirement: Node engine pinned

`web/admin-web/package.json` MUST declare `"engines": { "node": ">=20" }` to prevent install on incompatible Node versions.

#### Scenario: Node 18 install fails
- **WHEN** developer runs `pnpm install` on Node 18
- **THEN** pnpm prints an engine warning AND exits with non-zero

#### Scenario: Node 20+ install succeeds
- **WHEN** developer runs `pnpm install` on Node 20+
- **THEN** pnpm completes with exit 0
