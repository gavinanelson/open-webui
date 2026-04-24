#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export DOCKER_HOST="${DOCKER_HOST:-unix:///Users/gavin/.colima/default/docker.sock}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROD_DEPLOY_ROOT="/Users/gavin/.hermes/open-webui"
TEST_DEPLOY_ROOT="/Users/gavin/.hermes/open-webui-test"
COMPOSE_FILE="$TEST_DEPLOY_ROOT/docker-compose.yml"
SYNC_SCRIPT="$PROD_DEPLOY_ROOT/sync_hermes_native.py"
DEPLOY_DOC="$TEST_DEPLOY_ROOT/DEPLOYMENT.md"
IMAGE_NAME="open-webui-hermes-runtime-test"
IMAGE_TAG="testing"
DEPLOY_IMAGE="${OPENWEBUI_TEST_IMAGE:-${IMAGE_NAME}:${IMAGE_TAG}}"
BACKEND_PORT="${OPENWEBUI_TEST_BACKEND_PORT:-3023}"
PROXY_PORT="${OPENWEBUI_TEST_PROXY_PORT:-3022}"
PUBLIC_URL="${OPENWEBUI_TEST_PUBLIC_URL:-https://chat-test.yxanadu.com}"
FULL_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
SHORT_SHA="$(git -C "$REPO_ROOT" rev-parse --short=9 HEAD)"
BRANCH_NAME="${GITHUB_REF_NAME:-$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)}"
REPO_URL="$(git -C "$REPO_ROOT" remote get-url origin)"
VERSION="unknown"

if [[ -f "$REPO_ROOT/package.json" ]]; then
  VERSION="$(python3 - <<'PY' "$REPO_ROOT/package.json"
import json, sys
with open(sys.argv[1]) as f:
    print(json.load(f).get('version', 'unknown'))
PY
)"
fi

if [[ "$BRANCH_NAME" != "testing" ]]; then
  echo "Refusing to deploy test Open WebUI from branch '$BRANCH_NAME' (allowed: testing only)" >&2
  exit 1
fi

if [[ ! -f "$PROD_DEPLOY_ROOT/.env" ]]; then
  echo "Missing production Open WebUI env file: $PROD_DEPLOY_ROOT/.env" >&2
  exit 1
fi

if [[ ! -x "$SYNC_SCRIPT" ]]; then
  echo "Missing executable sync script: $SYNC_SCRIPT" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon unavailable; starting Colima..."
  colima start default
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is still unavailable after attempting to start Colima" >&2
  exit 1
fi

storage_maintenance() {
  local phase="$1"
  local helper="/Users/gavin/xanadu-storage/scripts/docker-storage-maintenance.sh"
  if [[ "${OPENWEBUI_TEST_SKIP_STORAGE_MAINTENANCE:-}" == "1" ]]; then
    echo "Skipping test deploy storage maintenance ($phase): OPENWEBUI_TEST_SKIP_STORAGE_MAINTENANCE=1"
    return 0
  fi
  if [[ -x "$helper" ]]; then
    "$helper" "$phase" open-webui-test-deploy
  fi
}

storage_maintenance preflight

echo "Preparing $IMAGE_NAME:$SHORT_SHA and $IMAGE_NAME:$IMAGE_TAG from $BRANCH_NAME @ $SHORT_SHA"
if [[ -n "${OPENWEBUI_TEST_IMAGE:-}" ]]; then
  echo "Using off-host built image for test deploy: $OPENWEBUI_TEST_IMAGE"
  docker pull "$OPENWEBUI_TEST_IMAGE"
  docker tag "$OPENWEBUI_TEST_IMAGE" "$IMAGE_NAME:$SHORT_SHA"
  docker tag "$OPENWEBUI_TEST_IMAGE" "$IMAGE_NAME:$IMAGE_TAG"
elif [[ "${ALLOW_LOCAL_TEST_BUILD:-}" == "1" ]]; then
  echo "ALLOW_LOCAL_TEST_BUILD=1 set; using constrained local fallback build."
  echo "This path is memory-limited and should be used only for emergency manual recovery, not normal testing deploys."
  DOCKER_BUILDKIT=0 docker build \
    --memory="${OPENWEBUI_TEST_BUILD_MEMORY:-3g}" \
    --memory-swap="${OPENWEBUI_TEST_BUILD_MEMORY_SWAP:-4g}" \
    --build-arg BUILD_HASH="$FULL_SHA" \
    --build-arg USE_SLIM=true \
    --build-arg NODE_MAX_OLD_SPACE_SIZE="${OPENWEBUI_TEST_NODE_OLD_SPACE:-2048}" \
    -t "$IMAGE_NAME:$SHORT_SHA" \
    -t "$IMAGE_NAME:$IMAGE_TAG" \
    "$REPO_ROOT"
else
  echo "Refusing local test Docker build on xanadu-host." >&2
  echo "Set OPENWEBUI_TEST_IMAGE to an off-host-built GHCR image; normal GitHub testing deploys do this automatically." >&2
  echo "Emergency-only override: ALLOW_LOCAL_TEST_BUILD=1, with memory limits still applied." >&2
  exit 64
fi

mkdir -p "$TEST_DEPLOY_ROOT"
cp "$PROD_DEPLOY_ROOT/.env" "$TEST_DEPLOY_ROOT/.env"
for file in pwa-manifest.json assetlinks.json loader.js service-worker.js stale-app-entry-rescue.js; do
  if [[ -f "$PROD_DEPLOY_ROOT/$file" ]]; then
    cp "$PROD_DEPLOY_ROOT/$file" "$TEST_DEPLOY_ROOT/$file"
  fi
done

python3 - <<'PY' "$PROD_DEPLOY_ROOT/Caddyfile" "$TEST_DEPLOY_ROOT/Caddyfile" "$BACKEND_PORT"
from pathlib import Path
import re, sys
src, dst, backend_port = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
text = src.read_text()
text = re.sub(r'host\.docker\.internal:\d+', f'host.docker.internal:{backend_port}', text)
dst.write_text(text)
PY

cat > "$COMPOSE_FILE" <<YAML
services:
  open-webui-test:
    image: ${DEPLOY_IMAGE}
    container_name: hermes-open-webui-test
    ports:
      - "127.0.0.1:${BACKEND_PORT}:8080"
    environment:
      OPENAI_API_BASE_URL: http://host.docker.internal:8642/v1
      OPENAI_API_BASE_URLS: http://host.docker.internal:8642/v1;http://host.docker.internal:8652/v1
      OPENAI_API_KEY: \${OPENAI_API_KEY}
      OPENAI_API_KEYS: \${OPENAI_API_KEY};\${OPENAI_API_KEY}
      HERMES_API_BASE_URL: http://host.docker.internal:8642
      HERMES_DASHBOARD_BASE_URL: http://host.docker.internal:9119
      ENABLE_OLLAMA_API: "false"
      WEBUI_URL: ${PUBLIC_URL}
      RAG_EMBEDDING_MODEL_EAGER_LOAD: "false"
      INSTALL_TOOL_AND_FUNCTION_DEPS_ON_START: "false"
      PRELOAD_TOOL_SERVER_SPECS_ON_START: "false"
      THREAD_POOL_SIZE: "\${OPENWEBUI_TEST_THREAD_POOL_SIZE:-8}"
      MALLOC_ARENA_MAX: "\${OPENWEBUI_TEST_MALLOC_ARENA_MAX:-2}"
      OMP_NUM_THREADS: "\${OPENWEBUI_TEST_NUM_THREADS:-1}"
      MKL_NUM_THREADS: "\${OPENWEBUI_TEST_NUM_THREADS:-1}"
      OPENBLAS_NUM_THREADS: "\${OPENWEBUI_TEST_NUM_THREADS:-1}"
      NUMEXPR_NUM_THREADS: "\${OPENWEBUI_TEST_NUM_THREADS:-1}"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - open-webui-test-data:/app/backend/data
      - ${PROD_DEPLOY_ROOT}/hermes-native:/app/backend/data/hermes-native:ro
    mem_limit: ${OPENWEBUI_TEST_MEMORY_LIMIT:-3g}
    memswap_limit: ${OPENWEBUI_TEST_MEMORY_SWAP_LIMIT:-4g}
    cpus: "${OPENWEBUI_TEST_CPUS:-2.0}"
    restart: unless-stopped

  open-webui-test-pwa-proxy:
    image: caddy:2-alpine
    container_name: hermes-open-webui-test-pwa-proxy
    depends_on:
      - open-webui-test
    ports:
      - "127.0.0.1:${PROXY_PORT}:8080"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./pwa-manifest.json:/srv/manifest.json:ro
      - ./assetlinks.json:/srv/assetlinks.json:ro
      - ./loader.js:/srv/static/loader.js:ro
      - ./service-worker.js:/srv/service-worker.js:ro
      - ./stale-app-entry-rescue.js:/srv/stale-app-entry-rescue.js:ro
    mem_limit: ${OPENWEBUI_TEST_PROXY_MEMORY_LIMIT:-256m}
    cpus: "${OPENWEBUI_TEST_PROXY_CPUS:-0.5}"
    restart: unless-stopped

volumes:
  open-webui-test-data:
YAML

cd "$TEST_DEPLOY_ROOT"
docker compose -p open-webui-test up -d --no-deps --force-recreate open-webui-test
docker compose -p open-webui-test up -d --no-deps open-webui-test-pwa-proxy

# The test stack uses a fresh Open WebUI DB volume. Seed only the prod admin
# login row (no chats/files/history) so Gavin can use the same login and the
# Hermes catalog sync has an admin user to own model/tool/skill rows.
if docker exec hermes-open-webui-test python3 - <<'PY' >/dev/null 2>&1
import sqlite3
conn=sqlite3.connect('/app/backend/data/webui.db')
cur=conn.cursor()
raise SystemExit(0 if cur.execute("SELECT 1 FROM user WHERE role='admin' LIMIT 1").fetchone() else 1)
PY
then
  echo "Test stack already has an admin user; skipping production admin seed."
else
python3 - <<'PY'
import json
import subprocess
prod_script = r'''
import json, sqlite3
conn=sqlite3.connect('/app/backend/data/webui.db')
conn.row_factory=sqlite3.Row
cur=conn.cursor()
user=cur.execute("SELECT * FROM user WHERE role='admin' ORDER BY created_at LIMIT 1").fetchone()
if not user:
    raise SystemExit('no production admin user found')
auth=cur.execute("SELECT * FROM auth WHERE id=?", (user['id'],)).fetchone()
print(json.dumps({'user': dict(user), 'auth': dict(auth) if auth else None}))
'''
payload = subprocess.check_output(['docker', 'exec', 'hermes-open-webui', 'python3', '-c', prod_script], text=True)
seed_script = r'''
import json, sqlite3, sys
payload=json.loads(sys.stdin.read())
conn=sqlite3.connect('/app/backend/data/webui.db')
cur=conn.cursor()
if cur.execute("SELECT 1 FROM user WHERE role='admin' LIMIT 1").fetchone():
    raise SystemExit(0)
user=payload['user']
auth=payload.get('auth')
cols=list(user.keys())
cur.execute(f"INSERT OR REPLACE INTO user ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})", [user[c] for c in cols])
if auth:
    cols=list(auth.keys())
    cur.execute(f"INSERT OR REPLACE INTO auth ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})", [auth[c] for c in cols])
conn.commit()
'''
subprocess.run(['docker', 'exec', '-i', 'hermes-open-webui-test', 'python3', '-c', seed_script], input=payload, text=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
PY
fi

OPENWEBUI_CONTAINER=hermes-open-webui-test \
OPENWEBUI_ROOT="$TEST_DEPLOY_ROOT" \
OPENWEBUI_CATALOG_ROOT="$PROD_DEPLOY_ROOT/hermes-native" \
OPENWEBUI_ENV="$PROD_DEPLOY_ROOT/.env" \
"$SYNC_SCRIPT"

cat > "$DEPLOY_DOC" <<DOC
# Open WebUI test deployment contract

## Purpose
This is the isolated Open WebUI test deployment. It exists so Gavin can keep using production Open WebUI while agents modify and verify Open WebUI changes against real Hermes API backends and fresh Open WebUI chat/session data.

## Canonical source of truth
- fork: \`$REPO_URL\`
- auto-deploy branch: \`testing\`
- current deployed commit: \`$FULL_SHA\`

## Runtime image
- image tag in compose: \`${DEPLOY_IMAGE}\`
- last built image tag: \`${IMAGE_NAME}:${SHORT_SHA}\`
- app version: \`$VERSION\`

## Test compose stack
- compose path: \`$COMPOSE_FILE\`
- public URL: \`${PUBLIC_URL}\`
- backend loopback: \`http://127.0.0.1:${BACKEND_PORT}\`
- proxy loopback: \`http://127.0.0.1:${PROXY_PORT}\`
- backend container: \`hermes-open-webui-test\`
- proxy container: \`hermes-open-webui-test-pwa-proxy\`
- data volume: \`open-webui-test_open-webui-test-data\`

## Isolation rules
- Production stays on \`chat.yxanadu.com\`, ports \`3013/3012\`, and volume \`open-webui_open-webui-data\`.
- Testing stays on \`chat-test.yxanadu.com\`, ports \`${BACKEND_PORT}/${PROXY_PORT}\`, and volume \`open-webui-test_open-webui-test-data\`.
- Both stacks share the same Hermes API backends on \`8642\` and \`8652\` so test chats exercise the real Hermes bridge.
- Open WebUI chat/session rows are separate because the test stack has its own database volume.

## Manual verification
\`\`\`bash
curl -s http://127.0.0.1:${BACKEND_PORT}/health
curl -s http://127.0.0.1:${BACKEND_PORT}/api/version
curl -s -o /dev/null -w 'test_proxy code=%{http_code} total=%{time_total}\\n' http://127.0.0.1:${PROXY_PORT}/
curl -s -o /dev/null -w 'test_public code=%{http_code} total=%{time_total}\\n' ${PUBLIC_URL}/
docker inspect hermes-open-webui-test --format '{{.Config.Image}}'
\`\`\`
DOC

check_url() {
  local url="$1"
  local expected="$2"
  local attempt code
  for attempt in {1..30}; do
    code="$(curl -k -s -o /tmp/openwebui-test-check.$$ -w '%{http_code}' "$url" || true)"
    if [[ "$code" == "$expected" ]]; then
      return 0
    fi
    sleep 2
  done
  echo "Verification failed for $url (last code=$code, expected=$expected)" >&2
  return 1
}

check_url "http://127.0.0.1:${BACKEND_PORT}/ready" "200"
check_url "http://127.0.0.1:${BACKEND_PORT}/" "200"
check_url "http://127.0.0.1:${PROXY_PORT}/" "200"
if [[ "${SKIP_PUBLIC_OPENWEBUI_TEST_CHECK:-}" != "1" ]]; then
  check_url "${PUBLIC_URL}/" "200"
  check_url "${PUBLIC_URL}/api/version" "200"
fi

storage_maintenance postdeploy

echo "Test deploy complete: $FULL_SHA"
