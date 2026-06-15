## 1. 摸底 + scaffold

- [x] 1.1 摸底:看 4 service pyproject `[tool.pytest.ini_options]` 锁定
  `--cov-fail-under=100` 跟 module name(`app` vs `gateway_scanner`)
- [x] 1.2 看现有 `.github/workflows/gateway-static-scan.yml` workflow
  pattern(参考 trigger / step 格式)
- [x] 1.3 确认 4 service 本地 `conda run -n chatbiz pytest
  services/<service>/tests/` 全 PASS(无 regression)
- [x] 1.4 决定 workflow-engine / mcp 2 service **不**进 matrix(scope
  排除)

## 2. 写 `.github/workflows/ci-cov.yml`

> 1 file → 1 yaml parse verify → 写 CLAUDE.md 段 → 写 verify.md

- [x] 2.1 写 `.github/workflows/ci-cov.yml` — D1 + D2 + D3 + D4 + D5
- [x] 2.2 跑 `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci-cov.yml'))"`
  验 YAML 合法
- [x] 2.3 跑 `grep "service:" .github/workflows/ci-cov.yml` 验 matrix 4
  service(不含 workflow-engine / mcp)

## 3. 写 CLAUDE.md 段

- [x] 3.1 在 `CLAUDE.md` 加 1 段"CI 触发约定" — D(spec)
- [x] 3.2 跑 `grep -A 3 "CI 触发约定" CLAUDE.md` 验命中

## 4. 本地 proxy verify

- [x] 4.1 跑 4 service pytest 验 100% 仍 PASS(本 change 不动 prod code,
  4 service 应仍 PASS)

## 5. Commit + 收尾

- [x] 5.1 `git add .github/workflows/ci-cov.yml CLAUDE.md`
- [x] 5.2 `git commit -m "ci(openspec): add ci-cov workflow + CLAUDE.md CI trigger rule"`
  (Co-Authored-By 结尾)
- [x] 5.3 跑 `git log -1 --format='%H %s'` 确认 commit 进 linear history
- [x] 5.4 跑 `git status` 确认 working tree clean
