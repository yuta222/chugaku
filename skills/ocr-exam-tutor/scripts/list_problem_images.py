#!/usr/bin/env python3
"""
OCR 問題に対応するページ画像パス、または Markdown 画像タグを出力する。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="問題ページ画像のパスまたは Markdown タグを出力します。")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source-pdf", type=Path, help="元 PDF の絶対パス。")
    source_group.add_argument("--text-path", type=Path, help="page-XXXX.txt の絶対パス。")
    source_group.add_argument("--image-dir", type=Path, help="page_images 側の PDF 画像フォルダ。")
    parser.add_argument(
        "--page",
        type=int,
        nargs="+",
        help="出力したいページ番号。複数可。指定しない場合は自動判定。",
    )
    parser.add_argument(
        "--all-pages",
        action="store_true",
        help="フォルダ内の全ページを出力する。",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Markdown 画像タグで出力する。",
    )
    return parser.parse_args()


def image_dir_from_source_pdf(source_pdf: Path) -> Path:
    resolved = source_pdf.expanduser().resolve()
    parts = list(resolved.parts)
    if "pdfs" not in parts:
        raise ValueError("source_pdf のパスに 'pdfs' が含まれていません。")
    parts[parts.index("pdfs")] = "page_images"
    return Path(*parts).with_suffix("")


def image_dir_and_default_pages_from_text_path(text_path: Path) -> tuple[Path, list[int]]:
    resolved = text_path.expanduser().resolve()
    match = re.fullmatch(r"page-(\d{4})\.txt", resolved.name)
    if not match:
        raise ValueError("text_path は page-XXXX.txt 形式である必要があります。")
    image_dir = resolved.parent.parent
    return image_dir, [int(match.group(1))]


def collect_images(image_dir: Path, page_numbers: list[int] | None, all_pages: bool) -> list[Path]:
    if not image_dir.exists():
        raise FileNotFoundError(f"画像ディレクトリが見つかりません: {image_dir}")

    images = sorted(image_dir.glob("page-*.png"))
    if not images:
        raise FileNotFoundError(f"ページ画像が見つかりません: {image_dir}")

    if all_pages or page_numbers is None:
        return images

    allowed = {f"page-{page:04d}.png" for page in page_numbers}
    selected = [image for image in images if image.name in allowed]
    if not selected:
        raise FileNotFoundError("指定されたページ番号に対応する画像が見つかりません。")
    return selected


def main() -> int:
    args = parse_args()

    if args.text_path:
        image_dir, default_pages = image_dir_and_default_pages_from_text_path(args.text_path)
    elif args.source_pdf:
        image_dir = image_dir_from_source_pdf(args.source_pdf)
        default_pages = None
    else:
        image_dir = args.image_dir.expanduser().resolve()
        default_pages = None

    page_numbers = args.page if args.page else default_pages
    images = collect_images(image_dir, page_numbers=page_numbers, all_pages=args.all_pages)

    for image in images:
        resolved = image.resolve()
        if args.markdown:
            page_match = re.fullmatch(r"page-(\d{4})\.png", image.name)
            page_label = int(page_match.group(1)) if page_match else image.stem
            print(f"![問題ページ {page_label}]({resolved})")
        else:
            print(str(resolved))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
