#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_PDF_ROOT = REPO_ROOT / "data/raw/pdfs/開成中学校"
PAGE_IMAGE_ROOT = REPO_ROOT / "data/derived/page-images/開成中学校"
OUTPUT_ROOT = REPO_ROOT / "data/derived/problem-labels/kaisei-all-years-math-bigq"
MANUAL_ROOT = REPO_ROOT / "config/problem-labels/kaisei-all-years-math-bigq"
YEARS = list(range(2026, 2004, -1))

QUESTION_LINE_RE = re.compile(r"^(?P<num>[1-6])[)）.]?$")
QUESTION_PREFIX_RE = re.compile(r"^(?P<num>[1-6])[)）. ]")
ANSWER_PREFIX_RE = re.compile(r"^(?P<num>[1-6])(?:[)）.]|\s*（|\s+[^\d])")
HAS_JAPANESE_RE = re.compile(r"[ぁ-んァ-ヶ一-龠]")
PAGE_MARKER_RE = re.compile(r"^## page-(\d+)$")
SEPARATOR_RE = re.compile(r"^[-=－ー_・…．.0-9： ]+$")
SHORT_FIGURE_RE = re.compile(r"^[A-ZＡ-Ｚa-zａ-ｚぁ-んァ-ヶ一-龠0-9０-９]+$")

CIRCLED_TO_ASCII = str.maketrans(
    {
        "①": "1",
        "②": "2",
        "③": "3",
        "④": "4",
        "⑤": "5",
        "⑥": "6",
        "⑦": "7",
        "⑧": "8",
        "⑨": "9",
    }
)

GENERIC_PAGE_LINES = {
    "このページは白紙です。",
    "問題はまだ続きます。",
    "問題は以上です。",
    "解答",
    "解答と解説",
    "算数",
    "開成",
    "成",
    "開",
    "BC算数",
}

BLANK_PAGE_HINTS = (
    "このページは白紙です。",
    "問題はまだ続きます。",
    "問題は以上です。",
)

GENERIC_PAGE_PATTERNS = [
    re.compile(r"^平成\d+年度$"),
    re.compile(r"^\d{4}年度$"),
    re.compile(r"^\(\d+分\)$"),
    re.compile(r"^開成中学校"),
    re.compile(r"^[BC]\d?算数"),
    re.compile(r"^B\d 算数"),
    re.compile(r"^C\d 算数"),
    re.compile(r"^B算数"),
    re.compile(r"^C算数"),
    re.compile(r"^◎"),
    re.compile(r"^【"),
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def merge_dict(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = merge_dict(existing, value)
        else:
            merged[key] = value
    return merged


def normalize_text(value: str) -> str:
    value = value.translate(CIRCLED_TO_ASCII)
    value = value.replace("　", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def split_full_text_pages(text: str) -> list[tuple[int, list[str]]]:
    current_page = None
    current_lines: list[str] = []
    pages: list[tuple[int, list[str]]] = []

    for raw_line in text.splitlines():
        marker = PAGE_MARKER_RE.match(raw_line.strip())
        if marker:
            if current_page is not None:
                pages.append((current_page, current_lines))
            current_page = int(marker.group(1))
            current_lines = []
            continue
        if current_page is not None:
            current_lines.append(raw_line.rstrip("\n"))

    if current_page is not None:
        pages.append((current_page, current_lines))

    return pages


def is_generic_line(line: str) -> bool:
    if not line:
        return True
    if line in GENERIC_PAGE_LINES:
        return True
    if SEPARATOR_RE.fullmatch(line) and len(line) <= 10:
        return True
    return any(pattern.search(line) for pattern in GENERIC_PAGE_PATTERNS)


def clean_problem_page(lines: Iterable[str]) -> tuple[list[str], bool]:
    cleaned: list[str] = []

    for raw in lines:
        line = normalize_text(raw)
        if not line:
            continue
        if "受験番号" in line:
            return cleaned, True
        if "このページは白紙です" in line or "問題はまだ続きます" in line or "問題は以上です" in line:
            continue
        if QUESTION_LINE_RE.fullmatch(line):
            cleaned.append(line)
            continue
        if len(line) <= 4 and not HAS_JAPANESE_RE.search(line):
            continue
        if is_generic_line(line):
            continue
        cleaned.append(line)

    return cleaned, False


def is_intro_page(lines: list[str]) -> bool:
    joined = " ".join(lines[:8])
    return any(
        token in joined
        for token in [
            "この冊子について",
            "解答上の注意",
            "試験中の注意",
            "試験開始の合図",
            "冊子に手をふれて",
            "答えはすべて",
            "解答用紙",
        ]
    )


def starts_with_subpart(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(("（", "(", "①", "②", "③", "④", "ア", "イ", "ウ", "エ", "A", "B", "C"))


def is_boundary_candidate(lines: list[str], idx: int, expected_q: int) -> bool:
    line = lines[idx]
    match = QUESTION_LINE_RE.fullmatch(line)
    if not match:
        return False
    if int(match.group("num")) != expected_q:
        return False
    if idx + 1 >= len(lines):
        return False
    next_line = lines[idx + 1].strip()
    if len(next_line) < 8:
        return False
    if next_line.startswith(("→", "・", "●", "A", "B", "C", "D", "E", "F", "P", "Q", "R")):
        return False
    return bool(HAS_JAPANESE_RE.search(next_line))


def extract_problem_blocks(full_text_path: Path) -> list[dict[str, object]]:
    pages = split_full_text_pages(read_text(full_text_path))
    blocks: list[dict[str, object]] = []
    current_q = 1
    current_lines: list[str] = []
    current_pages: list[int] = []
    started = False
    previous_blank_gap = False

    def flush() -> None:
        nonlocal current_lines, current_pages
        if not current_lines:
            return
        blocks.append(
            {
                "question_no": len(blocks) + 1,
                "pages": current_pages[:],
                "lines": current_lines[:],
            }
        )
        current_lines = []
        current_pages = []

    for page_no, raw_lines in pages:
        normalized_raw = [normalize_text(raw) for raw in raw_lines]
        page_was_blank = any(hint in line for line in normalized_raw for hint in BLANK_PAGE_HINTS)
        cleaned, should_stop = clean_problem_page(raw_lines)

        if should_stop and started and not cleaned:
            break
        if not cleaned:
            previous_blank_gap = page_was_blank
            if should_stop:
                break
            continue
        if not started:
            if is_intro_page(cleaned):
                continue
            started = True
        elif (
            previous_blank_gap
            and current_lines
            and not starts_with_subpart(cleaned[0])
            and not is_boundary_candidate(cleaned, 0, current_q)
            and not is_boundary_candidate(cleaned, 0, current_q + 1)
        ):
            flush()
            current_q += 1

        previous_blank_gap = False

        for idx, line in enumerate(cleaned):
            if is_boundary_candidate(cleaned, idx, current_q):
                if not current_lines:
                    continue
            elif is_boundary_candidate(cleaned, idx, current_q + 1):
                if current_lines:
                    flush()
                    current_q += 1
                    continue

            current_lines.append(line)
            if page_no not in current_pages:
                current_pages.append(page_no)

        if should_stop:
            break

    flush()

    return blocks


def extract_answer_blocks(full_text_path: Path) -> dict[int, str]:
    pages = split_full_text_pages(read_text(full_text_path))
    blocks: dict[int, list[str]] = {}
    current_q = None

    def parse_answer_qno(line: str) -> int | None:
        normalized = line.translate(CIRCLED_TO_ASCII)
        exact = QUESTION_LINE_RE.fullmatch(normalized)
        if exact:
            return int(exact.group("num"))
        prefixed = ANSWER_PREFIX_RE.match(normalized)
        if prefixed:
            return int(prefixed.group("num"))
        return None

    for _, raw_lines in pages:
        for raw in raw_lines:
            line = normalize_text(raw)
            if not line or is_generic_line(line):
                continue
            if "受験番号" in line:
                continue

            qno = parse_answer_qno(line)
            exact = QUESTION_LINE_RE.fullmatch(line)
            if exact:
                current_q = int(exact.group("num"))
                blocks.setdefault(current_q, [])
                continue
            prefixed = ANSWER_PREFIX_RE.match(line)
            if prefixed:
                current_q = int(prefixed.group("num"))
                blocks.setdefault(current_q, [])
                rest = line[prefixed.end() :].strip()
                if rest:
                    blocks[current_q].append(rest)
                continue
            if qno is not None and current_q != qno:
                current_q = qno
                blocks.setdefault(current_q, [])
                rest = line[1:].strip()
                if rest:
                    blocks[current_q].append(rest)
                continue

            if current_q is not None:
                blocks.setdefault(current_q, []).append(line)

    return {
        qno: normalize_text(" ".join(lines[:12]))[:500]
        for qno, lines in blocks.items()
        if lines
    }


def summarize_problem(lines: list[str]) -> str:
    informative: list[str] = []

    for line in lines:
        stripped = line.strip()
        if len(stripped) <= 1:
            continue
        if SHORT_FIGURE_RE.fullmatch(stripped) and len(stripped) <= 2:
            continue
        informative.append(stripped)
        if len(" ".join(informative)) >= 420:
            break

    return normalize_text(" ".join(informative))[:500]


def infer_problem_core(summary: str) -> str:
    if "何通り" in summary or "通り" in summary:
        return "条件に合う並べ方や個数を、漏れなく数え上げる問題です。"
    if any(token in summary for token in ["秒速", "分速", "時速", "出発", "到着", "往復", "地点", "追いつ"]):
        return "動き方や出会い方の条件を整理して、速さの関係を求める問題です。"
    if any(token in summary for token in ["立方体", "直方体", "角柱", "円柱", "切断", "断面", "展開図", "体積"]):
        return "立体の見え方や切断の条件を整理して、形や体積を求める問題です。"
    if any(token in summary for token in ["面積", "三角形", "四角形", "六角形", "円", "おうぎ形"]):
        return "図形の性質を使って、面積や長さを整理する問題です。"
    if any(token in summary for token in ["分数", "分子", "分母", "約分"]):
        return "分数の条件や大小関係を整理して、値を決める問題です。"
    if any(token in summary for token in ["割合", "食塩水", "百分率", "比"]):
        return "比や割合を同じ土俵にそろえて考える問題です。"
    if any(token in summary for token in ["倍数", "約数", "割り切れ", "公倍数", "公約数"]):
        return "数の性質や周期性を使って条件をしぼる問題です。"
    return "条件を整理しながら、複数の知識を組み合わせて解く問題です。"


@dataclass(frozen=True)
class UnitProfile:
    code: str
    name: str
    keywords: tuple[str, ...]
    support_units: tuple[str, ...]
    cross_skills: tuple[str, ...]
    advanced_labels: tuple[str, ...] = ()


UNIT_PROFILES = [
    UnitProfile(
        code="unit.speed",
        name="速さ（小6）",
        keywords=("秒速", "分速", "時速", "出発", "到着", "進み", "追いつ", "すれ違", "往復", "地点", "道のり", "旅", "時針", "分針", "秒針", "時計", "時報"),
        support_units=("比例（小5）", "変わり方（小4）"),
        cross_skills=("図にする", "表にする"),
        advanced_labels=("旅人算",),
    ),
    UnitProfile(
        code="unit.counting",
        name="場合の数（小6）",
        keywords=("何通り", "通り", "並べ", "選び", "組み", "場合", "カード", "種類", "個数", "すべて書き出し", "数え"),
        support_units=("変わり方（小4）", "大きい数（小4）"),
        cross_skills=("場合分け", "条件整理"),
        advanced_labels=("順列・組合せ",),
    ),
    UnitProfile(
        code="unit.solid",
        name="立体（小5）",
        keywords=("立方体", "直方体", "三角柱", "角柱", "円柱", "立体", "切断", "断面", "展開図", "見取図", "体積", "底面"),
        support_units=("面積（小5）", "比（小6）"),
        cross_skills=("図にする", "条件整理"),
        advanced_labels=("切断", "展開図"),
    ),
    UnitProfile(
        code="unit.area",
        name="面積（小5）",
        keywords=("面積", "三角形", "四角形", "正方形", "平行四辺形", "六角形", "図形", "扇形", "おうぎ形", "円", "正三角形"),
        support_units=("比（小6）", "拡大図と縮図（小6）"),
        cross_skills=("図にする", "同じ土俵にそろえる"),
        advanced_labels=("相似",),
    ),
    UnitProfile(
        code="unit.fraction",
        name="分数（小5）",
        keywords=("分数", "分子", "分母", "約分", "帯分数", "通分"),
        support_units=("大きい数（小4）", "文字と式（小6）"),
        cross_skills=("同じ土俵にそろえる", "条件整理"),
    ),
    UnitProfile(
        code="unit.ratio",
        name="比（小6）",
        keywords=("比", "割合", "百分率", "食塩水", "濃度", "もとにする量", "比べる量"),
        support_units=("割合（小5）", "単位量当たりの大きさ（小5）"),
        cross_skills=("同じ土俵にそろえる", "図にする"),
    ),
    UnitProfile(
        code="unit.divisibility",
        name="倍数と約数（小5）",
        keywords=("倍数", "約数", "公倍数", "公約数", "割り切れ", "9の倍数", "4の倍数", "整数"),
        support_units=("規則性を見つける",),
        cross_skills=("規則性を見つける", "条件整理"),
    ),
    UnitProfile(
        code="unit.expression",
        name="文字と式（小6）",
        keywords=("式", "あてはまる", "空らん", "x", "y", "関係", "一般", "何番目", "規則"),
        support_units=("式と計算の順序（小4）", "変わり方（小4）"),
        cross_skills=("条件整理", "逆に考える"),
    ),
]


def score_units(text: str) -> list[tuple[UnitProfile, int]]:
    scores: list[tuple[UnitProfile, int]] = []
    for profile in UNIT_PROFILES:
        score = 0
        for keyword in profile.keywords:
            if keyword in text:
                score += 3 if len(keyword) >= 3 else 2
        if score > 0:
            scores.append((profile, score))

    if not scores:
        fallback = next(profile for profile in UNIT_PROFILES if profile.code == "unit.expression")
        return [(fallback, 1)]

    scores.sort(key=lambda item: item[1], reverse=True)
    return scores


def detect_cross_skills(text: str, main_profile: UnitProfile) -> list[str]:
    skills = set(main_profile.cross_skills)
    if any(token in text for token in ["図", "三角形", "四角形", "円", "立方体", "直方体", "見取図", "展開図"]):
        skills.add("図にする")
    if any(token in text for token in ["表", "グラフ", "変化", "規則", "周期"]):
        skills.add("表にする")
    if any(token in text for token in ["場合", "通り", "分けて"]):
        skills.add("場合分け")
    if any(token in text for token in ["約分", "通分", "割合", "比", "単位", "秒速", "分速", "時速"]):
        skills.add("同じ土俵にそろえる")
    if any(token in text for token in ["最初", "最後", "戻", "逆", "引き返"]):
        skills.add("逆に考える")
    if any(token in text for token in ["くり返", "周期", "何番目", "順に"]):
        skills.add("規則性を見つける")
    return list(sorted(skills))


def detect_advanced_labels(text: str, main_profile: UnitProfile) -> list[str]:
    labels = set(main_profile.advanced_labels)
    if any(token in text for token in ["動点", "往復", "交点", "出発してから"]):
        labels.add("動点")
    if any(token in text for token in ["時針", "分針", "秒針", "時計", "時報"]):
        labels.add("時計算")
    if any(token in text for token in ["追いつ", "すれ違", "出会"]):
        labels.add("旅人算")
    if any(token in text for token in ["周期", "くり返"]):
        labels.add("周期算")
    if any(token in text for token in ["最大", "最も大きい", "最も小さい", "なるべく大きい"]):
        labels.add("最大最小")
    return list(sorted(labels))


def build_secondary_labels(
    scored_units: list[tuple[UnitProfile, int]],
    main_profile: UnitProfile,
    advanced_labels: list[str],
) -> list[dict[str, str]]:
    labels: list[dict[str, str]] = []

    for profile, _ in scored_units[1:3]:
        labels.append({"code": profile.code, "name": profile.name.replace("（小5）", "").replace("（小6）", "").replace("（小4）", "")})

    for label in advanced_labels:
        if len(labels) >= 2:
            break
        labels.append({"code": f"advanced.{label}", "name": label})

    if not labels and main_profile.name.startswith("速さ"):
        labels.append({"code": "skill.change", "name": "変わり方"})

    return labels[:2]


def normalize_unit_name(unit_name: str) -> str:
    return unit_name.replace("（小4）", "").replace("（小5）", "").replace("（小6）", "")


def build_rationale(
    summary: str,
    main_profile: UnitProfile,
    supporting_units: list[str],
    advanced_labels: list[str],
) -> str:
    pieces = [f"問題の中心は {normalize_unit_name(main_profile.name)} です。"]
    if supporting_units:
        pieces.append(f"{'、'.join(supporting_units[:2])} を補助的に使う構成です。")
    if advanced_labels:
        pieces.append(f"入試特有の見どころは {'、'.join(advanced_labels[:2])} です。")
    if "何通り" in summary or "通り" in summary:
        pieces.append("条件を漏れなく数え上げる整理が解法の軸になります。")
    elif any(token in summary for token in ["立方体", "切断", "断面", "展開図"]):
        pieces.append("図形の対応関係を追うことが解法の軸になります。")
    elif any(token in summary for token in ["秒速", "分速", "時速", "出発", "到着"]):
        pieces.append("動きの関係を図や表に置き換える整理が解法の軸になります。")
    return "".join(pieces)


def estimate_difficulty(text: str, pages: list[int], advanced_labels: list[str]) -> int:
    difficulty = 2
    if len(text) > 260:
        difficulty += 1
    if len(pages) >= 2:
        difficulty += 1
    if advanced_labels:
        difficulty += 1
    if any(token in text for token in ["何通り", "切断", "断面", "展開図", "時計", "時針", "秒針", "証明"]):
        difficulty += 1
    return min(difficulty, 5)


def estimate_confidence(scored_units: list[tuple[UnitProfile, int]]) -> tuple[float, str]:
    top_score = scored_units[0][1]
    second_score = scored_units[1][1] if len(scored_units) > 1 else 0
    margin = top_score - second_score
    confidence = min(0.94, 0.62 + (margin * 0.06))
    uncertainty = ""
    if margin <= 1:
        uncertainty = "主単元と副単元の境界が近く、最終確認では図や公式解答と突き合わせたいです。"
    elif margin == 2:
        uncertainty = "OCR の崩れ方しだいで補助単元の置き方が少し動く余地があります。"
    return round(confidence, 2), uncertainty


def classify_problem(summary: str, pages: list[int]) -> dict[str, object]:
    scored_units = score_units(summary)
    main_profile = scored_units[0][0]
    supporting_units = []

    for unit_name in main_profile.support_units:
        if "（" in unit_name:
            supporting_units.append(unit_name)

    for profile, _ in scored_units[1:3]:
        supporting_units.append(profile.name)

    dedup_supporting: list[str] = []
    for unit_name in supporting_units:
        if unit_name != main_profile.name and unit_name not in dedup_supporting:
            dedup_supporting.append(unit_name)

    advanced_labels = detect_advanced_labels(summary, main_profile)
    cross_skills = detect_cross_skills(summary, main_profile)
    difficulty = estimate_difficulty(summary, pages, advanced_labels)
    confidence, uncertainty = estimate_confidence(scored_units)

    primary_name = normalize_unit_name(main_profile.name)
    secondary_labels = build_secondary_labels(scored_units, main_profile, advanced_labels)

    return {
        "primary_label": {"code": main_profile.code, "name": primary_name},
        "secondary_labels": secondary_labels,
        "difficulty": {"level": difficulty, "scale": "exam_math_bigq_5_v1"},
        "confidence": confidence,
        "rationale": build_rationale(summary, main_profile, dedup_supporting, advanced_labels),
        "uncertainty": uncertainty,
        "learning_map": {
            "main_unit": main_profile.name,
            "supporting_units": dedup_supporting[:3],
            "cross_skills": cross_skills[:4],
            "advanced_labels": advanced_labels[:3],
        },
    }


def build_year_records(year: int) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, str]]]:
    exam_key = f"kaisei-{year}-math-bigq"
    question_pdf = RAW_PDF_ROOT / str(year) / "問題" / f"{year}、算数、開成中学校、問題.pdf"
    answer_pdf = RAW_PDF_ROOT / str(year) / "回答" / f"{year}、算数、開成中学校、解答.pdf"
    question_dir = PAGE_IMAGE_ROOT / str(year) / "問題" / f"{year}、算数、開成中学校、問題"
    answer_dir = PAGE_IMAGE_ROOT / str(year) / "回答" / f"{year}、算数、開成中学校、解答"
    manual_path = MANUAL_ROOT / f"{year}.json"
    manual = read_json(manual_path) if manual_path.exists() else {}
    manual_records = {
        record["display_id"]: record
        for record in manual.get("records", [])
    }

    question_blocks = extract_problem_blocks(question_dir / "ocr/full_text.txt")
    answer_blocks = extract_answer_blocks(answer_dir / "ocr/full_text.txt")
    expected_count = len(answer_blocks)
    manual_expected_count = None
    if manual.get("expected_problem_count"):
        manual_expected_count = int(manual["expected_problem_count"])
        expected_count = manual_expected_count

    roster: list[dict[str, object]] = []
    source_packs: list[dict[str, object]] = []
    review_records: list[dict[str, object]] = []
    issues: list[dict[str, str]] = []

    total_questions = manual_expected_count if manual_expected_count is not None else max(len(question_blocks), expected_count)

    for idx in range(1, total_questions + 1):
        block = question_blocks[idx - 1] if idx - 1 < len(question_blocks) else {"pages": [], "lines": []}
        pages = block["pages"]
        lines = block["lines"]
        official_answer = answer_blocks.get(idx, "")
        summary = summarize_problem(lines) or official_answer
        classification = classify_problem(summary, pages)

        source = {
            "question_pdf": str(question_pdf.relative_to(REPO_ROOT)),
            "answer_pdf": str(answer_pdf.relative_to(REPO_ROOT)),
            "page_images": [
                {
                    "label": f"{page_no}ページ",
                    "path": str((question_dir / f"page-{page_no:04d}.png").relative_to(REPO_ROOT)),
                }
                for page_no in pages
            ],
            "answer_images": [
                {
                    "label": "解答画像確認",
                    "path": str((answer_dir / "page-0001.png").relative_to(REPO_ROOT)),
                }
            ],
            "ocr_text_paths": [
                str((question_dir / f"ocr/page-{page_no:04d}.txt").relative_to(REPO_ROOT))
                for page_no in pages
            ],
            "ocr_json_paths": [
                str((question_dir / f"ocr/page-{page_no:04d}.json").relative_to(REPO_ROOT))
                for page_no in pages
            ],
            "verification": "draft_from_ocr",
        }
        problem_code = f"q{idx}"
        display_id = f"問{idx}"
        problem_core = infer_problem_core(summary)
        manual_record = manual_records.get(display_id)

        if manual_record and manual_record.get("source"):
            source = merge_dict(source, manual_record["source"])

        roster_record = {
            "exam_key": exam_key,
            "subject": "算数",
            "section_id": f"q{idx}",
            "problem_code": problem_code,
            "display_id": display_id,
            "sort_order": idx,
            "source": source,
        }
        source_pack = {
            "display_id": display_id,
            "problem_code": problem_code,
            "sort_order": idx,
            "section_id": f"q{idx}",
            "section_title": display_id,
            "source": source,
            "source_pack": {
                "prompt_summary": summary,
                "official_answer": official_answer,
                "explanation_summary": official_answer,
                "problem_core": problem_core,
                "ocr_notes": [
                    "大問境界は OCR から自動抽出した draft です。",
                    "図形や細かい数値はページ画像で最終確認してください。",
                ],
                "learning_map_hint": classification["learning_map"],
            },
        }
        review_record = {
            "exam_key": exam_key,
            "subject": "算数",
            "problem_code": problem_code,
            "display_id": display_id,
            "sort_order": idx,
            "section_id": f"q{idx}",
            "section_title": display_id,
            "status": "draft",
            "source": source,
            "search_labels": {
                "primary_label": classification["primary_label"],
                "secondary_labels": classification["secondary_labels"],
                "difficulty": classification["difficulty"],
                "confidence": classification["confidence"],
                "rationale": classification["rationale"],
                "uncertainty": classification["uncertainty"],
            },
            "learning_map": classification["learning_map"],
            "evidence": {
                "problem_core": problem_core,
                "official_answer": official_answer,
                "notes": summary,
            },
            "review": {
                "verdict": "needs_human_review",
                "notes": "全年度の年度別 draft 自動分類。必要に応じて画像と公式解答で spot check する。",
                "residual_uncertainty": classification["uncertainty"],
            },
        }

        if manual_record:
            if manual_record.get("source_pack"):
                source_pack["source_pack"] = merge_dict(source_pack["source_pack"], manual_record["source_pack"])
            if manual_record.get("status"):
                review_record["status"] = manual_record["status"]
            if manual_record.get("search_labels"):
                review_record["search_labels"] = manual_record["search_labels"]
            if manual_record.get("learning_map"):
                review_record["learning_map"] = manual_record["learning_map"]
                source_pack["source_pack"]["learning_map_hint"] = manual_record["learning_map"]
            if manual_record.get("evidence"):
                review_record["evidence"] = manual_record["evidence"]
            if manual_record.get("review"):
                review_record["review"] = manual_record["review"]

        roster.append(roster_record)
        source_packs.append(source_pack)
        review_records.append(review_record)

        if review_record["search_labels"]["uncertainty"]:
            issues.append(
                {
                    "display_id": display_id,
                    "kind": "classification_uncertainty",
                    "note": review_record["search_labels"]["uncertainty"],
                }
            )

    if expected_count and len(question_blocks) != expected_count:
        issues.append(
            {
                "display_id": f"{year}",
                "kind": "question_count_mismatch",
                "note": f"問題側の大問数 {len(question_blocks)} 件と、解答側の大問数 {expected_count} 件が一致していません。OCR 境界の再確認が必要です。",
            }
        )

    for issue in manual.get("global_issues", []):
        issues.append(issue)

    return roster, source_packs, review_records, issues


def build_review_md(year: int, status: str, records: list[dict[str, object]], issues: list[dict[str, str]]) -> str:
    lines = [
        f"# 開成中学校 {year} 算数 大問ラベルレビュー",
        "",
        f"- exam_key: `kaisei-{year}-math-bigq`",
        f"- status: `{status}`",
        "- granularity: `big-question`",
        f"- total_problems: `{len(records)}`",
        "",
        "## Review Table",
        "",
        "| display_id | primary | secondary | difficulty | confidence | main_unit | advanced_labels | uncertainty |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for record in records:
        secondary = ", ".join(label["name"] for label in record["search_labels"]["secondary_labels"])
        advanced = ", ".join(record["learning_map"]["advanced_labels"])
        lines.append(
            f"| {record['display_id']} | {record['search_labels']['primary_label']['name']} | {secondary} | "
            f"{record['search_labels']['difficulty']['level']} | {record['search_labels']['confidence']} | "
            f"{record['learning_map']['main_unit']} | {advanced} | {record['search_labels']['uncertainty']} |"
        )

    lines.extend(["", "## Issues", ""])
    if not issues:
        lines.append("- なし")
    else:
        for issue in issues:
            lines.append(f"- {issue['display_id']}: {issue['kind']} - {issue['note']}")

    lines.append("")
    return "\n".join(lines) + "\n"


def build_index(year_rows: list[dict[str, object]]) -> tuple[dict[str, object], str]:
    index_json = {
        "metadata": {
            "school": "開成中学校",
            "subject": "算数",
            "granularity": "big-question",
            "order": "desc",
            "years": [row["year"] for row in year_rows],
            "generated_by": "scripts/build_kaisei_all_years_math_bigq_review.py",
        },
        "years": year_rows,
    }

    lines = [
        "# 開成中学校 全年度 算数 大問分類",
        "",
        "- granularity: `big-question`",
        "- order: `2026 -> 2005`",
        "",
        "| year | exam_key | problems | review |",
        "| --- | --- | --- | --- |",
    ]

    for row in year_rows:
        lines.append(
            f"| {row['year']} | {row['exam_key']} | {row['total_problems']} | `{row['review_path']}` |"
        )

    lines.append("")
    return index_json, "\n".join(lines) + "\n"


def main() -> None:
    year_rows: list[dict[str, object]] = []

    for year in YEARS:
        roster, source_packs, review_records, issues = build_year_records(year)
        year_dir = OUTPUT_ROOT / str(year)
        manual_path = MANUAL_ROOT / f"{year}.json"
        status = read_json(manual_path).get("status") if manual_path.exists() else "draft"
        review_json = {
            "metadata": {
                "exam_key": f"kaisei-{year}-math-bigq",
                "subject": "算数",
                "status": status,
                "granularity": "big-question",
                "generated_from": f"data/derived/page-images/開成中学校/{year}/問題/{year}、算数、開成中学校、問題/ocr/full_text.txt",
                "total_problems": len(review_records),
            },
            "records": review_records,
            "issues": issues,
        }
        write_json(year_dir / "roster.json", roster)
        write_json(year_dir / "source-packs.json", source_packs)
        write_json(year_dir / "review.json", review_json)
        write_text(year_dir / "review.md", build_review_md(year, status, review_records, issues))

        year_rows.append(
            {
                "year": year,
                "exam_key": f"kaisei-{year}-math-bigq",
                "total_problems": len(review_records),
                "review_path": str((year_dir / "review.json").relative_to(REPO_ROOT)),
                "issues": len(issues),
            }
        )

    index_json, index_md = build_index(year_rows)
    write_json(OUTPUT_ROOT / "index.json", index_json)
    write_text(OUTPUT_ROOT / "index.md", index_md)


if __name__ == "__main__":
    main()
