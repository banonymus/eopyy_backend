# run_migrations.py
import asyncio
from alembic import command
from alembic.config import Config
from database import engine  # your AsyncEngine instance

def run_alembic_upgrade():
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")

async def main():
    # run alembic migrations (synchronous call)
    run_alembic_upgrade()
    # dispose async engine so pooled connections are closed
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
