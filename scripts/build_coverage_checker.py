#!/usr/bin/env python3
"""Build a unit-coverage checker: select a school, check off mastered units,
see coverage rate and priority study list.

Outputs:
  - data/published/sites/coverage/index.html    (school selection)
  - data/published/sites/coverage/checker.html   (checker player)
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from html import escape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_LABELS = REPO_ROOT / "config/problem-labels"
DERIVED_LABELS = REPO_ROOT / "data/derived/problem-labels"
OUTPUT_DIR = REPO_ROOT / "data/published/sites/coverage"

SUBJECT_EN_JP = {"math": "算数", "science": "理科", "social": "社会", "japanese": "国語"}
DIFFICULTY_LABELS = {1: "入門", 2: "基礎", 3: "標準", 4: "応用", 5: "差がつく"}
DIFFICULTY_COLORS = {1: "#6dae5a", 2: "#7cb5c7", 3: "#e0a83c", 4: "#d4704a", 5: "#b03a3a"}


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
# Record normalization & data loading
# ---------------------------------------------------------------------------

def _normalize_record(r: dict) -> dict | None:
    if isinstance(r.get("difficulty"), int) and "main_unit" in r:
        return {"difficulty_level": r["difficulty"], "main_unit": r.get("main_unit", "")}
    sl = r.get("search_labels", {})
    lm = r.get("learning_map", {})
    d = sl.get("difficulty", {})
    level = d.get("level") if isinstance(d, dict) else d if isinstance(d, int) else None
    if not level:
        return None
    return {"difficulty_level": level, "main_unit": lm.get("main_unit", "")}


def collect_all() -> dict:
    """Return {school_slug: {subject_en: [records]}}."""
    result: dict[str, dict[str, list]] = {}

    def add_records(school_slug: str, subject_en: str, raw_records: list):
        for r in raw_records:
            n = _normalize_record(r)
            if n and n["main_unit"]:
                result.setdefault(school_slug, {}).setdefault(subject_en, []).append(n)

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
                add_records(school_slug, subject_en, raw.get("records", []))

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
                add_records(school_slug, subject_en, raw.get("records", []))

    return result


def build_coverage_data(all_data: dict) -> dict:
    """Build per-school per-subject unit lists with frequency and avg difficulty.

    Returns: {school_slug: {subject_en: [{unit, count, avg_diff, weight}, ...]}}
    """
    coverage: dict[str, dict[str, list]] = {}

    for school_slug, school_data in all_data.items():
        for subject_en, records in school_data.items():
            unit_stats: dict[str, dict] = {}
            total = len(records)
            for r in records:
                u = r["main_unit"]
                if u not in unit_stats:
                    unit_stats[u] = {"count": 0, "diff_sum": 0}
                unit_stats[u]["count"] += 1
                unit_stats[u]["diff_sum"] += r["difficulty_level"]

            units = []
            for u, st in unit_stats.items():
                avg_d = st["diff_sum"] / st["count"] if st["count"] else 3.0
                weight = round(st["count"] / total * 100, 1) if total else 0
                units.append({
                    "unit": u,
                    "count": st["count"],
                    "avg_diff": round(avg_d, 1),
                    "weight": weight,
                })
            units.sort(key=lambda x: x["count"], reverse=True)
            coverage.setdefault(school_slug, {})[subject_en] = units

    return coverage


# ---------------------------------------------------------------------------
# HTML — index
# ---------------------------------------------------------------------------

def build_index_html(coverage: dict) -> str:
    cards = []
    for slug in sorted(coverage.keys()):
        info = SCHOOL_REGISTRY.get(slug, {"short": slug, "color": "#58687b"})
        subjects = sorted(coverage[slug].keys())
        badges = " ".join(
            f'<a href="checker.html?school={slug}&subject={s}" class="subj-badge subj-{s}">{SUBJECT_EN_JP[s]}</a>'
            for s in subjects
        )
        cards.append(f"""
        <div class="card" style="border-left-color:{info["color"]}">
          <div class="card-name" style="color:{info["color"]}">{escape(info["short"])}</div>
          <div class="card-subjects">{badges}</div>
        </div>""")

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>単元カバー率チェッカー — 学校選択</title>
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
  <h1>単元カバー率チェッカー</h1>
  <p class="sub">志望校を選び、習得済みの単元にチェック → カバー率と重点対策リストを確認</p>
  <input type="text" class="search-box" id="search" placeholder="学校名で検索…">
</div>
<div class="container">
  <div class="count" id="countLine">{len(cards)} 校</div>
  <div class="grid" id="grid">{"".join(cards)}</div>
  <div class="footer">単元カバー率チェッカー — {len(cards)} 校対応</div>
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
# HTML — checker player
# ---------------------------------------------------------------------------

def build_checker_html(coverage: dict) -> str:
    js_data = json.dumps(coverage, ensure_ascii=False)

    name_map = {}
    for slug in coverage:
        info = SCHOOL_REGISTRY.get(slug, {"short": slug, "color": "#58687b"})
        name_map[slug] = {"name": info["short"], "color": info.get("color", "#58687b")}
    js_names = json.dumps(name_map, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>単元カバー率チェッカー</title>
<style>
*,*::before,*::after{{box-sizing:border-box}}
body{{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans",sans-serif;background:#f7f7f5;color:#1a1a1a;line-height:1.5}}
.top-bar{{background:white;border-bottom:1px solid #e8e8e6;padding:14px 20px;position:sticky;top:0;z-index:100}}
.top-row{{display:flex;align-items:center;gap:16px}}
.back{{font-size:13px;color:#666;text-decoration:none}}
.back:hover{{color:#1a1a1a}}
.title{{font-size:16px;font-weight:700;flex:1}}
.container{{max-width:700px;margin:0 auto;padding:20px 16px 60px}}

/* Ring meter */
.meter-section{{text-align:center;margin-bottom:24px;padding:20px}}
.ring-wrap{{position:relative;width:160px;height:160px;margin:0 auto 12px}}
.ring-wrap svg{{transform:rotate(-90deg)}}
.ring-bg{{fill:none;stroke:#e8e8e6;stroke-width:12}}
.ring-fg{{fill:none;stroke-width:12;stroke-linecap:round;transition:stroke-dashoffset .4s,stroke .3s}}
.ring-text{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center}}
.ring-pct{{font-size:36px;font-weight:700;line-height:1}}
.ring-label{{font-size:12px;color:#888}}
.meter-stats{{display:flex;gap:20px;justify-content:center;font-size:13px;color:#666}}
.meter-stats strong{{color:#1a1a1a}}

/* Unit list */
.section-title{{font-size:14px;font-weight:700;margin:20px 0 12px;display:flex;align-items:center;gap:8px}}
.section-title .badge{{font-size:11px;background:#e8e8e6;color:#666;padding:2px 8px;border-radius:10px}}
.unit-list{{display:flex;flex-direction:column;gap:6px}}
.unit-item{{display:flex;align-items:center;gap:10px;padding:10px 14px;background:white;border:1px solid #e8e8e6;border-radius:8px;cursor:pointer;transition:all .15s;min-height:48px}}
.unit-item:hover{{border-color:#ccc}}
.unit-item.checked{{background:#f0faf0;border-color:#a5d6a7}}
.unit-item input[type=checkbox]{{width:20px;height:20px;accent-color:#4caf50;flex-shrink:0;cursor:pointer}}
.unit-name{{flex:1;font-size:14px}}
.unit-meta{{display:flex;gap:8px;flex-shrink:0;align-items:center}}
.unit-freq{{font-size:11px;color:#888;background:#f5f5f3;padding:2px 8px;border-radius:4px}}
.unit-diff{{font-size:11px;padding:2px 8px;border-radius:4px;color:white;font-weight:600}}
.unit-weight{{font-size:11px;color:#aaa}}

/* Priority list */
.priority-section{{margin-top:24px;padding:16px;background:#fff8e1;border:1px solid #ffe082;border-radius:10px}}
.priority-title{{font-size:14px;font-weight:700;color:#e65100;margin-bottom:10px}}
.priority-item{{font-size:13px;padding:6px 0;border-bottom:1px solid rgba(255,224,130,0.4);display:flex;align-items:center;gap:8px}}
.priority-item:last-child{{border-bottom:none}}
.priority-rank{{font-weight:700;color:#e65100;width:20px}}

.all-done{{text-align:center;padding:20px;color:#4caf50;font-size:14px;font-weight:600}}
.footer{{text-align:center;font-size:11px;color:#bbb;margin-top:32px;padding-top:16px;border-top:1px solid #eee}}
.no-data{{text-align:center;padding:60px 20px;color:#aaa;font-size:15px}}
.save-note{{text-align:center;font-size:11px;color:#aaa;margin-top:8px}}
</style>
</head>
<body>
<div class="top-bar">
  <div class="top-row">
    <a class="back" href="index.html">← 学校選択</a>
    <span class="title" id="pageTitle">カバー率チェック</span>
  </div>
</div>

<div class="container">
  <div id="content"></div>
  <div class="footer">単元カバー率チェッカー</div>
</div>

<script>
const ALL = {js_data};
const NAMES = {js_names};
const SUBJ_JP = {{"math":"算数","science":"理科","social":"社会","japanese":"国語"}};
const DIFF_COLORS = {{1:"#6dae5a",2:"#7cb5c7",3:"#e0a83c",4:"#d4704a",5:"#b03a3a"}};

const params = new URLSearchParams(location.search);
const school = params.get('school') || '';
const subject = params.get('subject') || '';

const info = NAMES[school] || {{name: school, color: '#58687b'}};
document.getElementById('pageTitle').textContent = info.name + ' ' + (SUBJ_JP[subject]||'') + ' カバー率';

const content = document.getElementById('content');
const units = (ALL[school]||{{}})[subject] || [];

if (units.length === 0) {{
  content.innerHTML = '<div class="no-data">この学校・教科のデータがありません。<br><a href="index.html">← 学校選択に戻る</a></div>';
}} else {{
  // localStorage key
  const storageKey = 'coverage_' + school + '_' + subject;

  // Load saved state
  let checked = {{}};
  try {{
    const saved = localStorage.getItem(storageKey);
    if (saved) checked = JSON.parse(saved);
  }} catch(e) {{}}

  const circumference = 2 * Math.PI * 68; // radius=68

  function render() {{
    const totalWeight = units.reduce((s,u) => s + u.weight, 0);
    const coveredWeight = units.filter(u => checked[u.unit]).reduce((s,u) => s + u.weight, 0);
    const pct = totalWeight > 0 ? Math.round(coveredWeight / totalWeight * 100) : 0;
    const checkedCount = units.filter(u => checked[u.unit]).length;
    const unchecked = units.filter(u => !checked[u.unit]);

    const dashOffset = circumference - (pct / 100) * circumference;
    const ringColor = pct >= 80 ? '#4caf50' : pct >= 50 ? '#ff9800' : info.color;

    let html = `
      <div class="meter-section">
        <div class="ring-wrap">
          <svg width="160" height="160">
            <circle class="ring-bg" cx="80" cy="80" r="68"/>
            <circle class="ring-fg" cx="80" cy="80" r="68"
              stroke="${{ringColor}}"
              stroke-dasharray="${{circumference}}"
              stroke-dashoffset="${{dashOffset}}"/>
          </svg>
          <div class="ring-text">
            <div class="ring-pct" style="color:${{ringColor}}">${{pct}}%</div>
            <div class="ring-label">カバー率</div>
          </div>
        </div>
        <div class="meter-stats">
          <span>習得済み <strong>${{checkedCount}}</strong> / ${{units.length}} 単元</span>
          <span>重み付き <strong>${{pct}}%</strong></span>
        </div>
        <div class="save-note">チェック状態は自動保存されます</div>
      </div>
    `;

    // Priority list (unchecked, sorted by frequency)
    if (unchecked.length > 0) {{
      const top5 = unchecked.slice(0, 5);
      html += `<div class="priority-section">
        <div class="priority-title">重点対策が必要な単元（上位${{Math.min(5, unchecked.length)}}）</div>
        ${{top5.map((u, i) => `
          <div class="priority-item">
            <span class="priority-rank">${{i+1}}</span>
            <span>${{u.unit}}</span>
            <span class="unit-freq">${{u.count}}回出題</span>
          </div>
        `).join('')}}
      </div>`;
    }} else {{
      html += '<div class="all-done">全単元クリア！</div>';
    }}

    // Checklist
    html += `
      <div class="section-title">単元リスト <span class="badge">${{checkedCount}}/${{units.length}}</span></div>
      <div class="unit-list">
        ${{units.map(u => `
          <label class="unit-item ${{checked[u.unit] ? 'checked' : ''}}">
            <input type="checkbox" data-unit="${{u.unit}}" ${{checked[u.unit] ? 'checked' : ''}}>
            <span class="unit-name">${{u.unit}}</span>
            <div class="unit-meta">
              <span class="unit-freq">${{u.count}}回</span>
              <span class="unit-diff" style="background:${{DIFF_COLORS[Math.round(u.avg_diff)] || '#888'}}">${{u.avg_diff}}</span>
              <span class="unit-weight">${{u.weight}}%</span>
            </div>
          </label>
        `).join('')}}
      </div>
    `;

    content.innerHTML = html;

    // Attach handlers
    content.querySelectorAll('input[type=checkbox]').forEach(cb => {{
      cb.addEventListener('change', () => {{
        const unit = cb.dataset.unit;
        if (cb.checked) checked[unit] = true;
        else delete checked[unit];
        try {{ localStorage.setItem(storageKey, JSON.stringify(checked)); }} catch(e) {{}}
        render();
      }});
    }});
  }}

  render();
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

    coverage = build_coverage_data(all_data)
    school_count = len(coverage)
    unit_count = sum(len(u) for subjs in coverage.values() for u in subjs.values())
    print(f"Coverage data: {school_count} schools, {unit_count} unit entries")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Write index
    idx = build_index_html(coverage)
    (OUTPUT_DIR / "index.html").write_text(idx, encoding="utf-8")
    print(f"Written: {(OUTPUT_DIR / 'index.html').relative_to(REPO_ROOT)}")

    # Write checker
    chk = build_checker_html(coverage)
    (OUTPUT_DIR / "checker.html").write_text(chk, encoding="utf-8")
    print(f"Written: {(OUTPUT_DIR / 'checker.html').relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
