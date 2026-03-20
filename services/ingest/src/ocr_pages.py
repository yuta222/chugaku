#!/usr/bin/env python3
"""
data/derived/page-images/ 配下のページ画像に OCR をかける。

出力:
- 各 PDF 画像フォルダ配下の ocr/ ディレクトリ
- 全ページ横断の data/derived/page-text-index/pages.jsonl
- PDF 単位の data/derived/page-text-index/pdfs.jsonl
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from processing_common import (
    NATIVE_DIR,
    PAGE_IMAGES_ROOT,
    PAGE_TEXT_INDEX_ROOT,
    compile_swift_helper,
    summarize_process_output,
)

DEFAULT_INPUT_ROOT = PAGE_IMAGES_ROOT
DEFAULT_INDEX_ROOT = PAGE_TEXT_INDEX_ROOT
OCR_SWIFT_SOURCE = NATIVE_DIR / "ocr_image.swift"
OCR_SWIFT_BINARY_NAME = "ocr_image_swift"
DEFAULT_JOBS = max(1, min(os.cpu_count() or 4, 4))


@dataclass(frozen=True)
class OcrJob:
    image_dir: Path
    relative_dir: Path
    school: str
    year: str
    kind: str
    pdf_name: str
    manifest_path: Path
    ocr_dir: Path


@dataclass(frozen=True)
class OcrResult:
    job: OcrJob
    status: str
    backend: str
    detail: str
    page_count: int = 0
    char_count: int = 0


class OCRBackend:
    name = "unknown"

    def ocr(self, image_path: Path, output_json: Path) -> int:
        raise NotImplementedError


class VisionSwiftBackend(OCRBackend):
    name = "swift-vision"

    def __init__(self, binary_path: Path):
        self.binary_path = binary_path

    @classmethod
    def build(cls) -> tuple["VisionSwiftBackend | None", str | None]:
        if sys.platform != "darwin":
            return None, "Vision backend は macOS 専用です。"
        if not shutil.which("swiftc"):
            return None, "`swiftc` が見つかりません。"
        if not OCR_SWIFT_SOURCE.exists():
            return None, f"OCR helper がありません: {OCR_SWIFT_SOURCE}"

        try:
            binary_path = compile_swift_helper(OCR_SWIFT_SOURCE, OCR_SWIFT_BINARY_NAME)
        except Exception as exc:  # pragma: no cover - environment dependent
            return None, str(exc)

        return cls(binary_path), None

    def ocr(self, image_path: Path, output_json: Path) -> int:
        result = subprocess.run(
            [str(self.binary_path), str(image_path), str(output_json)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"OCR 失敗: {summarize_process_output(result)}")

        stdout = result.stdout.strip()
        try:
            return int(stdout or "0")
        except ValueError as exc:
            raise RuntimeError(f"OCR helper の出力を解釈できません: {stdout!r}") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ページ画像に OCR をかけて索引を生成します。")
    parser.add_argument(
        "--input-root",
        type=Path,
        default=DEFAULT_INPUT_ROOT,
        help="入力画像ルート。既定: ./data/derived/page-images",
    )
    parser.add_argument(
        "--index-root",
        type=Path,
        default=DEFAULT_INDEX_ROOT,
        help="横断テキスト索引の出力先。既定: ./data/derived/page-text-index",
    )
    parser.add_argument(
        "--pdf-dir",
        nargs="+",
        type=Path,
        help="特定の PDF 画像フォルダだけ処理する。複数指定可。",
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
        help="問題/回答フォルダで絞り込む。既定: all",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=DEFAULT_JOBS,
        help=f"同時実行数。既定: {DEFAULT_JOBS}",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "swift-vision"],
        default="auto",
        help="OCR backend を指定する。既定: auto",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="先頭 N 件だけ処理する。テスト用。",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="既存 OCR 出力を削除して再生成する。",
    )
    parser.add_argument(
        "--skip-global-index",
        action="store_true",
        help="横断 JSONL 索引を更新しない。",
    )
    parser.add_argument(
        "--rebuild-global-index-only",
        action="store_true",
        help="OCR は実行せず、既存 OCR 出力から横断索引だけ再構築する。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="対象件数と出力先だけ確認する。",
    )
    return parser.parse_args()


def select_backend(name: str) -> OCRBackend:
    if name == "swift-vision":
        backend, reason = VisionSwiftBackend.build()
        if backend:
            return backend
        raise RuntimeError(reason or "swift-vision backend を初期化できませんでした。")

    backend, reason = VisionSwiftBackend.build()
    if backend:
        return backend
    raise RuntimeError(
        "利用可能な OCR backend が見つかりませんでした。\n"
        f"- swift-vision: {reason}"
    )


def collect_jobs(args: argparse.Namespace) -> list[OcrJob]:
    input_root = args.input_root.resolve()
    allowed_schools = set(args.school or [])
    allowed_years = set(args.year or [])

    image_dirs: list[Path]
    if args.pdf_dir:
        image_dirs = [path.expanduser().resolve() for path in args.pdf_dir]
    else:
        if not input_root.exists():
            raise FileNotFoundError(f"入力ルートがありません: {input_root}")
        image_dirs = []
        for manifest_path in sorted(input_root.rglob("manifest.json")):
            if manifest_path.parent.name == "ocr":
                continue
            if list(manifest_path.parent.glob("page-*.png")):
                image_dirs.append(manifest_path.parent)

    jobs: list[OcrJob] = []
    for image_dir in image_dirs:
        manifest_path = image_dir / "manifest.json"
        if not manifest_path.exists():
            continue

        try:
            relative_dir = image_dir.relative_to(input_root)
        except ValueError:
            relative_dir = Path(image_dir.name)

        parts = relative_dir.parts
        school = parts[0] if len(parts) >= 4 else ""
        year = parts[1] if len(parts) >= 4 else ""
        kind = parts[2] if len(parts) >= 4 else ""
        pdf_name = image_dir.name

        if allowed_schools and school not in allowed_schools:
            continue
        if allowed_years and year not in allowed_years:
            continue
        if args.kind != "all" and kind != args.kind:
            continue

        jobs.append(
            OcrJob(
                image_dir=image_dir,
                relative_dir=relative_dir,
                school=school,
                year=year,
                kind=kind,
                pdf_name=pdf_name,
                manifest_path=manifest_path,
                ocr_dir=image_dir / "ocr",
            )
        )

    if args.limit is not None:
        jobs = jobs[: args.limit]

    return jobs


def page_images(image_dir: Path) -> list[Path]:
    return sorted(image_dir.glob("page-*.png"))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def existing_ocr_matches(job: OcrJob) -> bool:
    index_path = job.ocr_dir / "index.json"
    if not index_path.exists():
        return False

    try:
        index_data = load_json(index_path)
    except Exception:
        return False

    manifest_stat = job.manifest_path.stat()
    if index_data.get("source_manifest_mtime_ns") != manifest_stat.st_mtime_ns:
        return False
    if index_data.get("source_manifest_size_bytes") != manifest_stat.st_size:
        return False
    if index_data.get("relative_image_dir") != job.relative_dir.as_posix():
        return False

    pages = index_data.get("pages") or []
    images = page_images(job.image_dir)
    if len(pages) != len(images):
        return False

    image_map = {image.name: image for image in images}
    for page in pages:
        image_name = page.get("image_file")
        text_file = page.get("text_file")
        json_file = page.get("json_file")
        if image_name not in image_map:
            return False
        image_path = image_map[image_name]
        image_stat = image_path.stat()
        if page.get("image_mtime_ns") != image_stat.st_mtime_ns:
            return False
        if page.get("image_size_bytes") != image_stat.st_size:
            return False
        if not (job.ocr_dir / text_file).exists():
            return False
        if not (job.ocr_dir / json_file).exists():
            return False

    return True


def write_text_outputs(stage_dir: Path, image_name: str, ocr_json: dict) -> tuple[Path, int, int, float | None]:
    text = ocr_json.get("text") or ""
    lines = ocr_json.get("lines") or []
    txt_path = stage_dir / f"{Path(image_name).stem}.txt"
    txt_path.write_text(text, encoding="utf-8")

    confidences = [float(line.get("confidence", 0.0)) for line in lines]
    avg_confidence = sum(confidences) / len(confidences) if confidences else None
    return txt_path, len(text), len(lines), avg_confidence


def render_ocr_job(job: OcrJob, backend: OCRBackend, overwrite: bool) -> OcrResult:
    if job.ocr_dir.exists():
        if overwrite:
            shutil.rmtree(job.ocr_dir)
        elif existing_ocr_matches(job):
            index_data = load_json(job.ocr_dir / "index.json")
            total_chars = sum(page.get("char_count", 0) for page in index_data.get("pages", []))
            return OcrResult(
                job=job,
                status="skipped",
                backend=backend.name,
                detail="already OCRed",
                page_count=index_data.get("page_count", 0),
                char_count=total_chars,
            )
        else:
            return OcrResult(
                job=job,
                status="skipped",
                backend=backend.name,
                detail="existing OCR output found (use --overwrite to rebuild)",
            )

    images = page_images(job.image_dir)
    if not images:
        return OcrResult(job=job, status="failed", backend=backend.name, detail="page images not found")

    stage_dir = job.image_dir / f".ocr.tmp-{uuid.uuid4().hex}"
    stage_dir.mkdir(parents=False, exist_ok=False)

    try:
        manifest_data = load_json(job.manifest_path)
        page_entries = []
        full_text_sections: list[str] = []
        total_chars = 0

        for page_number, image_path in enumerate(images, start=1):
            json_path = stage_dir / f"{image_path.stem}.json"
            backend.ocr(image_path, json_path)
            ocr_json = load_json(json_path)
            text_path, char_count, line_count, avg_confidence = write_text_outputs(stage_dir, image_path.name, ocr_json)

            image_stat = image_path.stat()
            total_chars += char_count
            text = ocr_json.get("text") or ""
            if text:
                full_text_sections.append(f"## {image_path.stem}\n{text}")
            else:
                full_text_sections.append(f"## {image_path.stem}")

            page_entries.append(
                {
                    "page": page_number,
                    "image_file": image_path.name,
                    "text_file": text_path.name,
                    "json_file": json_path.name,
                    "char_count": char_count,
                    "line_count": line_count,
                    "avg_confidence": avg_confidence,
                    "image_size_bytes": image_stat.st_size,
                    "image_mtime_ns": image_stat.st_mtime_ns,
                }
            )

        (stage_dir / "full_text.txt").write_text(
            "\n\n".join(full_text_sections).strip() + "\n",
            encoding="utf-8",
        )

        manifest_stat = job.manifest_path.stat()
        index_data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "backend": backend.name,
            "relative_image_dir": job.relative_dir.as_posix(),
            "source_image_dir": str(job.image_dir),
            "school": job.school,
            "year": job.year,
            "kind": job.kind,
            "pdf_name": job.pdf_name,
            "page_count": len(page_entries),
            "source_manifest_path": str(job.manifest_path),
            "source_manifest_mtime_ns": manifest_stat.st_mtime_ns,
            "source_manifest_size_bytes": manifest_stat.st_size,
            "source_pdf": manifest_data.get("source_pdf"),
            "relative_source_pdf": manifest_data.get("relative_source_pdf"),
            "pages": page_entries,
        }
        (stage_dir / "index.json").write_text(
            json.dumps(index_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        stage_dir.rename(job.ocr_dir)
        return OcrResult(
            job=job,
            status="rendered",
            backend=backend.name,
            detail=f"{len(page_entries)} pages / {total_chars} chars",
            page_count=len(page_entries),
            char_count=total_chars,
        )
    except Exception as exc:
        shutil.rmtree(stage_dir, ignore_errors=True)
        return OcrResult(job=job, status="failed", backend=backend.name, detail=str(exc))


def rebuild_global_index(input_root: Path, index_root: Path) -> tuple[int, int]:
    ocr_indices = sorted(input_root.rglob("ocr/index.json"))
    if not ocr_indices:
        raise FileNotFoundError("OCR index が見つかりませんでした。先に `ocr_pages.py` を実行してください。")

    staging_root = index_root.parent / f".{index_root.name}.tmp-{uuid.uuid4().hex}"
    staging_root.mkdir(parents=True, exist_ok=False)

    pages_written = 0
    pdfs_written = 0
    try:
        pages_fp = (staging_root / "pages.jsonl").open("w", encoding="utf-8")
        pdfs_fp = (staging_root / "pdfs.jsonl").open("w", encoding="utf-8")
        try:
            for index_path in ocr_indices:
                index_data = load_json(index_path)
                ocr_dir = index_path.parent
                full_text_path = ocr_dir / "full_text.txt"

                pdf_entry = {
                    "relative_image_dir": index_data["relative_image_dir"],
                    "source_pdf": index_data.get("source_pdf"),
                    "relative_source_pdf": index_data.get("relative_source_pdf"),
                    "school": index_data.get("school"),
                    "year": index_data.get("year"),
                    "kind": index_data.get("kind"),
                    "pdf_name": index_data.get("pdf_name"),
                    "page_count": index_data.get("page_count"),
                    "ocr_dir": str(ocr_dir),
                    "full_text_path": str(full_text_path),
                    "backend": index_data.get("backend"),
                }
                pdfs_fp.write(json.dumps(pdf_entry, ensure_ascii=False) + "\n")
                pdfs_written += 1

                relative_dir = Path(index_data["relative_image_dir"])
                for page in index_data.get("pages", []):
                    text_path = ocr_dir / page["text_file"]
                    json_path = ocr_dir / page["json_file"]
                    image_path = input_root / relative_dir / page["image_file"]
                    text = text_path.read_text(encoding="utf-8")

                    page_entry = {
                        "school": index_data.get("school"),
                        "year": index_data.get("year"),
                        "kind": index_data.get("kind"),
                        "pdf_name": index_data.get("pdf_name"),
                        "source_pdf": index_data.get("source_pdf"),
                        "relative_source_pdf": index_data.get("relative_source_pdf"),
                        "relative_image_dir": index_data["relative_image_dir"],
                        "page": page["page"],
                        "image_path": str(image_path),
                        "text_path": str(text_path),
                        "ocr_json_path": str(json_path),
                        "char_count": page.get("char_count", 0),
                        "line_count": page.get("line_count", 0),
                        "avg_confidence": page.get("avg_confidence"),
                        "text": text,
                    }
                    pages_fp.write(json.dumps(page_entry, ensure_ascii=False) + "\n")
                    pages_written += 1
        finally:
            pages_fp.close()
            pdfs_fp.close()

        meta = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pdf_count": pdfs_written,
            "page_count": pages_written,
            "input_root": str(input_root),
        }
        (staging_root / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if index_root.exists():
            shutil.rmtree(index_root)
        staging_root.rename(index_root)
        return pdfs_written, pages_written
    except Exception:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise


def print_dry_run(jobs: Sequence[OcrJob], input_root: Path, index_root: Path) -> None:
    print(f"[DRY RUN] 対象 PDF 画像フォルダ: {len(jobs)} 件")
    print(f"[入力ルート] {input_root}")
    print(f"[索引ルート] {index_root}")
    preview = jobs[:10]
    for job in preview:
        print(f"  - {job.relative_dir.as_posix()} -> {job.ocr_dir}")
    if len(jobs) > len(preview):
        print(f"  ... and {len(jobs) - len(preview)} more")


def main() -> int:
    args = parse_args()

    if args.jobs <= 0:
        print("[エラー] --jobs は 1 以上を指定してください。", file=sys.stderr)
        return 1

    input_root = args.input_root.resolve()
    index_root = args.index_root.resolve()

    if args.rebuild_global_index_only:
        try:
            pdfs_written, pages_written = rebuild_global_index(input_root, index_root)
        except Exception as exc:
            print(f"[エラー] {exc}", file=sys.stderr)
            return 1
        print(f"[index rebuilt] pdfs={pdfs_written} pages={pages_written}")
        return 0

    try:
        jobs = collect_jobs(args)
    except Exception as exc:
        print(f"[エラー] {exc}", file=sys.stderr)
        return 1

    if not jobs:
        print("[エラー] 対象 PDF 画像フォルダが見つかりませんでした。", file=sys.stderr)
        return 1

    if args.dry_run:
        print_dry_run(jobs, input_root, index_root)
        return 0

    try:
        backend = select_backend(args.backend)
    except Exception as exc:
        print(f"[エラー] {exc}", file=sys.stderr)
        return 1

    print(f"[入力ルート] {input_root}")
    print(f"[索引ルート] {index_root}")
    print(f"[対象件数] {len(jobs)}")
    print(f"[backend] {backend.name}")
    print(f"[jobs] {args.jobs}")

    rendered = 0
    skipped = 0
    failed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = {
            executor.submit(render_ocr_job, job, backend, args.overwrite): job
            for job in jobs
        }
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            result = future.result()
            rel_path = result.job.relative_dir.as_posix()
            if result.status == "rendered":
                rendered += 1
                print(
                    f"[{index:>5}/{len(jobs)}] rendered {rel_path} "
                    f"({result.page_count} pages / {result.char_count} chars)"
                )
            elif result.status == "skipped":
                skipped += 1
                print(f"[{index:>5}/{len(jobs)}] skipped  {rel_path} ({result.detail})")
            else:
                failed += 1
                print(f"[{index:>5}/{len(jobs)}] failed   {rel_path} ({result.detail})", file=sys.stderr)

    if failed == 0 and not args.skip_global_index:
        try:
            pdfs_written, pages_written = rebuild_global_index(input_root, index_root)
            print(f"[global index] pdfs={pdfs_written} pages={pages_written}")
        except Exception as exc:
            print(f"[index error] {exc}", file=sys.stderr)
            failed += 1

    print("\n[完了]")
    print(f"rendered: {rendered}")
    print(f"skipped : {skipped}")
    print(f"failed  : {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
