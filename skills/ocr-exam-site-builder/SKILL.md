---
name: ocr-exam-site-builder
description: Build a local HTML homepage from OCR-derived Japanese entrance exam materials, adding beginner-friendly answers and explanations, checking them against official answer PDFs, and calling out mismatches with primary-source verification when needed. Use when the user asks for a webpage/homepage/site/HTML from `pdfs/`, `page_images/`, `page_text_index/`, or OCR text.
---

# OCR Exam Site Builder

Use this skill when the deliverable is a local HTML page, not just a plain answer. Typical asks are:

- `この年度の社会の解答解説ページを作って`
- `OCRと公式解答を使ってホームページ化して`
- `最後に答えが合っているかもチェックして`

If the user only wants one question solved in text, use `ocr-exam-tutor` instead.
If the user wants a much slower or more detailed beginner explanation, also use `ocr-exam-beginner-scaffold`.

## Workflow

1. Gather the source set.
   - Locate the target `問題` PDF, `回答` PDF, rendered page PNGs, and OCR text.
   - Prefer page-level material under `page_images/.../ocr/` for explanation work.
   - If the page spans multiple images, collect the full range before writing.
2. Solve independently first.
   - Reconstruct the question from OCR and page images.
   - Do not trust the official answer PDF as the first source of truth.
   - When OCR is broken, inspect the page image before guessing.
3. Verify against the official answer.
   - Compare your independent answer with the `回答` PDF after solving.
   - Mark each item as `公式と一致` or `公式と不一致`.
   - If a mismatch looks like the official answer may be wrong, verify with a primary source.
   - For current-affairs or changeable facts, verify with up-to-date official sources and include exact dates.
4. Build the local site.
   - Create `site/<slug>/index.html`.
   - Keep extra images or crops in `site/<slug>/assets/`.
   - Use relative links to local PDFs and page images so the page can be opened directly in a browser.
5. Verify the deliverable.
   - If the HTML contains embedded JavaScript, extract it and run `node --check`.
   - Confirm every local `.png` and `.pdf` reference exists.
   - State explicitly whether you only did static checks or also opened a browser preview.

## Required Content

Unless the user asks for a different format, include these parts:

1. Hero summary
   - School, year, subject
   - What sources were used
   - Whether the answers matched the official answer sheet
2. Verification summary
   - Count of matches / mismatches
   - A highlighted note for any suspicious official answer
3. Per-section explanation
   - A short `先に読むガイド` for each big question
   - For each subquestion:
     - `Verified`
     - `Official`
     - short explanation
     - beginner-friendly reasoning steps when the question is nontrivial
     - `つまずきやすい点` when useful
4. Sources
   - Local source paths
   - External primary-source links used for mismatch resolution or current facts

## Beginner-Friendly Standard

When the page is meant for a first-time learner:

- Explain what to look at first before giving the answer.
- Separate `知識` from `解き方`.
- Prefer short, concrete sentences over textbook-style abstraction.
- For selection questions, explain why the wrong choices are wrong when that teaches the pattern.
- For map, graph, or figure questions, use the original image or a crop from the official answer if that is the clearest representation.
- If the user still finds that too difficult, switch to the stronger scaffold from `ocr-exam-beginner-scaffold` and expose visible blocks such as `問題をやさしく言うと`, `1歩ずつ解く`, and `最後の確認`.

## Repo Integration

In this repo, the main paths are:

- `pdfs/<学校>/<年度>/問題/...pdf`
- `pdfs/<学校>/<年度>/回答/...pdf`
- `page_images/<学校>/<年度>/問題/.../page-XXXX.png`
- `page_images/<学校>/<年度>/問題/.../ocr/page-XXXX.txt`
- `page_images/<学校>/<年度>/問題/.../ocr/full_text.txt`
- `page_images/<学校>/<年度>/回答/.../page-0001.png`
- `page_text_index/pages.jsonl`
- `page_text_index/pdfs.jsonl`

Useful commands:

```bash
python3 search_ocr_index.py '開成 日本国憲法' --subject 社会 --scope page --limit 10
python3 search_ocr_index.py '広島城' --subject 社会 --scope pdf --limit 10
python3 skills/ocr-exam-tutor/scripts/list_problem_images.py --source-pdf /abs/path/to/problem.pdf --markdown
```

There is already a concrete example page in this repo:

- `site/kaisei-2026-social/index.html`

When making a similar page, prefer copying the structure of the nearest existing page rather than starting from an empty file.

## Quality Bar

- Do not silently merge your answer into the official one. Keep both visible if they differ.
- When you infer that the official answer is wrong, say that it is an inference supported by the cited source.
- For modern topics, laws, statistics, exchange rates, tariffs, or political facts, use primary current sources.
- A static HTML page with clean relative links is better than an overengineered app.
