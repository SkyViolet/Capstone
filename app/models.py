from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    monthly_income = Column(Integer, default=0)
    budget_limit = Column(Integer, default=0)

    expenses = relationship("Expense", back_populates="owner")

class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index=True)
    item_name = Column(String(255), nullable=False)  # 품목명
    amount = Column(Integer, nullable=False)         # 금액
    category = Column(String(100))                   # AI가 분류할 카테고리
    is_ocr = Column(Boolean, default=False)          # 영수증 인식 여부
    receipt_image_path = Column(String(512), nullable=True)  # uploads 기준 상대 경로 (예: receipts/1/uuid.jpg)
    created_at = Column(DateTime, default=datetime.now)
    
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="expenses")