"""名刺画像を読み、氏名や住所に分けたJSONを出す。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from meishi_ocr.pipeline import recognize_card


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="名刺画像を読み取り、氏名・会社・住所などに分けて出力します。")
    parser.add_argument("image", help="名刺画像のパス")
    parser.add_argument("-o", "--output", help="JSONの保存先")
    parser.add_argument("--min-score", type=float, default=0.4, help="この信頼度未満の行は捨てる")
    args = parser.parse_args(argv)

    image_path = Path(args.image)
    if not image_path.is_file():
        print(f"画像が見つかりません: {image_path}", file=sys.stderr)
        return 1

    card = recognize_card(image_path, min_score=args.min_score)
    payload = json.dumps(card, ensure_ascii=False, indent=2)
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
