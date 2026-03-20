# 問題分類前段フロー設計図

## 1. 目的

- PDF / 画像 / OCR / 既存解説ページから、`問題単位の分類レビュー成果物` を作るまでの流れを固定する。
- ここでいう「分類まで」は、`problem_code の確定`, `source pack の作成`, `主ラベル / 副ラベル / 難度の初稿`, `review 用 JSON / Markdown` の生成までを指す。
- DB 永続化や管理 UI 反映はこの設計の範囲外に置く。

この設計は、まず `開成中学校 2026 算数` で回し、その後に他校・他教科へ広げる前提です。

## 2. 現在地

現状の repo には、分類前段として次の資産があります。

- 元 PDF
  - `data/raw/pdfs/...`
- PDF をページ画像化したもの
  - `data/derived/page-images/.../page-0001.png`
- OCR テキスト / OCR JSON
  - `data/derived/page-images/.../ocr/page-0001.txt`
  - `data/derived/page-images/.../ocr/page-0001.json`
- ページ索引
  - `data/derived/page-text-index/pdfs.jsonl`
  - `data/derived/page-text-index/pages.jsonl`
- 既存のローカル解答解説ページ
  - `data/published/sites/.../index.html`
- review-first の分類成果物
  - `data/derived/problem-labels/{exam_key}/...`

ただし、現在の `開成 2026 算数` の review-first ラベル生成は、問題境界の正本として既存のローカル解説ページを使っています。OCR 生データは参照先として持っているが、分類入力の中心にはまだ入っていません。

この設計では、その依存関係を明示しつつ、次の段階で `OCR / 画像` を source pack の正規入力に昇格させます。

## 3. ソースの優先順位

分類前段では、ソースを 3 層に分けて扱います。

### 3.1 Tier A: 原本系

- 問題 PDF
- 解答 PDF
- 問題ページ画像
- 解答画像

役割:

- 問題文の最終確認
- 図形・グラフ・表・斜線位置の確認
- OCR 崩れの修正
- 公式解答の最終確認

優先度:

- 最優先
- OCR や既存解説ページと食い違った場合は Tier A を採用する

### 3.2 Tier B: 機械抽出系

- OCR txt
- OCR json
- `page-text-index` の pages / pdfs JSONL

役割:

- テキスト検索
- source pack への抜粋
- OCR 品質の検知
- classifier に渡す文章素材の自動抽出

優先度:

- Tier A の次
- 図や文字が崩れていない範囲では classifier 入力の主材料にできる

### 3.3 Tier C: 誘導・圧縮系

- `data/published/sites/.../index.html`
- 既存 explanation / mainUnit / advancedLabels
- 過去に人が整理した prompt / verified / lesson

役割:

- 問題境界の仮決め
- source pack の圧縮ヒント
- 既存の学習導線の再利用

優先度:

- もっとも低い
- 原本や OCR の代わりには使わない
- 問題境界や説明のショートカットとしてのみ使う

## 4. 生成物

分類前段で確定させる生成物は 4 本です。

### 4.1 `roster.json`

1問 = 1レコードの canonical roster。

最低限の列:

- `exam_key`
- `subject`
- `section_id`
- `problem_code`
- `display_id`
- `sort_order`
- `source`

ここでは `problem_code` を ASCII 固定にする。

例:

```json
{
  "exam_key": "kaisei-2026-math",
  "subject": "算数",
  "section_id": "part1",
  "problem_code": "q1_2_a",
  "display_id": "問1(2)(a)",
  "sort_order": 2
}
```

### 4.2 `source-packs.json`

classifier に渡す前の最小入力。

最低限の列:

- `display_id`
- `problem_code`
- `source.question_pdf`
- `source.answer_pdf`
- `source.page_images`
- `source.answer_images`
- `source.ocr_text_paths`
- `source.ocr_json_paths`
- `source_pack.prompt_summary`
- `source_pack.official_answer`
- `source_pack.explanation_summary`
- `source_pack.problem_core`
- `source_pack.ocr_notes`
- `source_pack.learning_map_hint`

重要:

- source pack は長文 HTML 全体を渡さない
- `その問題に必要な抜粋だけ` を入れる

### 4.3 `review.json`

review-first の正本。

最低限の列:

- `problem_code`
- `display_id`
- `search_labels.primary_label`
- `search_labels.secondary_labels`
- `search_labels.difficulty`
- `search_labels.confidence`
- `search_labels.rationale`
- `search_labels.uncertainty`
- `learning_map`
- `evidence`
- `review`

### 4.4 `review.md`

人間が一覧で spot check するための表形式サマリ。

列は固定する。

- `display_id`
- `primary`
- `secondary`
- `difficulty`
- `confidence`
- `main_unit`
- `advanced_labels`
- `uncertainty`

## 5. フロー

### 5.1 対象試験を固定する

- `school`
- `year`
- `subject`
- 必要なら `round`

ここで `exam_key` を一意に決める。

例:

- `kaisei-2026-math`

### 5.2 原本・OCR・既存整理ページを集める

対象試験について次を解決する。

- 問題 PDF の path
- 解答 PDF の path
- 問題ページ画像 dir
- 解答ページ画像 dir
- OCR dir
- 既存のローカル解説ページ path

この段階ではまだ分類しない。パス解決だけを行う。

### 5.3 canonical roster を決める

v1 では次の優先順で問題境界を決める。

1. 既存のローカル解説ページに問題単位の区切りがあるなら、それを正本にする
2. なければ PDF / OCR から人手で roster を起こす
3. その roster を将来の正本として保存する

`開成 2026 算数` では、既存の [data/published/sites/kaisei-2026-math/index.html](/Users/yutazack/workspace/Python/yotsuyaotsuka-pdf/data/published/sites/kaisei-2026-math/index.html) にある `問1(1)` から `問4(3)` の 15 件を正本にする。

### 5.4 source pack を作る

問題ごとに、次を 1 パックへまとめる。

- 問題文要約
- 公式解答
- 既存 explanation の要点
- 対応ページ画像
- OCR txt / json の path
- OCR 注意点
- 既存 learning map のヒント

重要ルール:

- 図や表を含む問題では、`page_images` を必須にする
- OCR が崩れている問題では、`ocr_notes` に明記する
- `official_answer` は解答 PDF / 解答画像ベースで確定する

### 5.5 1次分類を行う

`problem_classifier` を使って、問題ごとに次を出す。

- `primary_label`
- `secondary_labels`
- `difficulty`
- `confidence`
- `rationale`
- `uncertainty`
- `learning_map`

ルール:

- `primary_label` は 1 件
- `secondary_labels` は 0〜2 件
- `difficulty` は 1〜5
- `uncertainty` は空でもよいが、曖昧なら狭く書く

ラベルは 2 層で持つ。

1. 検索用ラベル
   - taxonomy / 題型 / 主副ラベル
2. 学習用マップ
   - `main_unit`
   - `supporting_units`
   - `cross_skills`
   - `advanced_labels`

### 5.6 2次レビューを行う

`problem_reviewer` を使って、次の順で見る。

1. 大問単位
   - 小問同士のズレ
   - 難度の相対感
   - 主ラベルの揺れ
2. 試験全体
   - 大問をまたいだ難度バランス
   - taxonomy の過不足
   - search_labels と learning_map のズレ

reviewer がやること:

- 主ラベルが本当に主題か
- 副ラベルが多すぎないか
- 難度が相対的に破綻していないか
- `mainUnit` と search_labels が食い違いすぎていないか

### 5.7 review-first 成果物へ固める

- `review.json`
- `review.md`

この段階では DB へは入れない。

review-first の目的:

- 人間が一覧で確認できる
- taxonomy seed が未完成でも止まらない
- 将来の import shape に寄せられる

### 5.8 spot check して分類完了にする

最低限、次を spot check する。

- OCR 崩れが明記された問題
- reviewer が residual uncertainty を残した問題
- 図形・グラフ・斜線位置を含む問題
- 解答図が一意でない問題

`開成 2026 算数` での代表例:

- `問1(3)`
  - OCR 秒数崩れ
- `問4(3)`
  - 解答図は一意でない

## 6. current v1 と target v2

### 6.1 current v1

- 問題境界は `published site` を正本にする
- source pack は `published site` 由来の圧縮情報が中心
- PDF / 画像は path 参照として持つ
- OCR は spot check 補助で、classifier 入力の中心ではない

利点:

- 速い
- 既存の人手整理を活かせる
- 開成 2026 算数のような curated exam で安定する

弱点:

- `published site` がない試験に弱い
- OCR / 画像を直接読んでいないので、原本依存の自動性が低い

### 6.2 target v2

- 問題境界の正本は `roster.json`
- `published site` は補助ソースへ降格
- source pack に OCR txt / json 抜粋を必須で入れる
- 図形問題では page image path を classifier/reviewer の必須入力にする
- `published site` は `problemCore` や `lesson` の圧縮ヒントとしてだけ使う

これにより、既存のローカル解説ページがない試験にも広げやすくなる。

## 7. 開成中学校 2026 算数での具体パス

- 問題 PDF
  - [2026、算数、開成中学校、問題.pdf](/Users/yutazack/workspace/Python/yotsuyaotsuka-pdf/data/raw/pdfs/開成中学校/2026/問題/2026、算数、開成中学校、問題.pdf)
- 解答 PDF
  - [2026、算数、開成中学校、解答.pdf](/Users/yutazack/workspace/Python/yotsuyaotsuka-pdf/data/raw/pdfs/開成中学校/2026/回答/2026、算数、開成中学校、解答.pdf)
- 問題ページ画像
  - [page-images dir](/Users/yutazack/workspace/Python/yotsuyaotsuka-pdf/data/derived/page-images/開成中学校/2026/問題/2026、算数、開成中学校、問題)
- OCR dir
  - [ocr dir](/Users/yutazack/workspace/Python/yotsuyaotsuka-pdf/data/derived/page-images/開成中学校/2026/問題/2026、算数、開成中学校、問題/ocr)
- 既存のローカル解説ページ
  - [kaisei-2026-math/index.html](/Users/yutazack/workspace/Python/yotsuyaotsuka-pdf/data/published/sites/kaisei-2026-math/index.html)
- 現在の review-first 成果物
  - [review dir](/Users/yutazack/workspace/Python/yotsuyaotsuka-pdf/data/derived/problem-labels/kaisei-2026-math)

## 8. 完了条件

分類前段が完了したと見なす条件は次です。

- `roster.json` がある
- `source-packs.json` がある
- `review.json` がある
- `review.md` がある
- 全問題に `primary_label`, `difficulty`, `rationale`, `source.verification` がある
- `secondary_labels` は 2 件以下
- unresolved な reviewer disagreement が残っていない
- residual uncertainty と spot check 対象が明示されている

## 9. 範囲外

- taxonomy seed の確定
- Laravel DB への import
- `problems / problem_labels` テーブル実装
- review UI 実装
- 他教科への taxonomy 展開

この設計は、`分類レビューに持ち込める状態を再現可能に作る` ことだけに集中する。
