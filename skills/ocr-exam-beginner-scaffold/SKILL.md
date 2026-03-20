---
name: ocr-exam-beginner-scaffold
description: Rewrite OCR-derived Japanese entrance exam explanations for true beginners by breaking the solution into tiny steps, defining terms, showing why each step is valid, surfacing common mistakes, and adding “what to look at first” guidance. Use when the user asks for more detailed, easier, slower, or more beginner-friendly explanations from OCR exam materials or HTML answer pages.
---

# OCR Exam Beginner Scaffold

Use this skill when the user says things like:

- `もっと細かくして`
- `初心者でもわかるように`
- `一歩ずつ説明して`
- `まだ難しい`
- `式の意味から教えて`

This skill is about **pedagogy**, not answer discovery. Solve or verify first with `ocr-exam-tutor` or `ocr-exam-site-builder`, then use this skill to rewrite the explanation layer.

## Goal

Turn a correct explanation into one that a first-time learner can actually follow.

The standard is:

- The learner can tell **what to look at first**
- The learner can tell **why the next step is allowed**
- The learner can tell **where they are likely to get stuck**
- The learner can reproduce the method on a similar problem

## Workflow

1. Find the learner’s gap.
   - Is the problem in OCR reading, background knowledge, step order, formulas, graph reading, or wording?
   - Name that gap explicitly in the output.
2. Slow the explanation down.
   - Split one expert step into 2 to 5 small steps.
   - Explain each transformation or judgment in plain Japanese.
   - If a formula appears, say what each quantity means before using it.
3. Add a fixed beginner scaffold.
   - `この問題で最初に見るもの`
   - `わかっていること`
   - `求めるもの`
   - `どう考えるか`
   - `1歩ずつ解く`
   - `よくあるまちがい`
   - `最後の確認`
4. Keep the explanation concrete.
   - Prefer the exact numbers, labels, or phrases in the problem.
   - Avoid abstract “therefore / obviously / in general” leaps without support.
5. If the output is HTML, make the scaffolding visible.
   - Add separate blocks or cards for the sections above.
   - Do not bury the beginner steps inside one long paragraph.

## Output Rules

When rewriting a solution, use this order unless the user asks otherwise:

### 1. まずここを見る
- What the learner should inspect first
- One sentence only

### 2. 問題の意味を言いかえる
- Restate the question in easier Japanese
- Keep the original mathematical / scientific / historical meaning intact

### 3. わかっていること
- Flat bullet list
- Use the actual numbers or statements from the problem

### 4. 求めるもの
- One short sentence

### 5. 考え方
- Explain the key idea before calculation or selection
- If there are options, explain the comparison rule

### 6. 1歩ずつ解く
- Numbered steps
- One operation or judgment per step
- Each step says `何をしたか` and `なぜそれでよいか`

### 7. 答え
- Final answer alone

### 8. よくあるまちがい
- 1 to 3 items
- Explain the trap in simple words

### 9. 最後の確認
- A one-line self-check the learner can do

## Subject Defaults

Read [`references/explanation-recipes.md`](references/explanation-recipes.md) when you need a more detailed teaching pattern.

Use these defaults:

- 算数: 図や条件の読み替え -> 式の意味 -> 1行ずつ計算 -> 答えの妥当性確認
- 理科: 観察事実 -> 使う法則や現象 -> 因果関係 -> 言葉の定義
- 社会: 根拠箇所 -> 比較の軸 -> 正答と誤答の違い -> 用語確認
- 国語: 設問の型 -> 本文の根拠 -> 言い換え -> 答えの型

## For HTML Pages

When the explanation is rendered in a local HTML page:

- Replace short `初心者向けの考え方` bullets with visible scaffold blocks.
- Prefer separate blocks named:
  - `まずここを見る`
  - `問題をやさしく言うと`
  - `1歩ずつ解く`
  - `よくあるまちがい`
  - `最後の確認`
- For one-card layouts, keep the answer near the top but move the long explanation into structured sub-blocks below.

## Quality Bar

- Never use “なんとなく” explanations.
- Never skip why a formula or inference is allowed.
- If a background term may be unknown, define it once in easy language.
- If the learner would likely fail to start the problem alone, the explanation is still too advanced.
