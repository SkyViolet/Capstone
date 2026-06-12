import os
import jwt
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .database import get_db

load_dotenv()

# 기본값(fallback) 없이 필수로 둡니다 — .env 누락 시 약한 키로 몰래 돌지 않고 시작 단계에서 바로 실패시킵니다.
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY 환경 변수가 설정되지 않았습니다. .env 파일을 확인해주세요.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# 비밀번호 해싱(bcrypt)도 인증 책임이므로 crud.py가 아닌 여기서 관리합니다.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# JWT 토큰을 만들어주는 함수
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    # 비밀키를 이용해 데이터를 암호화하여 토큰 생성
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    # 순환 import 방지를 위해 함수 내부에서 import 합니다 (crud는 더 이상 auth를 참조하지 않지만 안전하게 유지).
    from . import crud

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
