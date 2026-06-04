from datetime import date, datetime, time
from typing import Optional

from sqlalchemy.orm import Session
from passlib.context import CryptContext
from . import models, schemas

# 비밀번호 암호화를 위한 설정 (bcrypt 알고리즘 사용)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 비밀번호를 해시(암호화)하는 함수
def get_password_hash(password):
    return pwd_context.hash(password)

# 이메일로 기존 유저가 있는지 확인하는 함수
def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

# 새로운 유저를 DB에 생성하는 함수
def create_user(db: Session, user: schemas.UserCreate):
    # 1. 비밀번호 암호화
    hashed_password = get_password_hash(user.password)
    
    # 2. DB 모델 객체 생성
    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password
    )
    
    # 3. DB에 저장 및 반영
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_user_expense(db: Session, expense: schemas.ExpenseCreate, user_id: int):
    db_expense = models.Expense(**expense.model_dump(), user_id=user_id)
    
    # DB에 저장
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    
    return db_expense


def create_user_expense_from_receipt(
    db: Session,
    user_id: int,
    item_name: str,
    amount: int,
    category: Optional[str],
    relative_image_path: str,
):
    db_expense = models.Expense(
        item_name=item_name,
        amount=amount,
        category=category,
        is_ocr=True,
        receipt_image_path=relative_image_path,
        user_id=user_id,
    )
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense


def get_user_expenses(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    # 기간 필터: 날짜만 주면 해당 일의 00:00:00 ~ 23:59:59.999999 로 범위를 잡습니다 (created_at 기준).
    q = db.query(models.Expense).filter(models.Expense.user_id == user_id)
    if start_date is not None:
        q = q.filter(models.Expense.created_at >= datetime.combine(start_date, time.min))
    if end_date is not None:
        q = q.filter(models.Expense.created_at <= datetime.combine(end_date, time.max))
    return (
        q.order_by(models.Expense.created_at.desc()).offset(skip).limit(limit).all()
    )

def get_user_expense(db: Session, expense_id: int, user_id: int):
    return (
        db.query(models.Expense)
        .filter(models.Expense.id == expense_id, models.Expense.user_id == user_id)
        .first()
    )

def update_user_expense(
    db: Session, expense: models.Expense, data: schemas.ExpenseUpdate
):
    patch = data.model_dump(exclude_unset=True)
    for field, value in patch.items():
        setattr(expense, field, value)
    db.commit()
    db.refresh(expense)
    return expense


def set_expense_category(db: Session, expense: models.Expense, category: str):
    expense.category = category
    db.commit()
    db.refresh(expense)
    return expense

def delete_user_expense(db: Session, expense: models.Expense):
    db.delete(expense)
    db.commit()

def set_expense_receipt_image(db: Session, expense: models.Expense, relative_path: str):
    expense.receipt_image_path = relative_path
    db.commit()
    db.refresh(expense)
    return expense

def update_user_profile(db: Session, user: models.User, profile_data: schemas.UserProfileUpdate):
    update_data = profile_data.model_dump(exclude_unset=True)

    # 이메일 변경 시 중복 여부 확인
    if "email" in update_data:
        existing_user = get_user_by_email(db, update_data["email"])
        if existing_user and existing_user.id != user.id:
            return None

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user

def update_user_budget(db: Session, user: models.User, budget_data: schemas.UserBudgetUpdate):
    user.monthly_income = budget_data.monthly_income
    user.budget_limit = budget_data.budget_limit
    db.commit()
    db.refresh(user)
    return user