import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# On Railway, DATABASE_URL is set as an environment variable
# Locally, falls back to your local PostgreSQL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:harmonica447@localhost:5432/fireflux"
)

# Railway sometimes provides postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()