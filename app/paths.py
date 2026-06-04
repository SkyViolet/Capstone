from pathlib import Path

# 프로젝트 루트(capstone/) — 이미지는 static/uploads 아래에만 저장합니다.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "static"
UPLOAD_DIR = STATIC_DIR / "uploads"


def ensure_static_upload_dirs() -> None:
    (UPLOAD_DIR / "receipts").mkdir(parents=True, exist_ok=True)
