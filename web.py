"""名刺画像をブラウザから読み取るローカル画面。"""

from __future__ import annotations

import base64
import html
import tempfile
from pathlib import Path

from flask import Flask, request

from meishi_ocr.pipeline import recognize_card

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

_FIELDS = (
    ("氏名", "氏名"),
    ("氏名カナ", "氏名カナ"),
    ("ローマ字", "ローマ字"),
    ("会社名", "会社名"),
    ("会社名英語", "会社名英語"),
    ("部署", "部署"),
    ("役職", "役職"),
    ("郵便番号", "郵便番号"),
    ("住所", "住所"),
    ("電話", "電話"),
    ("携帯", "携帯"),
    ("FAX", "FAX"),
    ("メール", "メール"),
    ("URL", "URL"),
    ("未分類", "未分類"),
)
_ALLOWED = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def main() -> None:
    app.run(host="127.0.0.1", port=8765, debug=False)


@app.get("/")
def index():
    return _page()


@app.post("/")
def read_card():
    upload = request.files.get("image")
    if upload is None or not upload.filename:
        return _page(error="画像を選んでください。"), 400
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in _ALLOWED:
        return _page(error="PNG、JPEG、WebP、BMP、TIFF のいずれかを選んでください。"), 400

    data = upload.read()
    if not data:
        return _page(error="空のファイルです。"), 400

    preview = base64.b64encode(data).decode("ascii")
    mime = upload.mimetype or "image/jpeg"
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(data)
            temp_path = Path(handle.name)
        try:
            card = recognize_card(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)
    except Exception as exc:
        return _page(error=f"読み取りに失敗しました: {exc}", preview=preview, mime=mime), 500
    return _page(card=card, preview=preview, mime=mime)


def _page(card: dict | None = None, error: str = "", preview: str = "", mime: str = "") -> str:
    body = ""
    if error:
        body += f'<p class="error">{html.escape(error)}</p>'
    if preview:
        body += f'<img class="preview" alt="読み取った名刺" src="data:{html.escape(mime)};base64,{preview}">'
    if card:
        rows = []
        for key, label in _FIELDS:
            value = card.get(key, "")
            if isinstance(value, list):
                value = "\n".join(value)
            rows.append(
                "<tr>"
                f"<th>{html.escape(label)}</th>"
                f"<td>{html.escape(value) if value else '<span class=\"empty\">—</span>'}</td>"
                "</tr>"
            )
        raw = "\n".join(card.get("読み取り行") or [])
        body += (
            '<table>' + "".join(rows) + "</table>"
            "<details><summary>読み取った行</summary>"
            f"<pre>{html.escape(raw)}</pre></details>"
        )
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>名刺OCR</title>
  <style>
    :root {{ color-scheme: light; }}
    body {{ margin: 0; font-family: "Yu Gothic UI", Meiryo, sans-serif; background: #f4f1ea; color: #1c1915; }}
    main {{ max-width: 880px; margin: 0 auto; padding: 32px 20px 64px; }}
    h1 {{ font-size: 1.6rem; margin-bottom: 0.3rem; }}
    p.lead {{ margin-top: 0; color: #5c564c; }}
    form {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; background: white; padding: 16px; border-radius: 12px; }}
    button {{ background: #1f4b3a; color: white; border: 0; border-radius: 8px; padding: 10px 16px; font: inherit; cursor: pointer; }}
    .error {{ background: #fde8e4; padding: 12px 14px; border-radius: 8px; }}
    .preview {{ display: block; max-width: 100%; margin: 20px 0; background: white; border-radius: 12px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; }}
    th, td {{ text-align: left; vertical-align: top; padding: 10px 14px; border-bottom: 1px solid #eee; white-space: pre-wrap; }}
    th {{ width: 8rem; color: #5c564c; font-weight: 600; }}
    .empty {{ color: #b0a89c; }}
    details {{ margin-top: 16px; }}
    pre {{ background: white; padding: 12px 14px; border-radius: 8px; overflow: auto; }}
  </style>
</head>
<body>
  <main>
    <h1>名刺OCR</h1>
    <p class="lead">画像は手元のPCで読みます。初回だけ文字認識モデルの取得に時間がかかります。</p>
    <form method="post" enctype="multipart/form-data">
      <input type="file" name="image" accept="image/*" required>
      <button type="submit">読み取る</button>
    </form>
    {body}
  </main>
</body>
</html>"""


if __name__ == "__main__":
    main()
