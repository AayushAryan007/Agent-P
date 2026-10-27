"""Async engine and session factory. One engine per process, created at startup."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings


class Database:
    def __init__(self, settings: Settings) -> None:
        self.url = str(settings.database_url)
        self.engine: AsyncEngine = create_async_engine(self.url, pool_size=10, pool_pre_ping=True)
        self.sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessionmaker() as session:
            yield session

    async def dispose(self) -> None:
        await self.engine.dispose()
