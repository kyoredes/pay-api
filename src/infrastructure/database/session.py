from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(database_url: str | None = None) -> None:
    """Call once at application startup (in lifespan) to initialise the engine."""
    global _engine, _session_factory
    url = database_url or get_settings().database_url
    _engine = create_async_engine(url, pool_pre_ping=True)
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def close_db() -> None:
    """Call once at application shutdown (in lifespan) to dispose the engine."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database not initialised. Call init_db() in lifespan first.")
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
