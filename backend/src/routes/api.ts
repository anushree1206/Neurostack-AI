import { Router, type IRouter, type Request, type Response } from "express";
import { logger } from "../lib/logger";
import { Readable } from "stream";

const router: IRouter = Router();

// Get the FastAPI backend URL from environment or use default
const FASTAPI_URL = process.env.FASTAPI_URL || "http://localhost:8080";

logger.info({ fastapi_url: FASTAPI_URL }, "FastAPI backend configured");

/**
 * Convert Web ReadableStream to Node.js Readable stream
 */
function webStreamToNodeStream(webStream: ReadableStream<Uint8Array>): Readable {
  const reader = webStream.getReader();
  
  return new Readable({
    async read() {
      try {
        const { done, value } = await reader.read();
        if (done) {
          this.push(null);
        } else {
          this.push(Buffer.from(value));
        }
      } catch (error) {
        this.destroy(error as Error);
      }
    },
  });
}

/**
 * Proxy handler for streaming responses (SSE)
 */
async function proxyStream(req: Request, res: Response, path: string) {
  try {
    const url = `${FASTAPI_URL}${path}`;
    logger.debug({ url, method: req.method }, "Proxying streaming request");

    const response = await fetch(url, {
      method: req.method,
      headers: {
        "Content-Type": "application/json",
        ...Object.fromEntries(
          Object.entries(req.headers).filter(
            ([key]) => !["host", "connection"].includes(key.toLowerCase())
          )
        ),
      },
      body: req.method !== "GET" ? JSON.stringify(req.body) : undefined,
    });

    // Check if response is ok
    if (!response.ok) {
      logger.warn({ status: response.status, url }, "FastAPI returned error status");
      const errorData = await response.text().catch(() => "");
      res.status(response.status).json({ error: errorData || "Upstream error" });
      return;
    }

    // Set response headers for streaming
    res.setHeader("Content-Type", response.headers.get("content-type") || "text/event-stream");
    res.setHeader("Cache-Control", "no-cache");
    res.setHeader("Connection", "keep-alive");
    res.setHeader("Access-Control-Allow-Origin", "*");

    // Pipe the response using Node stream
    if (response.body) {
      const nodeStream = webStreamToNodeStream(response.body);
      nodeStream.pipe(res);
    } else {
      res.end();
    }
  } catch (error) {
    logger.error({ error, path }, "Proxy error");
    res.status(500).json({ error: "Proxy request failed", detail: (error as Error).message });
  }
}

/**
 * Proxy handler for regular JSON responses
 */
async function proxyJson(req: Request, res: Response, path: string) {
  try {
    const url = `${FASTAPI_URL}${path}`;
    logger.debug({ url, method: req.method }, "Proxying JSON request");

    const response = await fetch(url, {
      method: req.method,
      headers: {
        "Content-Type": "application/json",
        ...Object.fromEntries(
          Object.entries(req.headers).filter(
            ([key]) => !["host", "connection"].includes(key.toLowerCase())
          )
        ),
      },
      body: req.method !== "GET" && req.method !== "HEAD" ? JSON.stringify(req.body) : undefined,
    });

    const data = await response.json().catch(() => ({}));
    
    if (!response.ok) {
      logger.warn({ status: response.status, url }, "FastAPI returned error status");
    }
    
    res.status(response.status).json(data);
  } catch (error) {
    logger.error({ error, path }, "JSON proxy error");
    res.status(500).json({ error: "Proxy request failed", detail: (error as Error).message });
  }
}

// 1. POST /api/query - Submit query with streaming SSE response
router.post("/query", async (req: Request, res: Response) => {
  logger.info({ query: req.body?.query }, "Received query submission");
  await proxyStream(req, res, "/api/query");
});

// 2. GET /api/trace/{job_id} - Retrieve full execution trace
router.get("/trace/:jobId", async (req: Request, res: Response) => {
  logger.info({ jobId: req.params.jobId }, "Fetching execution trace");
  await proxyJson(req, res, `/api/trace/${req.params.jobId}`);
});

// 3. GET /api/eval/summary - Retrieve latest eval run summary
router.get("/eval/summary", async (req: Request, res: Response) => {
  logger.info("Fetching eval summary");
  await proxyJson(req, res, "/api/eval/summary");
});

// 4. GET /api/eval/latest - Legacy endpoint for eval summary
router.get("/eval/latest", async (req: Request, res: Response) => {
  logger.info("Fetching eval latest (legacy)");
  await proxyJson(req, res, "/api/eval/latest");
});

// 5. GET /api/prompts - List prompts
router.get("/prompts", async (req: Request, res: Response) => {
  logger.info("Fetching prompts list");
  await proxyJson(req, res, "/api/prompts");
});

// 6. POST /api/eval/approve - Submit human approval/rejection for prompt rewrite
router.post("/eval/approve", async (req: Request, res: Response) => {
  logger.info({ rewriteId: req.body?.rewrite_id }, "Submitting eval approval");
  await proxyJson(req, res, "/api/eval/approve");
});

// 7. POST /api/eval/re-eval - Trigger targeted re-evaluation
router.post("/eval/re-eval", async (req: Request, res: Response) => {
  logger.info("Triggering re-evaluation");
  await proxyJson(req, res, "/api/eval/re-eval");
});

// 8. GET /api/prompts/:id/review - Placeholder for prompts review endpoint
router.get("/prompts/:id/review", async (req: Request, res: Response) => {
  logger.info({ promptId: req.params.id }, "Fetching prompt review");
  await proxyJson(req, res, `/api/prompts/${req.params.id}/review`);
});

// 9. GET /api/jobs/:jobId - Get job details
router.get("/jobs/:jobId", async (req: Request, res: Response) => {
  logger.info({ jobId: req.params.jobId }, "Fetching job details");
  await proxyJson(req, res, `/api/trace/${req.params.jobId}`);
});

// 10. POST /api/eval/rerun - Trigger eval rerun
router.post("/eval/rerun", async (req: Request, res: Response) => {
  logger.info("Triggering eval rerun");
  await proxyJson(req, res, "/api/eval/re-eval");
});

export default router;
