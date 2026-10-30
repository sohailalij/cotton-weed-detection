# Runbook

Last updated: 30 October 2026.

## What runs where

| Part | Where | Notes |
|---|---|---|
| Web app | Vercel (Hobby) | Built from `frontend`, API address set by `VITE_API_URL` |
| API | Render, free Docker web service, Virginia | Starts by fetching the model, running migrations, then serving |
| Database | Neon, free plan, Postgres 18, Virginia | Suspends when idle and wakes on the next request |
| Model file | Hugging Face model repo | Downloaded at startup from a pinned address and checked against a SHA-256 |

## Settings on the Render service

Values are never written in this repo. They live under Environment on the API service.

| Name | Purpose |
|---|---|
| `WEEDLAB_DATABASE_URL` | Neon connection string. Secret. Use the direct host, not the one with `-pooler` |
| `WEEDLAB_CORS_ORIGINS` | Comma separated list of allowed web addresses. No spaces, no trailing slash |
| `WEEDLAB_MODEL_PATH` | Where the model file lives inside the container |
| `WEEDLAB_MODEL_URL` | Pinned address of the model file |
| `WEEDLAB_MODEL_SHA256` | Expected hash of the model file. The API refuses to start if it differs |
| `WEEDLAB_RETENTION_DAYS` | Detections older than this are deleted. 0 keeps everything |
| `WEEDLAB_RATE_LIMIT_PER_MINUTE` | Detect requests allowed per visitor address per minute. Default 10 |
| `WEEDLAB_MAX_UPLOAD_MB` | Largest accepted upload. Default 15 |
| `WEEDLAB_TRUSTED_PROXY_HOPS` | Must be `3` on Render. See below |

### Why the proxy setting is 3

Requests reach the API through Cloudflare and then Render's own proxy. The `X-Forwarded-For` header ends up as: real visitor, a Cloudflare address, Render's internal address. The API counts from the right, so the visitor is third. Cloudflare addresses change between requests, so a smaller number gives each visitor several counters and the limit stops working. If Render changes its proxy layout, check this again: send 12 bad uploads quickly and expect a 429 on the 11th.

## Deploying

Merging to `main` does not deploy. Auto-Deploy is off on the Render service.

1. Merge the change and wait for CI to pass.
2. `git checkout main`, `git pull`, then `git tag -a vX.Y.Z -m "short note"` and `git push origin vX.Y.Z`.
3. The `deploy` workflow in GitHub Actions checks that the tagged commit is on `main`, then calls Render's deploy hook for that exact commit.
4. On Render, open Deploys. The new deploy should show trigger Deploy Hook and the tagged commit. Wait for Live.
5. Check `/health` (expect `status` ok and `model_loaded` true) and run one detection from the web app.

The hook address is stored as the GitHub secret `RENDER_DEPLOY_HOOK_URL`. If it leaks, regenerate it in Render's service settings and update the secret.

## Rolling back

Status: not yet tested.

Plan A: on Render, open Deploys, then Manual Deploy, then Deploy a specific commit, and pick the last good commit.
Plan B: on Render, open an earlier successful deploy and use its Rollback option, if the free plan offers it.

A rollback changes code only. The API runs migrations at startup and never undoes them, so rolling back past a release that added a migration needs a manual check of the database first.

## Where to look when something is wrong

- Logs: Render, API service, Logs. Use Application logs and search for an error word or a path such as `/v1/detect`.
- Health: `/health` on the API address, and `/v1/model` for the model name and test metrics.
- Metrics: Render, API service, Metrics, for CPU and memory.
- Database: the Neon dashboard shows whether the project is idle or has hit a free plan limit.

## When detections get slow

1. Normal on this setup: about 15 seconds per detection, because the free instance has 0.1 CPU.
2. About 50 seconds or more on the first request after a quiet period: Render woke the service. A Neon wake-up can add a few seconds.
3. Slower than that and steady: look at Metrics for CPU saturation, then at the logs for repeated errors or restarts.
4. Failing at startup: look for the model check lines. A hash mismatch or a failed download stops the service on purpose.

## Known limits

- The rate limiter lives in memory, so it resets on restart and is not shared between workers.
- Each browser gets its own history through a visitor id, and detections are deleted after the retention period.
- Free hosts change their terms. The whole stack also runs locally with Docker Compose.