---
name: elementary-math-unit-map
description: Map Japanese elementary school math problems to representative 小4・小5・小6 textbook units, identify which units are combined inside an entrance-exam question, and explain the solution as “this unit + that unit + this cross-cutting skill.” Use when the user asks which grade/unit a 算数 problem belongs to, what prior knowledge should be reviewed, or how to explain an OCR-derived 入試問題 as a combination of elementary math topics.
---

# Elementary Math Unit Map

Use this skill to classify a 算数 problem by unit, not to reconstruct OCR or prove the answer from scratch.

If the problem first needs to be located or solved from OCR material, use `ocr-exam-tutor` or `ocr-exam-site-builder` first.
If the user then wants the explanation slowed down further, pair this skill with `ocr-exam-beginner-scaffold`.

## Goal

Turn a problem into a reusable unit map such as:

- `主単元: 割合（小5）`
- `支える単元: 面積（小5）, 分数のかけ算（小6）`
- `横断スキル: 条件整理, 図に置き換える`

The point is to show **what knowledge is being combined** and **where each piece enters the solution**.

## Workflow

1. Decide what the problem is really asking.
   - quantity
   - comparison
   - shape
   - graph / table
   - counting cases
   - rule / change
2. Break the solution into knowledge pieces.
   - Name only the pieces that are materially necessary.
   - Prefer 2 to 4 labels, not a long shopping list.
3. Match those pieces to the closest representative unit names in [`references/grade4-6-unit-map.md`](references/grade4-6-unit-map.md).
   - Choose one `主単元`.
   - Add `支える単元` only when the problem truly combines ideas.
   - Add `横断スキル` for non-unit habits such as table-making or reverse reasoning.
4. Explain the combination.
   - Say what each unit contributes.
   - Say in which step it appears.
   - If the problem uses a private-exam technique name, keep both labels:
     - `教科書単元`
     - `受験発展`
5. Suggest a review order when useful.
   - Start from the supporting unit the learner is most likely missing.
   - End with a short “try this type next” suggestion if it helps.

## Matching Rules

- Prefer the **closest broad textbook unit**, not a hyper-specific chapter heading.
- Use the grade as an **approximate curriculum anchor**, not a claim that the problem can only be solved by that grade.
- Separate these clearly:
  - `教科書単元`
  - `横断スキル`
  - `受験発展`
- If the problem can be solved two ways, choose the unit map that best matches the explanation you are actually giving.
- If the problem is clearly beyond 小6 content, say so explicitly instead of forcing it into the map.

## Output Format

Use this structure unless the user asks for another format:

### 1. 問題の核
- What the problem is fundamentally about in one or two sentences

### 2. 使う単元の組み合わせ
- `主単元`
- `支える単元`
- `横断スキル`
- `受験発展` if needed

### 3. どこでその知識を使うか
- One short note per unit or skill

### 4. 解き方のつながり
- Explain how the units connect from start to finish

### 5. 復習するならこの順
- 2 to 4 items
- Put the weakest prerequisite first

## Companion Skills

- `ocr-exam-tutor`: use when the problem statement must be reconstructed or solved first
- `ocr-exam-site-builder`: use when working across a full exam or producing verified HTML
- `ocr-exam-beginner-scaffold`: use after this skill when the user wants the unit map turned into a slower beginner explanation

## Quality Bar

- Do not assign five different units just because the solution touches many facts.
- Do not confuse `割合`, `比`, `単位量当たりの大きさ`, and `比例・反比例`.
- Do not hide exam-only techniques inside textbook labels; mark them separately.
- Make it obvious why the explanation is “A + B” instead of just naming units.
