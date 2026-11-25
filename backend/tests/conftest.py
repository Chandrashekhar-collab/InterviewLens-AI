"""Pytest configuration and async test fixtures with isolated in-memory SQLite database.

Design notes
------------
* pytest-asyncio 1.5.0 with asyncio_default_fixture_loop_scope=function creates a
  brand-new event loop for every test function.  SQLAlchemy's async engine is bound
  to the event loop that created it, so a module-level engine would be stale and
  dead-lock every test after the first one.

  Fix: create the engine INSIDE a function-scoped fixture so it is always created
  on the same event loop that is running the current test.

* ASGITransport(app=test_app) used to trigger the lifespan context-manager in
  httpx 0.27+, which caused another dead-lock because the lifespan startup code
  (logging, compat patches) raced with the fixture event loop.

  Fix: create_application(use_lifespan=False) produces a lifespan-free app instance
  that is safe to use inside pytest-asyncio fixtures.

* The PyAV compat patch (av.open metadata_errors fix) is applied once at session
  start so it is in effect for all tests, including those that import speech-engine
  modules at collection time.
"""

from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.base import Base
from app.main import create_application

# ---------------------------------------------------------------------------
# Apply av.open compatibility patch once at import / collection time.
# ---------------------------------------------------------------------------
from app.engines.speech.compat import apply_pyav_compatibility_patch
apply_pyav_compatibility_patch()

# ---------------------------------------------------------------------------
# Lifespan-free FastAPI app for integration tests.
# ---------------------------------------------------------------------------
test_app = create_application(use_lifespan=False)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def anyio_backend():
    """Tell anyio / pytest-asyncio to use the asyncio backend."""
    return "asyncio"


@pytest.fixture
async def test_engine():
    """Create an async engine bound to the *current* test's event loop.

    Using StaticPool so every SQLAlchemy connection goes to the same
    in-memory database, which is required for aiosqlite + in-memory SQLite.
    The engine is disposed after each test.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield engine
    await engine.dispose()


@pytest.fixture
async def setup_test_database(test_engine):
    """Create all tables before each test, drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(test_engine, setup_test_database) -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated async database session for the current test."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client wired to the lifespan-free app with the test DB override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    test_app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client

    test_app.dependency_overrides.clear()
