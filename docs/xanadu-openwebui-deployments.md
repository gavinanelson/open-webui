# Xanadu Open WebUI deployments

Gavin's Open WebUI fork has two separate deployments.

## Testing deployment — default for agent work

- Branch: `testing`
- URL: `https://chat-test.yxanadu.com`
- Workflow: `.github/workflows/deploy-xanadu-test.yml`
- Trigger: push to `testing` only; no manual/broad push redeploy trigger
- Build isolation: the workflow builds the test image off-host on GitHub-hosted ARM and pushes `ghcr.io/gavinanelson/open-webui:xanadu-test-<sha>`; the Xanadu self-hosted deploy job only pulls that image and restarts the test stack
- GitHub environment: `xanadu-testing`, custom deployment branch policy `testing` only
- Script: `scripts/deploy-xanadu-openwebui-test.sh`
- Backend container: `hermes-open-webui-test`
- Proxy container: `hermes-open-webui-test-pwa-proxy`
- Ports: backend `127.0.0.1:3023`, proxy `127.0.0.1:3022`
- Data: separate Docker volume `open-webui-test_open-webui-test-data`

Use this deployment for all normal development, experiments, and Hermes agent harness validation. Pushes to `testing` deploy here automatically.

Important: do not move the test Docker build back onto `xanadu-host`. Local test image builds previously starved the Colima Docker VM and made the production backend container restart, which surfaced through Cloudflare as `chat.yxanadu.com` going down even though only `testing` was being deployed.

## Production deployment — only for approved releases

- Branch: `main`
- URL: `https://chat.yxanadu.com`
- Workflow: `.github/workflows/deploy-xanadu.yml`
- Trigger: push to `main` only; no manual/broad push redeploy trigger
- GitHub environment: `xanadu-production`, custom deployment branch policy `main` only
- Script: `scripts/deploy-xanadu-openwebui.sh`
- Backend container: `hermes-open-webui`
- Proxy container: `hermes-open-webui-pwa-proxy`
- Ports: backend `127.0.0.1:3013`, proxy `127.0.0.1:3012`
- Data: production Open WebUI volume

Do not use production for testing. Gavin may be actively using it.

## Shared Hermes harness

Both deployments intentionally point at the same real Hermes OpenAI-compatible backends:

- `127.0.0.1:8642` → `hermes-agent`
- `127.0.0.1:8652` → `implication`

That means test chats validate the real Hermes integration while keeping Open WebUI sessions, chats, files, and database rows isolated from production.

## Promotion rule

The safe path is:

1. Build and test on `testing`.
2. Verify on `https://chat-test.yxanadu.com`.
3. Ask Gavin before promoting to production.
4. Merge or cherry-pick the tested commits to `main` only after approval.
