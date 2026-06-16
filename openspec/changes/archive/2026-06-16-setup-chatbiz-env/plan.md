# setup-chatbiz-env Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task. 本 plan 已用 micro-step 拆好,直接
> follow checklist 即可。

**Goal:** 加 `tools/setup-chatbiz-env.sh` 单文件 shell script,1-shot 装
`chatbiz` conda env + 4 service dev deps;在 `CLAUDE.md` 加 1 段引用。

**Architecture:** 沿用 `tools/check-compose-naming.sh` 单文件 shell 模式
(`set -euo pipefail` / 头部 docstring / bash 4+ / macOS BSD awk 兼容),
4 mode (`full` / `--check` / `--env-only` / `--service <name>`)。
`--check` 用 `pip show <pkg> | awk '/^Location:/ {print $2}'` 拿 editable
install 路径,跟 `services/<name>/` 实际路径精确比对 — worktree 路径 ≠
main 路径就会 FAIL,这是正确信号(不是 bug)。

**Tech Stack:** bash 4+ (含 macOS BSD awk 兼容) + conda 4.6+ (在 PATH)。
无新依赖。

---

## Task 1: 写 `tools/setup-chatbiz-env.sh` 主体

**Files:**
- Create: `tools/setup-chatbiz-env.sh`(~144 行)

- [ ] **Step 1.1:** 写 script 头部 docstring(15-30 行,记决策背景 +
      Usage + Exit codes),沿用 `tools/check-compose-naming.sh` 第 1-30
      行结构
- [ ] **Step 1.2:** 写 `set -euo pipefail` + ROOT/ENV_NAME/PYTHON_VERSION/
      SERVICES=(audit-and-isolation credential gateway-scanner sso) 变量
- [ ] **Step 1.3:** 写 `MODE` 4 mode flag parsing(`full` / `check` /
      `env-only` / `single`),用 for-arg + case;`--service` 接 bare value
- [ ] **Step 1.4:** 写 `verify_conda` + `conda_env_exists` + `run_in_env`
      3 helper
- [ ] **Step 1.5:** 写 [1/3] 段(env create / verify + 共享 build tooling
      upgrade,但 `--check` 模式 skip upgrade)
- [ ] **Step 1.6:** 写 [2/3] 段的 `--check` 分支(`pip show` + Location
      路径比对,FAIL exit 3)
- [ ] **Step 1.7:** 写 [2/3] 段的 `single` / `env-only` / `full` 分支
      (`install_service_deps` helper,`pip install -e ".[dev]"`)
- [ ] **Step 1.8:** 写 [3/3] 段(summary + Next steps)

---

## Task 2: chmod +x + 验证 `--help` + 验证 `--check`

**Files:**
- Modify: `tools/setup-chatbiz-env.sh`(权限)

- [ ] **Step 2.1:** `chmod +x tools/setup-chatbiz-env.sh`
- [ ] **Step 2.2:** 跑 `bash tools/setup-chatbiz-env.sh --help` 验证输出
      docstring head 30 行(预期 30+ 行,exit 0)
- [ ] **Step 2.3:** 跑 `bash tools/setup-chatbiz-env.sh --check` 验证:
      - [OK] audit-and-isolation (Location=/Users/paulwang/work/ChatBiz/services/audit-and-isolation)
      - [FAIL] credential (没在 /Users/paulwang/work/ChatBiz/services/credential editable install)
      - [OK] gateway-scanner
      - [FAIL] sso
      - 整体 exit 3

---

## Task 3: 在 CLAUDE.md 插入引用段

**Files:**
- Modify: `CLAUDE.md`(+1 段,~11 行)

- [ ] **Step 3.1:** 找 anchor `### CI 触发约定(强制)` 段尾(约 182 行)
- [ ] **Step 3.2:** 在 `### 前端目录与端口约定(强制)` 段头前插入
      `### Python 后端环境设置(强制)` 段,11 行:
      - 第一段:新开发者入职跑 `bash tools/setup-chatbiz-env.sh`
      - 第二段:cross-ref memory `[[conda-chatbiz-env]]`
      - 第三段:3 个常见用法 `--check` / `--service <name>` / `--env-only`
- [ ] **Step 3.3:** `git diff CLAUDE.md` 验证只 +1 段、-0 行

---

## Task 4: apply 收尾 (commit + archive + push)

**Files:**
- Modify: git index (3 files added: tools/setup-chatbiz-env.sh,
  CLAUDE.md 改,openspec/changes/setup-chatbiz-env/* 8 文件)

- [ ] **Step 4.1:** `git status` 确认 working tree 包含 2 个 prod 改动
      (tools/setup-chatbiz-env.sh, CLAUDE.md) + 1 个 spec 改动
      (openspec/changes/setup-chatbiz-env/{brainstorm,design,proposal,
      specs,tasks,plan}.md)
- [ ] **Step 4.2:** `git add tools/setup-chatbiz-env.sh CLAUDE.md
      openspec/changes/setup-chatbiz-env/`
- [ ] **Step 4.3:** `git commit -m "feat(tools): add setup-chatbiz-env.sh
      + CLAUDE.md 引用段" -m "$(cat <<'EOF'
- 在 tools/ 下新增 setup-chatbiz-env.sh 4 mode 单文件 shell
- 沿用 check-compose-naming.sh 模式 (set -euo pipefail / 头部 docstring)
- --check 模式用 pip show | Location 精确校验 editable install 路径
- CLAUDE.md 加 'Python 后端环境设置(强制)' 11 行引用段
- 关联:openspec/changes/setup-chatbiz-env/ (8 artifact)
EOF
)"`
- [ ] **Step 4.4:** `openspec archive setup-chatbiz-env --yes`(自动写
      archive/2026-06-16-setup-chatbiz-env/ + sync spec 到
      openspec/specs/dev-env-setup/spec.md)
- [ ] **Step 4.5:** `git add -A && git commit -m "chore(openspec):
      archive setup-chatbiz-env"`
- [ ] **Step 4.6:** `git push`(推 main)
- [ ] **Step 4.7:** `openspec list` 验证 `setup-chatbiz-env` 不在
      active list

---

## 验收条件(对应 design.md Migration Plan)

1. ✅ `bash tools/setup-chatbiz-env.sh --help` 输出 docstring head 30 行
2. ✅ `bash tools/setup-chatbiz-env.sh --check` 在 main 仓库路径下对
   4 service 中已装的服务报 [OK],未装的报 [FAIL] + 修复命令
3. ✅ `bash tools/setup-chatbiz-env.sh --service sso` 单独装 sso
4. ⏭️ `shellcheck tools/setup-chatbiz-env.sh` (本机无 shellcheck,skip)
5. ✅ CLAUDE.md "Python 后端环境设置(强制)" 段引用此 script
