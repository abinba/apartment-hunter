"""Async engine and session factory."""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if url:
        # accept the psycopg-style URL people paste from elsewhere
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    user = os.getenv("POSTGRES_USER", "hunter")
    pwd = os.getenv("POSTGRES_PASSWORD", "hunter")
    host = os.getenv("POSTGRES_HOST", "db")
    port = os.getenv("POSTGRES_PORT", "5432")
    name = os.getenv("POSTGRES_DB", "apartment_hunter")
    return f"postgresql+asyncpg://{user}:{pwd}@{host}:{port}/{name}"


engine = create_async_engine(
    database_url(),
    pool_pre_ping=True,      # survives Postgres restarts without a 500
    pool_size=5, max_overflow=5,
    echo=os.getenv("SQL_ECHO", "") == "1",
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
