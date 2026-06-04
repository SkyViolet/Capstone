import re


def parse_receipt_title_and_amount(ocr_text: str) -> tuple[str, int]:
    """
    OCR 전체 텍스트에서 품목명(첫 줄 요약)과 금액 후보를 추출합니다.
    한국 영수증은 '합계/총액/결제' 등 키워드 줄의 숫자를 우선합니다.
    """
    lines = [ln.strip() for ln in ocr_text.splitlines() if ln.strip()]
    title = (lines[0][:100] if lines else "영수증") or "영수증"
    amount = 0
    keywords = ("합계", "총액", "결제", "판매", "금액", "받을")

    for line in reversed(lines):
        if any(k in line for k in keywords):
            for n in re.findall(r"[\d,]+", line.replace(" ", "")):
                v = int(n.replace(",", ""))
                if v > amount:
                    amount = v
            if amount > 0:
                break

    if amount == 0:
        for line in reversed(lines):
            for n in re.findall(r"[\d,]+", line.replace(" ", "")):
                v = int(n.replace(",", ""))
                if 0 < v <= 50_000_000:
                    amount = max(amount, v)

    return title, amount
