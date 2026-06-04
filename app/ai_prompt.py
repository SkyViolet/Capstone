from textwrap import dedent

from .schemas import ExpenseResponse


CATEGORIES = [
    "식비",
    "카페·간식",
    "교통",
    "문화·생활",
    "주거·통신",
    "기타",
]


def build_expense_categorization_prompt(
    *,
    expense: ExpenseResponse,
    ocr_text: str,
    user_budget_limit: int | None = None,
) -> str:
    category_list = ", ".join(CATEGORIES)

    budget_hint = ""
    if user_budget_limit is not None and user_budget_limit > 0:
        budget_hint = f"\n- 사용자의 월 예산 한도는 약 {user_budget_limit:,}원입니다."

    return dedent(
        f"""
        너는 개인 가계부 앱의 '지출 카테고리 분류기' 역할을 하는 한국어 금융 어시스턴트다.

        [영수증 OCR 원문]
        {ocr_text if ocr_text else "(없음)"}

        [앱이 추출한 정보]
        - 대표 품목/상호명: {expense.item_name}
        - 결제 금액(원): {expense.amount}
        - 현재 설정된 카테고리(있다면): {expense.category or "미설정"}
        - 추천 가능한 카테고리 목록: {category_list}{budget_hint}

        [요청]
        1. 위 정보를 보고 지출의 카테고리를 한글로 1개만 골라라.
        2. 반드시 위의 카테고리 목록 중 하나만 선택해야 한다. 애매하면 "기타"를 선택하라.
        3. 반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 절대 포함하지 마세요.

        {{
          "category": "선택한_카테고리명",
          "comment": "소비 습관에 대한 짧은 한국어 코칭 한두 문장"
        }}
        """
    ).strip()
