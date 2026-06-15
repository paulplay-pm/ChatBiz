# ci-integration-cov-matrix Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`)
> syntax for tracking.

**Goal**: 加 1 个 GitHub Actions workflow 文件 `.github/workflows/ci-cov.yml`
跑 4 service pytest + cov 100% 闸门 + 1 段 CLAUDE.md CI 触发约定,关
`ci-coverage-sso` retrospective §4.3 followup。

**Architecture**: 1 workflow file (`matrix.service` 列表 4 service) +
CLAUDE.md 1 段 trigger rule。沿用 conda env `chatbiz`(CLAUDE.md 锁定)+ 4
service pyproject `addopts` `--cov-fail-under=100`(已锁)。0 行 prod code
改动。workflow-engine / mcp 2 service 仍 0% cov,**不**进 matrix。

**Tech Stack**: Python 3.12 + pytest 8.x + pytest-cov 6.x +
GitHub Actions (`actions/checkout@v4` / `actions/setup-python@v5` /
`conda-incubator/setup-miniconda@v3`) + conda env `chatbiz`

---

## Task 1: 写 `.github/workflows/ci-cov.yml`

**Files:**
- Create: `.github/workflows/ci-cov.yml`

- [ ] **Step 1**: 创建 workflow 文件
```yaml
name: ci-cov

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  cov:
    name: ${{ matrix.service }} pytest --cov-fail-under=100
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        service:
          - audit-and-isolation
          - credential
          - gateway-scanner
          - sso
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Setup conda (chatbiz env)
        uses: conda-incubator/setup-miniconda@v3
        with:
          miniconda-version: latest
          auto-activate-base: false
          python-version: 3.12

      - name: Create chatbiz env
        run: |
          conda create -n chatbiz python=3.12 -y
          conda run -n chatbiz pip install --upgrade pip

      - name: Install service + test deps
        working-directory: services/${{ matrix.service }}
        run: |
          conda run -n chatbiz pip install -e .
          conda run -n chatbiz pip install pytest pytest-cov pytest-asyncio respx

      - name: Run pytest (cov-fail-under=100 from pyproject addopts)
        working-directory: services/${{ matrix.service }}
        run: conda run -n chatbiz pytest tests/
```

- [ ] **Step 2**: 验 YAML 合法:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci-cov.yml')); print('YAML OK')"
```
Expected: `YAML OK`

- [ ] **Step 3**: 验 matrix 4 service:
```bash
grep -A 8 "matrix:" .github/workflows/ci-cov.yml
```
Expected: matrix service 含 4 service,**不**含 workflow-engine / mcp

---

## Task 2: 写 CLAUDE.md CI 触发约定段

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1**: 在 `## Working here` 段(或合适位置)加 CI 触发约定
```markdown
## CI 触发约定

所有 service 进 `.github/workflows/ci-cov.yml` matrix 时,**必须**同步
更新(不允许 addopts `--cov-fail-under=100` 在 `pyproject.toml` 但不进
workflow matrix)。当前 matrix 列表 = `[audit-and-isolation, credential,
gateway-scanner, sso]`,新增 service 时:
1. 写 `services/<new-service>/pyproject.toml` 含 `--cov=app` 或
   `--cov=<module>` + `--cov-fail-under=100`
2. 同步加进 `.github/workflows/ci-cov.yml` matrix
3. PR 描述里登记端口表 + 新 service name

workflow-engine / mcp 2 service 仍是 0% cov,本约定未触发 — 他们 cov
matrix 收尾时一并加。
```

- [ ] **Step 2**: 验命中:
```bash
grep -A 3 "CI 触发约定" CLAUDE.md
```
Expected: 命中 ≥1 段

---

## Task 3: 本地 proxy verify

- [ ] **Step 1**: 4 service pytest 仍 PASS:
```bash
for svc in audit-and-isolation credential gateway-scanner sso; do
  conda run -n chatbiz pytest services/$svc/tests/ -q
done
```
Expected: 4 service 全 PASS,无 regression

---

## Task 4: Commit

- [ ] **Step 1**: `git add .github/workflows/ci-cov.yml CLAUDE.md`
- [ ] **Step 2**: `git commit -m "ci(openspec): add ci-cov workflow + CLAUDE.md CI trigger rule"
  ` with Co-Authored-By trailer
- [ ] **Step 3**: `git log -1 --format='%H %s'` 验证 commit 进 linear history
- [ ] **Step 4**: `git status` 验证 working tree clean
