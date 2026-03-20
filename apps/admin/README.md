# Admin App

このディレクトリは React 管理画面です。開発中は Vite dev server で起動し、本番配備用の build は `../api/public/admin` に出力します。

## 開発

```bash
cd /Users/yutazack/workspace/yotsuyaotsuka-pdf/apps/admin
npm install
npm run dev
```

## build

```bash
cd /Users/yutazack/workspace/yotsuyaotsuka-pdf/apps/admin
npm run build
```

生成物は `apps/api/public/admin/` に出力され、同一ホスト上で `/admin` から配信する前提です。API の接続先も同一オリジンの `/api` を前提にします。
