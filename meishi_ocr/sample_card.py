"""動作確認用の名刺画像を作る。"""

from __future__ import annotations

from pathlib import Path

_FONT_CANDIDATES = (
    Path(r"C:\Windows\Fonts\YuGothM.ttc"),
    Path(r"C:\Windows\Fonts\meiryo.ttc"),
    Path(r"C:\Windows\Fonts\msgothic.ttc"),
    Path(r"C:\Windows\Fonts\msmincho.ttc"),
)


def find_font() -> Path:
    for path in _FONT_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError("日本語フォントが見つかりません")


def render_sample(path: str | Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    font_path = str(find_font())
    image = Image.new("RGB", (1400, 800), "white")
    draw = ImageDraw.Draw(image)
    rows = (
        (90, 70, 54, "株式会社サンプル"),
        (90, 170, 32, "代表取締役"),
        (90, 230, 48, "山田 太郎"),
        (90, 300, 28, "ヤマダ タロウ"),
        (90, 400, 30, "〒100-0001"),
        (90, 450, 30, "東京都千代田区千代田1-1"),
        (90, 500, 30, "サンプルビル 5F"),
        (90, 580, 30, "TEL 03-1234-5678"),
        (90, 630, 30, "FAX 03-1234-5679"),
        (620, 580, 30, "携帯 090-1111-2222"),
        (90, 700, 30, "taro.yamada@example.co.jp"),
        (760, 700, 30, "https://example.co.jp"),
    )
    for x, y, size, text in rows:
        draw.text((x, y), text, fill="black", font=ImageFont.truetype(font_path, size))
    image.save(destination)
    return destination
