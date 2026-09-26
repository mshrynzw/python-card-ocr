"""PaddleOCRで名刺画像から行を取り出す。項目の意味づけはしない。"""

from __future__ import annotations

import os
from pathlib import Path

# Windows の CPU 版 Paddle は oneDNN 経路で落ちることがある。
# paddlex は import 時にこの値を読むので、import より前に置く。
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

from meishi_ocr.models import OcrLine

# 名刺は日本語と、メール・URL・FAX などの英数字が混ざる。
# PP-OCRv5 はその両方を1つのモデルで読む。日本語専用の v3 は @ や FAX を別の文字にしやすい。
RECOGNITION_MODEL = "PP-OCRv5_mobile_rec"

_engine = None


def recognize(image_path: str | Path, min_score: float = 0.4) -> list[OcrLine]:
    image = _load_bgr(image_path)
    raw = get_engine().predict(image)
    lines: list[OcrLine] = []
    for item in list(raw):
        payload = _payload(item)
        texts = list(payload.get("rec_texts") or [])
        scores = list(payload.get("rec_scores") or [])
        boxes = payload.get("rec_boxes")
        polys = payload.get("rec_polys")
        for index, text in enumerate(texts):
            score = float(scores[index]) if index < len(scores) else 1.0
            if score < min_score or not str(text).strip():
                continue
            x1, y1, x2, y2 = _box(boxes, polys, index)
            lines.append(OcrLine(text=str(text), score=score, x1=x1, y1=y1, x2=x2, y2=y2))
    return lines


def get_engine():
    global _engine
    if _engine is None:
        from paddleocr import PaddleOCR

        _engine = PaddleOCR(
            text_recognition_model_name=RECOGNITION_MODEL,
            use_doc_orientation_classify=True,
            use_doc_unwarping=False,
            use_textline_orientation=True,
            device="cpu",
        )
    return _engine


def _load_bgr(image_path: str | Path):
    import numpy as np
    from PIL import Image

    image = Image.open(Path(image_path)).convert("RGB")
    # PaddleOCR は OpenCV と同じ BGR 配列を受け取る。
    return np.array(image)[:, :, ::-1]


def _payload(item) -> dict:
    if isinstance(item, dict):
        inner = item.get("res", item)
        return inner if isinstance(inner, dict) else item

    json_attr = getattr(item, "json", None)
    if json_attr is not None:
        data = json_attr() if callable(json_attr) else json_attr
        if isinstance(data, str):
            import json

            data = json.loads(data)
        if isinstance(data, dict):
            inner = data.get("res", data)
            return inner if isinstance(inner, dict) else data

    if hasattr(item, "keys"):
        try:
            if "rec_texts" in item:
                return {key: item[key] for key in item.keys()}
            if "res" in item and isinstance(item["res"], dict):
                return item["res"]
        except Exception:
            return {}
    return {}


def _box(boxes, polys, index: int) -> tuple[float, float, float, float]:
    source = boxes if boxes is not None else polys
    if source is None:
        return (0.0, 0.0, 0.0, 0.0)
    try:
        box = source[index]
    except Exception:
        return (0.0, 0.0, 0.0, 0.0)
    values = box.tolist() if hasattr(box, "tolist") else list(box)
    if len(values) == 4 and not isinstance(values[0], (list, tuple)):
        x1, y1, x2, y2 = values
        return float(x1), float(y1), float(x2), float(y2)
    xs = [float(point[0]) for point in values]
    ys = [float(point[1]) for point in values]
    return min(xs), min(ys), max(xs), max(ys)
