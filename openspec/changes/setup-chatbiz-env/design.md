# setup-chatbiz-env — Design

## Context

ChatBiz 当前阶段为 pre-build,`docs/architecture.md` + `docs/prd.md` 已冻结,
eng-review 12 个工程决策(详见 design doc `## GSTACK REVIEW REPORT`)已 locked-in。
最近 4 周集中把 4 service (audit-and-isolation / credential / gateway-scanner /
sso) 推到 100% line cov + 接入 ci-cov workflow;13 个 openspec change 已全 archive。

memory [[conda-chatbiz-env]] 锁定了"Python 后端必须用 `chatbiz` conda env,禁止
anaconda3 base / uv" 的硬约束,但**当前没有脚本支撑这条约束** —— 新开发者入职时
是口头约定,没有 1-shot 自动化。ci-integration-cov-matrix retrospective 把
"setup-chatbiz-env + scaffold-cleanup" 列为 followup;scaffold-cleanup 部分经
摸底后确认是 0 work(没 openspec-specs-*.md 遗留、没 nested 空目录、`scripts/`
目录不存在),用户确认 scope 收窄为**只做 setup-chatbiz-env**。

`tools/` 目录已有 `check-compose-naming.sh` 单文件 shell script 作为同 pattern
参考(头部 docstring 写决策背景 + Usage + Exit codes,`set -euo pipefail`,
bash 4+ / macOS BSD awk 兼容)。本 change 沿用同模式,新增
`tools/setup-chatbiz-env.sh`。

4 service 的 `pyproject.toml` 经摸底全部走 PEP 621 + `setuptools.build_meta`,
**无 Poetry lock**:[project.dependencies] 走运行时, [project.optional-dependencies]
.dev 走 dev(测试 + lint)。Setup 行为因此简化为 `pip install -e ".[dev]"`,
**不需要** Poetry / uv / hatch 等额外工具。

## Goals / Non-Goals

**Goals:**
- 1 个 shell script(`tools/setup-chatbiz-env.sh`)自动装 `chatbiz` conda env
  (python 3.12) + 4 service 全部 dev deps
- 4 mode:`full` / `--check` / `--env-only` / `--service <name>`,覆盖新开发者
  入职 / CI pre-flight / 单 service 重装 3 个使用场景
- `--check` 干跑:不动 env,用 `pip show <pkg> | Location` 精确校验 4 service
  editable install 在 `services/<name>/` 实际路径(避免 import probe 假阳性)
- CLAUDE.md 加 1 段引用,指引新开发者跑这个 script
- 沿用 `tools/check-compose-naming.sh` 模式(同目录 / bash 4+ BSD awk 兼容 /
  头部 docstring / `set -euo pipefail` / `chmod +x` 后 git-tracked)

**Non-Goals:**
- 不引入 Makefile / taskipy / hatch(项目"零 build 框架"约束,见 CLAUDE.md
  "Commands" 段)
- 不装 workflow-engine / mcp 这 2 个 0% cov service 的 deps(等它们收尾时再扩,
  YAGNI 原则;CI 触发约定 matrix = `[audit-and-isolation, credential,
  gateway-scanner, sso]` 锁定)
- 不做 env 卸载 / 重建 / 升级
- 不处理 conda 自身安装(假设 `conda` 已在 PATH)
- 不替代 `docs/architecture.md` / `docs/prd.md` 的任何内容

## Decisions

### D1: 单文件 shell script(沿用 `tools/check-compose-naming.sh` 模式)

- **选择**:`tools/setup-chatbiz-env.sh`,chmod +x,git-tracked,沿用既有
  `tools/` 模式
- **理由**:仓库现状无 Makefile / root pyproject.toml(CLAUDE.md "Commands" 段
  明说"没有 build / lint / test 命令"),为 1 个 setup script 引入框架破例
  跟"零 build 框架"约定冲突;同 `tools/` 目录下 `check-compose-naming.sh` 已经
  证明这种模式 work
- **已考虑 alternative**:
  - Makefile 包装 — 拒绝,理由同上
  - root `pyproject.toml` + `[tool.taskipy]` — 拒绝,仓库无 root pyproject.toml
  - `hatch env create` — 拒绝,hatch 是 build tool 且跟"必须用 conda"锁定冲突

### D2: 4 service 全部走 `pip install -e ".[dev]"`(无 Poetry 分支)

- **选择**:脚本不检测 Poetry lock,统一 `pip install -e ".[dev]"`
- **理由**:摸底 4 service pyproject 后确认**全部**走 PEP 621 +
  `setuptools.build_meta`,无 Poetry.lock / pyproject.toml [tool.poetry.*]
  段。引入"双 mode 检测"是 YAGNI
- **已考虑 alternative**:
  - 检测 `[tool.poetry]` 段,有则 `poetry install` — 拒绝,4 service 都没 Poetry 段
  - 检测 Poetry.lock 文件存在 — 拒绝,同上

### D3: `--check` 用 `pip show <pkg> | Location` 校验(不用 import probe)

- **选择**:`pip show <pkg-name> | awk '/^Location:/ {print $2}'` 跟
  `services/<name>/` 实际路径精确比对
- **理由**:本机 chatbiz env 当前装 4 service 中只 2 个(audit-and-isolation /
  gateway-scanner) + 2 个额外(workflow-engine / mcp)。`import jose` /
  `import cryptography` / `import rich` 都被已装 service 共享 deps 满足,
  即使 sso / credential 没装,import probe 也会假阳性报 [OK]。`pip show`
  + `Location` 字段跟 `services/<name>/` 路径精确比对,**worktree 路径 ≠
  main 路径** 就会 FAIL — 这是正确信号("this service 还没在这个
  worktree 装,跑 `--service <name>` 装")
- **已考虑 alternative**:
  - `import jose` 等 import probe — 拒绝,假阳性
  - `pip list | grep <pkg>` — 拒绝,只查存在性,不查路径

### D4: `--check` 模式不调 `pip install --upgrade`(严格干跑)

- **选择**:`MODE == "check"` 时,跳过 `pip install --upgrade pip wheel setuptools`
- **理由**:干跑的本意是"不动 env",包括不动 pip 自身
- **已考虑 alternative**:
  - 干跑时只跳过 service deps install,仍 upgrade pip — 拒绝,跟"干跑"语义冲突

### D5: env name 写死为 `chatbiz`

- **选择**:脚本内 `ENV_NAME="chatbiz"`,无 `--env-name` flag
- **理由**:跟 memory[[conda-chatbiz-env]] 锁定一致;本仓库没理由多 env
- **已考虑 alternative**:
  - `--env-name <name>` 参数化 — 拒绝,YAGNI

### D6: 不动 workflow-engine / mcp 的 deps 安装

- **选择**:`SERVICES=(audit-and-isolation credential gateway-scanner sso)`,
  不含 workflow-engine / mcp
- **理由**:CI 触发约定 matrix = `[audit-and-isolation, credential, gateway-scanner,
  sso]` 锁定(CLAUDE.md "CI 触发约定(强制)" 段),这 2 个 service 仍 0% cov,
  本约定未触发。等它们收尾时再扩
- **已考虑 alternative**:
  - 一次性装 6 service 全 deps — 拒绝,YAGNI,且这 2 service 的 pyproject 格式
    跟 4 service 也不一定一致(需额外摸底)

## Risks / Trade-offs

- [Risk] `pip show` 拿 Location 在 macOS / Linux 路径大小写敏感下可能 mismatch →
  Mitigation: 用 `[ "$location" = "$svc_dir" ]` 严格等比,失败就报 [FAIL] 让用户
  重跑 `--service <name>` 装
- [Risk] `conda run -n <env>` 在某些 conda 版本(老于 4.6)不支持 → Mitigation:
  `conda info --base` 拿 base 路径 + source `etc/profile.d/conda.sh` 是兜底;
  本仓库假设 conda 4.6+(2026 年标配)
- [Trade-off] `--check` 在 worktree 里跑会 FAIL 即使主 env 装好 → 接受:这是
  "worktree 是隔离开发环境" 的正确信号,不是 bug;CLAUDE.md 引用段会说明
- [Trade-off] 脚本不检测 conda env 里 service 的 deps 版本漂移(只查 editable
  install 路径) → 接受:版本漂移是 pyproject.toml + 锁文件的事,跟 setup
  script 职责分离

## Migration Plan

**N/A — 本 change 不涉及部署 / DB / endpoint 变更**,只新增 1 个
git-tracked shell script + 改 CLAUDE.md 1 段。Rollback 策略:删除
`tools/setup-chatbiz-env.sh` + revert CLAUDE.md 那 1 段(2 个 hunk)。

**验收条件**(apply 阶段):
1. `bash tools/setup-chatbiz-env.sh --help` 输出 docstring head 30 行
2. `bash tools/setup-chatbiz-env.sh --check` 在 main 仓库路径下对 4 service
   中已装的服务报 [OK],未装的报 [FAIL] + 修复命令
3. `bash tools/setup-chatbiz-env.sh --service sso` 单独装 sso,5 分钟内完成
4. `shellcheck tools/setup-chatbiz-env.sh`(如本机有装)无 ERROR
5. CLAUDE.md "Python 后端环境设置(强制)" 段引用此 script

## Open Questions

无。本 change 范围已收敛,所有决策已锁定。
