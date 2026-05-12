"""
FastAPI application for Multi-Agent LLM Orchestration System

Exposes exactly 5 endpoints:
1. POST /api/query           — submit query, receive streaming SSE response
2. GET  /api/trace/{job_id}   — retrieve full execution trace for completed job by job ID
3. GET  /api/eval/summary     — retrieve latest eval run summary broken down by test category and scoring dimension
4. POST /api/eval/approve      — submit human approval or rejection for pending prompt rewrite
5. POST /api/eval/re-eval      — trigger targeted re-evaluation on previously failed cases using latest approved prompts
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.db.database import get_db, init_db
from backend.api.endpoints import MultiAgentAPI
from backend.worker import worker_loop
from backend import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    worker_task = asyncio.create_task(worker_loop())
    logger.info("Multi-Agent system initialized")
    yield
    worker_task.cancel()
    logger.info("Multi-Agent system shutting down")

# Create FastAPI app with multi-agent endpoints
app = FastAPI(
    title="Multi-Agent LLM Orchestration System",
    description="Production-grade multi-agent pipeline with dynamic routing, evaluation loop, and self-improving prompts",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def liveness():
    """Infra liveness only (Docker/K8s). Not counted in the five assignment API routes under /api."""
    return {"status": "ok"}


# Initialize multi-agent API with main app
multi_agent_api = MultiAgentAPI(app)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not config.STRICT_API_FIVE_ENDPOINTS:
    @app.get("/api/health", summary="Health check")
    async def health():
        return {"status": "ok", "service": "multi-agent-orchestration", "message": "Multi-agent system is running"}
