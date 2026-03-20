#!/usr/bin/env python3
"""
PDF を 1 ページ 1 PNG に分解するユーティリティ。

既定では `data/raw/pdfs/` 配下を走査し、`data/derived/page-images/` に同じ階層で出力する。
"""

from __future__ import annotations

import argparse
import concurrent.futures
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from processing_common import (
    NATIVE_DIR,
    PAGE_IMAGES_ROOT,
    PDF_ROOT,
    compile_swift_helper,
    summarize_process_output,
)

DEFAULT_INPUT_ROOT = PDF_ROOT
DEFAULT_OUTPUT_ROOT = PAGE_IMAGES_ROOT
SWIFT_SOURCE = NATIVE_DIR / "render_pdf.swift"
SWIFT_BINARY_NAME = "render_pdf_swift"
DEFAULT_JOBS = max(1, min(os.cpu_count() or 4, 4))


@dataclass(frozen=True)
class PdfJob:
    pdf_path: Path
    relative_pdf: Path
    school: str
    year: str
    kind: str
    output_dir: Path


@dataclass(frozen=True)
class JobResult:
    job: PdfJob
    status: str
    backend: str
    detail: str
    page_count: int = 0


class Renderer:
    name = "unknown"

    def render(self, pdf_path: Path, output_dir: Path, dpi: int) -> int:
        raise NotImplementedError


class PdftoppmRenderer(Renderer):
    name = "pdftoppm"

    def __init__(self, binary: str):
        self.binary = binary

    @classmethod
    def build(cls) -> tuple["PdftoppmRenderer | None", str | None]:
        binary = shutil.which("pdftoppm")
        if not binary:
            return None, "`pdftoppm` が見つかりません。"

        try:
            result = subprocess.run(
                [binary, "-v"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except OSError as exc:
            return None, f"`pdftoppm` の起動に失敗しました: {exc}"

        output = summarize_process_output(result)
        if result.returncode != 0:
            return None, f"`pdftoppm` が壊れているか実行できません: {output}"

        return cls(binary), None

    def render(self, pdf_path: Path, output_dir: Path, dpi: int) -> int:
        prefix = output_dir / "page-tmp"
        command = [
            self.binary,
            "-r",
            str(dpi),
            "-png",
            str(pdf_path),
            str(prefix),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"`pdftoppm` 変換失敗: {summarize_process_output(result)}")

        generated = sorted(
            output_dir.glob("page-tmp-*.png"),
            key=lambda path: int(path.stem.rsplit("-", 1)[-1]),
        )
        if not generated:
            raise RuntimeError("`pdftoppm` が PNG を生成しませんでした。")

        for index, image_path in enumerate(generated, start=1):
            image_path.rename(output_dir / f"page-{index:04d}.png")

        return len(generated)


class SwiftRenderer(Renderer):
    name = "swift"

    def __init__(self, binary_path: Path):
        self.binary_path = binary_path

    @classmethod
    def build(cls) -> tuple["SwiftRenderer | None", str | None]:
        if sys.platform != "darwin":
            return None, "Swift backend は macOS 専用です。"
        if not shutil.which("swiftc"):
            return None, "`swiftc` が見つかりません。"
        if not SWIFT_SOURCE.exists():
            return None, f"Swift helper がありません: {SWIFT_SOURCE}"

        try:
            binary_path = compile_swift_helper(SWIFT_SOURCE, SWIFT_BINARY_NAME)
        except Exception as exc:  # pragma: no cover - environment dependent
            return None, str(exc)

        return cls(binary_path), None

    def render(self, pdf_path: Path, output_dir: Path, dpi: int) -> int:
        result = subprocess.run(
            [str(self.binary_path), str(pdf_path), str(output_dir), str(dpi)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Swift backend 変換失敗: {summarize_process_output(result)}")

        stdout = result.stdout.strip()
        try:
            page_count = int(stdout)
        except ValueError as exc:
            raise RuntimeError(f"Swift backend の出力を解釈できません: {stdout!r}") from exc

        return page_count


class PyMuPDFRenderer(Renderer):
    name = "pymupdf"

    def __init__(self, fitz_module):
        self.fitz = fitz_module

    @classmethod
    def build(cls) -> tuple["PyMuPDFRenderer | None", str | None]:
        try:
            fitz_module = importlib.import_module("fitz")
        except ModuleNotFoundError:
            return None, "`PyMuPDF` が未インストールです。`uv pip install pymupdf` を実行してください。"
        except Exception as exc:
            return None, f"`PyMuPDF` の読み込みに失敗しました: {exc}"

        return cls(fitz_module), None

    def render(self, pdf_path: Path, output_dir: Path, dpi: int) -> int:
        document = self.fitz.open(pdf_path)
        page_count = document.page_count
        if page_count == 0:
            raise RuntimeError("ページ数 0 の PDF です。")

        scale = dpi / 72.0
        matrix = self.fitz.Matrix(scale, scale)

        for page_index in range(page_count):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            pixmap.save(output_dir / f"page-{page_index + 1:04d}.png")

        document.close()
        return page_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PDF をページごとの PNG に変換します。")
    parser.add_argument(
        "--input-root",
        type=Path,
        default=DEFAULT_INPUT_ROOT,
        help="入力 PDF ルート。既定: ./data/raw/pdfs",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="画像出力ルート。既定: ./data/derived/page-images",
    )
    parser.add_argument(
        "--pdf",
        nargs="+",
        type=Path,
        help="特定の PDF のみ変換する。複数指定可。",
    )
    parser.add_argument(
        "--school",
        nargs="+",
        help="学校名で絞り込む。例: --school 開成中学校 桜蔭中学校",
    )
    parser.add_argument(
        "--year",
        nargs="+",
        help="年度で絞り込む。例: --year 2025 2026",
    )
    parser.add_argument(
        "--kind",
        choices=["all", "問題", "回答"],
        default="all",
        help="問題/回答フォルダで絞り込む。既定: all",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=220,
        help="出力 DPI。既定: 220",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=DEFAULT_JOBS,
        help=f"同時実行数。既定: {DEFAULT_JOBS}",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="先頭 N 件だけ処理する。テスト用。",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "pdftoppm", "swift", "pymupdf"],
        default="auto",
        help="レンダラを指定する。既定: auto",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="既存画像を削除して再生成する。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="対象件数と出力先だけ確認する。",
    )
    return parser.parse_args()

def select_renderer(name: str) -> Renderer:
    builders = {
        "pdftoppm": PdftoppmRenderer.build,
        "swift": SwiftRenderer.build,
        "pymupdf": PyMuPDFRenderer.build,
    }

    if name != "auto":
        renderer, reason = builders[name]()
        if renderer:
            return renderer
        raise RuntimeError(reason or f"{name} backend を初期化できませんでした。")

    errors: list[str] = []
    for candidate in ("pdftoppm", "swift", "pymupdf"):
        renderer, reason = builders[candidate]()
        if renderer:
            return renderer
        errors.append(f"- {candidate}: {reason}")

    raise RuntimeError(
        "利用可能なレンダラが見つかりませんでした。\n"
        + "\n".join(errors)
    )


def make_job(pdf_path: Path, input_root: Path, output_root: Path) -> PdfJob:
    resolved_pdf = pdf_path.resolve()
    resolved_input_root = input_root.resolve()

    try:
        relative_pdf = resolved_pdf.relative_to(resolved_input_root)
        output_dir = output_root / relative_pdf.with_suffix("")
    except ValueError:
        relative_pdf = Path(resolved_pdf.name)
        output_dir = output_root / resolved_pdf.stem

    parts = relative_pdf.parts
    school = parts[0] if len(parts) >= 4 else ""
    year = parts[1] if len(parts) >= 4 else ""
    kind = parts[2] if len(parts) >= 4 else ""

    return PdfJob(
        pdf_path=resolved_pdf,
        relative_pdf=relative_pdf,
        school=school,
        year=year,
        kind=kind,
        output_dir=output_dir,
    )


def collect_jobs(args: argparse.Namespace) -> list[PdfJob]:
    input_root = args.input_root.resolve()
    output_root = args.output_root.resolve()

    pdf_paths: list[Path]
    if args.pdf:
        pdf_paths = [path.expanduser().resolve() for path in args.pdf]
    else:
        if not input_root.exists():
            raise FileNotFoundError(f"入力ルートがありません: {input_root}")
        pdf_paths = sorted(input_root.rglob("*.pdf"))

    jobs: list[PdfJob] = []
    allowed_schools = set(args.school or [])
    allowed_years = set(args.year or [])

    for pdf_path in pdf_paths:
        if pdf_path.name.startswith("._"):
            continue

        job = make_job(pdf_path, input_root, output_root)
        if allowed_schools and job.school not in allowed_schools:
            continue
        if allowed_years and job.year not in allowed_years:
            continue
        if args.kind != "all" and job.kind != args.kind:
            continue
        jobs.append(job)

    if args.limit is not None:
        jobs = jobs[: args.limit]

    return jobs


def existing_render_matches(job: PdfJob, dpi: int) -> bool:
    manifest_path = job.output_dir / "manifest.json"
    if not manifest_path.exists():
        return False

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return False

    images = manifest.get("images") or []
    if not images:
        return False

    source_stat = job.pdf_path.stat()
    if manifest.get("dpi") != dpi:
        return False
    if manifest.get("source_size_bytes") != source_stat.st_size:
        return False
    if manifest.get("source_mtime_ns") != source_stat.st_mtime_ns:
        return False
    if manifest.get("relative_source_pdf") != job.relative_pdf.as_posix():
        return False
    if manifest.get("page_count") != len(images):
        return False

    return all((job.output_dir / image_name).exists() for image_name in images)


def write_manifest(job: PdfJob, output_dir: Path, backend: str, dpi: int, page_files: Sequence[Path]) -> None:
    source_stat = job.pdf_path.stat()
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backend": backend,
        "dpi": dpi,
        "page_count": len(page_files),
        "source_pdf": str(job.pdf_path),
        "relative_source_pdf": job.relative_pdf.as_posix(),
        "school": job.school,
        "year": job.year,
        "kind": job.kind,
        "source_size_bytes": source_stat.st_size,
        "source_mtime_ns": source_stat.st_mtime_ns,
        "images": [path.name for path in page_files],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def render_job(job: PdfJob, renderer: Renderer, dpi: int, overwrite: bool) -> JobResult:
    if job.output_dir.exists():
        if overwrite:
            shutil.rmtree(job.output_dir)
        elif existing_render_matches(job, dpi):
            return JobResult(job=job, status="skipped", backend=renderer.name, detail="already rendered")
        else:
            return JobResult(
                job=job,
                status="skipped",
                backend=renderer.name,
                detail="existing output found (use --overwrite to rebuild)",
            )

    job.output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = job.output_dir.parent / f".{job.output_dir.name}.tmp-{uuid.uuid4().hex}"
    staging_dir.mkdir(parents=False, exist_ok=False)

    try:
        page_count = renderer.render(job.pdf_path, staging_dir, dpi)
        page_files = sorted(staging_dir.glob("page-*.png"))
        if page_count != len(page_files):
            raise RuntimeError(f"ページ数不一致: expected={page_count}, actual={len(page_files)}")
        if not page_files:
            raise RuntimeError("PNG が 1 枚も生成されませんでした。")

        write_manifest(job, staging_dir, renderer.name, dpi, page_files)
        staging_dir.rename(job.output_dir)
        return JobResult(
            job=job,
            status="rendered",
            backend=renderer.name,
            detail=f"{len(page_files)} pages",
            page_count=len(page_files),
        )
    except Exception as exc:
        shutil.rmtree(staging_dir, ignore_errors=True)
        return JobResult(job=job, status="failed", backend=renderer.name, detail=str(exc))


def print_dry_run(jobs: Sequence[PdfJob], output_root: Path) -> None:
    print(f"[DRY RUN] 対象 PDF: {len(jobs)} 件")
    print(f"[出力先] {output_root}")
    preview = jobs[:10]
    for job in preview:
        print(f"  - {job.relative_pdf.as_posix()} -> {job.output_dir}")
    if len(jobs) > len(preview):
        print(f"  ... and {len(jobs) - len(preview)} more")


def main() -> int:
    args = parse_args()

    if args.dpi <= 0:
        print("[エラー] --dpi は 1 以上を指定してください。", file=sys.stderr)
        return 1
    if args.jobs <= 0:
        print("[エラー] --jobs は 1 以上を指定してください。", file=sys.stderr)
        return 1

    try:
        jobs = collect_jobs(args)
    except Exception as exc:
        print(f"[エラー] {exc}", file=sys.stderr)
        return 1

    if not jobs:
        print("[エラー] 対象 PDF が見つかりませんでした。", file=sys.stderr)
        return 1

    if args.dry_run:
        print_dry_run(jobs, args.output_root.resolve())
        return 0

    try:
        renderer = select_renderer(args.backend)
    except Exception as exc:
        print(f"[エラー] {exc}", file=sys.stderr)
        return 1

    print(f"[入力ルート] {args.input_root.resolve()}")
    print(f"[出力ルート] {args.output_root.resolve()}")
    print(f"[対象件数] {len(jobs)}")
    print(f"[backend] {renderer.name}")
    print(f"[dpi] {args.dpi}")
    print(f"[jobs] {args.jobs}")

    rendered = 0
    skipped = 0
    failed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = {
            executor.submit(render_job, job, renderer, args.dpi, args.overwrite): job
            for job in jobs
        }
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            result = future.result()
            rel_path = result.job.relative_pdf.as_posix()
            if result.status == "rendered":
                rendered += 1
                print(f"[{index:>5}/{len(jobs)}] rendered {rel_path} ({result.page_count} pages)")
            elif result.status == "skipped":
                skipped += 1
                print(f"[{index:>5}/{len(jobs)}] skipped  {rel_path} ({result.detail})")
            else:
                failed += 1
                print(f"[{index:>5}/{len(jobs)}] failed   {rel_path} ({result.detail})", file=sys.stderr)

    print("\n[完了]")
    print(f"rendered: {rendered}")
    print(f"skipped : {skipped}")
    print(f"failed  : {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
