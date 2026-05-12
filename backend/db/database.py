from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import os
import ssl


DATABASE_URL = os.environ.get("DATABASE_URL", "")


def _build_async_url(url: str) -> tuple[str, dict]:
    """
    Convert a postgres:// URL to postgresql+asyncpg://.
    Strip sslmode from the URL and return it as connect_args instead,
    because asyncpg does not accept sslmode as a keyword argument.
    """
    connect_args = {}

    if url.startswith("postgresql://") or url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif not url.startswith("postgresql+asyncpg://"):
        return "sqlite+aiosqlite:///./agent_system.db", {}

    if "sslmode=require" in url:
        url = url.replace("?sslmode=require", "").replace("&sslmode=require", "").replace("sslmode=require&", "")
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx
    elif "sslmode=disable" in url:
        url = url.replace("?sslmode=disable", "").replace("&sslmode=disable", "").replace("sslmode=disable&", "")
        connect_args["ssl"] = False

    if "?" in url and url.endswith("?"):
        url = url[:-1]

    return url, connect_args


ASYNC_DATABASE_URL, _connect_args = _build_async_url(DATABASE_URL)

if not DATABASE_URL:
    ASYNC_DATABASE_URL = "sqlite+aiosqlite:///./agent_system.db"
    _connect_args = {}

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    connect_args=_connect_args,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    from backend.db import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
