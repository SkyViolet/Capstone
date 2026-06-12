import json
import logging
import os
import re
from dataclasses import dataclass

from google import genai

from .ai_prompt import CATEGORIES

logger = logging.getLogger(__name__)

# gemini-1.5-flash는 Google이 단계적 폐기 중이라 기본값을 2.5-flash로 둡니다.
# 모델 교체가 필요하면 코드 수정 없이 .env의 GEMINI_MODEL만 바꾸면 됩니다.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


@dataclass
class CategorizationResult:
    category: str
    comment: str


def _normalize_category(category: str) -> str:
    category = (category or "").strip()
    if category in CATEGORIES:
        return category
    return "기타"


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    raw = text[start : end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        fixed = re.sub(r"'", '"', raw)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return {}


def _rule_based(item_name: str) -> CategorizationResult:
    text = (item_name or "").lower()
    if any(k in text for k in ["커피", "카페", "스타벅스", "라떼", "아메리카노"]):
        return CategorizationResult("카페·간식", "카페 지출이네요. 홈카페를 활용하면 비용을 줄일 수 있어요.")
    if any(k in text for k in ["버스", "지하철", "택시", "주유", "ktx", "기차"]):
        return CategorizationResult("교통", "교통비 지출입니다. 정기권을 활용하면 절약에 도움이 돼요.")
    if any(k in text for k in ["마트", "편의점", "식당", "치킨", "피자", "밥", "점심", "저녁"]):
        return CategorizationResult("식비", "식비 지출입니다. 직접 요리하면 비용을 아낄 수 있어요.")
    if any(k in text for k in ["넷플릭스", "영화", "공연", "게임", "책"]):
        return CategorizationResult("문화·생활", "문화 생활 지출이에요. 합리적인 여가는 삶의 질을 높여줍니다.")
    if any(k in text for k in ["월세", "관리비", "통신", "인터넷", "핸드폰"]):
        return CategorizationResult("주거·통신", "주거/통신 고정 지출입니다.")
    return CategorizationResult("기타", "지출 내역을 확인했습니다. 소비 패턴을 꾸준히 기록해보세요.")


def categorize_expense_with_llm(prompt: str, item_name: str) -> CategorizationResult:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not api_key:
        logger.warning("GEMINI_API_KEY 미설정 — 규칙 기반 fallback으로 분류합니다.")
        return _rule_based(item_name)

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        content = response.text or ""
    except Exception:
        # 조용히 fallback으로 넘어가면 모델 폐기/쿼터 초과를 영영 모르게 되므로 반드시 로그를 남깁니다.
        logger.exception("Gemini 호출 실패 (model=%s) — 규칙 기반 fallback 사용", GEMINI_MODEL)
        return _rule_based(item_name)

    obj = _extract_json(content)
    if not obj:
        logger.warning(
            "Gemini 응답 JSON 파싱 실패 — 규칙 기반 fallback 사용. 응답 일부: %.200s", content
        )
        return _rule_based(item_name)

    category = _normalize_category(str(obj.get("category", "")))
    comment = str(obj.get("comment", "")).strip() or "지출이 분류되었습니다."
    return CategorizationResult(category=category, comment=comment)
