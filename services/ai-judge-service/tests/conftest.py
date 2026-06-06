import os

import pytest_asyncio
from app.database import get_db
from app.models import Base
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

TEST_DB_URL = os.getenv(
    "TEST_JUDGE_DB_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5434/judge_service_test",
)


@pytest_asyncio.fixture
async def db():
    """Fresh engine per test so it lives in the test's own event loop; the
    transaction is rolled back at the end to keep tests isolated.
    """
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    conn = await engine.connect()
    trans = await conn.begin()
    session = AsyncSession(bind=conn, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await conn.close()
        await engine.dispose()


@pytest_asyncio.fixture
async def client(db):
    from main import app

    async def override():
        yield db

    app.dependency_overrides[get_db] = override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
