import jwt
import uuid
from contextlib import asynccontextmanager
from datetime import date
from typing import List, Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .auth import ALGORITHM, SECRET_KEY, create_access_token
from . import crud, models, schemas
from .ai_prompt import build_expense_categorization_prompt
from .database import engine, ensure_expenses_schema, get_db
from .llm_service import categorize_expense_with_llm
from .ocr_service import extract_text_from_image_bytes
from .paths import STATIC_DIR, UPLOAD_DIR, ensure_static_upload_dirs
from .receipt_parser import parse_receipt_title_and_amount

models.Base.metadata.create_all(bind=engine)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# 업로드 허용 타입 (브라우저/앱에서 흔히 쓰는 영수증 이미지)
_RECEIPT_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_MAX_RECEIPT_BYTES = 10 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_static_upload_dirs()
    ensure_expenses_schema()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://172.31.7.209:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ocr/health")
def ocr_healthcheck():
    """
    배포/로컬에서 OCR 설정이 제대로 되었는지 빠르게 확인합니다.
    - GOOGLE_APPLICATION_CREDENTIALS 존재 여부
    - JSON 파일 경로 존재 여부
    """
    import os
    from pathlib import Path

    cred = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    return {
        "GOOGLE_APPLICATION_CREDENTIALS": cred,
        "exists": bool(cred) and Path(cred).exists(),
    }

@app.post("/signup", response_model=schemas.UserResponse)
def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # 1. 이미 등록된 이메일인지 확인
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")
    
    # 2. 유저 생성 후 결과 반환
    return crud.create_user(db=db, user=user)

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # 1. 이메일 확인 (OAuth2 규격상 이메일이 'username' 필드로 들어옵니다)
    user = crud.get_user_by_email(db, email=form_data.username)
    
    # 2. 유저가 없거나 비밀번호가 틀리면 에러 발생
    if not user or not crud.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="이메일이나 비밀번호가 틀렸습니다.")
    
    # 3. 로그인 성공 시 JWT 토큰 발급
    access_token = create_access_token(data={"sub": user.email})
    
    # 4. 토큰 반환 (이 규격을 맞춰야 Swagger UI가 토큰을 인식합니다)
    return {"access_token": access_token, "token_type": "bearer"}



def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="입장권(토큰)이 유효하지 않거나 만료되었습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 1. 토큰 해독 (암호 풀기)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # 2. 토큰 안에 숨겨둔 이메일(sub) 꺼내기
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
            
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="토큰이 만료되었습니다. 다시 로그인해주세요.")
    except jwt.InvalidTokenError:
        raise credentials_exception

    # 3. DB에서 이메일로 실제 유저 정보 찾기
    user = crud.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
        
    return user

@app.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    # Depends(get_current_user)가 알아서 토큰 검사 -> 유저 찾기 -> current_user에 쏙 넣어줍니다.
    return current_user

@app.patch("/users/me/profile", response_model=schemas.UserResponse)
def update_my_profile(
    profile_data: schemas.UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    updated_user = crud.update_user_profile(db=db, user=current_user, profile_data=profile_data)
    if updated_user is None:
        raise HTTPException(status_code=400, detail="이미 사용 중인 이메일입니다.")
    return updated_user

@app.patch("/users/me/budget", response_model=schemas.UserResponse)
def update_my_budget(
    budget_data: schemas.UserBudgetUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.update_user_budget(db=db, user=current_user, budget_data=budget_data)

@app.post("/expenses/from-receipt", response_model=schemas.ExpenseFromReceiptResponse)
async def create_expense_from_receipt(
    file: UploadFile = File(..., description="영수증 이미지 (JPEG/PNG/WebP)"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    이미지를 static/uploads/receipts/{user_id}/ 아래에 저장한 뒤 Vision OCR로 텍스트를 읽고,
    간단한 규칙으로 금액·품목 후보를 채워 지출 한 건을 만듭니다.
    브라우저에서 파일 URL: /static/ + DB의 receipt_image_path 값.
    """
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in _RECEIPT_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="지원하는 이미지 형식은 JPEG, PNG, WebP 입니다.",
        )

    body = await file.read()
    if len(body) == 0:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    if len(body) > _MAX_RECEIPT_BYTES:
        raise HTTPException(status_code=400, detail="파일 크기는 10MB 이하여야 합니다.")

    ensure_static_upload_dirs()
    ext = _RECEIPT_CONTENT_TYPES[content_type]
    fname = f"{uuid.uuid4().hex}{ext}"
    user_receipt_dir = UPLOAD_DIR / "receipts" / str(current_user.id)
    user_receipt_dir.mkdir(parents=True, exist_ok=True)
    dest_path = user_receipt_dir / fname
    dest_path.write_bytes(body)

    # DB에는 static 폴더 기준 상대 경로만 넣어 /static/... 으로 서빙합니다.
    relative_path = f"uploads/receipts/{current_user.id}/{fname}"

    try:
        ocr_text = extract_text_from_image_bytes(body)
    except RuntimeError as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=str(e)) from e

    title, amount = parse_receipt_title_and_amount(ocr_text)
    try:
        expense = crud.create_user_expense_from_receipt(
            db=db,
            user_id=current_user.id,
            item_name=title,
            amount=amount,
            category="OCR",
            relative_image_path=relative_path,
        )
    except Exception as e:
        # DB 스키마 불일치(컬럼 누락)나 연결 문제 등은 여기서 500으로 뻗지 않게 처리합니다.
        dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=503,
            detail=f"DB 저장 중 오류가 발생했습니다: {e}",
        ) from e
    base = schemas.ExpenseResponse.model_validate(expense)
    return schemas.ExpenseFromReceiptResponse(
        **base.model_dump(),
        ocr_text=ocr_text,
    )


@app.post("/expenses", response_model=schemas.ExpenseResponse)
def create_expense_for_user(
    expense: schemas.ExpenseCreate, 
    db: Session = Depends(get_db),
    # 📌 핵심: 이 코드가 '자물쇠(토큰)'를 검사하고, 통과하면 로그인한 유저 정보를 current_user에 담아줍니다.
    current_user: models.User = Depends(get_current_user)
):
    # crud 함수에 현재 로그인한 유저의 ID(current_user.id)를 함께 넘겨줍니다.
    return crud.create_user_expense(db=db, expense=expense, user_id=current_user.id)

@app.get("/expenses", response_model=List[schemas.ExpenseResponse])
def read_user_expenses(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = Query(
        None, description="기간 시작일(포함), 지출 created_at 기준"
    ),
    end_date: Optional[date] = Query(
        None, description="기간 종료일(포함), 지출 created_at 기준"
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date는 end_date보다 늦을 수 없습니다.",
        )
    expenses = crud.get_user_expenses(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
    )
    return expenses

@app.get("/expenses/{expense_id}", response_model=schemas.ExpenseResponse)
def read_user_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    expense = crud.get_user_expense(db, expense_id=expense_id, user_id=current_user.id)
    if expense is None:
        raise HTTPException(status_code=404, detail="지출 내역을 찾을 수 없습니다.")
    return expense

@app.patch("/expenses/{expense_id}", response_model=schemas.ExpenseResponse)
def update_user_expense(
    expense_id: int,
    body: schemas.ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    expense = crud.get_user_expense(db, expense_id=expense_id, user_id=current_user.id)
    if expense is None:
        raise HTTPException(status_code=404, detail="지출 내역을 찾을 수 없습니다.")
    if not body.model_dump(exclude_unset=True):
        raise HTTPException(
            status_code=400,
            detail="수정할 필드를 하나 이상 보내주세요.",
        )
    return crud.update_user_expense(db=db, expense=expense, data=body)

@app.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    expense = crud.get_user_expense(db, expense_id=expense_id, user_id=current_user.id)
    if expense is None:
        raise HTTPException(status_code=404, detail="지출 내역을 찾을 수 없습니다.")
    crud.delete_user_expense(db=db, expense=expense)
    return None


@app.get(
    "/expenses/{expense_id}/llm-prompt",
    response_model=schemas.LlmPromptPreview,
)
def get_expense_llm_prompt(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    특정 지출 건에 대해 '지출 카테고리 자동 분류'에 사용할 LLM 프롬프트를 미리봅니다.

    실제 EEVE-Korean 호출은 아직 붙이지 않고, 우선 프롬프트 내용을 눈으로 검증하는 단계입니다.
    """
    expense = crud.get_user_expense(db, expense_id=expense_id, user_id=current_user.id)
    if expense is None:
        raise HTTPException(status_code=404, detail="지출 내역을 찾을 수 없습니다.")

    expense_schema = schemas.ExpenseResponse.model_validate(expense)
    # OCR 기반 지출이면 원문을, 아니면 기본 텍스트만 사용
    ocr_text = ""
    if expense.is_ocr and expense.receipt_image_path:
        # 현재는 OCR 원문을 별도로 저장하지 않으므로, 간단히 품목/금액 위주로 프롬프트를 만듭니다.
        ocr_text = f"{expense_schema.item_name} / {expense_schema.amount}원 결제 영수증"

    prompt = build_expense_categorization_prompt(
        expense=expense_schema,
        ocr_text=ocr_text,
        user_budget_limit=current_user.budget_limit,
    )
    return schemas.LlmPromptPreview(
        model="EEVE-Korean-Instruct-10.8B-v1.0",
        prompt=prompt,
    )


@app.post(
    "/expenses/{expense_id}/auto-categorize",
    response_model=schemas.AutoCategorizeResponse,
)
def auto_categorize_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    지출 1건을 LLM(미설정 시 규칙기반 fallback)으로 자동 분류하고 DB category를 갱신합니다.
    """
    expense = crud.get_user_expense(db, expense_id=expense_id, user_id=current_user.id)
    if expense is None:
        raise HTTPException(status_code=404, detail="지출 내역을 찾을 수 없습니다.")

    expense_schema = schemas.ExpenseResponse.model_validate(expense)
    ocr_text = ""
    if expense.is_ocr and expense.receipt_image_path:
        ocr_text = f"{expense_schema.item_name} / {expense_schema.amount}원 결제 영수증"

    prompt = build_expense_categorization_prompt(
        expense=expense_schema,
        ocr_text=ocr_text,
        user_budget_limit=current_user.budget_limit,
    )
    result = categorize_expense_with_llm(prompt=prompt, item_name=expense_schema.item_name)

    updated = crud.set_expense_category(db=db, expense=expense, category=result.category)
    return schemas.AutoCategorizeResponse(
        expense=schemas.ExpenseResponse.model_validate(updated),
        comment=result.comment,
    )