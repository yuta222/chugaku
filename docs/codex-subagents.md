# Codex Subagents Quickstart

このリポジトリでは、Codex ネイティブの project-scoped subagents を `.codex/agents/` で定義しています。

## 使い分け

- `problem_classifier`
  OCR 済み問題の分類、主ラベル / 副ラベル候補、難度候補、根拠整理
- `problem_reviewer`
  分類結果の整合性チェック、ラベル漏れ確認、難度の妥当性確認
- `problem_executor`
  確定済みの分類結果を受けた Markdown 化、JSON 化、軽いファイル更新

## 推奨フロー

1. `problem_classifier` で分類候補を出す
2. 必要なら `problem_reviewer` で整合性を確認する
3. 判断が固まったら `problem_executor` に確定済み入力だけを渡す

分類と実行を同じ subagent に混ぜないほうが安定します。

## 親 agent からの依頼例

```text
この OCR 問題を分類して。problem_classifier を使って、
主ラベル、副ラベル、難度、根拠、不確実点だけを短く返して。
```

```text
problem_classifier で分類し、problem_reviewer で整合性を確認して。
最終回答では、採用する分類だけを短く要約して。
```

```text
problem_classifier で分類を確定し、
その結果だけを problem_executor に渡して Markdown 解説に整形して。
```

## 推奨 handoff 形式

親 agent から `problem_executor` に渡すときは、最低限次の情報を固定すると扱いやすいです。

```yaml
problem_id: "optional"
primary_label:
  code: "B3-8"
  name: "年齢算"
secondary_labels:
  - code: "H1-1"
    name: "和差算"
difficulty:
  level: 3
confidence: 0.82
rationale: "主題は年齢算で、和差による整理が補助的に必要"
uncertainty: "OCR の一部が不鮮明"
requested_output: "markdown"
```

`problem_executor` には、この確定済み入力だけを渡してください。未確定の分類判断を混ぜると、実行 agent が分類までやり直してぶれやすくなります。

## モデル方針

- 分類 / レビュー: `gpt-5.4` + `high`
- 実行: `gpt-5.4-mini` + `medium`

`gpt-5-nano` は API モデルとしては使えますが、このリポジトリの Codex-native subagent 標準には入れていません。
