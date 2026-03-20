#!/usr/bin/env python3
"""
OCR 済みの横断索引を検索する CLI。

既定では data/derived/page-text-index/pages.jsonl を対象に全文検索し、
学校名・年度・問題/回答・教科で絞り込める。
"""

from __future__ import annotations

import argparse
import json
import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from processing_common import PAGE_TEXT_INDEX_ROOT

DEFAULT_INDEX_ROOT = PAGE_TEXT_INDEX_ROOT


@dataclass(frozen=True)
class PageMatch:
    school: str
    year: str
    kind: str
    subject: str
    pdf_name: str
    page: int
    source_pdf: str
    text_path: str
    snippet: str
    relative_image_dir: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OCR 済みページ索引を検索します。")
    parser.add_argument("query", help="検索語。既定では部分一致。")
    parser.add_argument(
        "--index-root",
        type=Path,
        default=DEFAULT_INDEX_ROOT,
        help="横断索引のルート。既定: ./data/derived/page-text-index",
    )
    parser.add_argument(
        "--scope",
        choices=["page", "pdf"],
        default="page",
        help="ページ単位か PDF 単位で結果を返す。既定: page",
    )
    parser.add_argument(
        "--school",
        nargs="+",
        help="学校名で絞り込む。",
    )
    parser.add_argument(
        "--year",
        nargs="+",
        help="年度で絞り込む。",
    )
    parser.add_argument(
        "--kind",
        choices=["all", "問題", "回答"],
        default="all",
        help="問題/回答で絞り込む。既定: all",
    )
    parser.add_argument(
        "--subject",
        nargs="+",
        help="教科で絞り込む。例: 算数 国語",
    )
    parser.add_argument(
        "--regex",
        action="store_true",
        help="検索語を正規表現として扱う。",
    )
    parser.add_argument(
        "--ignore-case",
        action="store_true",
        help="大文字小文字を区別しない。",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="返す件数。page ならページ数、pdf なら PDF 数。既定: 20",
    )
    parser.add_argument(
        "--jsonl",
        action="store_true",
        help="整形表示ではなく JSON Lines で出力する。",
    )
    return parser.parse_args()


def infer_subject(pdf_name: str) -> str:
    parts = pdf_name.split("、")
    if len(parts) >= 4:
        return parts[1]
    return ""


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def compile_matcher(query: str, regex: bool, ignore_case: bool):
    if regex:
        flags = re.IGNORECASE if ignore_case else 0
        pattern = re.compile(query, flags)

        def find_span(text: str) -> tuple[int, int] | None:
            match = pattern.search(text)
            if not match:
                return None
            return match.start(), match.end()

        return find_span

    if ignore_case:
        needle = query.casefold()

        def find_span(text: str) -> tuple[int, int] | None:
            haystack = text.casefold()
            start = haystack.find(needle)
            if start < 0:
                return None
            return start, start + len(needle)

        return find_span

    def find_span(text: str) -> tuple[int, int] | None:
        start = text.find(query)
        if start < 0:
            return None
        return start, start + len(query)

    return find_span


def make_snippet(text: str, span: tuple[int, int], radius: int = 50) -> str:
    start, end = span
    snippet_start = max(0, start - radius)
    snippet_end = min(len(text), end + radius)
    snippet = text[snippet_start:snippet_end]
    snippet = normalize_text(snippet)
    if snippet_start > 0:
        snippet = "..." + snippet
    if snippet_end < len(text):
        snippet = snippet + "..."
    return snippet


def entry_matches(entry: dict, args: argparse.Namespace) -> bool:
    if args.school and entry.get("school") not in set(args.school):
        return False
    if args.year and entry.get("year") not in set(args.year):
        return False
    if args.kind != "all" and entry.get("kind") != args.kind:
        return False
    if args.subject:
        subject = infer_subject(entry.get("pdf_name") or "")
        if subject not in set(args.subject):
            return False
    return True


def iter_page_matches(args: argparse.Namespace) -> list[PageMatch]:
    pages_path = args.index_root / "pages.jsonl"
    if not pages_path.exists():
        raise FileNotFoundError(f"索引が見つかりません: {pages_path}")

    find_span = compile_matcher(args.query, regex=args.regex, ignore_case=args.ignore_case)
    matches: list[PageMatch] = []

    with pages_path.open("r", encoding="utf-8") as fp:
        for line in fp:
            entry = json.loads(line)
            if not entry_matches(entry, args):
                continue

            text = entry.get("text") or ""
            span = find_span(text)
            if span is None:
                continue

            matches.append(
                PageMatch(
                    school=entry.get("school") or "",
                    year=entry.get("year") or "",
                    kind=entry.get("kind") or "",
                    subject=infer_subject(entry.get("pdf_name") or ""),
                    pdf_name=entry.get("pdf_name") or "",
                    page=int(entry.get("page") or 0),
                    source_pdf=entry.get("source_pdf") or "",
                    text_path=entry.get("text_path") or "",
                    snippet=make_snippet(text, span),
                    relative_image_dir=entry.get("relative_image_dir") or "",
                )
            )
            if args.scope == "page" and len(matches) >= args.limit:
                break

    return matches


def print_page_matches(matches: list[PageMatch], as_jsonl: bool) -> None:
    if as_jsonl:
        for match in matches:
            print(json.dumps(match.__dict__, ensure_ascii=False))
        return

    if not matches:
        print("一致はありませんでした。")
        return

    for index, match in enumerate(matches, start=1):
        print(
            f"[{index}] {match.school} / {match.year} / {match.kind} / "
            f"{match.subject or '教科不明'} / p.{match.page}"
        )
        print(f"pdf: {match.source_pdf}")
        print(f"txt: {match.text_path}")
        print(f"hit: {match.snippet}")
        print()


def print_pdf_matches(matches: list[PageMatch], limit: int, as_jsonl: bool) -> None:
    grouped: OrderedDict[str, dict] = OrderedDict()
    for match in matches:
        group = grouped.setdefault(
            match.relative_image_dir,
            {
                "school": match.school,
                "year": match.year,
                "kind": match.kind,
                "subject": match.subject,
                "pdf_name": match.pdf_name,
                "source_pdf": match.source_pdf,
                "pages": [],
                "snippets": [],
            },
        )
        group["pages"].append(match.page)
        if len(group["snippets"]) < 3:
            group["snippets"].append(match.snippet)

    items = list(grouped.values())[:limit]

    if as_jsonl:
        for item in items:
            item["pages"] = sorted(set(item["pages"]))
            print(json.dumps(item, ensure_ascii=False))
        return

    if not items:
        print("一致はありませんでした。")
        return

    for index, item in enumerate(items, start=1):
        pages = ", ".join(str(page) for page in sorted(set(item["pages"])))
        print(
            f"[{index}] {item['school']} / {item['year']} / {item['kind']} / "
            f"{item['subject'] or '教科不明'}"
        )
        print(f"pdf: {item['source_pdf']}")
        print(f"pages: {pages}")
        for snippet in item["snippets"]:
            print(f"hit: {snippet}")
        print()


def main() -> int:
    args = parse_args()
    matches = iter_page_matches(args)
    if args.scope == "page":
        print_page_matches(matches[: args.limit], as_jsonl=args.jsonl)
    else:
        print_pdf_matches(matches, limit=args.limit, as_jsonl=args.jsonl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
