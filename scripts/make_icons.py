# PWA용 PNG 아이콘 생성 스크립트 (1회성 도구)
# iOS는 apple-touch-icon에 SVG를 지원하지 않아 PNG가 필수입니다.
# 실행: venv/Scripts/python scripts/make_icons.py
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent.parent / "frontend" / "public" / "icons"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BG_TOP = (134, 59, 255)      # favicon.svg의 보라(#863bff)
BG_BOTTOM = (94, 20, 220)    # 아래쪽을 살짝 어둡게 — 단색보다 입체감
FG = (255, 255, 255)


def make_icon(size: int, filename: str) -> None:
    img = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(img)

    # 세로 그라디언트 배경 (iOS가 모서리를 자동으로 둥글게 깎으므로 풀블리드 정사각형)
    for y in range(size):
        t = y / max(size - 1, 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM))
        draw.line([(0, y), (size, y)], fill=color)

    # 중앙 ₩ 글리프 — maskable 안전 영역(중앙 80%) 안에 들어가도록 크기를 잡습니다.
    font = None
    for candidate in (r"C:\Windows\Fonts\malgunbd.ttf", r"C:\Windows\Fonts\malgun.ttf",
                      r"C:\Windows\Fonts\arialbd.ttf"):
        try:
            font = ImageFont.truetype(candidate, int(size * 0.52))
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()

    glyph = "₩"  # ₩
    bbox = draw.textbbox((0, 0), glyph, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]), glyph, font=font, fill=FG)

    img.save(OUT_DIR / filename, "PNG")
    print(f"saved {OUT_DIR / filename}")


if __name__ == "__main__":
    make_icon(180, "apple-touch-icon.png")
    make_icon(192, "icon-192.png")
    make_icon(512, "icon-512.png")
