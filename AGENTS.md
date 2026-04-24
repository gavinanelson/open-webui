# Agent instructions for Gavin's Open WebUI fork

This repository has two Xanadu deployments. Do not confuse them.

## Default work target

- Use the `testing` branch for Open WebUI changes, experiments, and Hermes-harness testing.
- Push work to `testing` to deploy the isolated test stack.
- Test URL: `https://chat-test.yxanadu.com`
- Test workflow: `.github/workflows/deploy-xanadu-test.yml`
- Test deploy script: `scripts/deploy-xanadu-openwebui-test.sh`

## Production is protected by convention

- `main` deploys production at `https://chat.yxanadu.com`.
- Production workflow: `.github/workflows/deploy-xanadu.yml`
- Production deploy script: `scripts/deploy-xanadu-openwebui.sh`
- Do not push feature work directly to `main` unless Gavin explicitly asks for a production release.
- Do not use production for exploratory testing; it can interrupt Gavin's active sessions.

## Deployment isolation

- Production stack: `chat.yxanadu.com`, containers `hermes-open-webui` and `hermes-open-webui-pwa-proxy`, ports `3013/3012`, production data volume.
- Testing stack: `chat-test.yxanadu.com`, containers `hermes-open-webui-test` and `hermes-open-webui-test-pwa-proxy`, ports `3023/3022`, separate test data volume.
- Both stacks intentionally use the real Hermes API backends on ports `8642` and `8652`, so testing exercises the actual Hermes agent harness without touching Gavin's production Open WebUI chat/session data.
- Deployment triggers are branch-locked: production redeploys only when `main` is pushed; testing redeploys only when `testing` is pushed. Do not add broad push triggers, manual deploy triggers, or shared deploy concurrency groups that could make one branch interrupt the other.
- GitHub environment branch policies mirror this: `xanadu-production` allows only `main`, and `xanadu-testing` allows only `testing`.
- Testing deploys must not do heavy Docker builds on `xanadu-host`. The test workflow builds/pushes the image off-host to GHCR first, then the self-hosted job only pulls and recreates the isolated test containers. Do not move the test image build back onto the Xanadu self-hosted runner; local Docker builds have caused production `chat.yxanadu.com` backend restarts/Cloudflare 502s.
- The test deploy script refuses local builds unless `ALLOW_LOCAL_TEST_BUILD=1` is explicitly set for an emergency manual recovery. Normal test deployments must provide `OPENWEBUI_TEST_IMAGE` from GHCR.
- The testing workflow captures a production canary before/after each test deploy and fails if `hermes-open-webui` restarts or `https://chat.yxanadu.com/` stops returning `200`.

## Recommended workflow

1. Start from `testing`: `git fetch origin && git checkout testing && git pull --ff-only origin testing`.
2. Make changes and commit on `testing` or a short-lived branch based on `testing`.
3. Merge/cherry-pick back into `testing` and push.
4. Wait for the `deploy-xanadu-test` GitHub Action to finish.
5. Verify `https://chat-test.yxanadu.com` and the relevant Hermes-agent behavior.
6. Only after Gavin approves release, promote the tested change to `main` for production.

If the task mentions Open WebUI testing, Hermes harness validation, UI experiments, or agent functionality checks, treat `testing` as the correct deployment branch.
