# Explanation Recipes

Use this file only when the user explicitly wants a slower or more beginner-friendly explanation, or when the current explanation is still too compressed.

## Common Rewrite Pattern

Take an expert explanation like:

> 面積は 15 × ER だから、ER=20 のときです。

Rewrite it more like:

1. この問題では、三角形の面積を出したいです。
2. 面積を出すには、底辺と高さがわかればよいです。
3. この図では、底辺として長さ15の部分を使えます。
4. 高さにあたるのが ER です。
5. だから面積は `15 × ER` と書けます。
6. 面積が300なので、`15 × ER = 300` です。
7. 両方を15で割ると、`ER = 20` です。

The rewrite should expose:

- what is being computed
- what quantity plays each role
- what equation is formed
- why that equation is legal

## Block Recipes For HTML

### Minimal block set

- `まずここを見る`: 1 sentence
- `問題をやさしく言うと`: 1 to 2 sentences
- `わかっていること`: 2 to 5 bullets
- `1歩ずつ解く`: 3 to 7 numbered steps
- `よくあるまちがい`: 1 to 3 bullets
- `最後の確認`: 1 sentence

### When the problem is a graph or figure

Add:

- `図で見るポイント`
  - say which point, line, axis, region, or label to inspect first

### When the problem is a selection question

Add:

- `選び方のルール`
  - state the comparison axis
- `他の選択肢がちがう理由`
  - explain at least one wrong option if it teaches the pattern

### When the problem is a Japanese reading question

Add:

- `本文のどこを見るか`
  - identify the paragraph or relation
- `答えの型`
  - explain whether the answer should be a reason, contrast, summary, quote, or restatement

## Subject-Specific Recipes

## 算数

### Good beginner flow

1. 何を求める問題か言い直す
2. 図・条件から数字を拾う
3. どの式を使うか言う
4. 式の各数字がどこから来たか言う
5. 1行ずつ計算する
6. 答えの大きさがおかしくないか見る

### Useful starter phrases

- `まず図のどこが底辺になるかを見ます。`
- `この数字は問題文のここから来ています。`
- `ここで割るのは、1つ分を知りたいからです。`
- `この式は、○○を数で表したものです。`

### Typical traps

- 何を高さにしているかが曖昧
- 単位を書き忘れる
- 条件を1つ落とす
- 周期や往復を片道だけで考える

## 理科

### Good beginner flow

1. まず見えた事実を書く
2. それを説明する法則や現象を言う
3. 原因 -> 結果 の順で言う
4. 選択肢なら、正しい理由と誤りの理由を分ける

### Useful starter phrases

- `ここで大事なのは、実験結果として何が起きたかです。`
- `この変化を説明するのが○○です。`
- `温度差が大きいほど、変化は速くなります。`

### Typical traps

- 観察結果と理由が逆になる
- 用語だけ書いて説明がない
- グラフの増減を現象と結びつけていない

## 社会

### Good beginner flow

1. 何の時代・地域・制度の問題か決める
2. 比べる軸を1つ決める
3. 正答の根拠を書く
4. 代表的な誤答のズレも書く

### Useful starter phrases

- `まず時代を確定します。`
- `この選択肢は人物は合っていますが、時代が違います。`
- `この語句は○○とセットで覚えると間違えにくいです。`

## 国語

### Good beginner flow

1. 設問が何を求めている型か言う
2. 本文のどのあたりを見るか言う
3. 重要語をやさしく言い換える
4. それを答えの形に整える

### Useful starter phrases

- `この設問は理由を聞いています。`
- `本文ではこの前後にヒントがあります。`
- `言いかえると、○○という意味です。`
- `答えでは、この2つを両方入れる必要があります。`

### Typical traps

- 本文の言葉をそのまま並べるだけで意味がつながっていない
- 根拠が1つ足りない
- 設問の型が理由なのか要約なのかを取り違える
