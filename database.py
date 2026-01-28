from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session
from sqlalchemy.pool import NullPool  # Penting untuk Supabase Pooler
from contextlib import contextmanager
import os

# HAPUS parameter ?pgbouncer=true dari URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.fbwtabjrjvmgyfhopvmi:tJwnUP365RHRrsMq@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"
)

# Gunakan NullPool untuk Supabase Pooler
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,  # Wajib untuk Supabase dengan PgBouncer
    echo=False,  # Set True untuk debugging SQL
    future=True  # Untuk SQLAlchemy 2.0
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Penting untuk Supabase
)

# Base untuk models
Base = declarative_base()

# Dependency untuk mendapatkan session database
def get_db():
    """Generator untuk mendapatkan session database"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Context manager untuk transaction
@contextmanager
def db_transaction():
    """Context manager untuk transaction dengan auto commit/rollback"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()