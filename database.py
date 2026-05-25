# database.py
import os
import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# ---------------------------------------------------------
# 1. LOAD DATABASE URL FROM ENV
# ---------------------------------------------------------
raw_url = os.getenv("DATABASE_URL")

if not raw_url:
    raise RuntimeError("❌ DATABASE_URL is missing")

# ---------------------------------------------------------
# 2. REMOVE sslmode=require (Neon adds it automatically)
# ---------------------------------------------------------
if "sslmode=" in raw_url:
    raw_url = raw_url.split("?")[0]

# ---------------------------------------------------------
# 3. CREATE SSL CONTEXT FOR ASYNCPG
# ---------------------------------------------------------
ssl_ctx = ssl.create_default_context()

# ---------------------------------------------------------
# 4. CREATE ASYNC ENGINE WITH SSL
# ---------------------------------------------------------
engine = create_async_engine(
    raw_url,
    echo=False,
    future=True,
    connect_args={"ssl": ssl_ctx}
)

async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()

async def get_session():
    async with async_session() as session:
        yield session
