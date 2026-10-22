from collections.abc import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.db.session import Base, get_db_session
from app.llm import (
    ChatMessage,
    LLMProvider,
    LLMResponse,
    get_llm_provider,
)
from app.main import app
from sqlalchemy.pool import StaticPool

# Ensure tests run strictly in test environment (ADR-021 & Rule 7)
settings.environment = "test"

# In-memory SQLite async database engine for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


from app.llm.context import LLMContext


class FakeLLMProvider(LLMProvider):
    """Mock LLM Provider for hermetic testing."""

    def __init__(
        self,
        response_text: str = "Simulated assistant reply.",
        structured_response_text: str | None = None,
    ) -> None:
        self.response_text = response_text
        self.structured_response_text = structured_response_text
        self.call_history: list[LLMContext] = []
        self.structured_call_history: list[LLMContext] = []

    @property
    def provider_name(self) -> str:
        return "fake"

    async def generate_response(
        self,
        context: LLMContext,
    ) -> LLMResponse:
        self.call_history.append(context)
        return LLMResponse(content=self.response_text)

    async def generate_structured(
        self,
        context: LLMContext,
        response_schema=None,
    ) -> str:
        self.structured_call_history.append(context)
        if self.structured_response_text is not None:
            return self.structured_response_text
        return '{"signals": []}'

    async def generate_structured_response(
        self,
        context: LLMContext,
        response_schema=None,
    ) -> LLMResponse:
        self.structured_call_history.append(context)
        if self.structured_response_text is not None:
            return LLMResponse(content=self.structured_response_text)
        return LLMResponse(content=self.response_text)




@pytest.fixture
def fake_provider() -> FakeLLMProvider:
    """Fixture providing a configurable fake LLM provider."""
    return FakeLLMProvider()


@pytest.fixture
async def test_engine():
    """Create a temporary in-memory async SQLite engine for tests."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine, monkeypatch) -> AsyncGenerator[AsyncSession, None]:
    """Create an isolated test session."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    monkeypatch.setattr("app.character.post_turn_service.async_session_factory", session_factory)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(
    test_session: AsyncSession,
    fake_provider: FakeLLMProvider,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an HTTP async client with test DB and fake LLM provider overrides."""
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield test_session

    def override_get_llm() -> LLMProvider:
        return fake_provider

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_llm_provider] = override_get_llm

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
