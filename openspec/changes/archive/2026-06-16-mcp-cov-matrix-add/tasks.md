# Tasks: mcp-cov-matrix-add

> 关联 spec:`specs/mcp-cov-matrix-add/spec.md`
> 关联 design:`design.md`
> 任务粒度:每条 ≤ 2h;编码任务配对验证任务

## 1. 摸底 + pre-condition verify

- [ ] 1.1 跑 `conda run -n chatbiz pytest services/mcp/tests/ --cov=app
      --cov-report=term-missing -q` 验证 9 module 全 100% cov(对应 spec
      "mcp service retains 100% line cov pre-condition" 段)
- [ ] 1.2 确认 `.github/workflows/ci-cov.yml` 的 install step 适用于 mcp
      (`mcp` pyproject `[project.optional-dependencies].dev` 含 pytest /
      pytest-cov / pytest-asyncio / respx,跟现有 4 service 同 pattern)

## 2. 改 ci-cov.yml

- [ ] 2.1 在 `.github/workflows/ci-cov.yml` `matrix.service` 列表加 `- mcp`
      (alphabetical 排序,在 `gateway-scanner` 之后、`sso` 之前)
- [ ] 2.2 跑 `git diff .github/workflows/ci-cov.yml` 验证只 +1 行(验证
      任务,配对 2.1)
- [ ] 2.3 跑 `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci-cov.yml'))"`
      验证 yaml 合法(验证任务,配对 2.1)

## 3. 改 CLAUDE.md

- [ ] 3.1 在 `CLAUDE.md` "CI 触发约定(强制)" 段 `当前 matrix 列表 = [...]`
      数组加 `mcp` 元素(alphabetical 排序)
- [ ] 3.2 跑 `git diff CLAUDE.md` 验证只 +1 元素、-0 行(验证任务,配对 3.1)

## 4. apply 收尾

- [ ] 4.1 `git add .github/workflows/ci-cov.yml CLAUDE.md
      openspec/changes/mcp-cov-matrix-add/`
- [ ] 4.2 `git commit -m "ci(openspec): add mcp to ci-cov matrix" -m "$(cat <<'EOF'
- .github/workflows/ci-cov.yml matrix.service 列表加 mcp (alphabetical 第 4 位)
- CLAUDE.md "CI 触发约定" 段 matrix 列表同步加 mcp
- 关 ci-integration-cov-matrix retrospective followup
- 摸底确认 mcp 已 100% line cov (9 module, 183 tests PASS)
- 关联:openspec/changes/mcp-cov-matrix-add/ (5 artifact)
EOF
)"`
- [ ] 4.3 跑 `openspec archive mcp-cov-matrix-add --yes` 把 change 移到
      archive + spec 同步到 `openspec/specs/mcp-cov-matrix-add/spec.md`
- [ ] 4.4 写 retrospective(对应 `archive/<date>-mcp-cov-matrix-add/
      retrospective.md`)
- [ ] 4.5 `git add -A && git commit -m "chore(openspec): archive
      mcp-cov-matrix-add"`
- [ ] 4.6 `git push`(推 main)
- [ ] 4.7 跑 `openspec list` 确认 `mcp-cov-matrix-add` 不在 active
      list(验证任务,配对 4.6)
- [ ] 4.8 (apply 后,可选 sanity check) 跑 `git log --oneline -5` 确认
      2 commit 进 linear history

## 规范校验清单(apply 时逐项过)

- [ ] 跟 CLAUDE.md "CI 触发约定(强制)" 段 step 1/2/3 一致:
      - step 1 pyproject 已 lock `--cov=app` + `--cov-fail-under=100`(本机验证过)
      - step 2 加进 workflow matrix(本 change 主体)
      - step 3 PR 描述登记(本 change)
- [ ] 跟 `ci-integration-cov-matrix` archived change 2-commit pattern
      一致(feat + archive)
- [ ] matrix 顺序 = alphabetical + audit-and-isolation 排头
- [ ] 无新 workflow step / 新 install step / 新 prod code
- [ ] 无 `tools/setup-chatbiz-env.sh` 改动(D6 决策 lock)
- [ ] 无 `services/workflow-engine/` 改动(本 change 跟它无关)
- [ ] 无 docker-compose / 端口表 / 前端改动

## 安全校验清单(apply 时逐项过)

- [ ] 不动本地 env state(本机 mcp editable install broken 留独立 followup)
- [ ] yaml 文件合法(`yaml.safe_load` 解析无错)
- [ ] 不假设 secrets 在 env(跟 4 service 同 pattern,conda env 名 hard-code)
- [ ] 无 `--cov-fail-under` 数值改动(沿用 mcp pyproject 已 lock 的 100)
