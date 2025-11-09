import os
import logging
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from models import Base

logger = logging.getLogger("database")

# Load environment variables from .env.local
load_dotenv(".env.local")

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is not set. "
        "Please add DATABASE_URL to your .env.local file"
    )

# Create async engine with asyncpg driver
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging during debugging
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=5,  # Number of connections to keep in the pool
    max_overflow=10,  # Maximum overflow connections
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit
)


async def init_db():
    """Initialize database tables.
    
    Creates all tables defined in the Base metadata if they don't exist.
    Should be called once at application startup.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully")

