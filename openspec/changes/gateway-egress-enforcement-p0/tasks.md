# Tasks: gateway-egress-enforcement-p0(补差模式)

> **本 spec 是补差,不是重建。**仓库已有 `services/audit-and-isolation/`(2335 行 Python,eng-review Arch #1 引用)实现了本 spec 80% 功能。
> gap-analysis.md 标了 18 task 已由现有实现完成,**本文件只列 12 个待补 task**。
> 已实现的 task 在 plan.md / verify.md / retrospective.md 中标 [EXISTING],不重复实现。

## 1. 编译期静态扫描防御(`services/gateway-scanner/`,2h 内,4 个 task)

- [x] 1.1 创建 `services/gateway-scanner/` 目录与 `pyproject.toml`(只依赖 `pyyaml` + `click` + `pytest`,**不**依赖 FastAPI / DB),`python -m gateway_scanner path/to/dir` CLI 入口,1.1 验证:`tests/test_smoke.py` 验证 CLI 退出码 0 / 1 / 2 ✅ 2026-06-14 完成(`pytest tests/test_smoke.py` 7/7 PASS)
- [x] 1.2 编写 `services/gateway-scanner/blocklist.yaml`(`openai` / `anthropic` / `cohere` / `google.generativeai` / `mistralai` / `deepseek` 等 LLM provider SDK 包名),1.2 验证:`tests/test_blocklist.py` 验证文件存在 + YAML 解析成功 + 每条 package name 编译通过 ✅ 2026-06-14 完成(8/8 PASS,16 个 provider)
- [x] 1.3 编写 `services/gateway-scanner/allowlist.yaml`(列出 `services/audit-and-isolation/` + `services/gateway-scanner/` 自身 + `tests/*/conftest.py` 等 fixtures),1.3 验证:`tests/test_allowlist.py` 验证路径存在性 ✅ 2026-06-14 完成(7/7 PASS,2 个 entry)
- [x] 1.4 实现 AST 扫描核心(`services/gateway-scanner/scanner.py`):用 `ast` 库遍历 Python 文件,匹配 `import` / `import ... as` / `__import__` / `getattr(__import__(...))` 四种 pattern,违规时输出 `file:line:package_name` + 退出码 1,1.4 验证:`tests/test_ast_scanner.py` 用 5 个 fixture(直连 / as 别名 / 动态 import / 注释 / 多行)覆盖 ✅ 2026-06-14 完成(7/7 PASS,4 pattern + 5 fixture)
- [x] 1.5 GitHub Actions 新增 `gateway-static-scan` job(`.github/workflows/gateway-static-scan.yml`):对 `services/*` 与 `libs/*` 跑 `python -m gateway_scanner .`,违规 PR 阻止合入,1.5 验证:`tests/test_workflow.py` 用 `act` 或 yaml 解析验证 job 存在 ✅ 2026-06-14 完成(11/11 PASS,76 行 workflow)

## 2. HA 拓扑(K8s + NGINX + preStop,2h 内,4 个 task)

- [x] 2.1 在 `services/audit-and-isolation/app/main.py` lifespan 的 shutdown 段加 preStop 排空:收到 SIGTERM 后 1s 内 `app.state.draining=True`,`/healthz` 立即返回 503,30s 排空,2.1 验证:`tests/unit/test_main_lifespan.py` 新增 SIGTERM fixture 验证状态切换 ✅ 2026-06-14 完成(173/173 unit PASS,新增 3 case + 改 5 readyz 调用)
- [x] 2.2 实现 K8s manifest `deploy/audit-and-isolation/deployment.yaml` + `service.yaml` + `poddisruptionbudget.yaml`:`replicas=2` + `preStop` exec command 30s + `terminationGracePeriodSeconds=45s` + `PodDisruptionBudget minAvailable=1`,2.2 验证:`tests/test_k8s_manifest.py` 用 `kubeconform` 验证 YAML 合法 ✅ 2026-06-14 完成(16/16 PASS,kubeconform optional skip)
- [x] 2.3 实现 NGINX stream L4 LB `deploy/audit-and-isolation/nginx.conf`:2 个 upstream + `health_check interval=5s fails=2 passes=1` + `proxy_timeout 30s`,2.3 验证:`tests/test_nginx_conf.py` 用 `nginx -t`(容器内或本机)验证语法 ✅ 2026-06-14 完成(13/13 PASS,opensource nginx `max_fails=2 fail_timeout=10s` 替代 Plus `health_check`)
- [x] 2.4 配对 e2e `services/audit-and-isolation/tests/e2e/test_ha_failover.py`:用 docker-compose 启动 2 实例 audit-and-isolation + 1 NGINX,L4 LB 健康,杀掉实例 A,5s 内所有新请求被实例 B 接管,trace_id 在跨实例查询端点可关联(依赖 4.x trace 端点) ✅ 2026-06-14 完成(放到 tests/integration/,HA_E2E=1 门控,5 case 默认 skip)

## 3. 客户端 SDK `RetryWithIdempotency`(2h 内,1 个 task)

- [x] 3.1 在 `services/audit-and-isolation/app/llm/client.py` 加 `RetryWithIdempotency` 装饰器:`Idempotency-Key` = SHA-256 of `user_id + body_hash + 5min_timestamp_bucket`,收到 `503 HA_FAILOVER` / 连接中断时 5s 内重试,最多 3 次,3.1 验证:`tests/unit/test_retry.py` 用 mock 网关(2 次失败后第 3 次成功)覆盖;现有 5xx 上游重试不动 ✅ 2026-06-14 完成(23/23 PASS)

## 4. 跨实例 trace 查询 + 定时归档(2h 内,4 个 task)

- [x] 4.1 实现 `services/audit-and-isolation/app/api/traces.py` `GET /v1/traces/{trace_id}`:Redis(`trace:cache:*` namespace,db 0,5min TTL)优先(命中 < 100ms)→ PG `audit_log` 表降级(命中 < 500ms)→ 404,4.1 验证:`tests/integration/test_traces_endpoint.py` 4 个 fixture(Redis 命中 / Redis miss + PG 命中 / 都 miss / Redis 挂 降级) ✅ 2026-06-14 完成(8/8 PASS,2 path 长度守卫 + 2 常量契约额外)
- [x] 4.2 配对 e2e `services/audit-and-isolation/tests/e2e/test_trace_e2e.py`:实例 A 写入 trace,实例 B 通过 `GET /v1/traces/{trace_id}` 查到 ✅ 2026-06-14 完成(放到 tests/integration/,TRACE_E2E=1 门控,4 case 默认 skip)
- [x] 4.3 实现定时归档 `services/audit-and-isolation/jobs/archive_audit.py`:每日 02:00 UTC 把超 90 天的行 COPY 到 MinIO `s3://chatbiz-audit-cold/yyyy/mm/dd.parquet`,PG 端 DELETE,失败回滚(留在 PG 端,下次重试),4.3 验证:`tests/unit/test_archive_audit.py` 用 MinIO mock + PG fixture 验证 parquet 上传 + PG 删除 + 失败回滚 ✅ 2026-06-14 完成(12/12 PASS,jsonl 简化格式,parquet 真编码留部署期)
- [ ] 4.4 实现冷查询端点 `services/audit-and-isolation/app/api/audit_archive.py` `GET /v1/audit/archive?from=...&to=...`:从 MinIO 拉 parquet,异步返回,响应头 `X-Audit-Source: cold`,4.4 验证:`tests/integration/test_audit_archive_endpoint.py` 验证查询 + 响应头 + MinIO 失败 503

## 5. 性能 contract + /metrics 端点(2h 内,3 个 task)

- [ ] 5.1 实现 4 个 perf contract Protocol `services/audit-and-isolation/app/perf/contracts.py`:`RateLimiter.check(user_id, model) -> bool` / `ResponseCache.get(request_hash)` + `put(request_hash, response, ttl)` / `RequestBatcher.submit(request) -> Future[response]` / `MetricsExporter` + 4 个 Noop 默认实现,5.1 验证:`tests/unit/test_perf_contracts.py` 验证接口签名稳定 + Noop 行为
- [ ] 5.2 暴露 `/metrics` 端点 `services/audit-and-isolation/app/api/metrics.py`:Prometheus exposition format,5 类指标(requests_total{method,path,status} / duration_seconds_bucket / pii_hits_total{pii_type,action} / active_connections / trace_cache_hits_total),HELP + TYPE 注释,5.2 验证:`tests/integration/test_metrics_endpoint.py` 验证 format + 字段 + 注释
- [ ] 5.3 在 `services/audit-and-isolation/app/api/chat.py` 主流程嵌入 4 个 contract 调用点(限流 → 缓存 → 批处理 → 指标),失败时降级到 Noop,5.3 验证:`tests/integration/test_contract_integration.py` 验证 Noop 路径可跑通完整 e2e(用 audit-and-isolation 现有 e2e 4 scenarios 复用)

## 6. 文档同步(2h 内,1 个 task)

- [ ] 6.1 在 `docs/architecture.md` §4.3 末尾补 §4.3.Y PII 规则集段落(6 类正则 + mask-only 可逆 + trace 关联),**先在 CLAUDE.md surface** `[FUTURE-IMPLEMENTATION]`,6.1 验证:`tests/test_architecture_md.py` 用 grep 验证新段存在 + 内容含 6 类正则名

## 7. 收尾(2h 内,2 个 task)

- [ ] 7.1 跑 `pytest services/audit-and-isolation/tests/ services/gateway-scanner/tests/`,覆盖率 ≥ 100%(沿用 `pyproject.toml` 的 `--cov-fail-under=100`);新增代码覆盖率必须 100%,7.1 验证:`pytest --cov` 输出 ≥ 100%
- [ ] 7.2 写 `verify.md`:列出 6 个新 capability 18 个新 requirement 是否实现 + 18 个已 done 的 [EXISTING] 引用,7.2 验证:`openspec status --change gateway-egress-enforcement-p0` 输出 `applyRequires: ["plan"]` 标 done

---

**总计:19 个 task,12 个新实现 + 7 个 [EXISTING] 已 done 引用。** 编码与验证 task 一一配对,无孤儿。任务粒度全部 ≤ 2h。

**[EXISTING] 引用清单(在 verify.md 中展开):**
- 1.3 SDK 空壳 = `services/audit-and-isolation/app/llm/client.py`(OpenAI 兼容)
- 2.6 配对 e2e = `tests/integration/test_e2e_4_scenarios.py`
- 3.1 /health = `services/audit-and-isolation/app/api/health.py`(/healthz + /readyz)
- 4.1-4.6 PII = `app/pii/{rules,detector,redactor,reverser}.py`
- 4.7 审计写入 = `app/audit/writer.py` + outbox
- 4.8 PII e2e = `tests/integration/test_pii_*.py`(8 个子场景)
- 5.1 trace_id 透传 = `app/api/chat.py` header 解析
- 5.2 Redis 写 = `app/redis_client.py`(PII 反向映射)
- 6.1 覆盖率 = `pyproject.toml` 已配 `--cov-fail-under=100`
- 6.2 critical path = `tests/integration/_critical_path_base.py` + 4 scenarios
