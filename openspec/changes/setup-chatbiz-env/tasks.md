# Tasks: setup-chatbiz-env

> 关联 spec:`specs/dev-env-setup/spec.md`
> 关联 design:`design.md`
> 任务粒度:每条 ≤ 2h;编码任务配对验证任务

## 1. setup-chatbiz-env.sh 脚本本体

- [ ] 1.1 在 `tools/setup-chatbiz-env.sh` 写完 4 mode 主体(`full` / `--check` /
      `--env-only` / `--service <name>`),沿用 `tools/check-compose-naming.sh`
      模式(`set -euo pipefail` / 头部 docstring / bash 4+ / macOS BSD awk 兼容)
- [ ] 1.2 chmod +x `tools/setup-chatbiz-env.sh` 并提交到 git
- [ ] 1.3 跑 `bash tools/setup-chatbiz-env.sh --help` 验证 docstring head 30 行
      正常输出(验证任务,配对 1.1)
- [ ] 1.4 跑 `bash tools/setup-chatbiz-env.sh --check` 在本机 main 仓库路径下
      验证 4 service editable install 状态,期望 audit-and-isolation /
      gateway-scanner → [OK],credential / sso → [FAIL] + 修复命令(验证任务,
      配对 1.1)
- [ ] 1.5 (可选)用 `shellcheck tools/setup-chatbiz-env.sh` 验证无 ERROR;
      本机如无装则 skip(本机为 `darwin` 默认无 shellcheck)

## 2. CLAUDE.md 引用段

- [ ] 2.1 在 `CLAUDE.md` 已有"CI 触发约定(强制)" 段后插入
      `### Python 后端环境设置(强制)` 段,引用 `tools/setup-chatbiz-env.sh` +
      memory `[[conda-chatbiz-env]]` + 3 个常见用法
- [ ] 2.2 用 `git diff CLAUDE.md` 验证只 +1 段、不动其它段(验证任务,配对 2.1)

## 3. apply 收尾

- [ ] 3.1 `git add tools/setup-chatbiz-env.sh CLAUDE.md
      openspec/changes/setup-chatbiz-env/`
- [ ] 3.2 `git commit -m "feat(tools): add setup-chatbiz-env.sh + CLAUDE.md
      引用段"` 提交(用本仓库 commit message 风格:`feat(...)` 前缀)
- [ ] 3.3 跑 `openspec archive setup-chatbiz-env --yes` 把 change 移到 archive
      + spec 同步到 `openspec/specs/dev-env-setup/spec.md`
- [ ] 3.4 `git add -A && git commit -m "chore(openspec): archive
      setup-chatbiz-env"` archive commit
- [ ] 3.5 `git push` 推 main(本任务不开 PR,按本仓库 13 commits 的归档 pattern)
- [ ] 3.6 跑 `openspec list` 确认 `setup-chatbiz-env` 不在 active list(验证任务,
      配对 3.5)

## 规范校验清单(apply 时逐项过)

- [ ] 跟 memory `[[conda-chatbiz-env]]` 一致(env name = `chatbiz`,禁止 base / uv)
- [ ] 跟 `tools/check-compose-naming.sh` pattern 一致(bash 4+ / BSD awk 兼容 /
      `set -euo pipefail` / 头部 docstring)
- [ ] 4 service 列表 = ci-cov matrix `[audit-and-isolation, credential,
      gateway-scanner, sso]`,不含 workflow-engine / mcp
- [ ] 无新增 build 框架(无 Makefile / pyproject.toml / hatch / poetry)
- [ ] 无 `--cov-fail-under=100` 改动(本脚本是 dev tooling,不走 ci-cov)
- [ ] 无 docker-compose / GitHub workflow / 端口表改动

## 安全校验清单(apply 时逐项过)

- [ ] `--check` 模式不调任何 state-modifying 命令(`pip install` /
      `pip upgrade` / `conda create`)
- [ ] 脚本不假设 `sudo`,所有操作限于 conda env + 当前用户 `pip`
- [ ] 头部 docstring 不写任何 secret / token / 内部 IP
- [ ] chmod +x 后 git-tracked,无 `+x` 后门(`git ls-files -s` 验证)
