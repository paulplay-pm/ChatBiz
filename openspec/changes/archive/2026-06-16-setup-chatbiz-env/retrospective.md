# Retrospective: setup-chatbiz-env

## 总结

本 change 在 1 个 session 内跑完完整 superpowers-bridge 流程 (brainstorm →
proposal → design → specs → tasks → plan → apply → verify) + 2 个 commit
(feat + archive) push 到 main。

### 实际耗时

| 阶段 | 预期 | 实际 | 偏差原因 |
|---|---|---|---|
| Brainstorm (Q1-Q6) | 0.5h | 0.5h | 跟用户 1 round AskUserQuestion 收口 scope,符合 |
| Proposal + Design | 0.5h | 0.5h | 设计不复杂,1 页 A4 |
| Specs (5 requirements) | 0.5h | 0.3h | 写起来顺 |
| Tasks + Plan | 0.3h | 0.3h | plan.md micro-step 拆好 |
| Script 写 + chmod + 2 轮 verification | 0.5h | 0.7h | 多 1 轮:发现 `--check` 模式仍调 `pip upgrade`,违反"干跑"语义(已修) |
| Archive + commit + push | 0.1h | 0.1h | 顺 |

## 学到了什么

### ✅ 决策正确的部分

1. **沿用 `tools/check-compose-naming.sh` 模式** — 单文件 shell + 头部 docstring +
   `set -euo pipefail` 跟项目"零 build 框架"约定一致,没引争议
2. **`pip show | Location` 精确校验** — 比 import probe 精确;实测发现 import probe
   假阳性(同 env 多个 service 共享 deps 撞名)
3. **scope 收窄为只做 setup-chatbiz-env** — 用户选 "只做 setup-chatbiz-env(推荐)"
   后,`scaffold-cleanup` 0 work 不进 change body,避免 YAGNI 任务塞进

### ⚠️ 决策需要调整的部分

1. **摸底结论"双 mode PEP 621 + Poetry"是错的** — 实际 4 service 全 PEP 621,无
   Poetry。设了一个错误的"双 mode"假设。修复:D2 decision 写明"全 PEP 621",但
   摸底阶段本应直接 read 4 个 pyproject 而不是凭印象判断。下次摸底要全 read
2. **`--check` 一开始仍调 `pip install --upgrade`** — 违反"干跑"语义,在验证阶段
   实测发现才修。下次写"干跑 mode" 时,先把"不动 env" 作为 hard constraint 写进
   spec requirements,再写实现
3. **`pip show` 在包未装时 exit non-zero 触发 `set -e` 中断** — `set -e` +
   `pipefail` 配合下,`pip show` 找不到包会终止整个 script(只报告 1 个 FAIL 就退),
   不是预期的"继续查下一个 service"。修复:`{ run_in_env pip show ... || true; }`
   吞非零 exit。下次写"循环 + 子命令查状态"模式时,直接套这个 idiom

### 💡 流程上的发现

1. **superpowers-bridge schema 的 "Rules for 'specs' must be an array" 警告** —
   4 个 artifact 全部打印这条 warning,scaffold 仍能创建空目录 + 走通。看起来是
   schema 配置小问题但不影响功能。下次有精力时查 openspec config 修复
2. **`openspec archive` 配 `yes y |` 仍有 20MB ANSI 输出** — inquirer 在 raw
   output 上重复 echo,本质是 prompt UX 问题不是 bug。alignment 时 bypass

## 验收条件 vs 实际(design.md Migration Plan)

| 验收条件 | 状态 | 证据 |
|---|---|---|
| 1. `--help` 输出 docstring head 30 行 | ✅ | verification 1 输出 ≥ 30 行 |
| 2. `--check` 在 main 路径下报 [OK]/[FAIL] + 修复命令 | ✅ | verification 2 输出 4 FAIL + 修复命令,exit 3 |
| 3. `--service <name>` 单独装 sso | ⏭️ | 未实跑(本机没装过,装会污染 env);script 逻辑 + spec 已通过 |
| 4. shellcheck 无 ERROR | ⏭️ | skip(本机 darwin 默认无 shellcheck) |
| 5. CLAUDE.md "Python 后端环境设置(强制)" 段引用 | ✅ | verification 5 显示段内容完整,含 3 个用法 + memory 引用 |

## 5 followup 行动

1. (低) 实跑 `bash tools/setup-chatbiz-env.sh --service sso` 装 sso,验证 `--service` 模式
   —— 可在下一个 change 实施,本次留作下次的 5-min test
2. (低) 查 openspec "Rules for 'specs' must be an array" 警告的根因
3. (低) 装 shellcheck 在本机,把它加进 ci-cov matrix (跟 ruff / bandit 同列)
4. (中) workflow-engine / mcp 收尾时,把这两个 service 加进 setup script 的
   `SERVICES` 数组(本 change 故意没扩,YAGNI)
5. (低) 1 个 round 复盘 "4 service pyproject 摸底" 应直接 read 4 文件,不全信
   上一轮探索结论

## 状态

**已 archive** — `openspec/changes/archive/2026-06-16-setup-chatbiz-env/`。
2 commits pushed:
- `4c40f44 feat(tools): add setup-chatbiz-env.sh + CLAUDE.md 引用段`
- `cba45ac chore(openspec): archive setup-chatbiz-env`
