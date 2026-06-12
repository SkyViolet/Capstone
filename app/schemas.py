from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

# --- 유저 관련 ---
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    monthly_income: int
    budget_limit: int

    class Config:
        from_attributes = True

class UserProfileUpdate(BaseModel):
    email: Optional[EmailStr] = None

class UserBudgetUpdate(BaseModel):
    monthly_income: int = Field(ge=0, description="월 수입은 0 이상이어야 합니다.")
    budget_limit: int = Field(ge=0, description="예산 한도는 0 이상이어야 합니다.")

# --- 지출 내역 관련 ---
class ExpenseBase(BaseModel):
    item_name: str
    amount: int = Field(ge=0)
    category: Optional[str] = None

class ExpenseCreate(ExpenseBase):
    pass

class ExpenseUpdate(BaseModel):
    """부분 수정: 보낸 필드만 갱신합니다."""
    item_name: Optional[str] = None
    amount: Optional[int] = Field(default=None, ge=0)
    category: Optional[str] = None

class ExpenseResponse(ExpenseBase):
    id: int
    created_at: datetime
    user_id: int
    is_ocr: bool = False
    receipt_image_path: Optional[str] = None

    class Config:
        from_attributes = True


class ExpenseFromReceiptResponse(ExpenseResponse):
    """영수증 업로드 + OCR 직후 응답: 디버깅·프롬프트용으로 원문 텍스트를 함께 돌려줍니다."""
    ocr_text: str


class AutoCategorizeResponse(BaseModel):
    expense: ExpenseResponse
    comment: str