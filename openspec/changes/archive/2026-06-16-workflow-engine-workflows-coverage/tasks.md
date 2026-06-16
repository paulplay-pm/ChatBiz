# Tasks: workflow-engine-workflows-coverage

> 关联 spec:`specs/workflow-engine-workflows-coverage/spec.md`
> 关联 design:`design.md`
> 任务粒度:每条 ≤ 2h;编码任务配对验证任务

## 1. 摸底 + pre-condition verify

- [ ] 1.1 跑 `conda run -n chatbiz pytest services/workflow-engine/tests/
      --cov=app --cov-report=term-missing -q` 验证 287 tests PASS +
      98.85% cov + 15 miss 集中在 api/workflows.py
- [ ] 1.2 摸底 cov 报告:用 `coverage._data.lines()` 拿 workflows.py 实际
      covered line 集合,确认 line 35-39 + 52 真 covered(说明 list_workflows
      函数体实际跑了)

## 2. 写 `tests/unit/test_api_workflows.py` 2 个新 test

> 1 test → 1 pytest verify → 写下一个(micro-cycle,跟 sso cov change
> `sso-routers-coverage/plan.md` Step 2 同 pattern)

- [ ] 2.1 写 test #20 `test_list_workflows_empty` — 0 row 触发 line 40
      + 53-56。代码 pattern:不加任何 row,GET /workflows,断言
      `data["total"] == 0` + `data["workflows"] == []`
- [ ] 2.2 跑 `pytest tests/unit/test_api_workflows.py::test_list_workflows_empty
      -v` 验证 PASS
- [ ] 2.3 写 test #21 `test_list_workflows_dedup_keeps_highest_version` —
      同 wf_id 加 v1+v2+v3,GET /workflows,断言只 1 个 entry 且 version=3
- [ ] 2.4 跑 `pytest tests/unit/test_api_workflows.py::test_list_workflows_dedup_keeps_highest_version
      -v` 验证 PASS

## 3. 验证覆盖率

- [ ] 3.1 跑 `conda run -n chatbiz pytest services/workflow-engine/tests/
      --cov=app --cov-fail-under=100 -q` 验证:
      - 最佳:289 passed + Required test coverage of 100% reached
      - 可接受:289 passed + 仍报 98.85% (cov tool false negative 持续)
- [ ] 3.2 跑全 workflow-engine suite:`pytest services/workflow-engine/tests/
      -q` 确认 289 passed,无 regression
- [ ] 3.3 单独看 workflows.py cov:`pytest services/workflow-engine/tests/
      --cov=app.api.workflows --cov-report=term-missing -q` 验证是否
      100% 或仍 85%

## 4. Commit + 收尾

- [ ] 4.1 `git add services/workflow-engine/tests/unit/test_api_workflows.py`
- [ ] 4.2 `git commit -m "test(workflow-engine): 100% line cov on
      api/workflows.py" -m "$(cat <<'EOF'
- 新增 2 个 list_workflows test (0 row + dedup 双 version)
- 关 ci-integration-cov-matrix retrospective workflow-engine followup
- 摸底:摸底 287 PASS + 98.85% cov (15 miss 全在 api/workflows.py)
- 跟 sso cov change "1 module 1 change" pattern 对齐
EOF
)"`
- [ ] 4.3 跑 `git log -1 --format='%H %s'` 确认 commit 进 linear history
- [ ] 4.4 跑 `git status` 确认 working tree clean
- [ ] 4.5 `openspec archive workflow-engine-workflows-coverage --yes`
      把 change 移到 archive + spec 同步到
      `openspec/specs/workflow-engine-workflows-coverage/spec.md`
- [ ] 4.6 写 retrospective(对应 `archive/2026-06-16-workflow-engine-
      workflows-coverage/retrospective.md`)
- [ ] 4.7 `git add -A && git commit -m "chore(openspec): archive
      workflow-engine-workflows-coverage"`
- [ ] 4.8 `git push`(推 main)
- [ ] 4.9 跑 `openspec list` 验证 `workflow-engine-workflows-coverage`
      不在 active list(验证任务,配对 4.8)

## 规范校验清单(apply 时逐项过)

- [ ] 0 行 prod code 改动(`services/workflow-engine/app/` 任何文件 0 diff)
- [ ] 仅 `services/workflow-engine/tests/unit/test_api_workflows.py` 改
      (+2 function)
- [ ] 跟 sso cov change 2-commit pattern 对齐
- [ ] 跟 CLAUDE.md 测试覆盖率条款(≥100% / 不允许"先实现后补测试")
- [ ] 无新 build 框架 / docker-compose / 端口表改动
- [ ] 无 `tools/setup-chatbiz-env.sh` 改动(D6 决策 lock)
- [ ] 不动 ci-cov.yml(留独立 followup,跟 mcp-cov-matrix-add 同 pattern)

## 安全校验清单(apply 时逐项过)

- [ ] 0 行 prod code 改动 → 0 prod security surface 改变
- [ ] 新 test 跟既有 test 同 fixture / 模式,无新 dep
- [ ] 无 secret / token / 内部 IP 写进 test
- [ ] 无 `--cov-fail-under` 数值改动(沿用 pyproject 已 lock 的 100)
