from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
INGEST_ROOT = SRC_DIR.parent
PROJECT_ROOT = INGEST_ROOT.parent.parent
BASE_DIR = PROJECT_ROOT
DATA_ROOT = Path(os.getenv("YOTSUYA_DATA_ROOT", str(PROJECT_ROOT / "data"))).expanduser().resolve()
RAW_DATA_ROOT = DATA_ROOT / "raw"
DERIVED_DATA_ROOT = DATA_ROOT / "derived"
PUBLISHED_DATA_ROOT = DATA_ROOT / "published"
PDF_ROOT = RAW_DATA_ROOT / "pdfs"
PAGE_IMAGES_ROOT = DERIVED_DATA_ROOT / "page-images"
PAGE_TEXT_INDEX_ROOT = DERIVED_DATA_ROOT / "page-text-index"
SITE_ROOT = PUBLISHED_DATA_ROOT / "sites"
NATIVE_DIR = INGEST_ROOT / "native"
TMP_ROOT = Path(tempfile.gettempdir()) / "yotsuyaotsuka-pdf"
CLANG_CACHE = TMP_ROOT / "clang-module-cache"
SWIFT_CACHE = TMP_ROOT / "swift-module-cache"


def summarize_process_output(result: subprocess.CompletedProcess[str]) -> str:
    output = (result.stderr or "").strip() or (result.stdout or "").strip()
    output = output.replace("\n", " ").strip()
    return output[:300] if output else f"exit={result.returncode}"


def swift_env() -> dict[str, str]:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    CLANG_CACHE.mkdir(parents=True, exist_ok=True)
    SWIFT_CACHE.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["CLANG_MODULE_CACHE_PATH"] = str(CLANG_CACHE)
    env["SWIFT_MODULECACHE_PATH"] = str(SWIFT_CACHE)
    return env


def compile_swift_helper(source: Path, binary_name: str) -> Path:
    if not source.exists():
        raise RuntimeError(f"Swift helper がありません: {source}")

    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    binary_path = TMP_ROOT / binary_name
    if binary_path.exists() and binary_path.stat().st_mtime >= source.stat().st_mtime:
        return binary_path

    result = subprocess.run(
        ["swiftc", str(source), "-o", str(binary_path)],
        capture_output=True,
        text=True,
        env=swift_env(),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Swift helper のコンパイルに失敗しました: {summarize_process_output(result)}"
        )

    return binary_path
