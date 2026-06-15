## Context

11 个 coverage change 累计达成 audit-and-isolation / credential / sso /
gateway-scanner 4 service 100% line cov。`ci-coverage-sso` retrospective
§4.3 列"CI workflow 不跑"为 followup。

**Stakeholders**: paul(sponsor)/ 未来 contributor / CI 维护者。

**Constraints**:
- 0 行 prod code 改动
- 沿用 conda env `chatbiz`(CLAUDE.md 锁定)
- 4 service 全部有 `addopts` 含 `--cov-fail-under=100`(`gateway-scanner`
  用 `--cov=gateway_scanner`,其他 3 service 用 `--cov=app`)
- workflow-engine / mcp 2 service 仍是 0% cov,本 change **不**进 matrix
  (留后续 change 触发)
- 仅引入 3 个标准 GitHub Action (`actions/checkout@v4` /
  `actions/setup-python@v5` / `conda-incubator/setup-miniconda@v3`)

## Goals / Non-Goals

**Goals:**
1. 1 个 GitHub Actions workflow `.github/workflows/ci-cov.yml` 跑 4
   service pytest + cov 100%
2. 触发:`push` main + `pull_request` main
3. 4 service matrix 独立跑(单 service 失败不阻塞其他)
4. CLAUDE.md 加 1 段"CI 触发约定"
5. 0 行 prod code 改动

**Non-Goals:**
1. 不动 4 service 任何 prod code 或 pyproject
2. 不动现有 `.github/workflows/gateway-static-scan.yml`
3. workflow-engine / mcp service 不进 matrix(留后续 change)
4. 不写真实 PG/Redis integration test
5. 不引入 secret / self-hosted runner(GitHub-hosted ubuntu-latest)

## Decisions

### D1: 1 workflow 4 service matrix (`strategy.matrix.service`)

- **选择**: `strategy.matrix.service` 列表 4 service
  (`audit-and-isolation` / `credential` / `gateway-scanner` / `sso`)
- **理由**: GitHub Actions matrix 标准 pattern,DRY 友好,4 service 维护
  成本 = 1 workflow
- **已考虑 alternative**:
  - 1 service 1 workflow(4 文件)→ 维护成本 × 4
  - 1 service 1 job in same workflow(无 matrix)→ 失去 matrix 优势
    (parallel / fail-fast 控制)

### D2: conda env `chatbiz` + per-service `pip install -e`

- **选择**: `conda-incubator/setup-miniconda@v3` + `conda env create
  -n chatbiz python=3.12` (or update) + `conda run -n chatbiz pip install
  -e services/<service>` + `conda run -n chatbiz pip install pytest
  pytest-cov pytest-asyncio respx` + `conda run -n chatbiz pytest
  services/<service>/tests/`
- **理由**: 跟 CLAUDE.md 锁定 + 11 个 coverage change 本地验证模式
  一致
- **已考虑 alternative**:
  - 纯 venv + pip → 跟 CLAUDE.md 锁定冲突
  - docker → CI 装 docker 多 1 层 + docker-in-docker 风险

### D3: 触发 `push` main + `pull_request` main

- **选择**: 2 trigger 标准 GitHub Actions pattern
- **理由**: PR 必跑防 regression,main push 必跑防直推;feature branch
  push 不跑(经 PR 触发)

### D4: 4 service 跑 parallel(`fail-fast: false`)

- **选择**: `fail-fast: false` — 1 service 失败不阻塞其他 service
- **理由**: 让 4 service 全部反馈可见,而不是 1 个 fail 中断 3 个待跑
  service 的反馈

### D5: 简化 per-service steps(无 artifact upload,无 cache)

- **选择**: 1 job = 1 service,steps = checkout + setup-python + setup-conda
  + install + pytest
- **理由**: 4 service 跑 ~2-3 min 总时间(每个 ~30-60s),无需要 cache;cov
  report 输出到 log 即可,无需 artifact upload
- **已考虑 alternative**:
  - 加 `actions/upload-artifact@v4` 上传 cov XML → 复杂度增加,本仓库
    无 SonarQube 等外部 cov dashboard

## Risks / Trade-offs

**[Risk] conda 装 1-2 min 慢,4 service × 1-2 min = 4-8 min 总 CI 时间** 
→ Mitigation: matrix 4 service parallel 跑(单 service 仍 1-2 min setup
+ 30-60s pytest,总 4 service 时间 2-3 min)

**[Trade-off] workflow-engine / mcp 2 service 不进 matrix** → 接受:
2 service 仍是 0% cov,本 change 锁死 4 service 100% 闸门;2 service
进 matrix 留后续 change(他们 cov matrix 收尾时一并加)

**[Trade-off] 不加 cache step** → 接受:conda env setup 1-2 min 可接受
trade-off 不维护 cache key 失效问题

**[Trade-off] 0% coverage 服务的 workflow 集成不在本 change scope** →
接受:本 change 锁定 4 service 100% cov 闸门,workflow-engine/mcp 进
matrix 留 V1.0+ 触发(2 service 仍 0 行 test,加进 matrix 会立即 fail)

## Migration Plan

N/A — 本 change **不涉及服务部署或代码部署**。仅新增 1 个 CI workflow
文件 + 1 段 CLAUDE.md 文本。

**部署步骤**: 0
**Rollback 策略**: `git revert <commit>`,纯 CI 文件 + 文本
**验收条件**:
- `.github/workflows/ci-cov.yml` 存在 + YAML 合法
- 本地跑 `conda run -n chatbiz pytest services/<service>/tests/` 4 service
  仍全 PASS
- CLAUDE.md 含 1 段"CI 触发约定"

**Note on GitHub Actions 不能本地 dry-run**: 实际 workflow 行为需 push
后由 GitHub Actions 跑验证。本 change 在本地 **无法** 跑真 workflow;
verify.md §5.5 标为"workflow 行为待 push 后由 GA 验证",**不**作为本
change archive 阻塞条件。

## Open Questions

(本轮无 — D1-D5 决策链已穷举,选完无需进一步澄清)
