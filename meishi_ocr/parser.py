"""OCR行を、氏名・会社・住所などの項目へ振り分ける。

文字の読み取りはしない。渡された行の並びと文言だけを見る。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from meishi_ocr.models import OcrLine

KANJI = r"\u4e00-\u9fff\u3400-\u4dbf々〆"

PREFECTURES = (
    "北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|"
    "茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|"
    "新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|"
    "滋賀県|京都府|大阪府|兵庫県|奈良県|和歌山県|"
    "鳥取県|島根県|岡山県|広島県|山口県|"
    "徳島県|香川県|愛媛県|高知県|"
    "福岡県|佐賀県|長崎県|熊本県|大分県|宮崎県|鹿児島県|沖縄県"
)

_PREF_RE = re.compile(PREFECTURES)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>]+", re.IGNORECASE)
_DOMAIN_RE = re.compile(
    r"(?<![@/\w.])((?:[a-z0-9-]+\.)+(?:co\.jp|ne\.jp|or\.jp|ac\.jp|go\.jp|com|net|jp))(?![\w.])",
    re.IGNORECASE,
)
_POSTAL_T_RE = re.compile(r"(?:^|\s)[T〒]\s*(\d{3})\s*[-‐ー−－]?\s*(\d{4})(?!\d)")
_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"((?:\+81[\s\-－ー]*)?"
    r"(?:\(\d{1,4}\)|\d{1,4})"
    r"(?:[\-－ー]\d{2,4}){1,3})"
    r"(?!\d)"
)
_PHONE_SPACE_RE = re.compile(r"(?<!\d)(\d{2,4}(?: \d{2,4}){2,3})(?!\d)")
_LABEL_BEFORE_RE = re.compile(
    r"(ファックス|ファクス|FAX|携帯電話|携帯|MOBILE|TEL|電話|℡)\s*[:：]?\s*$",
    re.IGNORECASE,
)
_LABEL_WORD_RE = re.compile(
    r"(?:^|\s)(?:TEL|FAX|Email|E-mail|Mail|URL|Web|HP|電話|携帯|携帯電話|メール|ファックス|ファクス|住所)\s*[:：]?",
    re.IGNORECASE,
)
_COMPANY_MARK_RE = re.compile(
    r"株式会社|有限会社|合同会社|合名会社|合資会社|"
    r"一般社団法人|一般財団法人|公益社団法人|公益財団法人|"
    r"医療法人|社会医療法人|学校法人|社会福祉法人|"
    r"\(株\)|\(有\)|"
    r"\b(?:Inc\.?|Ltd\.?|LLC|GmbH|Corp(?:oration)?\.?|Co\.,?\s*Ltd\.?)\b",
    re.IGNORECASE,
)
_JP_COMPANY_RE = re.compile(r"株式会社|有限会社|合同会社|合名会社|合資会社|\(株\)|\(有\)")
_LEGAL_ONLY = {
    "株式会社",
    "有限会社",
    "合同会社",
    "合名会社",
    "合資会社",
    "(株)",
    "(有)",
    "Inc.",
    "Inc",
    "Ltd.",
    "Ltd",
}
_PREFIX_LEGAL = {"株式会社", "有限会社", "合同会社", "合名会社", "合資会社", "(株)", "(有)"}
_ORG_HINT_RE = re.compile(
    r"(商事|工業|産業|製作|建設|不動産|銀行|製薬|電機|システム|サービス|クリニック|ホールディング)"
)
_NOT_NAME = {
    "営業",
    "総務",
    "企画",
    "開発",
    "技術",
    "人事",
    "経理",
    "広報",
    "本社",
    "支社",
    "本部",
    "研究所",
    "東京",
    "大阪",
    "名古屋",
    "横浜",
    "本店",
}
_TITLE_RE = re.compile(
    r"^(?:"
    r"代表取締役社長|代表取締役|取締役社長|取締役|執行役員|"
    r"社長|副社長|専務取締役|常務取締役|専務|常務|"
    r"会長|副会長|所長|店長|校長|理事長|理事|監査役|相談役|"
    r".{0,12}部長|部長|次長|.{0,12}課長|課長|係長|主任|主査|"
    r".{0,12}マネージャ[ー]?|"
    r"(?:[A-Za-z]+\s+){0,3}(?:CEO|CTO|CFO|COO|President|Director|Manager)"
    r")$",
    re.IGNORECASE,
)
_TITLE_SPLIT_RE = re.compile(
    r"^(?P<title>"
    r"代表取締役社長|代表取締役|取締役社長|取締役|執行役員|"
    r"社長|副社長|専務取締役|常務取締役|専務|常務|"
    r"会長|副会長|.{0,8}所長|店長|"
    r".{1,12}部長|次長|.{1,12}課長|課長|係長|主任|"
    r".{0,12}マネージャ[ー]?"
    r")"
    r"[\s/:：|・]+"
    r"(?P<rest>.+)$"
)
_DEPT_RE = re.compile(
    r"^.{1,24}(?:事業部|本部|部|課|室|局|グループ|センター|支店|支社|営業所)$"
)
_DEPT_TAIL_RE = re.compile(
    r"^(?P<body>.+?)\s+(?P<dept>.{1,24}(?:事業部|本部|部|課|室|支店|支社|営業所))$"
)
_POSTAL_MARKED_RE = re.compile(r"〒\s*(\d{3})\s*[-‐ー−－]?\s*(\d{4})")
_POSTAL_BARE_RE = re.compile(r"(?<!\d)(\d{3})[-‐ー−－](\d{4})(?!\d)")


@dataclass
class _Row:
    text: str
    height: float
    index: int
    postal: str = ""
    consumed: bool = False


def empty_card() -> dict:
    return {
        "氏名": "",
        "氏名カナ": "",
        "ローマ字": "",
        "会社名": "",
        "会社名英語": "",
        "部署": "",
        "役職": "",
        "郵便番号": "",
        "住所": "",
        "電話": [],
        "携帯": [],
        "FAX": [],
        "メール": [],
        "URL": [],
        "未分類": [],
        "読み取り行": [],
    }


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\u3000", " ")
    text = re.sub(r"FA[×✕✗]", "FAX", text, flags=re.IGNORECASE)
    text = re.sub(r"(https?):\]/", r"\1://", text, flags=re.IGNORECASE)
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


def sort_reading_order(lines: list[OcrLine]) -> list[OcrLine]:
    """横書きは上から下・左から右。縦書きが大半なら右の列から読む。"""
    usable = [line for line in lines if normalize(line.text)]
    if not usable:
        return []
    if not any(line.width > 0 or line.height > 0 for line in usable):
        return usable

    vertical = sum(1 for line in usable if line.height > line.width * 1.4 and line.width > 0)
    if vertical >= max(1, len(usable) * 0.6):
        return sorted(usable, key=lambda line: (-line.x1, line.y1))

    ordered = sorted(usable, key=lambda line: ((line.y1 + line.y2) / 2, line.x1))
    rows: list[list[OcrLine]] = []
    for line in ordered:
        cy = (line.y1 + line.y2) / 2
        height = max(line.height, 1.0)
        if rows:
            ref = rows[-1][0]
            ref_cy = (ref.y1 + ref.y2) / 2
            ref_h = max(ref.height, 1.0)
            if abs(cy - ref_cy) <= max(height, ref_h) * 0.6:
                rows[-1].append(line)
                continue
        rows.append([line])

    result: list[OcrLine] = []
    for row in rows:
        row.sort(key=lambda line: line.x1)
        result.extend(row)
    return result


def parse_card(lines: list[OcrLine]) -> dict:
    ordered = sort_reading_order(lines)
    card = empty_card()
    card["読み取り行"] = [normalize(line.text) for line in ordered]

    emails: list[str] = []
    urls: list[str] = []
    phones: list[tuple[str, str]] = []
    rows: list[_Row] = []

    for index, line in enumerate(ordered):
        residue, found = _extract_contacts(normalize(line.text))
        emails.extend(found["emails"])
        urls.extend(found["urls"])
        phones.extend(found["phones"])
        row = _Row(text=residue, height=line.height, index=index, postal=found["postal"])
        if not row.text and not row.postal:
            row.consumed = True
        rows.append(row)

    _merge_split_companies(rows)

    companies_ja: list[tuple[float, int, str]] = []
    companies_en: list[tuple[float, int, str]] = []
    titles: list[str] = []
    departments: list[str] = []

    for row in rows:
        if row.consumed or not row.text:
            continue
        company_body, dept = _split_company(row.text)
        if company_body:
            target = companies_ja if _JP_COMPANY_RE.search(company_body) else companies_en
            target.append((row.height, -row.index, company_body))
            if dept:
                departments.append(dept)
            row.consumed = True
            continue
        title, rest = _split_title_name(row.text)
        if title and rest:
            titles.append(title)
            row.text = rest
            continue
        if _TITLE_RE.fullmatch(row.text):
            titles.append(row.text)
            row.consumed = True
            continue
        if _DEPT_RE.fullmatch(row.text):
            departments.append(row.text)
            row.consumed = True

    address_parts: list[str] = []
    postals: list[str] = []
    collecting = False
    for row in rows:
        if row.postal:
            postals.append(row.postal)
        if row.consumed or not row.text:
            continue
        if is_address_start(row.text):
            collecting = True
            address_parts.append(row.text)
            row.consumed = True
            continue
        if collecting and is_address_continuation(row.text):
            address_parts.append(row.text)
            row.consumed = True
            continue
        if collecting:
            collecting = False

    company_found = bool(companies_ja or companies_en)
    kana = _take_kana(rows, company_found)
    name, romaji = _take_names(rows)

    if companies_ja:
        card["会社名"] = _best(companies_ja)
        if companies_en:
            card["会社名英語"] = _best(companies_en)
    elif companies_en:
        card["会社名"] = _best(companies_en)

    card["氏名"] = name
    card["氏名カナ"] = kana
    card["ローマ字"] = romaji
    card["部署"] = " ".join(_dedupe(departments))
    card["役職"] = " ".join(_dedupe(titles))
    card["郵便番号"] = postals[0] if postals else ""
    card["住所"] = re.sub(r"\s+", " ", " ".join(address_parts)).strip()
    card["メール"] = _dedupe(emails)
    card["URL"] = _dedupe(urls)

    for kind, number in phones:
        bucket = {"tel": "電話", "mobile": "携帯", "fax": "FAX"}[kind]
        if number not in card[bucket]:
            card[bucket].append(number)

    card["未分類"] = [row.text for row in rows if not row.consumed and row.text]
    return card


def is_address_start(text: str) -> bool:
    if _PREF_RE.search(text):
        return True
    return bool(re.search(r"\d", text) and re.search(r"(丁目|番地|番|号|郡|[市区町村])", text))


def is_address_continuation(text: str) -> bool:
    if is_address_start(text):
        return True
    if re.search(r"(ビル|マンション|タワー|ハイツ|コーポ|号室|階)", text):
        return True
    if re.fullmatch(r"\d{1,2}\s*[Ff]", text):
        return True
    return re.fullmatch(r"[\d\-]+", text) is not None


def _extract_contacts(text: str) -> tuple[str, dict]:
    spans: list[tuple[int, int]] = []
    emails: list[str] = []
    urls: list[str] = []
    phones: list[tuple[str, str]] = []

    for match in _EMAIL_RE.finditer(text):
        emails.append(match.group())
        spans.append(match.span())

    for match in _URL_RE.finditer(text):
        if _overlaps(match.span(), spans):
            continue
        urls.append(_normalize_url(match.group().rstrip(".,)、。)")))
        spans.append(match.span())

    for match in _DOMAIN_RE.finditer(text):
        if _overlaps(match.span(), spans):
            continue
        urls.append(_normalize_url(match.group(1)))
        spans.append(match.span())

    for pattern in (_PHONE_RE, _PHONE_SPACE_RE):
        pos = 0
        while pos < len(text):
            match = pattern.search(text, pos)
            if not match:
                break
            if _overlaps(match.span(1), spans):
                pos = match.end()
                continue
            parsed = _consume_phone(match.group(1))
            if not parsed:
                pos = match.start(1) + 1
                continue
            formatted, rel_end = parsed
            start = match.start(1)
            end = start + rel_end
            window = text[max(0, start - 16) : start]
            label_match = _LABEL_BEFORE_RE.search(window)
            kind = _phone_kind(label_match.group(1) if label_match else "", formatted)
            label_start = max(0, start - 16) + label_match.start() if label_match else start
            phones.append((kind, formatted))
            spans.append((label_start, end))
            pos = end

    residue = _blank_spans(text, spans)
    residue = _LABEL_WORD_RE.sub(" ", residue)
    residue = re.sub(r"\s+", " ", residue).strip(" -:：|・")
    postal, residue = _take_postal(residue)
    residue = re.sub(r"\s+", " ", residue).strip(" -:：|・")
    return residue, {"emails": emails, "urls": urls, "phones": phones, "postal": postal}


def _take_postal(text: str) -> tuple[str, str]:
    match = _POSTAL_MARKED_RE.search(text)
    if not match:
        # 〒 は T と読まれることが多い。
        match = _POSTAL_T_RE.search(text)
    if not match:
        bare = _POSTAL_BARE_RE.search(text)
        if bare and (_PREF_RE.search(text) or text.strip() == bare.group(0)):
            match = bare
    if not match:
        return "", text
    code = f"{match.group(1)}-{match.group(2)}"
    rest = f"{text[: match.start()]} {text[match.end() :]}"
    return code, re.sub(r"\s+", " ", rest).strip()


def _consume_phone(raw: str) -> tuple[str, int] | None:
    groups = list(re.finditer(r"\d+", raw))
    has_country = raw.lstrip().startswith("+81") or raw.lstrip().startswith("81-") or raw.lstrip().startswith("81 ")
    for count in range(len(groups), 1, -1):
        used = groups[:count]
        digits = "".join(group.group() for group in used)
        if has_country and digits.startswith("81"):
            digits = "0" + digits[2:]
        if _valid_phone_digits(digits):
            return _format_phone(digits), used[-1].end()
    return None


def _valid_phone_digits(digits: str) -> bool:
    if not digits.startswith("0"):
        return False
    if len(digits) == 10:
        return True
    if len(digits) == 11 and digits[:3] in {"070", "080", "090", "050"}:
        return True
    if len(digits) == 11 and digits[:2] not in {"03", "06"}:
        return True
    return False


def _format_phone(digits: str) -> str:
    if digits.startswith(("070", "080", "090", "050")) and len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    if digits.startswith(("0120", "0800")) and len(digits) == 10:
        return f"{digits[:4]}-{digits[4:7]}-{digits[7:]}"
    if len(digits) == 10 and digits[:2] in {"03", "06"}:
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    return digits


def _phone_kind(label: str, formatted: str) -> str:
    folded = label.upper()
    if "FAX" in folded or "ファックス" in label or "ファクス" in label:
        return "fax"
    if "携帯" in label or "MOBILE" in folded:
        return "mobile"
    if formatted.startswith(("070-", "080-", "090-")):
        return "mobile"
    return "tel"


def _normalize_url(url: str) -> str:
    url = url.strip()
    if re.match(r"https?://", url, re.IGNORECASE):
        return url
    return "https://" + url


def _overlaps(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(not (end <= old_start or start >= old_end) for old_start, old_end in spans)


def _blank_spans(text: str, spans: list[tuple[int, int]]) -> str:
    chars = list(text)
    for start, end in spans:
        for index in range(max(0, start), min(end, len(chars))):
            chars[index] = " "
    return "".join(chars)


def _merge_split_companies(rows: list[_Row]) -> None:
    for index, row in enumerate(rows):
        if row.consumed or row.text not in _LEGAL_ONLY:
            continue
        for other_index in (index + 1, index - 1):
            if not 0 <= other_index < len(rows):
                continue
            other = rows[other_index]
            if other.consumed or not other.text or other.text in _LEGAL_ONLY:
                continue
            if _looks_like_person(other.text) or _TITLE_RE.fullmatch(other.text) or _DEPT_RE.fullmatch(other.text):
                continue
            if other.postal or is_address_start(other.text):
                continue
            if row.text in _PREFIX_LEGAL:
                other.text = f"{row.text}{other.text}"
            else:
                other.text = f"{other.text} {row.text}".strip()
            other.height = max(other.height, row.height)
            row.text = ""
            row.consumed = True
            break


def _looks_like_person(text: str) -> bool:
    if re.fullmatch(r"[ァ-ヴー]{1,8}[\s・][ァ-ヴー]{1,8}", text):
        return True
    if re.fullmatch(rf"[{KANJI}]{{1,4}}\s+[{KANJI}]{{1,5}}", text):
        return True
    if re.fullmatch(r"[A-Za-z][A-Za-z.'\-]+\s+[A-Za-z][A-Za-z.'\-]+", text):
        return True
    if re.fullmatch(rf"[{KANJI}]{{2,4}}", text) and text not in _NOT_NAME and not _ORG_HINT_RE.search(text):
        return True
    return False


def _split_company(text: str) -> tuple[str, str]:
    if not _COMPANY_MARK_RE.search(text):
        return "", ""
    tail = _DEPT_TAIL_RE.fullmatch(text)
    if tail and _COMPANY_MARK_RE.search(tail.group("body")):
        return tail.group("body").strip(), tail.group("dept").strip()
    return text, ""


def _split_title_name(text: str) -> tuple[str, str]:
    match = _TITLE_SPLIT_RE.fullmatch(text)
    if not match:
        return "", ""
    rest = match.group("rest").strip()
    if _looks_like_person(rest) or re.fullmatch(r"[ァ-ヴー\s・]{2,20}", rest):
        return match.group("title").strip(), rest
    return "", ""


def _take_kana(rows: list[_Row], company_found: bool) -> str:
    spaced = [row for row in rows if not row.consumed and re.fullmatch(r"[ァ-ヴー]+[\s・][ァ-ヴー]+", row.text)]
    if spaced:
        best = max(spaced, key=lambda row: (row.height, -row.index))
        best.consumed = True
        return best.text
    if not company_found:
        return ""
    plain = [row for row in rows if not row.consumed and re.fullmatch(r"[ァ-ヴー]{3,16}", row.text)]
    if not plain:
        return ""
    best = max(plain, key=lambda row: (row.height, -row.index))
    best.consumed = True
    return best.text


def _take_names(rows: list[_Row]) -> tuple[str, str]:
    kanji: list[tuple[int, float, int, _Row]] = []
    romaji: list[tuple[float, int, _Row]] = []
    for row in rows:
        if row.consumed or not row.text:
            continue
        rank = _kanji_name_rank(row.text)
        if rank:
            kanji.append((rank, row.height, -row.index, row))
        elif re.fullmatch(r"[A-Za-z][A-Za-z.'\-]+(?:\s+[A-Za-z][A-Za-z.'\-]+){1,2}", row.text):
            romaji.append((row.height, -row.index, row))

    name = ""
    latin = ""
    if kanji:
        chosen = max(kanji)[3]
        name = chosen.text
        chosen.consumed = True
    if romaji:
        chosen = max(romaji)[2]
        chosen.consumed = True
        if name:
            latin = chosen.text
        else:
            name = chosen.text
    return name, latin


def _kanji_name_rank(text: str) -> int:
    if text in _NOT_NAME:
        return 0
    if re.fullmatch(rf"[{KANJI}]{{1,4}}\s+[{KANJI}]{{1,5}}", text):
        return 3
    if re.fullmatch(rf"[{KANJI}]{{2,4}}", text):
        return 2
    return 0


def _best(items: list[tuple[float, int, str]]) -> str:
    return max(items)[2]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
