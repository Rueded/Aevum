import asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

async def main():
    engine = create_async_engine("sqlite+aiosqlite:///aevum.db")
    async with engine.connect() as conn:
        res = await conn.execute(sa.text("SELECT id, role, content FROM messages WHERE conversation_id='e830b270-4506-4de1-ba86-ae2053ad4736' ORDER BY created_at ASC"))
        for r in res.fetchall():
            print(f"[{r[1]}]")
            print(r[2])
            print("-" * 40)
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
