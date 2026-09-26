from dataclasses import dataclass


@dataclass
class OcrLine:
    """OCRが返した1行。座標が無いときは 0 のままでよい。"""

    text: str
    score: float = 1.0
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)
