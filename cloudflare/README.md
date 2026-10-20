# Cloudflare scheduled stock jobs

This runtime moves scheduled ingestion from a long-running local machine to Cloudflare Containers. The Python backend remains the source of business logic; the Worker only schedules and starts short-lived container jobs.

## Runtime layout

- Worker Cron Trigger: schedule and manual authenticated launch.
- Cloudflare Container: runs the existing `python -m stock_data.cli ...` commands.
- PostgreSQL: remains the durable database and must be reachable from the Container.
- R2: mounted through FUSE at `/mnt/r2`; `RAW_DATA_DIR=/mnt/r2/raw`, so raw SZSE XLSX and SSE JSON survive container shutdown.

Cloudflare Containers require the Workers Paid plan.

## Schedules

Cron expressions use UTC.

| UTC | China time | Job |
| --- | --- | --- |
| 09:30 Mon-Fri | 17:30 Mon-Fri | sync both masters + latest SSE + current-date SZSE |
| 11:30 daily | 19:30 daily | BaoStock SZSE history, 50 pending symbols |
| 13:30 daily | 21:30 daily | BaoStock SSE history, 50 pending symbols |

BaoStock history intentionally keeps the current fixed target end `2025-08-31`. Change `HISTORY_END` only when that historical phase is deliberately extended.

## One-time Cloudflare setup

Create an R2 bucket, for example `stock-data`, and an R2 Access API key with read/write access to the bucket.

Install dependencies:

```bash
npm install
```

Set Worker secrets:

```bash
npx wrangler secret put DATABASE_URL
npx wrangler secret put AWS_ACCESS_KEY_ID
npx wrangler secret put AWS_SECRET_ACCESS_KEY
npx wrangler secret put R2_ACCOUNT_ID
npx wrangler secret put R2_BUCKET_NAME
npx wrangler secret put RUN_TOKEN
```

`DATABASE_URL` must point to persistent PostgreSQL reachable from Cloudflare. The local default `127.0.0.1:10007` cannot be used from the hosted Container.

Deploy:

```bash
npm run cf:deploy
```

Wrangler builds `Dockerfile.cloudflare`, uploads the image, and deploys the Worker + Container configuration.

## Smoke test

Health only checks the Worker:

```bash
curl 'https://<worker>.workers.dev/health'
```

Run migrations:

```bash
curl -X POST \
  -H 'Authorization: Bearer <RUN_TOKEN>' \
  'https://<worker>.workers.dev/run/migrate'
```

Run one daily collection:

```bash
curl -X POST \
  -H 'Authorization: Bearer <RUN_TOKEN>' \
  'https://<worker>.workers.dev/run/daily'
```

Other manual jobs:

```text
POST /run/master
POST /run/history-szse
POST /run/history-sse
```

Each job uses a stable separate Container instance name.

## Persistence

Do not put database or R2 credentials in `wrangler.jsonc`; they are passed from Worker Secrets.

Container local disk is ephemeral. Raw exchange files are therefore written through the R2 FUSE mount. PostgreSQL ingestion checkpoints continue to control BaoStock resume behavior.
