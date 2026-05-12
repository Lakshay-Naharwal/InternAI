import datetime
from sqlalchemy import String, Text, DateTime, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# SQLite async URL
DATABASE_URL = "sqlite+aiosqlite:///./internships.db"

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Async session factory
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass

class Internship(Base):
    __tablename__ = "internships"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    apply_url: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    source_board: Mapped[str] = mapped_column(String(100), nullable=False)
    deadline: Mapped[str | None] = mapped_column(String(100), nullable=True)
    scraped_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now
    )

class UserProfile(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    primary_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    target_roles: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    experience_level: Mapped[str] = mapped_column(String(100), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now
    )

async def init_db():
    """Initializes the database schema."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
