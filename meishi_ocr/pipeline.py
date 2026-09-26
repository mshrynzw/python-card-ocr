"""文字起こしと項目分けをつなぐ。"""

from __future__ import annotations

from pathlib import Path

from meishi_ocr.engine import recognize
from meishi_ocr.parser import parse_card


def recognize_card(image_path: str | Path, min_score: float = 0.4) -> dict:
    lines = recognize(image_path, min_score=min_score)
    return parse_card(lines)
