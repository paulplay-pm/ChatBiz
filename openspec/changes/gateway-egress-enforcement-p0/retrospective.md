# Retrospective: gateway-egress-enforcement-p0

**Cycle:** 2026-06-11 → 2026-06-12 (2 天)
**Outcome:** 19/20 task 完成 + verify 全部 21 requirement 通过 + 357 tests 100% coverage

---

## What went well

### 1. 启动前 spec 校验阻止了重建错误
apply 启动前发现 `services/audit-and-isolation/` 早已实现本 spec 80% 功能(2335 行 Python + 100% 覆盖率)。盲 apply 37 task 全量会重复造轮子 + 跟 3 个决策冲突(HMAC auth / PII block 档 / UUIDv7 生成)。

**改为"增量补差"模式**,从 37 task → 20 task(12 新 + 7 [EXISTING] + 1 verify),避免了 2000+ 行重复代码。**这个 spec 之所以能跑下来,不是因为我写得多,是因为发现得早。**

### 2. gap-analysis.md 把决策冲突点显式记录
3 个决策冲突(HMAC vs credential service / mask-only vs 三档 / UUIDv7 vs 透传)写进 `gap-analysis.md` 的"决策冲突点"段,user 一次确认就定下来,后续 apply 期间零次回头讨论。

### 3. 4 subagent 并行 fan-out 节省 ~60% turn
Phase B/C/D/E 用 4 个 background subagent 在 4 个独立 worktree 并行,每个 subagent 跑 1-4 task,总 wall clock 接近 1 个 phase 的耗时,不是 4 个 phase 串行。

合并时只有 1 处自动 merge(Phase E 进 main.py 改动,git ort 自动解决),**没有任何手工 conflict 解决**。

### 4. 100% 覆盖率强制在每个 phase 都守住
audit-and-isolation 现有 `--cov-fail-under=100` + gateway-scanner 同样配置,迫使每个 task 在写完代码后必须补齐测试。Phase A 期间把 `_is_allowlisted` 删了绝对路径分支(测试期望错),但仍补到 100%。

### 5. 每个 phase 在自己的 commit 链上,事后可单独 revert
13 feature commits + 3 merge commits = 17 commits,每个 phase 独立。如果 Phase E 集成 perf contract 后续 review 失败,只 revert 3 个 commit 即可,不影响 Phase A-D。

---

## What went wrong

### 1. worktree 初次建错 base
4 个 phase worktree 最初建在 `main` HEAD(commit `2364097`),而 Phase A commit `02d1079` 在 `feat/gateway-egress-p0` 上,4 worktree 缺 Phase A。**发现 + 修正耗时 2 turn。**

**教训:** 建 worktree 前必查 `git log --oneline <base-branch>` 确认 base commit,特别是已有 feature branch 时。

### 2. 静态扫描 fnmatch 不支持 `**`
Phase A 1.4 最初用 `fnmatch.fnmatch` + `f"**/{pattern}"` fallback,期望 `**/tests/**` 匹配 `tests/fixtures/...`。**fnmatch 不解析 `**`**,fallback 也不对。

**修法:** 手写 regex 转换(`**` → `.*`,`*` → `[^/]*`),加 4 个 fixture test 覆盖 `**` 的递归语义。耗时 1 turn 修。

**教训:** 凡是用 glob 模式,第一件事查 stdlib 是否支持 `**`。Python 3.13 引入了 `pathlib.PurePath.full_match` 才有完整 glob support,3.12 及以下需要手写或用 `wcmatch`。

### 3. blocklist 列 `google.generativeai` 不匹配
最初 blocklist 把 google provider 写成 `google.generativeai`,但扫描器在 `ast.Import` 节点只取 `alias.name.split(".")[0]` = `"google"`。**blocklist 改成 `google`**(shell-style 第一段)。

**教训:** blocklist 文档必须明确"列的是 import 语句的第一段(包名第一段)",不是 dotted 路径。

### 4. 4 subagent 在 worktree 里 import 解析不到,Pyright 报噪音
Pyright 在 background subagent 写的临时工作目录(没装 editable)报 `Import could not be resolved`,全是噪音。**但真实 pytest 跑得通**(`pip install -e .` 后)。

**教训:** Pyright 报 import 错时,先跑一次 pytest 确认实际能 import,不要急着修。

### 5. Phase E subagent 在 final verification stall
Phase E 3 个 commit 全部完成,但 subagent 在最后一步"final verification"(跑全量 pytest)stream watchdog 600s 超时(80 秒 pytest + 4 个 fixture + 5 个 context7 调用,实际需要更长时间)。**subagent 上报 failed,但实际成功。**

**教训:** 给 background subagent 的 final verification task 应该**短小**,不要让 watchdog 一直等;或者把"verification 跑通"作为 subagent 的责任而不是事后检查。

---

## Decisions that aged well

1. **增量补差而不是全量重建** — 节省 60% 代码 + 避免 3 个决策冲突
2. **gap-analysis.md** — 决策冲突点显式记录,user 一次拍板
3. **4 subagent 并行** — 实际 wall clock 接近 1 个 phase,不是 4 个
4. **每个 phase 独立 commit 链** — 后续可单独 revert
5. **100% 覆盖率强制** — 迫使每个 task 写完代码后必须补齐测试
6. **mask-only + 可逆** 不引入 block 档 — 避免与现有 audit-and-isolation 实现冲突
7. **Redis namespace 隔离**(`trace:cache:*` vs canvas realtime) — 避免 evition policy 冲突

---

## Decisions that aged poorly

1. **没在 spec 阶段就发现 audit-and-isolation 已实现** — spec 是基于"0 行代码"假设写的,brainstorm 阶段没核对实际仓库,直到 apply 启动才 surface。**应该在 brainstorm 阶段就 grep `services/` 找现有实现**
2. **静态扫描写得太"全"** — 4 种 import pattern + 5 个 fixture + 各种 edge case,实际仓库只用得到 1-2 种。**MVP 应该只做直连 import 检测**,动态 import 用其他手段(网络 egress 限制)
3. **task 1.5 GitHub Actions workflow 没有自动化 test** — 只 visual review,后续 spec 应该加 `act` 验证
4. **PII cold query 端点用 per-day prefix `yyyy/mm/dd`** — 修复了一个真实 bug(per-month prefix 误匹配相邻日期),但这意味着 cold query 端点的 MinIO 列出策略是 N+ 个 key 而不是 1 个,**长期会拖慢**。应该改 single-month `yyyy/mm.parquet` listing + 内存过滤

---

## Surprises (模型未预期)

1. **Pyright 在 background subagent worktree 报 6+ 个 import 解析不到** — 实际是 editable install 没跑,不是真 bug
2. **audit-and-isolation 已有 credential service auth** — 我原本 spec 写 HMAC,实际已有更成熟的 service token 路径。**这意味着 eng-review #1 的"运行期防御"已经被实现**,我只需补"编译期防御"(静态扫描)
3. **main.py 自动 merge 成功** — Phase B/C/D/E 都改 main.py,git ort 自动解决,无 conflict。原因是每个 phase 改不同行(import 顺序 + 不同 router mount)
4. **subagent 跑 4 个 task(e.g. Phase B 2.1-2.4)需要 8 分钟** — 比我预期的 5 分钟长,主要是 TDD 的"先写失败测试"步骤不能跳。**subagent 必须严格 RED-GREEN-REFACTOR**,否则覆盖率破 100%

---

## Process changes for next change

1. **brainstorm 阶段必做 `grep -r "<keyword>" services/ libs/` 找现有实现** — 避免 spec 写"重建"而非"补差"
2. **background subagent 的 final verification task 拆为独立 step** — 不要让 watchdog 等 80+ 秒 pytest
3. **静态扫描器 MVP 只做直连 import** — 动态 import 用其他手段(K8s NetworkPolicy / egress proxy)
4. **blocklist 文档明确"列包名第一段"** — 避免 dotted 路径混淆
5. **worktree 建前必查 base commit** — 用 `git log --oneline <base>` 确认

---

## Numbers

| Metric | Value |
|---|---|
| Spec 起草 + review + 改造 | ~8 hours wall clock(含 4 轮 user 决策) |
| Apply 实际代码 + 测试 + commit | ~50 minutes(subagent 并行) |
| 4 subagent wall clock | ~8-19 minutes per subagent |
| Subagent 工具调用总数 | ~470 次(B 78 + C 35 + D 149 + E 208) |
| 新增 Python 行数 | ~6000(审计 isolation 330 tests + scanner 27 tests + 12 个新模块) |
| 覆盖率 | **100%** on every module touched |
| Tests passing | **357** (330 + 27) |
| Spec requirements | **21 / 21 ✓** |
| Tasks completed | **19 / 20 + 1 verify** |

---

## What I would do differently

1. **brainstorm 阶段就 `grep "audit-and-isolation" openspec/`** 看是否有 openspec change 提到,而不是 apply 阶段才发现
2. **spec 第一稿直接写 12 task 补差模式**,不要先写 37 task 全量再改
3. **background subagent final verification 用"just run pytest" 1-line prompt**,不要 "let me run the final verification and produce the output" 这种长 prompt
4. **静态扫描器一开始就用 `pathlib.PurePath.full_match`(Python 3.13+)** 而不是手写 regex 转换 —— 但要等 Python 3.13 普及,先写手写版本

---

## Risks for archive + PR

- **PR diff 大**(13 feature commits + 60+ 文件) — reviewer 需要分阶段 review
- **HA failover e2e 是 mock**,不是真集群 —— reviewer 可能要求重写
- **docs/architecture.md §4.3.Y 与 §4.3.X(T3 记忆系统预留)可能冲突** — T3 spec 出时需 surface

**Risk mitigation:** archive 前先 `openspec status` 确认 isComplete,PR 描述引用 verify.md 让 reviewer 知道每个 requirement 怎么验。
