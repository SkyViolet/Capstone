import os
from pathlib import Path

from google.cloud import vision
from google.auth.exceptions import DefaultCredentialsError


def extract_text_from_image_bytes(image_bytes: bytes) -> str:
    """
    Google Cloud Vision API(document_text_detection)로 이미지에서 텍스트를 읽습니다.
    로컬/서버에 서비스 계정 JSON 경로를 GOOGLE_APPLICATION_CREDENTIALS 로 두어야 합니다.
    """
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        raise RuntimeError(
            "GOOGLE_APPLICATION_CREDENTIALS 가 설정되지 않았습니다. "
            "서비스 계정 JSON 경로를 환경 변수로 지정해 주세요."
        )

    # .env에 넣은 경로가 실제 파일로 존재하는지(상대경로/오타/권한) 빠르게 확인합니다.
    p = Path(cred_path)
    if not p.exists():
        raise RuntimeError(
            f"서비스 계정 JSON 파일을 찾을 수 없습니다: {cred_path}"
        )

    try:
        client = vision.ImageAnnotatorClient()
    except DefaultCredentialsError as e:
        raise RuntimeError(
            "Google 자격증명을 로드하지 못했습니다. "
            "GOOGLE_APPLICATION_CREDENTIALS 경로/파일 내용을 확인해 주세요. "
            f"(원인: {e})"
        ) from e
    image = vision.Image(content=image_bytes)
    response = client.document_text_detection(image=image)

    if response.error.message:
        # 여기 메시지는 보통 'Vision API 미활성화/결제 미연결/권한' 등 Google 쪽 설정 문제입니다.
        raise RuntimeError(response.error.message)

    if response.full_text_annotation and response.full_text_annotation.text:
        return response.full_text_annotation.text.strip()

    # 문서 레이아웃이 약할 때 백업: 일반 TEXT_DETECTION
    response2 = client.text_detection(image=image)
    if response2.error.message:
        raise RuntimeError(response2.error.message)
    texts = response2.text_annotations
    if texts:
        return texts[0].description.strip()
    return ""
