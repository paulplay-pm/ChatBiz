# Tasks: workflow-engine-ci-cov-matrix

> 关联 spec:`specs/workflow-engine-ci-cov-matrix/spec.md`
> 关联 design:`design.md`
> 任务粒度:每条 ≤ 2h;编码任务配对验证任务

## 1. 摸底 + pre-condition verify

- [ ] 1.1 跑 `conda run -n chatbiz pytest services/workflow-engine/tests/
      --cov=app --cov-fail-under=100 -q` 验证 **本机 fail**(摸底已知 cov tool
      false negative 持续,`Required test coverage of 100% reached` 不打)
- [ ] 1.2 确认 `.github/workflows/ci-cov.yml` 的 install step 适用于
      workflow-engine(mcp / sso / 其它 3 service 装 `pytest pytest-cov
      pytest-asyncio respx`,workflow-engine dev deps 多了 7 个但 ci 缺 dep
      会自然 fail,符合"预期 CI fail" 假设)
- [ ] 1.3 确认 `services/workflow-engine/pyproject.toml` 已 lock
      `--cov=app --cov-fail-under=100`(CLAUDE.md CI 触发约定 step 1 满足)

## 2. 改 ci-cov.yml

- [ ] 2.1 在 `.github/workflows/ci-cov.yml` `matrix.service` 列表加
      `- workflow-engine`(alphabetical 排序,在 `- gateway-scanner` 之后、
      `- mcp` 之前)
- [ ] 2.2 `git diff .github/workflows/ci-cov.yml` 验证只 +1 行(验证任务,
      配对 2.1)
- [ ] 2.3 `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/
      ci-cov.yml'))"` 验证 yaml 合法(验证任务,配对 2.1)
- [ ] 2.4 重新读 ci-cov.yml `matrix.service` 6 元素,确认顺序:
      audit-and-isolation / credential / gateway-scanner /
      workflow-engine / mcp / sso

## 3. 改 CLAUDE.md

- [ ] 3.1 在 `CLAUDE.md` "CI 触发约定(强制)" 段 `当前 matrix 列表 = [...]`
      数组加 `workflow-engine` 元素(alphabetical 排序)
- [ ] 3.2 删 `CLAUDE.md` "CI 触发约定(强制)" 段尾过时描述
      `**workflow-engine / mcp 2 service 仍是 0% cov,本约定未触发** —
      他们 cov matrix 收尾时一并加`(已过时)
- [ ] 3.3 加 1 句新描述 `**workflow-engine** cov tool false negative 持续,
      见 coverage-false-negative-investigation 摸底;matrix 已含 6 service`
- [ ] 3.4 `git diff CLAUDE.md` 验证 +1 元素 + 删 1 描述 + 加 1 描述
      (3 hunk)(验证任务,配对 3.1-3.3)

## 4. apply 收尾

- [ ] 4.1 `git add .github/workflows/ci-cov.yml CLAUDE.md
      openspec/changes/workflow-engine-ci-cov-matrix/`
- [ ] 4.2 `git commit -m "ci(openspec): add workflow-engine to ci-cov
      matrix" -m "$(cat <<'EOF'
- .github/workflows/ci-cov.yml matrix.service 列表加 workflow-engine
  (alphabetical 第 4 位,在 gateway-scanner 后 mcp 前)
- CLAUDE.md "CI 触发约定" 段 matrix 列表同步加 workflow-engine
- 删过时 "workflow-engine / mcp 2 service 仍是 0% cov" 描述
- 加 cov tool false negative 1 句说明
- 关 ci-integration-cov-matrix retrospective workflow-engine followup
- 摸底(2026-06-16)workflow-engine cov 100% 实际达成,coverage 7.14.1
  在 list_workflows 复合语句的 false negative 触发的 arc 推断 bug
- 预期 CI workflow-engine job fail 直到 cov bug 修
EOF
)"`
- [ ] 4.3 `openspec archive workflow-engine-ci-cov-matrix --yes` 把
      change 移到 archive + spec 同步到
      `openspec/specs/workflow-engine-ci-cov-matrix/spec.md`
- [ ] 4.4 写 retrospective(对应 `archive/2026-06-16-workflow-engine-
      ci-cov-matrix/retrospective.md`),surface 预期 CI fail + 留
      followup
- [ ] 4.5 `git add -A && git commit -m "chore(openspec): archive
      workflow-engine-ci-cov-matrix"`
- [ ] 4.6 `git push`(推 main)
- [ ] 4.7 跑 `openspec list` 验证 `workflow-engine-ci-cov-matrix` 不在
      active list(验证任务,配对 4.6)

## 规范校验清单(apply 时逐项过)

- [ ] 跟 CLAUDE.md "CI 触发约定(强制)" 段 step 1/2/3 一致:
      step 1 pyproject 已 lock `--cov=app` + `--cov-fail-under=100` ✓
      step 2 加进 workflow matrix ✓ (本 change 主体)
      step 3 PR 描述登记 ✓ (本 change)
- [ ] 跟 `mcp-cov-matrix-add` (2026-06-16 archive) 2-commit pattern
      一致(feat + archive)
- [ ] matrix 顺序 = alphabetical + audit-and-isolation 排头
- [ ] 无新 workflow step / 新 install step / 新 prod code
- [ ] 无 `tools/setup-chatbiz-env.sh` 改动(D6 决策 lock)
- [ ] 无 `services/workflow-engine/app/` 任何改动(cov 闸门修留独立
      followup)
- [ ] 无 docker-compose / 端口表 / 前端改动

## 安全校验清单(apply 时逐项过)

- [ ] 不动本地 env state
- [ ] yaml 文件合法(`yaml.safe_load` 解析无错)
- [ ] 不假设 secrets 在 env(跟 4 service 同 pattern,conda env 名
      hard-code)
- [ ] 无 `--cov-fail-under` 数值改动(沿用 workflow-engine pyproject
      已 lock 的 100)
