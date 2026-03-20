# API App

このディレクトリは Laravel API の置き場です。標準開発環境では、アプリ本体は macOS ローカルで直実行し、DB だけルートの `docker-compose.yml` から MySQL を起動します。

## 標準フロー

```bash
cd /Users/yutazack/workspace/yotsuyaotsuka-pdf
docker compose up -d mysql

cd apps/api
composer install
cp .env.example .env
php artisan key:generate
php artisan migrate
php artisan serve
```

既定の接続先は次です。

```env
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

## OCR index import

Laravel 側には OCR 横断索引を取り込む command を置きます。

```bash
php artisan app:import-page-text-index
```

既定では workspace ルートの `data/derived/page-text-index` を読みます。別パスを使うときは `--index-root=/path/to/index` を指定します。

## 管理画面の配備

React 管理画面の build 成果物は `public/admin/` に置く前提です。`/admin` と `/admin/*` は Laravel から同一ホストで配信します。
