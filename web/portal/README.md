# ChatBiz Portal (V1)

`web/portal` 子应用 — portal 主框架,独立 Vite dev 5174。

## 范围(V1)

- ✅ 独立 Vite + React + TS strict + Tailwind 3.4
- ✅ 11 个 primitives(Button / Card / Modal / Form / Input / Toast / Sidebar / 等)
- ✅ 30+ 项侧栏菜单 + 5 个 section
- ✅ Login / Dashboard / ComingSoon 3 个 page
- ✅ 登录态写 `localStorage['chatbiz.auth']`
- ❌ **不**集成 nginx 5173 — V2 + V3 一起做
- ❌ **不**改 canvas / admin — V2 / V3 独立 change

## dev(V1 期间)

```bash
pnpm --dir web/portal install
pnpm --dir web/portal exec vite          # http://localhost:5174/portal/
```

## build

```bash
pnpm --dir web/portal exec tsc --noEmit
pnpm --dir web/portal exec vite build    # → web/portal/dist/
```

## test

```bash
pnpm --dir web/portal exec vitest run    # 单元 + 集成
pnpm --dir web/portal exec playwright test  # e2e
```

## 设计 token

以 `docs/prototype.html` 头部 `tailwind.config` 块为唯一 source of truth。V2 / V3 集成时,canvas / admin 的 `tailwind.config.js` 必须与 portal 逐位一致 — 详见 `openspec/changes/web-portal-shell/checklist/tailwind-config-parity.md`。