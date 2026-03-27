# 志望校別インタラクティブ機能 構想書

## 背景

624校 × 4教科の trend-light 分類（16,584件）が完了し、HTMLプロファイルも2,128件生成済み。
このデータを**保護者・他塾関係者が使いたくなるインタラクティブ機能**に昇華させる。

---

## 機能一覧（優先順）

### 1. 難易度マップ (`difficulty-map/`)

**ターゲット**: 他塾関係者・保護者
**概要**: 全624校 × 4教科のヒートマップ。学校（行）× 教科（列）で平均難易度を色分け表示。ソート・フィルタ付き。

**UI**:
- フィルタバー: 地域ドロップダウン、難易度レンジ
- テーブル: 学校名 | 算数 | 理科 | 社会 | 国語 | 総合平均
- セルクリック → 対応する学校プロファイルへリンク
- モバイル: 1列固定 + 横スクロール

**スクリプト**: `scripts/build_difficulty_map.py`
**出力**: `data/published/sites/difficulty-map/index.html`

**処理**:
1. `config/problem-labels/` を全スキャンし、学校×教科ごとに平均難易度・問題数を集計
2. `config/all-schools.json` から学校名・地域を取得
3. ヒートマップHTML生成（インラインJS でソート・フィルタ）

---

### 2. 志望校傾向4択クイズ (`quiz/`)

**ターゲット**: 保護者・生徒
**概要**: 志望校を選ぶと「この学校の算数で最も出る単元は？」等の4択が10問出題される。正答率で理解度を可視化。

**出題パターン**（config/problem-labels から自動生成）:
| パターン | 例 |
|---------|------|
| 最頻出単元 | 「開成の算数で最も出る単元は？」 |
| 難易度 | 「麻布の理科の平均難易度に最も近いのは？」 |
| 出題回数 | 「桜蔭の算数で『速さ』は直近4年で何回出た？」 |
| 年度変化 | 「2025→2026で新たに登場した単元は？」 |
| 難度帯 | 「この学校で難度4-5の割合は全体の何%？」 |
| 教科横断 | 「この学校で最も難しい教科は？」 |

**スクリプト**: `scripts/build_school_quiz.py`
**出力**:
- `data/published/sites/quiz/index.html` — 学校選択画面
- `data/published/sites/quiz/quiz.html` — クイズプレイヤー

**JS仕様**:
- URL パラメータで学校・教科を受取 (`quiz.html?school=kaisei&subject=math`)
- 10問ランダム出題、即時フィードバック（正解/不正解のハイライト）
- 終了時: スコア表示 + 学校傾向サマリー + プロファイルページへのリンク
- モバイル: 大きなタップターゲット（48px以上）、プログレスバー

**ダミー選択肢の生成ロジック**:
- 正解1つ + ダミー3つ（同学年の別単元、他校の値等から生成）
- 数値問題: 正解±20%の範囲で3つのダミーを生成（重複なし）
- 単元名問題: 同教科の他単元からランダム抽出

---

### 3. 単元カバー率チェッカー (`coverage/`)

**ターゲット**: 保護者
**概要**: 志望校を選び、子どもが習得済みの単元にチェック → カバー率と「重点対策が必要な単元」を表示。

**スクリプト**: `scripts/build_coverage_checker.py`
**出力**:
- `data/published/sites/coverage/index.html` — 学校選択
- `data/published/sites/coverage/checker.html` — チェッカー本体

**JS仕様**:
- チェックボックスリスト（出題頻度順にソート）
- リアルタイムカバー率メーター（プログレスリング）
- 未チェック単元を「重点対策リスト」として強調表示
- localStorage で状態保存（次回訪問時に復元）
- 複数校比較: 2校選択して差分表示も可能（将来拡張）

---

## 技術方針

- **静的 HTML + vanilla JS**（ビルドステップなし、フレームワークなし）
- データは `<script>` 内に `const DATA = {...}` で埋め込み（fetch不要、ファイルシステムから直接開ける）
- 既存の CSS パターン踏襲（system fonts, 難易度5色, レスポンシブ）
- 全データ埋め込みサイズは ~300-400KB（624校×4教科の集計値）

## 参照する既存コード

| 用途 | ファイル |
|------|---------|
| データ読み込みパターン | `scripts/build_school_subject_profiles.py` の `discover_school_subjects()`, `collect_data()` |
| 学校レジストリ読み込み | `scripts/build_school_subject_profiles.py` の `_load_school_registry()` |
| HTML+インラインJS生成 | `scripts/build_hengan_dashboard.py` のパターン全般 |
| 難易度色・ラベル | `DIFFICULTY_COLORS`, `DIFFICULTY_LABELS`（複数スクリプトで共通） |
| 既存ドリルUI | `data/published/sites/kaisei-2026-science/drill.html` のカード形式 |

## ファイル構成

```
scripts/
  build_difficulty_map.py      # Phase 1
  build_school_quiz.py         # Phase 2
  build_coverage_checker.py    # Phase 3

data/published/sites/
  difficulty-map/
    index.html
  quiz/
    index.html                 # 学校選択グリッド
    quiz.html                  # 4択クイズプレイヤー
  coverage/
    index.html                 # 学校選択
    checker.html               # カバー率チェッカー
```

## 検証方法

各 Phase 完了時:
1. `python3 scripts/build_{feature}.py` が正常終了
2. 生成された HTML をブラウザで開いて動作確認
3. モバイル幅（375px）でのレイアウト確認
4. 学校プロファイルページへのリンクが正しく遷移
