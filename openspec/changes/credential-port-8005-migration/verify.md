# Verification Report

> 此檔案由 `openspec-verify-change` skill 在 apply 完成後產生。

**Change**: `credential-port-8005-migration`
**Verified at**: TBD
**Verifier**: TBD

---

## 1. Structural Validation

- [ ] 本 change `credential-port-8005-migration` `"valid": true`

---

## 2. Task Completion

- [ ] 所有 `- [ ]` 已变为 `- [x]`

---

## 3. credential host port 8000 → 8005

- [ ] `infrastructure/docker-compose.yml` `credential.ports` 改 `"8005:8000"`
  - 命令：`grep -n "8005:8000" infrastructure/docker-compose.yml` 输出 1
- [ ] `infrastructure/README.md` 改 `localhost:8005`
  - 命令：`grep -n "localhost:8000" infrastructure/README.md` 输出 0
- [ ] `services/credential/locust/locustfile.py` 改 `--host http://localhost:8005`
  - 命令：`grep -n "host http://localhost:8005" services/credential/locust/locustfile.py` 输出 1

---

## 4. CLAUDE.md 端口表

- [ ] 8000 行标"已迁移到 8005 (2026-06-13)" + 备注
  - 命令：`grep "已迁移" CLAUDE.md` 输出 ≥1
- [ ] 8005 行新增 "credential" / "已分配"
  - 命令：`grep "^\| 8005 \|" CLAUDE.md` 输出含"credential"

---

## 5. 端到端 7-service up

- [ ] 干净 dev 机 `docker compose -p chatbiz down -v && docker compose -p chatbiz up --wait` 5min
- [ ] `docker compose -p chatbiz ps` 7 service 全 healthy
- [ ] `curl http://localhost:8005/healthz` 200（credential 新 host port）
- [ ] `curl http://localhost:8080/healthz` 200（audit-and-isolation）
- [ ] `curl http://localhost:8001/healthz` 200（workflow-engine）

---

## 6. inter-service 链路

- [ ] audit-and-isolation 容器日志不含 "credential service unavailable"
- [ ] workflow-engine 容器日志不含 "credential service unavailable"

---

## 7. README 同步

- [ ] `web/integration-tests/README.md` Known Issues #4 标"已修（`credential-port-8005-migration` change merged 后）"

---

## 8. eng-review 决策对齐

- [ ] **Test #1** 3 层测试金字塔：本 change 解阻塞 7-service 端到端
- [ ] **Test #2** 4 critical path：解阻塞 ① paul 完整链路

---

## 9. openspec/config.yaml §apply.rules 触发

- [ ] "MUST: 端口从 CLAUDE.md 端口分配表选用" — 满足 (8005 标"未来")
- [ ] "MUST: 服务容器在 production compose 注册" — 满足 (改的就是该文件)
- [ ] "MUST: 健康检查用 HTTP GET" — 满足 (既有 healthcheck 不动)

---

## Overall Decision

- [ ] ✅ PASS — 可进入 archive
- [ ] ⚠️ PASS WITH WARNINGS — 需注意：`<说明>`
- [ ] ❌ FAIL — 返回失败 artifact 修正后重跑 verify

**下一步**：TBD
