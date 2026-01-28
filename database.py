from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
import os

# URL tanpa parameter pgbouncer
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.fbwtabjrjvmgyfhopvmi:tJwnUP365RHRrsMq@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"
)

# Supabase khusus memerlukan NullPool
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,  # Wajib untuk Supabase Transaction Pooler
    echo=False,          # Set True untuk debugging SQL queries
    future=True,
    connect_args={
        'connect_timeout': 10,
        'application_name': 'dynamic_scheduler'
    }
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

Base = declarative_base()

def get_db():
    """Dependency untuk mendapatkan database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()