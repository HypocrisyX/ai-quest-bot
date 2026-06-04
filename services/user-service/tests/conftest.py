import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.database import get_db
from app.models import Base

TEST_DB_URL = os.getenv(
    "TEST_USER_DB_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/user_service_test",
)


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db(test_engine):
    """Transaction-per-test: every test rolls back automatically."""
    async with test_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        yield session
        await session.close()
        await conn.rollback()


@pytest_asyncio.fixture
async def client(db):
    from main import app

    async def override():
        yield db

    app.dependency_overrides[get_db] = override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
