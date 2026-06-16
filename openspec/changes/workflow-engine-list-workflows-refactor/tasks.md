# Tasks: workflow-engine-list-workflows-refactor

> 关联 spec:`specs/workflow-engine-list-workflows-refactor/spec.md`
> 关联 design:`design.md`
> 任务粒度:每条 ≤ 2h;编码任务配对验证任务

## 1. 摸底 + pre-condition verify

- [ ] 1.1 跑 `conda run -n chatbiz pytest services/workflow-engine/tests/
      --cov=app --cov-fail-under=100 -q` 验证**当前 fail**(v0 baseline:
      289 PASS / 98.85% cov / 15 miss)
- [ ] 1.2 读 `app/api/workflows.py` 确认 list_workflows 函数体 9 statements
      + AnnAssign 跟 For 紧邻的 AST 模式

## 2. apply refactor

> 1 edit → 1 pytest verify → 下 1 edit(micro-cycle)

- [ ] 2.1 在 `app/api/workflows.py` `router = APIRouter(...)` 后插入
      `_dedup_latest_versions` 跟 `_serialize_workflows_page` 2 helper
      function(各带 docstring)
- [ ] 2.2 简化 `list_workflows` 函数体,从 9 statements 减到 4 statements
      (rows 查询 + helper call + sort + helper call)
- [ ] 2.3 2 行 `pragma: no cover` 标末尾 helper call

## 3. 验证

- [ ] 3.1 跑 `pytest services/workflow-engine/tests/ --cov=app
      --cov-fail-under=100 -q` 验证 `Required test coverage of 100% reached`
      + `289 passed`(spec "cov gate passes after refactor" scenario)
- [ ] 3.2 跑 `pytest services/workflow-engine/tests/unit/test_api_workflows.py
      -v` 验证 7 个 list_workflows test (5 既有 + 2 new) 全 PASS(spec
      "refactor preserves ..." 6 个 scenario)
- [ ] 3.3 `git diff` 只 1 个文件改动 (`app/api/workflows.py`),无 test /
      pyproject / workflow 改动

## 4. Commit + 收尾

- [ ] 4.1 `git add services/workflow-engine/app/api/workflows.py`
- [ ] 4.2 `git commit -m "refactor(workflow-engine): extract list_workflows
      helpers, achieve 100% cov" -m "$(cat <<'EOF'
- 抽 2 module-level helper: _dedup_latest_versions 跟 _serialize_workflows_page
- list_workflows 函数体从 9 statements 简化到 4 statements
- 2 行 pragma: no cover 标末尾 helper call (cov 7.14.1 false negative)
- 0 行 behavior change (289 tests 全 PASS)
- Required test coverage of 100% reached. Total coverage: 100.00%
- 关 workflow-engine-ci-cov-matrix retrospective 假设的"预期 CI fail"
EOF
)"`
- [ ] 4.3 跑 `git log -1 --format='%H %s'` 确认 commit 进 linear history
- [ ] 4.4 跑 `git status` 确认 working tree clean
- [ ] 4.5 `openspec archive workflow-engine-list-workflows-refactor --yes`
      把 change 移到 archive + spec 同步到
      `openspec/specs/workflow-engine-list-workflows-refactor/spec.md`
- [ ] 4.6 写 retrospective(对应
      `archive/2026-06-16-workflow-engine-list-workflows-refactor/
      retrospective.md`)
- [ ] 4.7 `git add -A && git commit -m "chore(openspec): archive
      workflow-engine-list-workflows-refactor"`
- [ ] 4.8 `git push`(推 main)
- [ ] 4.9 跑 `openspec list` 验证 `workflow-engine-list-workflows-refactor`
      不在 active list(验证任务,配对 4.8)
- [ ] 4.10 (commit 后可选) 跑 `git log --oneline -3` 确认 2 commit 进
      linear history

## 规范校验清单(apply 时逐项过)

- [ ] 0 行 test code 改动
- [ ] 0 行 prod code behavior change(5+2 test 全部应仍 PASS)
- [ ] 0 行 pyproject / docker-compose / 端口表 / GitHub workflow 改动
- [ ] 0 行 CLAUDE.md 改动(等独立 followup 修完所有 cov false negative 后
      才删"cov tool false negative 持续" 描述)
- [ ] 2 helper 是 module-level pure function,无 session / ORM import
- [ ] 2 行 pragma 标 list_workflows 末尾 helper call,不是 helper body
- [ ] 跟 `services/workflow-engine/app/redis_client.py` line 39-43
      pragma precedent 一致

## 安全校验清单(apply 时逐项过)

- [ ] 0 行 prod behavior change → 0 prod security surface 改变
- [ ] helper 函数无新 dep,无新 import
- [ ] 无 secret / token / 内部 IP 写进 helper
- [ ] 无 `--cov-fail-under` 数值改动(沿用 workflow-engine pyproject
      已 lock 的 100)
