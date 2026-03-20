# 中学受験算数 分類システム Laravel / React 構成案

## 1. 方針

- Backend は Laravel で統一する
- DB スキーマ管理、API、import、レビュー状態管理は Laravel 側に持たせる
- 表形式の管理画面は React で実装する
- OCR パイプラインは当面この Python リポジトリで維持し、Laravel はその出力を取り込む

## 2. 全体構成

```text
Python OCR pipeline
  -> data/derived/page-text-index/pdfs.jsonl
  -> data/derived/page-text-index/pages.jsonl

Laravel backend
  -> import command / queue job
  -> MySQL
  -> REST API

React admin
  -> problem list table
  -> problem detail editor
  -> taxonomy manager
  -> review queue
```

標準開発環境:

- OCR / ingest は macOS ローカルで実行
- Laravel / React もローカルで直実行
- DB だけ Docker Compose で MySQL を起動
- 本番は一般的な PHP レンタルサーバー + MySQL を想定

## 3. Laravel の責務

Laravel 側に持たせるもの:

- migration
- seed
- Eloquent model
- problem / taxonomy / review API
- OCR index 取り込み command
- 難易度・ラベルの監査ログ
- 認証・権限

Laravel 側に寄せないもの:

- PDF ダウンロード
- 画像化
- OCR 実行そのもの

理由:

- OCR はバッチ性が強く、既存 Python 資産がある
- 分類レビューは CRUD と検索が中心で Laravel が向いている

## 4. React の責務

React 側に持たせるもの:

- 問題一覧の表
- 絞り込み
- 並び替え
- ラベル編集
- 難易度編集
- 問題文・解答・出典ページの詳細表示
- taxonomy マスタ編集

UI は「表が主、詳細が従」で組むのがよいです。

- 左または中央に問題一覧テーブル
- 右に詳細パネル
- 行クリックでラベルと難易度を編集

## 5. 標準 DB

このプロジェクトの標準は `MySQL` です。

優先順位は次です。

1. MySQL
2. PostgreSQL
3. SQLite

理由:

- 最終配備先を一般的な PHP レンタルサーバーに置きやすい
- ローカルでも Docker で同じ MySQL を再現しやすい
- PostgreSQL は VPS や自由度の高い環境に移るときの有力候補
- SQLite は簡易確認には便利だが、標準運用にはしない

## 6. Laravel のテーブル対応

前提スキーマは [math-taxonomy-schema.sql](/Users/yutazack/workspace/yotsuyaotsuka-pdf/docs/math-taxonomy-schema.sql) をベースにします。

主な Eloquent model:

- `School`
- `Exam`
- `ExamDocument`
- `DocumentPage`
- `TaxonomyVersion`
- `TaxonomyNode`
- `Problem`
- `ProblemDocumentSpan`
- `ProblemLabel`
- `ProblemDifficultyAssessment`

主要な relation:

- `School hasMany Exam`
- `Exam hasMany ExamDocument`
- `Exam hasMany Problem`
- `ExamDocument hasMany DocumentPage`
- `Problem belongsTo Exam`
- `Problem belongsTo Problem` as parent
- `Problem hasMany ProblemLabel`
- `Problem hasMany ProblemDifficultyAssessment`
- `TaxonomyNode belongsTo TaxonomyVersion`

## 7. Laravel API 設計

### 7.1 問題一覧

`GET /api/problems`

主な query:

- `school_id`
- `year`
- `subject`
- `document_kind`
- `taxonomy_node_id`
- `difficulty_min`
- `difficulty_max`
- `status`
- `q`
- `page`
- `per_page`
- `sort`

返却イメージ:

```json
{
  "data": [
    {
      "id": 101,
      "school": "開成中学校",
      "exam_year": 2025,
      "subject": "算数",
      "problem_code": "3-(2)",
      "display_title": "年齢算",
      "primary_label": { "code": "B3-8", "name": "年齢算" },
      "secondary_labels": [
        { "code": "H1-1", "name": "和差算" }
      ],
      "current_difficulty": 3,
      "status": "reviewed"
    }
  ],
  "meta": {
    "current_page": 1,
    "per_page": 50,
    "total": 12345
  }
}
```

### 7.2 問題詳細

`GET /api/problems/{problem}`

返すもの:

- 問題本文
- 解答
- 解説
- 紐づく document span
- OCR ページ情報
- ラベル一覧
- 難易度履歴

### 7.3 ラベル更新

`PUT /api/problems/{problem}/labels`

送信例:

```json
{
  "labels": [
    {
      "taxonomy_node_id": 501,
      "is_primary": true,
      "label_order": 1,
      "source_type": "human",
      "rationale": "主題は年齢算"
    },
    {
      "taxonomy_node_id": 802,
      "is_primary": false,
      "label_order": 2,
      "source_type": "human",
      "rationale": "和差で整理する"
    }
  ]
}
```

### 7.4 難易度更新

`POST /api/problems/{problem}/difficulty-assessments`

送信例:

```json
{
  "difficulty_level": 3,
  "source_type": "human",
  "rationale": "典型だが条件整理が一段必要",
  "make_current": true
}
```

### 7.5 taxonomy 管理

- `GET /api/taxonomy/versions`
- `GET /api/taxonomy/nodes`
- `POST /api/taxonomy/nodes`
- `PATCH /api/taxonomy/nodes/{taxonomyNode}`

### 7.6 import

- `POST /api/imports/page-text-index`
- または Artisan command:
  `php artisan app:import-page-text-index`

API より command 中心のほうが安全です。

## 8. React 管理画面

最低限必要な画面は 4 つです。

### 8.1 問題一覧画面

列候補:

- 学校
- 年度
- 教科
- 問題番号
- 問題タイトル
- 主ラベル
- 副ラベル
- 難易度
- レビュー状態
- 更新日時

必要機能:

- サーバーサイド pagination
- 多条件 filter
- ソート
- 行選択
- 一括ラベル変更は後回しでよい

### 8.2 問題詳細画面

表示内容:

- 問題文
- 解答
- 解説
- 対応ページ番号
- OCR テキスト
- ラベル編集フォーム
- 難易度編集フォーム

### 8.3 taxonomy 管理画面

必要機能:

- ノード一覧
- 親子関係の確認
- assignable 判定変更
- `-99 その他` の利用状況確認

### 8.4 レビュー待ち画面

一覧条件:

- 未分類
- LLM 推定のみ
- 難易度未確定
- `その他` 使用中

## 9. Laravel 実装方針

### 9.1 migration

Laravel migration では次を守るとよいです。

- 主キーは `id()`
- 外部キーは `foreignId()->constrained()`
- 監査系を残すテーブルは `timestamps()`
- 履歴系テーブルは `timestamps()` を有効にする

### 9.2 Form Request

更新 API は Form Request で制約を固定します。

例:

- 主ラベルは最大 1 件
- 難易度は 1〜5
- assignable でない taxonomy node は付与禁止

### 9.3 Service 層

Controller に寄せず、最低でも次の service を分けるのが安全です。

- `ProblemLabelService`
- `ProblemDifficultyService`
- `TaxonomyService`
- `PageTextIndexImportService`

### 9.4 Queue

v1 は同期実行を標準にします。

- shared hosting で常駐 worker を前提にしない
- OCR index import はまず command 中心で回す
- LLM によるラベル候補生成や難易度候補生成は後から queue 化する

## 10. React 実装方針

### 10.1 表の作り

テーブルは次の前提にしたほうが安全です。

- server-side pagination
- server-side filtering
- server-side sorting

理由:

- 問題数が数万件になる前提では、全件を React に積まないほうがよい

### 10.2 状態管理

複雑にしすぎず、次を分けるだけで十分です。

- 一覧条件
- 選択中 problem
- 編集中 labels / difficulty
- API fetch 状態

### 10.3 UX の要点

- 行クリックで右ペインに詳細を開く
- ラベル編集後に一覧へ即反映
- 難易度変更時に理由入力を必須にするかは運用で決める
- `その他` ラベルは目立つ色で警告する

## 11. 実装順

1. Laravel migration を作る
2. taxonomy seed を作る
3. OCR index import command を作る
4. `problems` の CRUD を作る
5. `problem_labels` と `difficulty` API を作る
6. React の問題一覧画面を作る
7. React の詳細編集画面を作る
8. レビュー待ち一覧を作る

## 12. いまの要件に対する推奨結論

この要件なら、次の構成が最も素直です。

- DB: MySQL
- Backend: Laravel API
- Frontend: React 管理画面
- OCR / ingest 元データ生成: 既存 Python

理由は単純で、分類レビュー業務は「検索、一覧、編集、履歴」が中心で、最終的に一般的な PHP レンタルサーバーに載せやすい形を優先するからです。  
この部分は Laravel と React の分担がきれいにハマります。
