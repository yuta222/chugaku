#!/usr/bin/env python3
"""Build a school-selection page and 4-choice quiz player for exam trend knowledge.

Scans config/problem-labels/ for all school-subject combinations,
generates quiz questions (6 patterns), and outputs:
  - data/published/sites/quiz/index.html   (school selection grid)
  - data/published/sites/quiz/quiz.html    (quiz player)
"""
from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from html import escape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_LABELS = REPO_ROOT / "config/problem-labels"
DERIVED_LABELS = REPO_ROOT / "data/derived/problem-labels"
OUTPUT_DIR = REPO_ROOT / "data/published/sites/quiz"

SUBJECT_EN_JP = {"math": "算数", "science": "理科", "social": "社会", "japanese": "国語"}
DIFFICULTY_LABELS = {1: "入門", 2: "基礎", 3: "標準", 4: "応用", 5: "差がつく"}

random.seed(42)  # reproducible builds


# ---------------------------------------------------------------------------
# School registry
# ---------------------------------------------------------------------------

def _load_school_registry() -> dict:
    PALETTE = [
        "#a73c34", "#2c5f8a", "#4a6741", "#6a4f8a", "#2f6f63",
        "#8e2e47", "#456a92", "#8f7031", "#5c5f91", "#2f6c6e",
    ]
    registry: dict[str, dict] = {}
    schools_json = REPO_ROOT / "config/all-schools.json"
    if not schools_json.exists():
        schools_json = REPO_ROOT / "config/kanto-schools-100.json"
    if schools_json.exists():
        data = json.loads(schools_json.read_text(encoding="utf-8"))
        for s in data.get("schools", []):
            slug = s["slug"]
            name = s["name"]
            short = name.replace("中学校", "").replace("中等部", "").replace("中等科", "").replace("中学部", "")
            short = short.replace("（第１回）", "").replace("（A日程）", "").strip()
            region = s.get("region", "")
            idx = int(hashlib.md5(slug.encode()).hexdigest(), 16) % len(PALETTE)
            registry[slug] = {"name": name, "short": short, "color": PALETTE[idx], "region": region}
    return registry


SCHOOL_REGISTRY = _load_school_registry()


# ---------------------------------------------------------------------------
# Record normalization
# ---------------------------------------------------------------------------

def _normalize_record(r: dict) -> dict | None:
    if isinstance(r.get("difficulty"), int) and "main_unit" in r:
        return {
            "difficulty_level": r["difficulty"],
            "main_unit": r.get("main_unit", ""),
            "tags": r.get("tags", []),
        }
    sl = r.get("search_labels", {})
    lm = r.get("learning_map", {})
    d = sl.get("difficulty", {})
    level = d.get("level") if isinstance(d, dict) else d if isinstance(d, int) else None
    if not level:
        return None
    return {
        "difficulty_level": level,
        "main_unit": lm.get("main_unit", ""),
        "tags": lm.get("advanced_labels", []),
    }


# ---------------------------------------------------------------------------
# Data collection — per school × subject × year
# ---------------------------------------------------------------------------

def collect_all() -> dict:
    """Return {school_slug: {subject_en: {year: [records], ...}}}."""
    result: dict[str, dict[str, dict[int, list]]] = {}

    def add_records(school_slug: str, subject_en: str, year: int, raw_records: list):
        for r in raw_records:
            n = _normalize_record(r)
            if n:
                result.setdefault(school_slug, {}).setdefault(subject_en, {}).setdefault(year, []).append(n)

    # config/problem-labels/
    if CONFIG_LABELS.exists():
        for d in sorted(CONFIG_LABELS.iterdir()):
            if not d.is_dir():
                continue
            subject_en = school_slug = None
            for se in ["math", "science", "social", "japanese"]:
                tag = f"-{se}-bigq"
                if d.name.endswith(tag):
                    subject_en = se
                    school_slug = d.name[: -len(tag)]
                    break
            if not subject_en:
                continue
            for jf in sorted(d.glob("*.json")):
                if not jf.stem.isdigit():
                    continue
                try:
                    raw = json.loads(jf.read_text(encoding="utf-8"))
                except Exception:
                    continue
                add_records(school_slug, subject_en, int(jf.stem), raw.get("records", []))

    # data/derived/problem-labels/
    if DERIVED_LABELS.exists():
        for d in sorted(DERIVED_LABELS.iterdir()):
            if not d.is_dir():
                continue
            subject_en = school_slug = None
            for se in ["math", "science", "social", "japanese"]:
                tag = f"-{se}-bigq"
                if d.name.endswith(tag):
                    subject_en = se
                    school_slug = d.name[: -len(tag)]
                    break
            if not subject_en:
                continue
            if school_slug in result and subject_en in result.get(school_slug, {}):
                continue
            for year_dir in sorted(d.iterdir()):
                if not year_dir.is_dir() or not year_dir.name.isdigit():
                    continue
                rp = year_dir / "review.json"
                if not rp.exists():
                    continue
                try:
                    raw = json.loads(rp.read_text(encoding="utf-8"))
                except Exception:
                    continue
                add_records(school_slug, subject_en, int(year_dir.name), raw.get("records", []))

    return result


# ---------------------------------------------------------------------------
# Quiz question generation
# ---------------------------------------------------------------------------

def _all_units_for_subject(all_data: dict, subject_en: str) -> list[str]:
    """Collect all distinct main_unit values for a subject across all schools."""
    units: set[str] = set()
    for school_data in all_data.values():
        for year_records in school_data.get(subject_en, {}).values():
            for r in year_records:
                if r["main_unit"]:
                    units.add(r["main_unit"])
    return sorted(units)


def generate_questions(school_slug: str, subject_en: str, school_data: dict, all_data: dict) -> list[dict]:
    """Generate quiz questions for a school × subject."""
    subj_data = school_data.get(subject_en, {})
    if not subj_data:
        return []

    all_records = [r for recs in subj_data.values() for r in recs]
    if len(all_records) < 3:
        return []

    questions = []
    subj_jp = SUBJECT_EN_JP[subject_en]
    info = SCHOOL_REGISTRY.get(school_slug, {"short": school_slug})
    school_name = info["short"]

    # Unit counter
    unit_ctr = Counter(r["main_unit"] for r in all_records if r["main_unit"])
    sorted_units = unit_ctr.most_common()
    all_subj_units = _all_units_for_subject(all_data, subject_en)

    # Difficulty
    diffs = [r["difficulty_level"] for r in all_records]
    avg_diff = sum(diffs) / len(diffs) if diffs else 3.0
    diff_ctr = Counter(diffs)

    years = sorted(subj_data.keys())

    # --- Pattern 1: 最頻出単元 ---
    if len(sorted_units) >= 4:
        correct = sorted_units[0][0]
        distractors = []
        for u, _ in sorted_units[1:]:
            if u != correct:
                distractors.append(u)
            if len(distractors) == 3:
                break
        # If not enough distractors, pull from other schools
        while len(distractors) < 3:
            candidates = [u for u in all_subj_units if u != correct and u not in distractors]
            if not candidates:
                break
            distractors.append(random.choice(candidates))
        if len(distractors) == 3:
            choices = [correct] + distractors
            random.shuffle(choices)
            questions.append({
                "q": f"{school_name}の{subj_jp}で最も出題頻度が高い単元は？",
                "choices": choices,
                "answer": choices.index(correct),
                "explanation": f"正解は「{correct}」（{unit_ctr[correct]}回出題）。2位は「{sorted_units[1][0]}」（{sorted_units[1][1]}回）。",
            })

    # --- Pattern 2: 平均難易度 ---
    correct_val = round(avg_diff, 1)
    # Generate 3 distractor values
    distractor_vals = set()
    for delta in [0.5, -0.5, 1.0, -1.0, 0.8, -0.8]:
        v = round(avg_diff + delta, 1)
        if 1.0 <= v <= 5.0 and v != correct_val:
            distractor_vals.add(v)
    distractor_vals = sorted(distractor_vals)[:3]
    if len(distractor_vals) == 3:
        choices_val = [correct_val] + list(distractor_vals)
        random.shuffle(choices_val)
        choices_str = [str(v) for v in choices_val]
        questions.append({
            "q": f"{school_name}の{subj_jp}の平均難易度（5段階）に最も近いのは？",
            "choices": choices_str,
            "answer": choices_val.index(correct_val),
            "explanation": f"正解は {correct_val}。全{len(all_records)}問の平均値です。",
        })

    # --- Pattern 3: 特定単元の出題回数 ---
    if sorted_units:
        target_unit = sorted_units[0][0]
        # Count in recent 4 years
        recent_years = years[-4:] if len(years) >= 4 else years
        recent_count = sum(
            1 for y in recent_years for r in subj_data.get(y, [])
            if r["main_unit"] == target_unit
        )
        if recent_count > 0:
            correct_c = str(recent_count)
            dist_c = set()
            for delta in [1, -1, 2, -2, 3]:
                v = recent_count + delta
                if v > 0 and str(v) != correct_c:
                    dist_c.add(str(v))
            dist_c = sorted(dist_c)[:3]
            if len(dist_c) == 3:
                choices_c = [correct_c] + list(dist_c)
                random.shuffle(choices_c)
                yr_range = f"{min(recent_years)}〜{max(recent_years)}"
                questions.append({
                    "q": f"{school_name}の{subj_jp}で「{target_unit}」は{yr_range}の間に何回出た？",
                    "choices": choices_c,
                    "answer": choices_c.index(correct_c),
                    "explanation": f"正解は {recent_count} 回。{yr_range}の{len(recent_years)}年分のデータです。",
                })

    # --- Pattern 4: 年度変化（新登場単元） ---
    if len(years) >= 2:
        last_year = years[-1]
        prev_year = years[-2]
        prev_units = {r["main_unit"] for r in subj_data.get(prev_year, []) if r["main_unit"]}
        new_units = [r["main_unit"] for r in subj_data.get(last_year, [])
                     if r["main_unit"] and r["main_unit"] not in prev_units]
        if new_units:
            correct_new = new_units[0]
            old_units = [u for u in prev_units if u != correct_new]
            distractors_new = random.sample(old_units, min(3, len(old_units))) if old_units else []
            while len(distractors_new) < 3:
                candidates = [u for u in all_subj_units if u != correct_new and u not in distractors_new]
                if not candidates:
                    break
                distractors_new.append(random.choice(candidates))
            if len(distractors_new) == 3:
                choices_new = [correct_new] + distractors_new
                random.shuffle(choices_new)
                questions.append({
                    "q": f"{school_name}の{subj_jp}で{prev_year}→{last_year}に新たに登場した単元は？",
                    "choices": choices_new,
                    "answer": choices_new.index(correct_new),
                    "explanation": f"正解は「{correct_new}」。{last_year}年で初めて出題されました。",
                })

    # --- Pattern 5: 難度帯の割合 ---
    total = len(all_records)
    hard_count = diff_ctr.get(4, 0) + diff_ctr.get(5, 0)
    if total > 0:
        hard_pct = round(hard_count / total * 100)
        correct_pct = f"{hard_pct}%"
        dist_pcts = set()
        for delta in [10, -10, 20, -20, 15, -15]:
            v = hard_pct + delta
            if 0 <= v <= 100:
                dist_pcts.add(f"{v}%")
        dist_pcts.discard(correct_pct)
        dist_pcts = sorted(dist_pcts)[:3]
        if len(dist_pcts) == 3:
            choices_pct = [correct_pct] + list(dist_pcts)
            random.shuffle(choices_pct)
            questions.append({
                "q": f"{school_name}の{subj_jp}で難度4〜5の問題は全体の約何%？",
                "choices": choices_pct,
                "answer": choices_pct.index(correct_pct),
                "explanation": f"正解は {hard_pct}%（{hard_count}/{total}問）。",
            })

    # --- Pattern 6: 教科横断（最も難しい教科） ---
    subj_avgs = {}
    for se in ["math", "science", "social", "japanese"]:
        recs = [r for rs in school_data.get(se, {}).values() for r in rs]
        if recs:
            subj_avgs[se] = sum(r["difficulty_level"] for r in recs) / len(recs)
    if len(subj_avgs) >= 3:
        hardest = max(subj_avgs, key=subj_avgs.get)
        choices_subj = [SUBJECT_EN_JP[se] for se in ["math", "science", "social", "japanese"] if se in subj_avgs]
        if len(choices_subj) >= 4:
            choices_subj = choices_subj[:4]
        correct_subj = SUBJECT_EN_JP[hardest]
        if correct_subj in choices_subj:
            questions.append({
                "q": f"{school_name}で平均難易度が最も高い教科は？",
                "choices": choices_subj,
                "answer": choices_subj.index(correct_subj),
                "explanation": f"正解は「{correct_subj}」（平均{subj_avgs[hardest]:.1f}）。",
            })

    return questions


# ---------------------------------------------------------------------------
# HTML generation — index page
# ---------------------------------------------------------------------------

def build_index_html(school_subjects: dict[str, dict]) -> str:
    """Build school selection grid."""
    cards = []
    for slug in sorted(school_subjects.keys()):
        info = SCHOOL_REGISTRY.get(slug, {"short": slug, "name": slug, "color": "#58687b", "region": ""})
        subjects = sorted(school_subjects[slug].keys())
        subj_badges = " ".join(
            f'<a href="quiz.html?school={slug}&subject={s}" class="subj-badge subj-{s}">{SUBJECT_EN_JP[s]}</a>'
            for s in subjects
        )
        cards.append(f"""
        <div class="card" style="border-left-color:{info["color"]}">
          <div class="card-name" style="color:{info["color"]}">{escape(info["short"])}</div>
          <div class="card-subjects">{subj_badges}</div>
        </div>""")

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>志望校傾向クイズ — 学校選択</title>
<style>
*,*::before,*::after{{box-sizing:border-box}}
body{{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans",sans-serif;background:#f7f7f5;color:#1a1a1a;line-height:1.5}}
.top-bar{{background:white;border-bottom:1px solid #e8e8e6;padding:20px 20px 16px;position:sticky;top:0;z-index:100}}
.top-bar h1{{font-size:20px;margin:0 0 4px;font-weight:700}}
.top-bar .sub{{font-size:13px;color:#888;margin:0 0 12px}}
.search-box{{font-size:14px;padding:8px 12px;border:1px solid #ddd;border-radius:8px;width:100%;max-width:360px}}
.container{{max-width:900px;margin:0 auto;padding:20px 16px 40px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}}
.card{{background:white;border:1px solid #e8e8e6;border-left:4px solid #ccc;border-radius:10px;padding:14px 16px}}
.card-name{{font-size:14px;font-weight:700;margin-bottom:8px}}
.card-subjects{{display:flex;gap:6px;flex-wrap:wrap}}
.subj-badge{{font-size:12px;padding:4px 10px;border-radius:6px;text-decoration:none;color:white;font-weight:600;min-height:32px;display:flex;align-items:center}}
.subj-badge:active{{opacity:0.8}}
.subj-math{{background:#a73c34}}
.subj-science{{background:#2f6f63}}
.subj-social{{background:#5c5f91}}
.subj-japanese{{background:#8f7031}}
.footer{{text-align:center;font-size:11px;color:#bbb;margin-top:32px;padding-top:16px;border-top:1px solid #eee}}
.count{{font-size:13px;color:#aaa;margin-bottom:12px}}
</style>
</head>
<body>
<div class="top-bar">
  <h1>志望校傾向クイズ</h1>
  <p class="sub">学校と教科を選んで、出題傾向の知識をチェック！</p>
  <input type="text" class="search-box" id="search" placeholder="学校名で検索…">
</div>
<div class="container">
  <div class="count" id="countLine">{len(cards)} 校</div>
  <div class="grid" id="grid">{"".join(cards)}</div>
  <div class="footer">志望校傾向クイズ — {len(cards)} 校対応</div>
</div>
<script>
const cards = document.querySelectorAll('.card');
const search = document.getElementById('search');
const countLine = document.getElementById('countLine');
search.addEventListener('input', () => {{
  const q = search.value.toLowerCase();
  let n = 0;
  cards.forEach(c => {{
    const show = !q || c.textContent.toLowerCase().includes(q);
    c.style.display = show ? '' : 'none';
    if (show) n++;
  }});
  countLine.textContent = n + ' 校';
}});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTML generation — quiz player
# ---------------------------------------------------------------------------

def build_quiz_html(all_questions: dict) -> str:
    """Build the quiz player page. all_questions = {school_slug: {subject_en: [questions]}}"""
    js_data = json.dumps(all_questions, ensure_ascii=False)

    # Build school name map for display
    name_map = {}
    for slug in all_questions:
        info = SCHOOL_REGISTRY.get(slug, {"short": slug, "color": "#58687b"})
        name_map[slug] = {"name": info["short"], "color": info.get("color", "#58687b")}
    js_names = json.dumps(name_map, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>志望校傾向クイズ</title>
<style>
*,*::before,*::after{{box-sizing:border-box}}
body{{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans",sans-serif;background:#f7f7f5;color:#1a1a1a;line-height:1.5}}
.top-bar{{background:white;border-bottom:1px solid #e8e8e6;padding:14px 20px;position:sticky;top:0;z-index:100;display:flex;align-items:center;gap:16px}}
.back{{font-size:13px;color:#666;text-decoration:none}}
.back:hover{{color:#1a1a1a}}
.title{{font-size:16px;font-weight:700;flex:1}}
.progress-wrap{{width:100%;height:6px;background:#e8e8e6;border-radius:3px;margin-top:2px}}
.progress-bar{{height:100%;border-radius:3px;transition:width .3s}}
.container{{max-width:640px;margin:0 auto;padding:24px 16px 60px}}
.question-num{{font-size:12px;color:#888;margin-bottom:4px}}
.question-text{{font-size:18px;font-weight:700;margin-bottom:20px;line-height:1.5}}
.choices{{display:flex;flex-direction:column;gap:10px}}
.choice-btn{{font-size:15px;padding:14px 18px;border:2px solid #e0e0e0;border-radius:10px;background:white;cursor:pointer;text-align:left;transition:all .15s;min-height:48px;display:flex;align-items:center;gap:12px}}
.choice-btn:hover:not(.disabled){{border-color:#999;background:#fafafa}}
.choice-btn.correct{{border-color:#4caf50;background:#e8f5e9;color:#2e7d32;font-weight:600}}
.choice-btn.wrong{{border-color:#e53935;background:#ffebee;color:#c62828}}
.choice-btn.disabled{{cursor:default;opacity:0.85}}
.choice-btn.reveal-correct{{border-color:#4caf50;background:#e8f5e9}}
.choice-label{{font-weight:700;color:#888;width:20px;flex-shrink:0;text-align:center}}
.explanation{{margin-top:16px;padding:14px 18px;background:#fff8e1;border:1px solid #ffe082;border-radius:8px;font-size:14px;color:#6d4c00;display:none}}
.explanation.show{{display:block}}
.next-btn{{margin-top:16px;font-size:14px;padding:10px 24px;border:none;border-radius:8px;background:#1a1a1a;color:white;cursor:pointer;font-weight:600;display:none}}
.next-btn.show{{display:inline-block}}
.next-btn:hover{{background:#333}}
.result{{text-align:center;padding:40px 20px}}
.result-score{{font-size:48px;font-weight:700;margin-bottom:8px}}
.result-score .total{{font-size:24px;color:#888}}
.result-label{{font-size:16px;color:#888;margin-bottom:24px}}
.result-msg{{font-size:15px;margin-bottom:24px;color:#555;line-height:1.6}}
.result-links{{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}}
.result-links a{{font-size:14px;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:600}}
.btn-primary{{background:#1a1a1a;color:white}}
.btn-secondary{{background:white;border:1px solid #ddd;color:#333}}
.footer{{text-align:center;font-size:11px;color:#bbb;margin-top:32px;padding-top:16px;border-top:1px solid #eee}}
.no-data{{text-align:center;padding:60px 20px;color:#aaa;font-size:15px}}
</style>
</head>
<body>
<div class="top-bar">
  <a class="back" href="index.html">← 学校選択</a>
  <span class="title" id="quizTitle">クイズ</span>
</div>

<div class="container">
  <div class="progress-wrap"><div class="progress-bar" id="progressBar" style="width:0%"></div></div>
  <div id="quizArea"></div>
  <div class="footer">志望校傾向クイズ</div>
</div>

<script>
const ALL_Q = {js_data};
const NAMES = {js_names};
const SUBJ_JP = {{"math":"算数","science":"理科","social":"社会","japanese":"国語"}};
const SUBJ_COLOR = {{"math":"#a73c34","science":"#2f6f63","social":"#5c5f91","japanese":"#8f7031"}};
const MAX_Q = 10;

const params = new URLSearchParams(location.search);
const school = params.get('school') || '';
const subject = params.get('subject') || '';

const schoolInfo = NAMES[school] || {{name: school, color: '#58687b'}};
const titleEl = document.getElementById('quizTitle');
titleEl.textContent = schoolInfo.name + ' ' + (SUBJ_JP[subject]||'') + ' クイズ';

const progressBar = document.getElementById('progressBar');
progressBar.style.background = schoolInfo.color;

const area = document.getElementById('quizArea');

// Get questions
let questions = [];
if (ALL_Q[school] && ALL_Q[school][subject]) {{
  questions = ALL_Q[school][subject].slice();
  // Shuffle and limit to MAX_Q
  for (let i = questions.length - 1; i > 0; i--) {{
    const j = Math.floor(Math.random() * (i + 1));
    [questions[i], questions[j]] = [questions[j], questions[i]];
  }}
  questions = questions.slice(0, MAX_Q);
}}

if (questions.length === 0) {{
  area.innerHTML = '<div class="no-data">この学校・教科のクイズデータがありません。<br><a href="index.html">← 学校選択に戻る</a></div>';
}} else {{
  let current = 0;
  let score = 0;

  function renderQuestion() {{
    const q = questions[current];
    const labels = ['A','B','C','D'];
    const total = questions.length;
    progressBar.style.width = ((current) / total * 100) + '%';

    area.innerHTML = `
      <div class="question-num">${{current+1}} / ${{total}}</div>
      <div class="question-text">${{q.q}}</div>
      <div class="choices">
        ${{q.choices.map((c, i) => `
          <button class="choice-btn" data-idx="${{i}}">
            <span class="choice-label">${{labels[i]}}</span>
            <span>${{c}}</span>
          </button>
        `).join('')}}
      </div>
      <div class="explanation" id="explanation">${{q.explanation}}</div>
      <button class="next-btn" id="nextBtn">${{current < total - 1 ? '次の問題 →' : '結果を見る'}}</button>
    `;

    document.querySelectorAll('.choice-btn').forEach(btn => {{
      btn.addEventListener('click', () => onChoose(parseInt(btn.dataset.idx)));
    }});
    document.getElementById('nextBtn').addEventListener('click', onNext);
  }}

  function onChoose(idx) {{
    const q = questions[current];
    const btns = document.querySelectorAll('.choice-btn');
    btns.forEach(b => {{
      b.classList.add('disabled');
      const bi = parseInt(b.dataset.idx);
      if (bi === q.answer) b.classList.add('correct');
      if (bi === idx && idx !== q.answer) b.classList.add('wrong');
    }});
    if (idx === q.answer) score++;
    document.getElementById('explanation').classList.add('show');
    document.getElementById('nextBtn').classList.add('show');
  }}

  function onNext() {{
    current++;
    if (current >= questions.length) {{
      showResult();
    }} else {{
      renderQuestion();
    }}
  }}

  function showResult() {{
    const total = questions.length;
    const pct = Math.round(score / total * 100);
    progressBar.style.width = '100%';
    let msg = '';
    if (pct >= 80) msg = '素晴らしい！この学校の出題傾向をよく理解しています。';
    else if (pct >= 50) msg = 'いい線いっています！プロファイルページで詳しく確認してみましょう。';
    else msg = '出題傾向の理解を深めましょう。プロファイルページが参考になります。';

    area.innerHTML = `
      <div class="result">
        <div class="result-score">${{score}} <span class="total">/ ${{total}}</span></div>
        <div class="result-label">正答率 ${{pct}}%</div>
        <div class="result-msg">${{msg}}</div>
        <div class="result-links">
          <a href="quiz.html?school=${{school}}&subject=${{subject}}" class="btn-primary">もう一度</a>
          <a href="index.html" class="btn-secondary">他の学校</a>
        </div>
      </div>
    `;
  }}

  renderQuestion();
}}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    all_data = collect_all()
    print(f"Loaded data for {len(all_data)} schools")

    # Generate questions
    all_questions: dict[str, dict[str, list]] = {}
    school_subjects: dict[str, dict] = {}  # for index page
    total_q = 0

    for school_slug, school_data in all_data.items():
        for subject_en in school_data:
            qs = generate_questions(school_slug, subject_en, school_data, all_data)
            if qs:
                all_questions.setdefault(school_slug, {})[subject_en] = qs
                school_subjects.setdefault(school_slug, {})[subject_en] = True
                total_q += len(qs)

    print(f"Generated {total_q} questions for {len(all_questions)} schools")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Write index
    index_html = build_index_html(school_subjects)
    (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print(f"Written: {(OUTPUT_DIR / 'index.html').relative_to(REPO_ROOT)}")

    # Write quiz player
    quiz_html = build_quiz_html(all_questions)
    (OUTPUT_DIR / "quiz.html").write_text(quiz_html, encoding="utf-8")
    print(f"Written: {(OUTPUT_DIR / 'quiz.html').relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
