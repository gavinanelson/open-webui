#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export DOCKER_HOST="${DOCKER_HOST:-unix:///Users/gavin/.colima/default/docker.sock}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_ROOT="/Users/gavin/.hermes/open-webui"
COMPOSE_FILE="$DEPLOY_ROOT/docker-compose.yml"
SYNC_SCRIPT="$DEPLOY_ROOT/sync_hermes_native.py"
DEPLOY_DOC="$DEPLOY_ROOT/DEPLOYMENT.md"
IMAGE_NAME="open-webui-hermes-runtime-clean"
IMAGE_TAG="latest"
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

if [[ "$BRANCH_NAME" != "main" && "$BRANCH_NAME" != "master" ]]; then
  echo "Refusing to deploy from branch '$BRANCH_NAME' (allowed: main or master)" >&2
  exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Missing compose file: $COMPOSE_FILE" >&2
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

echo "Building $IMAGE_NAME:$SHORT_SHA and $IMAGE_NAME:$IMAGE_TAG from $BRANCH_NAME @ $SHORT_SHA"
docker build -t "$IMAGE_NAME:$SHORT_SHA" -t "$IMAGE_NAME:$IMAGE_TAG" "$REPO_ROOT"

python3 - <<'PY' "$COMPOSE_FILE" "$IMAGE_NAME:$IMAGE_TAG"
from pathlib import Path
import re, sys
path = Path(sys.argv[1])
image = sys.argv[2]
text = path.read_text()
new_text, n = re.subn(r'(^\s*image:\s*)open-webui-hermes-runtime-clean:[^\s]+', r'\1' + image, text, count=1, flags=re.M)
if n != 1:
    raise SystemExit(f'Could not update image reference in {path}')
path.write_text(new_text)
PY

cd "$DEPLOY_ROOT"
docker compose up -d --force-recreate open-webui open-webui-pwa-proxy
"$SYNC_SCRIPT"

python3 - <<'PY' "$DEPLOY_DOC" "$REPO_URL" "$BRANCH_NAME" "$FULL_SHA" "$SHORT_SHA" "$VERSION"
from pathlib import Path
import sys
path = Path(sys.argv[1])
repo_url, branch, full_sha, short_sha, version = sys.argv[2:]
content = f'''# Open WebUI live deployment contract

## Canonical source of truth
The live `chat.yxanadu.com` app is now auto-deployed from Gavin's fork branch via GitHub Actions.

- fork: `{repo_url}`
- auto-deploy branch: `{branch}`
- current deployed commit: `{full_sha}`

## Runtime image
- image tag in compose: `open-webui-hermes-runtime-clean:latest`
- last built image tag: `open-webui-hermes-runtime-clean:{short_sha}`
- app version: `{version}`

## Deployment method
A repository self-hosted GitHub Actions runner on `xanadu-host` rebuilds and redeploys Open WebUI on pushes to `main` or `master`.

- runner name: `xanadu-host-open-webui-deploy`
- workflow: `.github/workflows/deploy-xanadu.yml`
- deploy script: `scripts/deploy-xanadu-openwebui.sh`

## Live compose stack
- compose path: `/Users/gavin/.hermes/open-webui/docker-compose.yml`
- service image: `open-webui-hermes-runtime-clean:latest`
- public URL: `https://chat.yxanadu.com`
- backend loopback: `http://127.0.0.1:3013`
- proxy loopback: `http://127.0.0.1:3012`

## What is intentionally kept
- `open-webui-data` Docker volume
- `./hermes-native:/app/backend/data/hermes-native:ro`
- public proxy via `Caddyfile`
- Hermes API backends on `8642` and `8652`

## What was intentionally dropped from the live app
- vault-specific bind mounts
- vault-specific runtime env vars
- hybrid code overlays from `open-webui-src`

## Manual verification
```bash
curl -s https://chat.yxanadu.com/api/version
curl -s http://127.0.0.1:3013/api/version
docker inspect hermes-open-webui --format '{{{{.Config.Image}}}}'
gh run list -R gavinanelson/open-webui --workflow deploy-xanadu.yml --limit 5
```

Expected outcomes:
- version reports the current deployed app
- container image is `open-webui-hermes-runtime-clean:latest`
- the latest GitHub Actions deploy run is green
'''
path.write_text(content)
PY

check_url() {
  local url="$1"
  local expected="$2"
  local attempt code
  for attempt in {1..30}; do
    code="$(curl -k -s -o /tmp/openwebui-check.$$ -w '%{http_code}' "$url" || true)"
    if [[ "$code" == "$expected" ]]; then
      return 0
    fi
    sleep 2
  done
  echo "Verification failed for $url (last code=$code, expected=$expected)" >&2
  return 1
}

check_url "http://127.0.0.1:3013/health" "200"
check_url "http://127.0.0.1:3013/" "200"
check_url "http://127.0.0.1:3012/" "200"
check_url "https://chat.yxanadu.com/" "200"
check_url "https://chat.yxanadu.com/api/version" "200"

echo "Deploy complete: $FULL_SHA"
