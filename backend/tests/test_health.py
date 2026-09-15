import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok(client: AsyncClient):
    """Verify that GET /health returns 200 and structured status."""
    response = await client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "Aevum Core"
    assert data["version"] == "0.1.0"
    assert data["database"] == "connected"
