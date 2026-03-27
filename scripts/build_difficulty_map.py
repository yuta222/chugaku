#!/usr/bin/env python3
"""Build a full-school × subject difficulty heatmap as a static HTML page.

Scans config/problem-labels/ for all school-subject combinations,
computes average difficulty and problem counts, and produces
a sortable/filterable heatmap at data/published/sites/difficulty-map/index.html.
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
OUTPUT = REPO_ROOT / "data/published/sites/difficulty-map/index.html"

SUBJECT_SLUG_MAP = {"算数": "math", "理科": "science", "社会": "social", "国語": "japanese"}
SUBJECT_EN_JP = {"math": "算数", "science": "理科", "social": "社会", "japanese": "国語"}

DIFFICULTY_COLORS = {1: "#6dae5a", 2: "#7cb5c7", 3: "#e0a83c", 4: "#d4704a", 5: "#b03a3a"}
DIFFICULTY_LABELS = {1: "入門", 2: "基礎", 3: "標準", 4: "応用", 5: "差がつく"}


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
# Data loading
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


def load_all_data() -> list[dict]:
    """Scan config/problem-labels + data/derived, return per-school aggregated rows."""
    # Collect (school_slug, subject_en) → [records]
    school_subject: dict[tuple[str, str], list[dict]] = {}

    # Scan config/problem-labels/
    if CONFIG_LABELS.exists():
        for d in sorted(CONFIG_LABELS.iterdir()):
            if not d.is_dir():
                continue
            subject_en = None
            school_slug = None
            for subj_en in ["math", "science", "social", "japanese"]:
                tag = f"-{subj_en}-bigq"
                if d.name.endswith(tag):
                    subject_en = subj_en
                    school_slug = d.name[: -len(tag)]
                    break
            if not subject_en or not school_slug:
                continue
            key = (school_slug, subject_en)
            for jf in sorted(d.glob("*.json")):
                if not jf.stem.isdigit():
                    continue
                try:
                    raw = json.loads(jf.read_text(encoding="utf-8"))
                except Exception:
                    continue
                for r in raw.get("records", []):
                    n = _normalize_record(r)
                    if n:
                        school_subject.setdefault(key, []).append(n)

    # Also scan data/derived/problem-labels/
    if DERIVED_LABELS.exists():
        for d in sorted(DERIVED_LABELS.iterdir()):
            if not d.is_dir():
                continue
            subject_en = None
            school_slug = None
            for subj_en in ["math", "science", "social", "japanese"]:
                tag = f"-{subj_en}-bigq"
                if d.name.endswith(tag):
                    subject_en = subj_en
                    school_slug = d.name[: -len(tag)]
                    break
            if not subject_en or not school_slug:
                continue
            key = (school_slug, subject_en)
            if key in school_subject:
                continue  # config/ already loaded
            for year_dir in sorted(d.iterdir()):
                if not year_dir.is_dir() or not year_dir.name.isdigit():
                    continue
                review_path = year_dir / "review.json"
                if not review_path.exists():
                    continue
                try:
                    raw = json.loads(review_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                for r in raw.get("records", []):
                    n = _normalize_record(r)
                    if n:
                        school_subject.setdefault(key, []).append(n)

    # Aggregate per school
    school_data: dict[str, dict] = {}
    for (school_slug, subject_en), records in school_subject.items():
        if school_slug not in school_data:
            info = SCHOOL_REGISTRY.get(school_slug, {"name": school_slug, "short": school_slug, "color": "#58687b", "region": ""})
            school_data[school_slug] = {
                "slug": school_slug,
                "name": info["name"],
                "short": info["short"],
                "region": info["region"],
                "subjects": {},
            }
        diffs = [r["difficulty_level"] for r in records]
        avg = sum(diffs) / len(diffs) if diffs else 0
        school_data[school_slug]["subjects"][subject_en] = {
            "avg": round(avg, 2),
            "count": len(records),
        }

    # Compute overall average
    rows = []
    for slug, sd in school_data.items():
        all_avgs = [v["avg"] for v in sd["subjects"].values() if v["count"] > 0]
        sd["overall_avg"] = round(sum(all_avgs) / len(all_avgs), 2) if all_avgs else 0
        sd["total_count"] = sum(v["count"] for v in sd["subjects"].values())
        rows.append(sd)

    rows.sort(key=lambda x: x["overall_avg"], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def _diff_color(avg: float) -> str:
    if avg == 0:
        return "#f0f0ee"
    if avg >= 4.5:
        return DIFFICULTY_COLORS[5]
    if avg >= 3.5:
        return DIFFICULTY_COLORS[4]
    if avg >= 2.5:
        return DIFFICULTY_COLORS[3]
    if avg >= 1.5:
        return DIFFICULTY_COLORS[2]
    return DIFFICULTY_COLORS[1]


def _diff_text_color(avg: float) -> str:
    return "#fff" if avg >= 3.5 else "#333" if avg > 0 else "#ccc"


def build_html(rows: list[dict]) -> str:
    regions = sorted({r["region"] for r in rows if r["region"]})

    # Build JS data
    js_rows = []
    for r in rows:
        subj = {}
        for s in ["math", "science", "social", "japanese"]:
            d = r["subjects"].get(s, {"avg": 0, "count": 0})
            subj[s] = {"a": d["avg"], "c": d["count"]}
        js_rows.append({
            "slug": r["slug"],
            "name": r["short"],
            "region": r["region"],
            "subjects": subj,
            "overall": r["overall_avg"],
            "total": r["total_count"],
        })

    js_data = json.dumps(js_rows, ensure_ascii=False)
    js_regions = json.dumps(regions, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>全校難易度マップ — {len(rows)}校×4教科</title>
<style>
*,*::before,*::after{{box-sizing:border-box}}
body{{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans",sans-serif;background:#f7f7f5;color:#1a1a1a;line-height:1.5}}
.top-bar{{background:white;border-bottom:1px solid #e8e8e6;padding:16px 20px;position:sticky;top:0;z-index:100}}
.top-bar h1{{font-size:18px;margin:0 0 4px;font-weight:700}}
.top-bar .sub{{font-size:13px;color:#888;margin:0}}
.filters{{display:flex;gap:12px;flex-wrap:wrap;margin-top:12px;align-items:center}}
.filters label{{font-size:12px;color:#888}}
.filters select,.filters input{{font-size:13px;padding:4px 8px;border:1px solid #ddd;border-radius:6px;background:white}}
.filters input[type=text]{{width:180px}}
.container{{max-width:1100px;margin:0 auto;padding:16px 12px 40px}}
.table-wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
table{{width:100%;border-collapse:collapse;font-size:13px;min-width:640px}}
thead th{{position:sticky;top:92px;background:#fafaf8;border-bottom:2px solid #e0e0e0;padding:8px 10px;text-align:center;font-weight:600;cursor:pointer;user-select:none;white-space:nowrap;z-index:50}}
thead th:hover{{background:#f0f0ee}}
thead th.sort-asc::after{{content:" ▲";font-size:10px}}
thead th.sort-desc::after{{content:" ▼";font-size:10px}}
thead th:first-child{{text-align:left;min-width:160px;position:sticky;left:0;z-index:60;background:#fafaf8}}
tbody td{{padding:6px 10px;text-align:center;border-bottom:1px solid #f0f0ee}}
tbody td:first-child{{text-align:left;font-weight:500;position:sticky;left:0;background:#fafaf8;z-index:10;white-space:nowrap}}
tbody tr:hover td{{background:rgba(0,0,0,0.02)}}
.cell{{display:inline-block;min-width:52px;padding:3px 8px;border-radius:5px;font-weight:600;font-size:12px;text-align:center;line-height:1.4}}
.cell small{{display:block;font-weight:400;font-size:10px;opacity:0.8}}
.cell-empty{{color:#ccc;font-size:11px}}
.school-link{{color:inherit;text-decoration:none}}
.school-link:hover{{text-decoration:underline}}
.legend{{display:flex;gap:16px;flex-wrap:wrap;margin-top:12px;font-size:12px;color:#888}}
.legend-item{{display:flex;align-items:center;gap:4px}}
.legend-dot{{width:14px;height:14px;border-radius:3px}}
.stats{{font-size:12px;color:#aaa;margin-top:8px}}
.footer{{text-align:center;font-size:11px;color:#bbb;margin-top:24px;padding-top:16px;border-top:1px solid #eee}}
@media(max-width:600px){{
  .filters{{flex-direction:column;gap:8px}}
  thead th{{font-size:12px;padding:6px 4px}}
  tbody td{{padding:4px 4px;font-size:12px}}
}}
</style>
</head>
<body>

<div class="top-bar">
  <h1>全校 難易度マップ</h1>
  <p class="sub">{len(rows)} 校 × 4 教科の平均難易度ヒートマップ</p>
  <div class="filters">
    <label>地域:
      <select id="regionFilter">
        <option value="">すべて</option>
      </select>
    </label>
    <label>難易度:
      <select id="diffFilter">
        <option value="">すべて</option>
        <option value="4">4.0以上（応用〜）</option>
        <option value="3">3.0以上（標準〜）</option>
        <option value="2">2.0〜3.0（基礎〜標準）</option>
        <option value="1">2.0未満（入門〜基礎）</option>
      </select>
    </label>
    <label>検索:
      <input type="text" id="searchInput" placeholder="学校名…">
    </label>
  </div>
  <div class="legend">
    <span class="legend-item"><span class="legend-dot" style="background:#6dae5a"></span>入門(1)</span>
    <span class="legend-item"><span class="legend-dot" style="background:#7cb5c7"></span>基礎(2)</span>
    <span class="legend-item"><span class="legend-dot" style="background:#e0a83c"></span>標準(3)</span>
    <span class="legend-item"><span class="legend-dot" style="background:#d4704a"></span>応用(4)</span>
    <span class="legend-item"><span class="legend-dot" style="background:#b03a3a"></span>差がつく(5)</span>
  </div>
</div>

<div class="container">
  <div class="stats" id="statsLine"></div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th data-col="name">学校名</th>
          <th data-col="math">算数</th>
          <th data-col="science">理科</th>
          <th data-col="social">社会</th>
          <th data-col="japanese">国語</th>
          <th data-col="overall">総合平均</th>
          <th data-col="total">問題数</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
  <div class="footer">全校難易度マップ — {len(rows)} 校</div>
</div>

<script>
const DATA = {js_data};
const REGIONS = {js_regions};
const DIFF_COLORS = {{1:"#6dae5a",2:"#7cb5c7",3:"#e0a83c",4:"#d4704a",5:"#b03a3a"}};
const PROFILE_SUBJECTS = {{"math":"school-math-profiles","science":"school-science-profiles","social":"school-social-profiles","japanese":"school-japanese-profiles"}};

// Populate region filter
const regionSel = document.getElementById('regionFilter');
REGIONS.forEach(r => {{
  const o = document.createElement('option');
  o.value = r; o.textContent = r;
  regionSel.appendChild(o);
}});

function diffColor(avg) {{
  if (avg === 0) return '#f0f0ee';
  if (avg >= 4.5) return DIFF_COLORS[5];
  if (avg >= 3.5) return DIFF_COLORS[4];
  if (avg >= 2.5) return DIFF_COLORS[3];
  if (avg >= 1.5) return DIFF_COLORS[2];
  return DIFF_COLORS[1];
}}
function textColor(avg) {{
  return avg >= 3.5 ? '#fff' : avg > 0 ? '#333' : '#ccc';
}}

function cellHtml(subj, slug) {{
  const d = subj || {{a:0,c:0}};
  if (d.c === 0) return '<span class="cell-empty">—</span>';
  const bg = diffColor(d.a);
  const tc = textColor(d.a);
  return `<span class="cell" style="background:${{bg}};color:${{tc}}">${{d.a.toFixed(1)}}<small>${{d.c}}問</small></span>`;
}}

let sortCol = 'overall', sortDir = 'desc';

function render() {{
  const region = regionSel.value;
  const diffF = document.getElementById('diffFilter').value;
  const search = document.getElementById('searchInput').value.toLowerCase();

  let filtered = DATA.filter(r => {{
    if (region && r.region !== region) return false;
    if (search && !r.name.toLowerCase().includes(search) && !r.slug.includes(search)) return false;
    if (diffF === '4' && r.overall < 4.0) return false;
    if (diffF === '3' && r.overall < 3.0) return false;
    if (diffF === '2' && (r.overall < 2.0 || r.overall >= 3.0)) return false;
    if (diffF === '1' && r.overall >= 2.0) return false;
    return true;
  }});

  filtered.sort((a, b) => {{
    let va, vb;
    if (sortCol === 'name') {{ va = a.name; vb = b.name; }}
    else if (sortCol === 'total') {{ va = a.total; vb = b.total; }}
    else if (sortCol === 'overall') {{ va = a.overall; vb = b.overall; }}
    else {{ va = (a.subjects[sortCol]||{{}}).a||0; vb = (b.subjects[sortCol]||{{}}).a||0; }}
    if (typeof va === 'string') return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortDir === 'asc' ? va - vb : vb - va;
  }});

  const tbody = document.getElementById('tbody');
  tbody.innerHTML = filtered.map(r => {{
    const subjects = ['math','science','social','japanese'];
    const cells = subjects.map(s => `<td>${{cellHtml(r.subjects[s], r.slug)}}</td>`).join('');
    return `<tr>
      <td>${{r.name}}</td>
      ${{cells}}
      <td><span class="cell" style="background:${{diffColor(r.overall)}};color:${{textColor(r.overall)}}">${{r.overall.toFixed(1)}}</span></td>
      <td>${{r.total}}</td>
    </tr>`;
  }}).join('');

  document.getElementById('statsLine').textContent = `${{filtered.length}} 校表示中 / 全 ${{DATA.length}} 校`;

  // Update sort indicators
  document.querySelectorAll('thead th').forEach(th => {{
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.col === sortCol) th.classList.add(sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
  }});
}}

// Sort click handlers
document.querySelectorAll('thead th').forEach(th => {{
  th.addEventListener('click', () => {{
    const col = th.dataset.col;
    if (sortCol === col) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    else {{ sortCol = col; sortDir = col === 'name' ? 'asc' : 'desc'; }}
    render();
  }});
}});

// Filter handlers
regionSel.addEventListener('change', render);
document.getElementById('diffFilter').addEventListener('change', render);
document.getElementById('searchInput').addEventListener('input', render);

render();
</script>
</body>
</html>"""


def main():
    rows = load_all_data()
    print(f"Collected {len(rows)} schools")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build_html(rows), encoding="utf-8")
    print(f"Written: {OUTPUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
