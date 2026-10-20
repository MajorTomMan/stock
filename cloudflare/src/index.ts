import { Container, getContainer } from "@cloudflare/containers";

type Job = "daily" | "history-szse" | "history-sse" | "master" | "migrate";

interface Env {
  STOCK_JOB_CONTAINER: DurableObjectNamespace<StockJobContainer>;
  DATABASE_URL: string;
  AWS_ACCESS_KEY_ID: string;
  AWS_SECRET_ACCESS_KEY: string;
  R2_ACCOUNT_ID: string;
  R2_BUCKET_NAME: string;
  RUN_TOKEN: string;
  HISTORY_END: string;
  HISTORY_BATCH_SIZE: string;
  HISTORY_DELAY_SECONDS: string;
  HISTORY_RETRIES: string;
  HTTP_TIMEOUT_SECONDS: string;
}

const CRON_JOBS: Record<string, Job> = {
  "30 9 * * 1-5": "daily",
  "30 11 * * *": "history-szse",
  "30 13 * * *": "history-sse",
};

const PATH_JOBS: Record<string, Job> = {
  "/run/daily": "daily",
  "/run/history-szse": "history-szse",
  "/run/history-sse": "history-sse",
  "/run/master": "master",
  "/run/migrate": "migrate",
};

export class StockJobContainer extends Container<Env> {
  enableInternet = true;
  sleepAfter = "1m";
}

function containerEnv(env: Env): Record<string, string> {
  return {
    DATABASE_URL: env.DATABASE_URL,
    AWS_ACCESS_KEY_ID: env.AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY: env.AWS_SECRET_ACCESS_KEY,
    R2_ACCOUNT_ID: env.R2_ACCOUNT_ID,
    R2_BUCKET_NAME: env.R2_BUCKET_NAME,
    HISTORY_END: env.HISTORY_END,
    HISTORY_BATCH_SIZE: env.HISTORY_BATCH_SIZE,
    HISTORY_DELAY_SECONDS: env.HISTORY_DELAY_SECONDS,
    HISTORY_RETRIES: env.HISTORY_RETRIES,
    HTTP_TIMEOUT_SECONDS: env.HTTP_TIMEOUT_SECONDS,
    RAW_DATA_DIR: "/mnt/r2/raw",
    PYTHONUNBUFFERED: "1",
  };
}

async function launch(env: Env, job: Job): Promise<void> {
  const container = getContainer(env.STOCK_JOB_CONTAINER, job);
  await container.start({
    entrypoint: ["/usr/local/bin/stock-job", job],
    envVars: containerEnv(env),
    enableInternet: true,
  });
}

function authorized(request: Request, env: Env): boolean {
  if (!env.RUN_TOKEN) return false;
  return request.headers.get("authorization") === `Bearer ${env.RUN_TOKEN}`;
}

export default {
  async scheduled(controller: ScheduledController, env: Env): Promise<void> {
    const job = CRON_JOBS[controller.cron];
    if (!job) throw new Error(`No stock job mapped for cron: ${controller.cron}`);
    await launch(env, job);
    console.log(`started scheduled stock job: ${job}`);
  },

  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/health") {
      return Response.json({ status: "ok", service: "stock-market-jobs" });
    }

    const job = PATH_JOBS[url.pathname];
    if (!job || request.method !== "POST") {
      return new Response("Not found", { status: 404 });
    }
    if (!authorized(request, env)) {
      return new Response("Unauthorized", { status: 401 });
    }

    await launch(env, job);
    return Response.json({ status: "started", job }, { status: 202 });
  },
};
