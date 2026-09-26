# python-card-ocr

名刺の画像を手元の PC で読み、氏名・会社・住所・電話・メールなどに分けて出します。文字起こしと項目の判断は別々で、項目分けに学習は使いません。画像も結果も外部へ送りません。

## 使い方・動作環境

動作確認は Windows、Python 3.12、CPU です。PaddleOCR 3 系は Python 3.9〜3.13 を前提にしています。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

初回の読み取りで、文字認識モデルが `C:\Users\<ユーザー>\.paddlex\official_models` に保存されます。2 回目以降はそれを使います。

### 画面から読む

```powershell
.\.venv\Scripts\python.exe web.py
```

ブラウザで http://127.0.0.1:8765 を開いて、画像を選んで「読み取る」を押します。受け付ける形式は PNG、JPEG、WebP、BMP、TIFF で、サイズの上限は 8MB です。

### コマンドから読む

プロジェクトのフォルダで実行します。

```powershell
.\.venv\Scripts\python.exe -m meishi_ocr 名刺.jpg
.\.venv\Scripts\python.exe -m meishi_ocr 名刺.jpg -o result.json
```

信頼度が低い行を捨てるしきい値は `--min-score` です。初期値は `0.4` です。

### テスト

項目分けだけを確認します。画像も PaddleOCR も使いません。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

## 技術スタック

| 役割 | ライブラリ |
| --- | --- |
| 文字の検出と認識 | PaddlePaddle 3、PaddleOCR 3（認識モデルは `PP-OCRv5_mobile_rec`） |
| 画面 | Flask。待ち受けは `127.0.0.1:8765` |
| 画像の読み込み | Pillow。PaddleOCR には BGR の配列を渡す |
| 項目分け | Python 標準ライブラリの正規表現。追加のモデルや API キーは不要 |

認識は CPU です。Windows の CPU 版 Paddle は oneDNN 経由で落ちることがあるため、起動時に `PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT=False` を入れています。

## 内部の仕組み

処理は 2 段です。

1. **文字起こし**（`meishi_ocr/engine.py`）  
   画像の向きを直し、文字行の向きを見たうえで、各行の文字列・信頼度・座標を取り出します。名刺は日本語と、メールや URL や FAX などの英数字が混ざるので、その両方を 1 つのモデルで読む `PP-OCRv5_mobile_rec` を使います。
2. **項目分け**（`meishi_ocr/parser.py`）  
   座標から読む順を決めます。横書きは上から下、左から右です。枠の縦横比から縦書きが大半だと分かるときは、右の列から読みます。その後、行の文言だけを見て項目へ振り分けます。

振り分けの順は次のとおりです。

1. 全角英数を半角にそろえ、`FA×` を `FAX` に、崩れた `https:]/` を `https://` に直す。
2. メール、URL、電話、FAX、携帯、郵便番号を行から抜き出す。`〒` が `T` と読まれた `T100-0001` も郵便番号にする。
3. 「株式会社」などが隣の行と分かれているときは、人名でなければ会社名としてつなぐ。
4. 役職、部署、住所（都道府県やビル名など）を取る。
5. 残った行から、カナ、漢字の氏名、ローマ字を選ぶ。
6. どれにも当てはまらなかった行は `未分類` に残す。

`meishi_ocr/pipeline.py` がこの 2 段をつなぎます。画面（`web.py`）もコマンド（`python -m meishi_ocr`）も、同じ関数を呼んでいます。

## 出力項目

| キー | 内容 |
| --- | --- |
| 氏名、氏名カナ、ローマ字 | 人名。カナとローマ字が両方あるときは、漢字を氏名にする |
| 会社名、会社名英語 | 日本語の社名を優先し、英語表記は会社名英語へ分ける |
| 部署、役職 | 「営業部」は部署、「営業部長」は役職 |
| 郵便番号、住所 | 郵便番号のあとに続く住所行は 1 つにまとめる |
| 電話、携帯、FAX | 番号の並び。070 / 080 / 090 は携帯 |
| メール、URL | 見つかったものを配列で返す |
| 未分類 | 項目にできなかった行 |
| 読み取り行 | 読む順に並べた、振り分け前の文字列 |

## ディレクトリ

```
web.py                 ローカル画面
meishi_ocr/engine.py   PaddleOCR
meishi_ocr/parser.py   項目分け
meishi_ocr/pipeline.py 上記 2 つをつなぐ
meishi_ocr/__main__.py コマンド
tests/test_parser.py   項目分けのテスト
```

## うまく読めないとき

文字そのものが違うときは `読み取り行` を見ます。文字は合っているのに項目が違うときは `未分類` を見ます。縦書き、ロゴだけの社名、小さい字、強い影は取りこぼすことがあります。氏名のカナは、空白が落ちて `ヤマダタロウ` のように 1 語になることがあります。
