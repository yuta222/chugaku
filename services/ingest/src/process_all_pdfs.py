#!/usr/bin/env python3
"""
全 PDF に対して画像化と OCR を順に実行する。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from processing_common import SRC_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="全 PDF を画像化し、その後 OCR 索引を生成します。")
    parser.add_argument("--school", nargs="+", help="学校名で絞り込む。")
    parser.add_argument("--year", nargs="+", help="年度で絞り込む。")
    parser.add_argument(
        "--kind",
        choices=["all", "問題", "回答"],
        default="all",
        help="問題/回答フォルダで絞り込む。既定: all",
    )
    parser.add_argument("--limit", type=int, help="先頭 N 件だけ処理する。")
    parser.add_argument("--dpi", type=int, default=220, help="画像化 DPI。既定: 220")
    parser.add_argument("--render-jobs", type=int, default=4, help="画像化の並列数。既定: 4")
    parser.add_argument("--ocr-jobs", type=int, default=4, help="OCR の並列数。既定: 4")
    parser.add_argument(
        "--render-backend",
        choices=["auto", "pdftoppm", "swift", "pymupdf"],
        default="auto",
        help="画像化 backend。既定: auto",
    )
    parser.add_argument(
        "--ocr-backend",
        choices=["auto", "swift-vision"],
        default="auto",
        help="OCR backend。既定: auto",
    )
    parser.add_argument("--overwrite-render", action="store_true", help="既存画像を再生成する。")
    parser.add_argument("--overwrite-ocr", action="store_true", help="既存 OCR を再生成する。")
    parser.add_argument("--skip-render", action="store_true", help="画像化を飛ばす。")
    parser.add_argument("--skip-ocr", action="store_true", help="OCR を飛ばす。")
    parser.add_argument("--dry-run", action="store_true", help="実行コマンドだけ表示する。")
    return parser.parse_args()


def extend_common_filters(command: list[str], args: argparse.Namespace) -> None:
    if args.school:
        command.extend(["--school", *args.school])
    if args.year:
        command.extend(["--year", *args.year])
    if args.kind != "all":
        command.extend(["--kind", args.kind])
    if args.limit is not None:
        command.extend(["--limit", str(args.limit)])


def run_command(command: list[str]) -> None:
    print("[run]", " ".join(command))
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    args = parse_args()

    render_command = [
        sys.executable,
        str(SRC_DIR / "render_pages.py"),
        "--dpi",
        str(args.dpi),
        "--jobs",
        str(args.render_jobs),
        "--backend",
        args.render_backend,
    ]
    extend_common_filters(render_command, args)
    if args.overwrite_render:
        render_command.append("--overwrite")

    ocr_command = [
        sys.executable,
        str(SRC_DIR / "ocr_pages.py"),
        "--jobs",
        str(args.ocr_jobs),
        "--backend",
        args.ocr_backend,
    ]
    extend_common_filters(ocr_command, args)
    if args.overwrite_ocr:
        ocr_command.append("--overwrite")

    if args.dry_run:
        if not args.skip_render:
            print("[render]", " ".join(render_command))
        if not args.skip_ocr:
            print("[ocr]", " ".join(ocr_command))
        return 0

    if not args.skip_render:
        run_command(render_command)
    if not args.skip_ocr:
        run_command(ocr_command)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
