# 0001: Host the API on Render

Date: 30 October 2026
Status: accepted

## Context

The API needs a public address, a Docker container, and no cost. The first attempt was a Hugging Face Docker Space, but Docker Spaces turned out to need a paid plan.

## Decision

Run the API as a free Docker web service on Render. The web page stays on Vercel, the database on Neon, and the model file in a Hugging Face model repository, which the API downloads at startup and checks against a SHA-256.

## Consequences

- The free instance has a tenth of a CPU, so a detection takes about 15 seconds.
- The service sleeps when idle, so the first request after a quiet period takes about 50 seconds.
- Requests come through Cloudflare and Render's proxy, so the rate limiter needs `WEEDLAB_TRUSTED_PROXY_HOPS=3`.
- Deploys happen only on version tags, because Auto-Deploy is off.
- Moving to another host later means changing environment variables, not code.