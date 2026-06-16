#!/usr/bin/env bash
# setup-chatbiz-env.sh — 在新机器上 1-shot 装 ChatBiz Python 后端开发环境。
#
# 决策背景:
#   - memory [[conda-chatbiz-env]] 锁定:Python 后端必须用 `chatbiz` conda env,
#     禁止 anaconda3 base / uv 默认 python。base 缺 jose、langgraph 等项目依赖;
#     uv run --python 3.12 环境未对齐会引发依赖版本漂移。
#   - openspec/config.yaml 后端规范:SQLAlchemy ORM + 异步 + 审计埋点。
#   - 4 service (audit-and-isolation / credential / gateway-scanner / sso) 全部
#     走 PEP 621 + setuptools.build_meta(`[project.dependencies]` +
#     `[project.optional-dependencies].dev`),**无 Poetry lock**。所以 deps
#     安装统一用 `pip install -e ".[dev]"`。
#   - workflow-engine / mcp 2 service 仍是 0% cov,本脚本不触碰它们的 deps
#     (CI 触发约定 4 service matrix 是 audit-and-isolation / credential /
#     gateway-scanner / sso;workflow-engine / mcp 等收尾时再扩)。
#
# Usage:
#   bash tools/setup-chatbiz-env.sh                # 全量装:建 env + 装 4 service dev deps
#   bash tools/setup-chatbiz-env.sh --check       # 干跑:验证 env + deps 已就位,不修改
#   bash tools/setup-chatbiz-env.sh --env-only    # 只建 env + 装公共 build deps,不碰 service deps
#   bash tools/setup-chatbiz-env.sh --service <name>   # 只装单个 service 的 dev deps (e.g. sso)
#
# Exit codes:
#   0 — env 装好(或已存在)且全部 service deps 验证通过
#   1 — conda 不在 PATH / env 创建失败
#   2 — 4 service 任一 pip install 失败
#   3 — --check 模式下 4 service 任一 import 失败
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_NAME="chatbiz"
PYTHON_VERSION="3.12"
SERVICES=(audit-and-isolation credential gateway-scanner sso)

# ---------------------------------------------------------------------------
# flag parsing
# ---------------------------------------------------------------------------
MODE="full"        # full | check | env-only
SINGLE_SERVICE=""
for arg in "$@"; do
  case "$arg" in
    --check)       MODE="check" ;;
    --env-only)    MODE="env-only" ;;
    --service)     MODE="single"; SINGLE_SERVICE="" ;;  # value 走下一轮
    --service=*)   MODE="single"; SINGLE_SERVICE="${arg#--service=}" ;;
    -h|--help)
      sed -n '2,30p' "$0"
      exit 0
      ;;
    *)
      # bare value → --service <name> 的 value
      if [ "$MODE" = "single" ] && [ -z "$SINGLE_SERVICE" ]; then
        SINGLE_SERVICE="$arg"
      else
        echo "Unknown arg: $arg" >&2
        exit 1
      fi
      ;;
  esac
done

if [ "$MODE" = "single" ] && [ -z "$SINGLE_SERVICE" ]; then
  echo "--service requires a service name" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
step() { printf '\n==> %s\n' "$*"; }
die()  { echo "[ERROR] $*" >&2; exit 1; }

conda_env_exists() {
  conda env list 2>/dev/null | awk -v env="^${ENV_NAME}[[:space:]]" '$0 ~ env { found=1 } END { exit !found }'
}

verify_conda() {
  command -v conda >/dev/null 2>&1 || die "conda 不在 PATH;装 Miniconda/Anaconda 后重试"
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
}

# ---------------------------------------------------------------------------
# 1. env create / verify
# ---------------------------------------------------------------------------
step "[1/3] verify conda env '$ENV_NAME' (python $PYTHON_VERSION)"

verify_conda

if conda_env_exists; then
  echo "  env '$ENV_NAME' already exists"
else
  echo "  creating env '$ENV_NAME' (python=$PYTHON_VERSION) ..."
  conda create -n "$ENV_NAME" "python=$PYTHON_VERSION" -y
fi

# 在 conda env 里跑命令的 helper(不依赖 caller 已 activate)
run_in_env() { conda run -n "$ENV_NAME" "$@"; }

run_in_env python --version
run_in_env python -c "import sys; assert sys.version_info[:2] == (3, 12), sys.version" \
  || die "env '$ENV_NAME' 不是 Python 3.12"

# 公共 build / packaging 工具(给 pip install -e 用)。
# 仅在 [2/3] 真要装 service deps 时升级;--check 干跑路径不碰 env。
if [ "$MODE" != "check" ]; then
  step "[1/3] install shared build tooling in env '$ENV_NAME'"
  run_in_env pip install --upgrade pip wheel setuptools
else
  echo "  --check 干跑,跳过 pip upgrade"
fi

if [ "$MODE" = "check" ]; then
  step "[2/3] --check mode: verify all 4 service editable installs"
  FAIL=0
  for svc in "${SERVICES[@]}"; do
    svc_dir="$ROOT/services/$svc"
    [ -d "$svc_dir" ] || { echo "  [SKIP] $svc: dir not found"; continue; }
    # pyproject [project].name 是真实 pip 的 Name(可能带 chatbiz- 前缀或不带)。
    # 用 editable install (`pip show` 返回 Location=<svc_dir>) 来验证该 service
    # 是不是在自己的目录装过 — 避免 import probe 跟同 env 其它 service 的
    # 共享 deps 撞名导致假阳性。
    pkg_name="$(
      run_in_env python -c "
import tomllib
with open('$svc_dir/pyproject.toml','rb') as f:
    print(tomllib.load(f)['project']['name'])
" 2>/dev/null
    )"
    if [ -z "$pkg_name" ]; then
      echo "  [WARN] $svc: 解析 pyproject [project].name 失败"
      FAIL=1
      continue
    fi
    location="$(
      # `pip show` 在包未装时 exit 1 → 配合 set -e + pipefail 会终止脚本,
      # 但本场景就是想要 "找不到时报 FAIL",所以用 `|| true` 吞掉非零 exit,
      # 让 awk 拿空 input 输出空 location,正常走下面 [FAIL] 分支。
      { run_in_env pip show "$pkg_name" 2>/dev/null || true; } \
        | awk -F': ' '/^Location:/ {print $2; exit}'
    )"
    if [ -n "$location" ] && [ "$location" = "$svc_dir" ]; then
      echo "  [OK]   $svc ($pkg_name editable at $svc_dir)"
    else
      echo "  [FAIL] $svc ($pkg_name 没在 $svc_dir editable install) — 跑 'bash tools/setup-chatbiz-env.sh --service $svc'"
      FAIL=1
    fi
  done
  [ "$FAIL" -eq 0 ] || exit 3
  echo ""
  echo "OK: env '$ENV_NAME' + 4 service 都已 editable install 在自己的 services/<name>/ 目录"
  exit 0
fi

# ---------------------------------------------------------------------------
# 2. install per-service dev deps
# ---------------------------------------------------------------------------
install_service_deps() {
  local svc="$1"
  local svc_dir="$ROOT/services/$svc"
  if [ ! -d "$svc_dir" ]; then
    echo "  [WARN] services/$svc 不存在,跳过"
    return 0
  fi
  if [ ! -f "$svc_dir/pyproject.toml" ]; then
    echo "  [WARN] services/$svc/pyproject.toml 不存在,跳过"
    return 0
  fi
  echo "  --> $svc"
  # PEP 621 + setuptools.build_meta:[project.optional-dependencies].dev
  # workflow-engine / mcp 走 [project.dependencies] 即可(无 dev 段) — 但本脚本
  # 当前只覆盖 4 service matrix,等它们收尾时再扩。
  ( cd "$svc_dir" && run_in_env pip install -e ".[dev]" ) \
    || die "pip install -e '.[dev]' 失败:$svc"
}

if [ "$MODE" = "single" ]; then
  step "[2/3] install dev deps for single service: $SINGLE_SERVICE"
  install_service_deps "$SINGLE_SERVICE"
elif [ "$MODE" = "env-only" ]; then
  step "[2/3] --env-only mode: 跳过 service deps 安装"
else
  step "[2/3] install dev deps for 4 services: ${SERVICES[*]}"
  for svc in "${SERVICES[@]}"; do
    install_service_deps "$svc"
  done
fi

# ---------------------------------------------------------------------------
# 3. summary
# ---------------------------------------------------------------------------
step "[3/3] summary"
run_in_env python -V
echo "  env  : $ENV_NAME ($(run_in_env python -c 'import sys;print(sys.executable)'))"
echo "  4 svc: ${SERVICES[*]}"
echo ""
echo "Next steps:"
echo "  conda activate $ENV_NAME"
echo "  bash tools/check-compose-naming.sh        # 顺手 lint docker-compose"
echo "  pytest services/sso/tests/ -q             # 任一 service 跑测试"
echo ""
echo "OK: ChatBiz dev env 就绪"
