import unittest

from meishi_ocr.models import OcrLine
from meishi_ocr.parser import normalize, parse_card, sort_reading_order


def lines(*texts: str) -> list[OcrLine]:
    return [OcrLine(text) for text in texts]


class ParserTests(unittest.TestCase):
    def test_standard_japanese_card(self):
        card = parse_card(
            lines(
                "株式会社サンプル",
                "代表取締役",
                "山田 太郎",
                "ヤマダ タロウ",
                "〒100-0001",
                "東京都千代田区千代田1-1",
                "サンプルビル 5F",
                "TEL 03-1234-5678",
                "FAX 03-1234-5679",
                "携帯 090-1111-2222",
                "taro.yamada@example.co.jp",
                "https://example.co.jp",
            )
        )
        self.assertEqual(card["会社名"], "株式会社サンプル")
        self.assertEqual(card["役職"], "代表取締役")
        self.assertEqual(card["氏名"], "山田 太郎")
        self.assertEqual(card["氏名カナ"], "ヤマダ タロウ")
        self.assertEqual(card["郵便番号"], "100-0001")
        self.assertEqual(card["住所"], "東京都千代田区千代田1-1 サンプルビル 5F")
        self.assertEqual(card["電話"], ["03-1234-5678"])
        self.assertEqual(card["FAX"], ["03-1234-5679"])
        self.assertEqual(card["携帯"], ["090-1111-2222"])
        self.assertEqual(card["メール"], ["taro.yamada@example.co.jp"])
        self.assertEqual(card["URL"], ["https://example.co.jp"])
        self.assertEqual(card["未分類"], [])

    def test_legal_form_merges_with_brand_not_person(self):
        merged = parse_card(lines("株式会社", "サンプル", "山田 太郎"))
        self.assertEqual(merged["会社名"], "株式会社サンプル")
        self.assertEqual(merged["氏名"], "山田 太郎")

        separate = parse_card(lines("株式会社", "山田 太郎", "ヤマダ タロウ"))
        self.assertEqual(separate["会社名"], "株式会社")
        self.assertEqual(separate["氏名"], "山田 太郎")
        self.assertEqual(separate["氏名カナ"], "ヤマダ タロウ")

    def test_title_and_name_on_one_line(self):
        card = parse_card(lines("株式会社サンプル", "代表取締役 山田 太郎", "営業部"))
        self.assertEqual(card["役職"], "代表取締役")
        self.assertEqual(card["氏名"], "山田 太郎")
        self.assertEqual(card["部署"], "営業部")

    def test_title_is_not_department(self):
        card = parse_card(lines("株式会社サンプル", "営業部長", "山田太郎", "第一営業部"))
        self.assertEqual(card["役職"], "営業部長")
        self.assertEqual(card["部署"], "第一営業部")
        self.assertEqual(card["氏名"], "山田太郎")

    def test_postal_and_address_on_one_line(self):
        card = parse_card(lines("〒100-0001 東京都千代田区丸の内1-1-1", "丸の内ビルディング 10階"))
        self.assertEqual(card["郵便番号"], "100-0001")
        self.assertEqual(card["住所"], "東京都千代田区丸の内1-1-1 丸の内ビルディング 10階")

    def test_tel_and_fax_on_one_line(self):
        card = parse_card(lines("TEL: 03-1111-2222  FAX: 03-1111-2223", "山田 太郎"))
        self.assertEqual(card["電話"], ["03-1111-2222"])
        self.assertEqual(card["FAX"], ["03-1111-2223"])

    def test_fullwidth_and_company_mark(self):
        card = parse_card(
            lines(
                "\u3231サンプル",
                "山田 太郎",
                "ＴＥＬ　０３－１２３４－５６７８",
                "\u2121 03-9999-0000",
            )
        )
        self.assertEqual(card["会社名"], "(株)サンプル")
        self.assertEqual(card["氏名"], "山田 太郎")
        self.assertIn("03-1234-5678", card["電話"])
        self.assertIn("03-9999-0000", card["電話"])

    def test_english_card(self):
        card = parse_card(
            lines(
                "Sample Inc.",
                "Sales Manager",
                "Taro Yamada",
                "taro@sample.com",
                "www.sample.com",
            )
        )
        self.assertEqual(card["会社名"], "Sample Inc.")
        self.assertEqual(card["役職"], "Sales Manager")
        self.assertEqual(card["氏名"], "Taro Yamada")
        self.assertEqual(card["メール"], ["taro@sample.com"])
        self.assertEqual(card["URL"], ["https://www.sample.com"])

    def test_company_and_english_name(self):
        card = parse_card(lines("株式会社サンプル", "山田 太郎", "Taro Yamada", "ヤマダタロウ"))
        self.assertEqual(card["氏名"], "山田 太郎")
        self.assertEqual(card["ローマ字"], "Taro Yamada")
        self.assertEqual(card["氏名カナ"], "ヤマダタロウ")

    def test_mobile_without_label_and_free_dial(self):
        card = parse_card(lines("090-1234-5678", "0120-123-456", "山田 太郎"))
        self.assertEqual(card["携帯"], ["090-1234-5678"])
        self.assertEqual(card["電話"], ["0120-123-456"])

    def test_unclassified_logo_text(self):
        card = parse_card(lines("株式会社サンプル", "山田 太郎", "SINCE 1998"))
        self.assertEqual(card["未分類"], ["SINCE 1998"])

    def test_reading_order_uses_boxes(self):
        ordered = sort_reading_order(
            [
                OcrLine("下", x1=10, y1=200, x2=80, y2=240),
                OcrLine("右", x1=200, y1=20, x2=280, y2=60),
                OcrLine("左", x1=10, y1=20, x2=80, y2=60),
            ]
        )
        self.assertEqual([line.text for line in ordered], ["左", "右", "下"])

    def test_postal_symbol_and_fax_misread(self):
        card = parse_card(
            lines(
                "T100-0001",
                "東京都千代田区千代田1-1",
                "FA×03-1234-5679",
                "https:]/example.co.jp",
                "山田 太郎",
            )
        )
        self.assertEqual(card["郵便番号"], "100-0001")
        self.assertEqual(card["住所"], "東京都千代田区千代田1-1")
        self.assertEqual(card["FAX"], ["03-1234-5679"])
        self.assertEqual(card["URL"], ["https://example.co.jp"])
        self.assertEqual(card["氏名"], "山田 太郎")
        self.assertEqual(card["未分類"], [])

    def test_normalize_nfkc(self):
        self.assertEqual(normalize("ＴＥＬ　０３－１"), "TEL 03-1")
        self.assertEqual(normalize("\u3231"), "(株)")


if __name__ == "__main__":
    unittest.main()
