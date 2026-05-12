"""
Standalone background worker entry point for Docker deployment.
In production, run this as a separate service: python -m backend.worker_standalone
"""
import asyncio
import logging
from backend.db.database import init_db
from backend.worker import worker_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Standalone worker initializing DB...")
    await init_db()
    logger.info("Standalone worker started")
    await worker_loop()


if __name__ == "__main__":
    asyncio.run(main())
