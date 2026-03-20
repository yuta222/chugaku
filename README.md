# 四谷大塚 中学受験データ基盤

四谷大塚の中学入試過去問 PDF を収集し、画像化・OCR・索引化し、Laravel API と React 管理画面で扱える形にするためのワークスペースです。

## 現在の構成

```text
.
├── apps/
│   ├── admin/                # React 管理画面の置き場
│   └── api/                  # Laravel API の置き場
├── data/
│   ├── raw/pdfs/             # 元 PDF
│   ├── derived/page-images/  # PDF をページ画像化した成果物
│   ├── derived/page-text-index/ # OCR 横断索引
│   └── published/sites/      # 生成済み HTML サイト
├── docs/                     # 設計資料
├── services/
│   └── ingest/
│       ├── bin/              # 実行ラッパー
│       ├── native/           # Swift 補助
│       └── src/              # Python ingest 処理
└── skills/                   # Codex 用ローカル skill
```

## 標準開発環境

- OCR / ingest: macOS ローカルで Python + Swift を直実行
- API: `apps/api` の Laravel をローカル直実行
- 管理画面: `apps/admin` の React + Vite をローカル直実行
- DB: ルートの `docker-compose.yml` で MySQL だけを起動

`Laravel Sail` や「全部 Docker」は採用していません。OCR 側が macOS 依存なので、Docker は MySQL の再現性確保にだけ使います。

## 初期セットアップ

```bash
cd /Users/yutazack/workspace/yotsuyaotsuka-pdf
source /Users/yutazack/workspace/Python/env/bin/activate
docker compose up -d mysql
```

依存ライブラリは既存環境を使う前提です。環境変数ファイルは用途ごとに分かれます。

- ルート `.env`: ingest 用
- `apps/api/.env`: Laravel 用

```env
# ingest 用
YOTSUYA_ID=あなたの会員番号
YOTSUYA_PASSWORD=あなたのパスワード
DOWNLOAD_DIR=./data/raw/pdfs
MAX_CONCURRENT=3
```

```env
# apps/api/.env の既定値
DB_CONNECTION=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=yotsuyaotsuka
DB_USERNAME=app
DB_PASSWORD=app
SESSION_DRIVER=file
CACHE_STORE=file
QUEUE_CONNECTION=sync
```

補足:

- `DOWNLOAD_DIR` を省略すると既定で `data/raw/pdfs` を使います
- 旧設定の `./pdfs` も互換的に `data/raw/pdfs` として扱います
- `YOTSUYA_DATA_ROOT` を設定すると `data/` の置き場を外に逃がせます
- MySQL は `docker compose down` で停止できます

## 起動手順

標準の起動コマンドは次の 3 本です。

```bash
# 1. MySQL
docker compose up -d mysql

# 2. Laravel API
cd apps/api
composer install
cp .env.example .env
php artisan key:generate
php artisan migrate
php artisan serve

# 3. React 管理画面
cd apps/admin
npm install
npm run dev
```

## 管理画面の build と配備

`apps/admin` の build 成果物は `apps/api/public/admin/` に出力されます。

```bash
cd apps/admin
npm run build
```

この構成では、同一ホスト上で次を前提にします。

- `/api/*`: Laravel
- `/admin/*`: React 管理画面の静的 build

Laravel 側には `/admin` の SPA fallback route を用意してあるため、shared hosting でも `/admin/...` の直接アクセスを扱えます。

## 使い方

実行は `services/ingest/bin/` のラッパー経由を推奨します。

```bash
# 全学校のPDFをダウンロード
services/ingest/bin/download-pdfs

# dry-run
services/ingest/bin/download-pdfs --dry-run

# PDFを1ページずつPNG化
services/ingest/bin/render-pages

# 特定学校・年度・問題だけを画像化
services/ingest/bin/render-pages --school 開成中学校 --year 2025 --kind 問題

# OCRを実行
services/ingest/bin/ocr-pages

# OCR済み索引を検索
services/ingest/bin/search-ocr-index '比' --subject 算数 --limit 10

# 画像化からOCRまでまとめて実行
services/ingest/bin/process-all-pdfs --school 開成中学校 --year 2025 --kind 問題
```

直接 Python を叩く場合は `services/ingest/src/` 配下のスクリプトを使います。

## 主要パス

- 元 PDF: `data/raw/pdfs/`
- ページ画像: `data/derived/page-images/`
- OCR 横断索引: `data/derived/page-text-index/`
- 生成サイト: `data/published/sites/`
- ingest 実装: `services/ingest/src/`
- Swift 補助: `services/ingest/native/`

## 現在の実装ポイント

- OCR 索引は `data/derived/page-text-index/*.jsonl` として保持する
- Laravel 側に OCR 索引 import command を置く
- `relative_source_pdf` とページ画像パスを DB から辿れるようにする
- 管理画面は `apps/admin` から `apps/api/public/admin` へ build する

## Codex Subagents

project-scoped の custom agent は `.codex/agents/` に置いています。

- `problem_classifier`: `gpt-5.4` + `high`。OCR 済み問題の分類、難度、根拠整理向け
- `problem_executor`: `gpt-5.4-mini` + `medium`。分類結果を受けた Markdown 化、JSON 化、軽い編集向け
- `problem_reviewer`: `gpt-5.4` + `high`。分類結果の整合性チェック向け

グローバルな subagent 制御は `.codex/config.toml` に置いており、既定では `max_threads = 4`, `max_depth = 1` です。

使い方の例:

```text
この OCR 問題を分類して。problem_classifier を使って主ラベル、副ラベル、難度、根拠、不確実点を要約して。

problem_classifier で分類し、problem_reviewer で整合性を確認してから、最後に人間向けに短くまとめて。

problem_classifier で分類を確定し、その結果だけを problem_executor に渡して Markdown 解説テンプレートに整形して。
```

Codex は subagent を自動起動しないため、明示的に「spawn」「delegate」「parallel」などの指示を与える前提です。

詳細な運用メモは [Codex Subagents Quickstart](/Users/yutazack/workspace/Python/yotsuyaotsuka-pdf/docs/codex-subagents.md) に置いています。

## 設計資料

- [DB 設計](/Users/yutazack/workspace/yotsuyaotsuka-pdf/docs/math-taxonomy-db-design.md)
- [Laravel / React 構成案](/Users/yutazack/workspace/yotsuyaotsuka-pdf/docs/math-taxonomy-laravel-react-architecture.md)
- [横断検索プロダクト設計](/Users/yutazack/workspace/yotsuyaotsuka-pdf/docs/exam-problem-search-product-design.md)
- [`/hobby` 学校別4択クイズ連携設計](/Users/yutazack/workspace/yotsuyaotsuka-pdf/docs/hobby-school-quiz-integration-design.md)
- [SQL たたき台](/Users/yutazack/workspace/yotsuyaotsuka-pdf/docs/math-taxonomy-schema.sql)
- [Codex Subagents Quickstart](/Users/yutazack/workspace/Python/yotsuyaotsuka-pdf/docs/codex-subagents.md)
- [問題分類前段フロー設計図](/Users/yutazack/workspace/Python/yotsuyaotsuka-pdf/docs/problem-classification-review-blueprint.md)

## 全年度分類

- 開成中学校の算数を `2026 -> 2005` の順で大問単位に draft 分類するには `python3 scripts/build_kaisei_all_years_math_bigq_review.py` を実行します。
- 生成先は [index.md](/Users/yutazack/workspace/Python/yotsuyaotsuka-pdf/data/derived/problem-labels/kaisei-all-years-math-bigq/index.md) と [index.json](/Users/yutazack/workspace/Python/yotsuyaotsuka-pdf/data/derived/problem-labels/kaisei-all-years-math-bigq/index.json) です。
