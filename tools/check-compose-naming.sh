#!/usr/bin/env bash
# check-compose-naming.sh — lint hook for ChatBiz docker-compose service keys.
#
# 决策背景:fix-compose-postgres-naming 锁定以下规则,任何后续 dev / base
# compose 修改都不能违反:
#   1. service key 必须以 `chatbiz-` 前缀(避免与外部容器名冲突 + 暗示命名空间)
#   2. 每个 service 必须显式 `container_name: chatbiz-...`(便于 `docker ps` 排查)
#
# 扫描范围:base (`infrastructure/docker-compose.yml`) + dev overlay
# (`infrastructure/docker-compose-dev.yml`)。test compose
# (`infrastructure/docker-compose-test.yml`) by design 隔离网络 + 独立命名空间,
# 不归本 lint 管。
#
# Baseline: V6 阶段只迁移了 chatbiz-postgres / chatbiz-redis 2 个 shared infra
# service 的命名。其它 12 个 application service (credential / audit-and-isolation
# / workflow-engine / sso / web + 各 migrate / cron 变体) 在 fix-compose
# change 期间**未**触动。baseline 列表反映 2026-06-14 状态;未来新加 service
# 禁止加进 baseline,必须直接满足规则。彻底扫清时由独立 change
# (compose-naming-migration-full) 一次性 rename 全部 baseline 段。
#
# 实现:每文件用 awk 抽出 (service_name, has_container_name) 二元组序列。
# awk 状态机:每行看缩进 — `  <key>:` 2 空格=新 service;`    container_name:` 4 空格
# 标记当前 service 有显式 container_name;其他 4 空格 = 当前 service body。
# 触发下一个 `  <key>:` 时 print 上一条 `(name, has_cn)` 记录。
#
# Usage:
#   bash tools/check-compose-naming.sh                # lint base + dev
#   bash tools/check-compose-naming.sh --strict       # baseline 也算 ERROR
#   bash tools/check-compose-naming.sh --show-baseline # 打印 baseline 列表后退出
#
# Exit codes:
#   0 — all rules pass (or only baseline violations in non-strict mode)
#   1 — at least one non-baseline ERROR
#   2 — only baseline violations in --strict mode
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INFRA="$ROOT/infrastructure"

STRICT=0
SHOW_BASELINE=0
for arg in "$@"; do
  case "$arg" in
    --strict) STRICT=1 ;;
    --show-baseline) SHOW_BASELINE=1 ;;
    -h|--help)
      sed -n '2,30p' "$0"
      exit 0
      ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

if [ "$SHOW_BASELINE" -eq 1 ]; then
  echo "Baseline service keys (12 entries,扫清时由 compose-naming-migration-full 一次性处理):"
  echo "  - credential (base + dev)"
  echo "  - credential-cron (dev)"
  echo "  - credential-migrate (base + dev)"
  echo "  - audit-and-isolation (base + dev)"
  echo "  - audit-and-isolation-migrate (base + dev)"
  echo "  - workflow-engine (base + dev)"
  echo "  - workflow-engine-migrate (base + dev)"
  echo "  - sso (dev)"
  echo "  - sso-migrate (dev)"
  echo "  - web (dev)"
  echo "  - chatbiz-postgres / chatbiz-redis in dev compose (alias extends 段,base 段覆盖)"
  exit 0
fi

# 12 个 service key 在 fix-compose 期间未触动,记入 baseline 抑制错误。
BASELINE_SERVICES='credential|credential-cron|credential-migrate|audit-and-isolation|audit-and-isolation-migrate|workflow-engine|workflow-engine-migrate|sso|sso-migrate|web'
is_baseline() { [[ "$1" =~ ^($BASELINE_SERVICES)$ ]]; }

# 对单个 compose 文件,输出多行 `service_name<TAB>has_container_name`。
extract_services() {
  local f="$1"
  awk '
    # 进入 services: 顶层段
    /^services:[[:space:]]*$/ { in_svc=1; next }
    # 离开 services: 顶层段(遇任何其它顶层 key)
    in_svc && /^[a-zA-Z_]/ { in_svc=0 }
    in_svc {
      # 顶层 service key: 2 空格 + 名字 + 冒号结尾
      if (/^  [a-zA-Z_][a-zA-Z0-9_-]*:[[:space:]]*$/) {
        # flush previous
        if (cur_name != "") print cur_name "\t" cur_cn
        # 提取 service 名
        sub(/^  /, "")
        sub(/:[[:space:]]*$/, "")
        cur_name = $0
        cur_cn = 0
        next
      }
      # service body 内的 container_name 字段(4 空格缩进)
      # 用 [^[:space:]] 替代 \S,macOS BSD awk 不支持 \S
      if (/^[[:space:]]+container_name:[[:space:]]*[^[:space:]]/) {
        cur_cn = 1
      }
    }
    END {
      if (cur_name != "") print cur_name "\t" cur_cn
    }
  ' "$f"
}

ERRORS=0
WARNINGS=0
report_err()   { echo "  [ERROR] $*" >&2; ERRORS=$((ERRORS+1)); }
report_warn() { echo "  [WARN-baseline] $*" >&2; WARNINGS=$((WARNINGS+1)); }

FILES=("$INFRA/docker-compose.yml" "$INFRA/docker-compose-dev.yml")
for f in "${FILES[@]}"; do
  if [ ! -f "$f" ]; then
    echo "  [WARN] file not found: $f (skipping)" >&2
    WARNINGS=$((WARNINGS+1))
    continue
  fi
  echo "==> $f"

  while IFS=$'\t' read -r svc_name has_cn; do
    [ -z "$svc_name" ] && continue
    if [[ "$svc_name" != chatbiz-* ]]; then
      if is_baseline "$svc_name"; then
        report_warn "service key '$svc_name' missing 'chatbiz-' prefix (rule 1)"
      else
        report_err "service key '$svc_name' missing 'chatbiz-' prefix (rule 1)"
      fi
    fi
    if [ "$has_cn" != "1" ]; then
      if is_baseline "$svc_name"; then
        report_warn "service '$svc_name' missing 'container_name:' field (rule 2)"
      else
        report_err "service '$svc_name' missing 'container_name:' field (rule 2)"
      fi
    fi
  done < <(extract_services "$f")
done

echo ""
if [ "$ERRORS" -gt 0 ]; then
  echo "FAIL: $ERRORS error(s), $WARNINGS warning(s)" >&2
  exit 1
fi
if [ "$STRICT" -eq 1 ] && [ "$WARNINGS" -gt 0 ]; then
  echo "FAIL (--strict): $WARNINGS warning(s) treated as errors" >&2
  exit 2
fi
echo "OK: $ERRORS error(s), $WARNINGS warning(s)"
exit 0
