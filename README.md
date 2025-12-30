# X-Archiver

X（旧Twitter）のスレッドをブログ記事形式（Markdown）に変換するツールです。

## フォルダ構成

- `main.py`: メインの実行ファイル。スレッドの取得から変換までを行います。
- `src/`: プログラムの主要ロジック（取得・整形・メディア保存）。
- `data/`: ログイン情報（`cookies.json`）が保存されます。
- `out/`: 生成されたMarkdownファイルとメディア（画像・動画）が保存されます。
- `debug/`: 問題発生時のスクリーンショットなどが保存されます。
- `docs/`: 要件定義書、基本設計書、リリースノートなどのドキュメント。

## 準備

1. 依存関係のインストール:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. ログイン情報の設定 (推奨):
   X（Twitter）はログインしていない状態だと、スレッドの続き（リプライ）を表示しません。全ツイートを取得するには、以下の手順でログイン情報を設定してください。

   1. ブラウザ拡張機能（例: [Get cookies.txt locally](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) / [GitHub](https://github.com/kairi003/Get-cookies.txt-Locally)）を使用して、ログイン済みの `x.com` のクッキーを **JSON形式** でエクスポートします。
   2. プロジェクト直下に `data` フォルダを作成し、その中に `cookies.json` という名前で保存します。
   
   ※ `data/cookies.json` が存在しない場合は、最初のツイートのみを取得します。

## 使い方

スレッドの最初の投稿のURLを指定して実行します：

```bash
python main.py "https://x.com/username/status/1234567890"
```

### オプション

* `--no-media`: 画像や動画をローカルにダウンロードせず、オリジナルのリンクを使用します。
* `--no-headless`: ブラウザの動作を確認したい場合に、ヘッドフルモード（画面あり）で実行します。

## 出力
- `out/thread_<ID>.md`: 生成されたブログ記事。
- `out/media/<ID>/`: ツイートに含まれる画像や動画ファイル。

> **注意**: メディアのダウンロード時には `gallery-dl` を使用してスレッド全体をスキャンするため、今回の取得範囲外（過去のリプライなど）のメディアも `out/media/<ID>/` にダウンロードされる場合があります。これは動画ファイルを確実に特定するための仕様です。Markdown記事内では、取得したツイートに直接紐づくメディアのみが正しく表示・参照されます。

## 技術要素
- **Scraping**: Playwright (Headless mode)
- **Media Download**: gallery-dl
- **Formatting**: Python string formatting (Markdown)
