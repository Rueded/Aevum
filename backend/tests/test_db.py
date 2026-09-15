import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_database_connection(test_session: AsyncSession):
    """Verify that the async SQLite engine executes queries successfully."""
    result = await test_session.execute(text("SELECT 1 AS test_val"))
    row = result.mappings().one()
    assert row["test_val"] == 1
