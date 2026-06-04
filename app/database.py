from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def ensure_expenses_schema():
    """
    create_all()은 기존 테이블에 컬럼을 추가하지 않아서,
    개발 단계에서만 최소한의 컬럼 보강을 자동으로 수행합니다.

    배포 단계에선 Alembic 마이그레이션으로 대체하는 게 정석입니다.
    """
    insp = inspect(engine)
    if not insp.has_table("expenses"):
        return

    cols = {c["name"] for c in insp.get_columns("expenses")}
    with engine.begin() as conn:
        if "is_ocr" not in cols:
            conn.execute(text("ALTER TABLE expenses ADD COLUMN is_ocr BOOLEAN NOT NULL DEFAULT 0"))
        if "receipt_image_path" not in cols:
            conn.execute(text("ALTER TABLE expenses ADD COLUMN receipt_image_path VARCHAR(512) NULL"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()