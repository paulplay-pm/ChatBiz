# design-tokens Specification

## Purpose
TBD - created by archiving change web-portal-shell. Update Purpose after archive.
## Requirements
### Requirement: tailwind.config.js 与 prototype 逐位一致

`web/portal/tailwind.config.js` MUST 复制 `docs/prototype.html:7-40` 头部的 `tailwind.config` 块,包含 brand-50..900 / ink-50..950 / font-sans(DM Sans) / font-mono(Space Mono)。V2 / V3 集成时,canvas / admin 的 `tailwind.config.js` MUST 与 portal 逐位一致。

#### Scenario: portal tailwind.config.js 完整复制 prototype
- **WHEN** `web/portal/tailwind.config.js` 与 `docs/prototype.html:7-40` 比对
- **THEN** brand-{50,100,200,300,400,500,600,700,800,900} 的 hex 值 MUST 完全一致(50: #f0f4ff, 100: #e0e9ff, 200: #c2d4ff, 300: #94b4ff, 400: #5e8bff, 500: #3b6ef5, 600: #2a52d8, 700: #2240b0, 800: #1f368e, 900: #1e3072);ink-{50,100,200,300,400,500,600,700,800,900,950} 的 hex 值 MUST 完全一致(50: #f6f7f9, 100: #eceef2, 200: #d5d9e2, 300: #b0b8c8, 400: #8591a8, 500: #66728a, 600: #525b70, 700: #444b5c, 800: #3a3f4d, 900: #1e2128, 950: #0f1115);font-sans MUST 是 `['DM Sans', 'system-ui', 'sans-serif']`;font-mono MUST 是 `['Space Mono', 'monospace']`

#### Scenario: glass 工具类定义
- **WHEN** `web/portal/src/index.css` 包含 `.glass` 工具类
- **THEN** MUST 包含 `background: rgba(255,255,255,0.92)` + `backdrop-filter: blur(20px) saturate(1.4)` + `border-bottom: 1px solid rgba(0,0,0,0.06)`(与 `docs/prototype.html:37-41` 一致)

#### Scenario: Google Fonts 引入
- **WHEN** `web/portal/index.html` 加载字体
- **THEN** MUST 在 `<head>` 包含 `<link href="https://fonts.googleapis.com/css2?family=DM+Sans:...&family=Space+Mono:...&display=swap" rel="stylesheet" />`

### Requirement: V2 / V3 集成时三套 tailwind.config.js 逐位一致(占位)

V2 / V3 集成时 `web/canvas/tailwind.config.js` 与 `web/admin/tailwind.config.js` MUST 与 `web/portal/tailwind.config.js` 逐位一致;V1 verify 时仅校验 portal 单份(本 V1 不写 canvas / admin config)。

#### Scenario: V2 / V3 集成时 diff 检查
- **WHEN** V2 / V3 集成后
- **THEN** `diff web/portal/tailwind.config.js web/canvas/tailwind.config.js` MUST 无输出;`diff web/portal/tailwind.config.js web/admin/tailwind.config.js` MUST 无输出

