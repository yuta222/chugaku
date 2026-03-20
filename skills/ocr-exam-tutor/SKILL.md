---
name: ocr-exam-tutor
description: Solve OCR-derived Japanese entrance exam questions in 算数, 理科, 社会, and 国語, then produce beginner-friendly answers, explanations, keyword lists, and Markdown outputs with embedded problem images. Use when Codex receives OCR text, page images, page_text_index hits, or page_images/ocr files and needs to reconstruct the question, answer it, explain the reasoning step by step, and summarize the core concepts clearly for a first-time learner.
---

# OCR Exam Tutor

Use this skill for OCR 済みの入試問題を解くとき。特に `page_text_index/pages.jsonl`、`page_images/.../ocr/page-XXXX.txt`、`page_images/.../page-XXXX.png`、貼り付けられた OCR テキストが入力になっているときに使う。

If the user wants a local HTML homepage or answer/explanation site for a whole exam or subject, switch to the companion skill `ocr-exam-site-builder`.
If the user says the explanation is still too hard, too short, or not beginner-friendly enough, also use the companion skill `ocr-exam-beginner-scaffold`.

## Workflow

1. Locate the target question.
   - In this repo, prefer `python3 search_ocr_index.py '検索語' --subject 算数 --scope page` to narrow candidates.
   - If the user already gave a `page-XXXX.txt` or `page-XXXX.png`, start from that file.
   - If the question spans multiple pages, collect all pages before solving.
   - If the user wants Markdown, also collect the relevant page image paths.
2. Clean the OCR enough to solve.
   - Rewrite the question in natural Japanese.
   - Preserve numbers, units, labels, tables, and choices exactly when they are readable.
   - If a symbol, digit, or phrase is unclear, mark it as `OCR不確実` instead of guessing silently.
   - If the ambiguity changes the answer materially, present the plausible branches or ask for the page image.
3. Solve once from the problem statement.
   - Do not look at `回答` first unless the user explicitly asks to use it.
   - If a `回答` PDF exists, use it after solving to verify or explain discrepancies.
4. Teach, not just answer.
   - Assume the reader is a beginner.
   - Define jargon the first time it appears.
   - Use short sentences and show why each step is valid.
   - End with a small keyword list and one-line definitions.
   - If the user wants a slower explanation, rewrite with `ocr-exam-beginner-scaffold` style sections such as `まずここを見る`, `1歩ずつ解く`, and `よくあるまちがい`.

## Markdown With Images

When the user asks for Markdown, include the problem page image near the top of the answer.

- Use standard Markdown image syntax with an absolute local path:
  - `![問題ページ 1](/absolute/path/to/page-0001.png)`
- Never use relative paths or `file://` URLs.
- If the question is clearly one page, embed only that page by default.
- If the question spans multiple pages or a figure/table is on another page, embed all relevant pages in order.
- Put the image block before `問題の整理` unless the user asks for a different layout.

If you already have a `page-XXXX.txt`, `source_pdf`, or image directory, use [`scripts/list_problem_images.py`](scripts/list_problem_images.py) to emit the image paths or Markdown tags.

Example:

```md
![問題ページ 3](/Users/.../page_images/学校名/2025/問題/2025、算数、学校名、問題/page-0003.png)

## 問題の整理
- ...
```

## OCR Handling

- Prefer the page image over OCR text when formulas, tables, furigana, graphs, or choice labels look broken.
- Distinguish facts from inference:
  - `OCRから読めること`
  - `推定したこと`
- Never fabricate unseen numbers or options.
- If a question is partially unreadable, still give the maximum safe help:
  - explain the likely topic
  - outline the solving method
  - state what exact missing text prevents a unique answer

## Output Format

Use this structure unless the user asks for something else:

### 0. 問題画像
- Markdown を求められている場合だけ入れる
- 必要なページ画像を `![問題ページ n](...)` で並べる

### 1. 問題の整理
- 何を求める問題か
- 与えられている条件
- OCR 不確実箇所があれば短く明記

### 2. 解答
- 結論だけを最初に書く
- 小問が複数ある場合は小問ごとに分ける

### 3. やさしい解説
- 初学者が追える順序で説明する
- 算数は式変形の理由、理科は現象と因果、社会は根拠、国語は本文根拠を明示する
- 必要なら途中式・判断基準・消去法を示す

### 4. キーワード
- 3〜5個まで
- 1行定義で短く説明する

### 5. つまずきやすい点
- 1〜3個
- よくある誤読や勘違いを短く補足する

## Subject Playbooks

Read [`references/subject-guides.md`](references/subject-guides.md) when the subject is clear and you need the detailed solving pattern.

Use these defaults:

- 算数: 条件整理 -> 式や図の関係 -> 計算 -> 答えの妥当性確認
- 理科: 観察事実 -> 関連法則/現象 -> 問いへの対応 -> 用語整理
- 社会: 資料や本文の根拠 -> 関連知識 -> 選択肢比較または記述化
- 国語: 設問タイプ判定 -> 本文根拠 -> 言い換え -> 解答

## Repo Integration

In this repo, these files are the main entry points:

- `page_text_index/pages.jsonl`: ページ単位の OCR 横断索引
- `page_text_index/pdfs.jsonl`: PDF 単位の OCR 横断索引
- `page_images/.../page-XXXX.png`: 元のページ画像
- `page_images/.../ocr/page-XXXX.txt`: ページごとの OCR テキスト
- `page_images/.../ocr/index.json`: OCR メタデータ

Useful commands:

```bash
python3 search_ocr_index.py '反比例' --subject 算数 --scope page --limit 5
python3 search_ocr_index.py '光合成' --subject 理科 --scope pdf --limit 5
python3 search_ocr_index.py '日本国憲法' --subject 社会 --scope page --limit 5
python3 search_ocr_index.py '気持ち' --subject 国語 --scope page --limit 5
python3 ~/.codex/skills/ocr-exam-tutor/scripts/list_problem_images.py --text-path /abs/path/to/page-0003.txt --markdown
python3 ~/.codex/skills/ocr-exam-tutor/scripts/list_problem_images.py --source-pdf /abs/path/to/problem.pdf --markdown
```

After finding a hit, open the linked OCR text and, if needed, the corresponding `page-XXXX.png`.

## Quality Bar

- Prefer correctness over fluency when OCR is damaged.
- Prefer one clear method over many alternative methods unless comparison is educationally useful.
- Keep the explanation compact but complete enough that a beginner can reproduce the reasoning.
- If you verify against `回答`, explicitly say whether it matched your independent solution.
