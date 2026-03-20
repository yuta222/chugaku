## Local Skills

### Available local skills

- `ocr-exam-tutor`: OCR 済みの入試問題を解いて、初学者向けの解答・解説を作る。単問回答や Markdown 解説向け。 (file: `/Users/yutazack/workspace/yotsuyaotsuka-pdf/skills/ocr-exam-tutor/SKILL.md`)
- `ocr-exam-site-builder`: OCR・問題 PDF・解答 PDF から、検証付きのローカル HTML 解答解説ページを作る。ホームページ化、公式解答照合、不一致チェックが必要なときに使う。 (file: `/Users/yutazack/workspace/yotsuyaotsuka-pdf/skills/ocr-exam-site-builder/SKILL.md`)
- `ocr-exam-beginner-scaffold`: OCR 入試問題の解説を、超初心者向けに一歩ずつ組み直す。`もっと細かく`, `まだ難しい`, `式の意味から`, `一歩ずつ` の要求が入ったときに使う。 (file: `/Users/yutazack/workspace/yotsuyaotsuka-pdf/skills/ocr-exam-beginner-scaffold/SKILL.md`)
- `elementary-math-unit-map`: 小4・小5・小6の算数単元に問題を対応づけ、`この単元 + この単元` の組み合わせとして説明する。`何年生の何の単元?`, `どこを復習?`, `この問題は何の組み合わせ?` の要求で使う。 (file: `/Users/yutazack/workspace/yotsuyaotsuka-pdf/skills/elementary-math-unit-map/SKILL.md`)

### How to use local skills

- 単問や短い解説なら `ocr-exam-tutor` を使う。
- `ホームページ`, `Webページ`, `HTML`, `サイト化`, `最終チェック`, `公式解答と照合` の依頼が入ったら `ocr-exam-site-builder` を優先する。
- `もっと細かく`, `超初心者向け`, `まだ難しい`, `一歩ずつ`, `式の意味から` の依頼が入ったら `ocr-exam-beginner-scaffold` を併用する。
- `何年生の何の単元`, `どの単元の組み合わせ`, `どこを復習すべきか`, `この問題は割合と何の組み合わせか` の依頼が入ったら `elementary-math-unit-map` を使う。
- 必要なら `ocr-exam-tutor` で独立に解いてから `ocr-exam-site-builder` で検証・HTML化する。
- 必要なら `ocr-exam-tutor` で解いてから `elementary-math-unit-map` で単元ラベルを付け、その後 `ocr-exam-beginner-scaffold` で超初心者向けに組み直す。

## Codex Subagents

- `problem_classifier` を、OCR 済み問題の分類、主ラベル / 副ラベル候補、難度候補、根拠整理に使う。
- `problem_classifier` は高推論前提。分類の精度を優先し、不要なファイル編集はさせない。
- `problem_executor` を、分類結果を受けた Markdown 化、JSON 化、軽いファイル更新に使う。
- `problem_executor` は `gpt-5.4-mini` 前提。速度とコストを優先し、分類そのものは再判断しない。
- `problem_reviewer` を、分類結果の整合性チェック、ラベル漏れ確認、難度の妥当性確認に使う。
- 問題分類の subagent は、少なくとも `主ラベル候補 / 副ラベル候補 / 難度候補 / 根拠 / 不確実点` を返す。
- write-heavy な parallel 実行は最小限にし、まず `problem_classifier` と `problem_reviewer` で判断を固め、その後 `problem_executor` で出力や編集に進める。
