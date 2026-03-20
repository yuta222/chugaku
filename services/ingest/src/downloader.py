#!/usr/bin/env python3
"""
四谷大塚 中学入試過去問データベース PDFダウンローダー

PDFファイルは認証不要で直接URLアクセス可能。
URLパターン: /chugaku_kakomon/pc/uploadPdfs/{school_id}/{year}/{subject}-{type}.pdf

使い方:
    python downloader.py              # 全校ダウンロード
    python downloader.py --school 10  # 指定学校IDのみ
    python downloader.py --dry-run    # URLのみ表示
"""

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from processing_common import PDF_ROOT, PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")

BASE_URL = "https://www.yotsuyaotsuka.com"
SCHOOL_LIST_URL = "https://www.yotsuyaotsuka.com/chugaku_kakomon/system"
PDF_BASE = "https://www.yotsuyaotsuka.com/chugaku_kakomon/pc/uploadPdfs"

download_dir_env = os.getenv("DOWNLOAD_DIR")
if download_dir_env in {None, "", "./pdfs", "pdfs"}:
    DOWNLOAD_DIR = PDF_ROOT
else:
    candidate = Path(download_dir_env).expanduser()
    DOWNLOAD_DIR = candidate if candidate.is_absolute() else (PROJECT_ROOT / candidate).resolve()

MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "20"))

# 対象年度（2013〜2026年）
YEARS = list(range(2013, 2027))

# 科目と種別の全組み合わせ
SUBJECTS = ["kokugo", "sansu", "rika", "shakai", "eigo", "seikatsu", "sogo"]
TYPES = ["mondai", "kaito"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
}


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def get_all_schools(session: requests.Session) -> list[dict]:
    """メインページから全学校のID・名前を取得（認証不要）"""
    print("[スクレイピング] 学校一覧を取得中...")
    resp = session.get(SCHOOL_LIST_URL, headers=HEADERS, timeout=30)
    resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "html.parser")

    schools = []
    seen_ids = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "classes.php?id=" in href:
            match = re.search(r"id=(\d+)", href)
            if match:
                school_id = match.group(1)
                if school_id not in seen_ids:
                    seen_ids.add(school_id)
                    schools.append({
                        "id": school_id,
                        "name": a_tag.get_text(strip=True),
                    })

    print(f"[スクレイピング] {len(schools)} 校を検出しました。")
    return schools


def get_pdf_urls_via_school_page(session: requests.Session, school: dict) -> list[dict]:
    """学校ページにアクセスしてPDF URLを取得（アクセス可能な学校のみ）"""
    url = f"{BASE_URL}/chugaku_kakomon/system/classes.php?id={school['id']}"
    try:
        resp = session.get(url, headers=HEADERS, timeout=30, allow_redirects=False)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        pdfs = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.endswith(".pdf") and "uploadPdfs" in href:
                full_url = urljoin(BASE_URL, href)
                parts = full_url.replace(PDF_BASE + "/", "").split("/")
                year = parts[1] if len(parts) >= 2 else "unknown"
                filename = parts[2] if len(parts) >= 3 else href.split("/")[-1]
                pdfs.append({
                    "url": full_url, "filename": filename, "year": year,
                    "school_id": school["id"], "school_name": school["name"],
                })
        return pdfs
    except Exception:
        return []


def build_candidate_urls(school_id: str, school_name: str) -> list[dict]:
    """URLパターンで候補PDF URLを生成（学校ページ非依存）"""
    candidates = []
    for year in YEARS:
        for subject in SUBJECTS:
            for t in TYPES:
                filename = f"{subject}-{t}.pdf"
                url = f"{PDF_BASE}/{school_id}/{year}/{filename}"
                candidates.append({
                    "url": url, "filename": filename, "year": str(year),
                    "school_id": school_id, "school_name": school_name,
                })
    return candidates


def check_pdf_exists(session: requests.Session, url: str) -> bool:
    """HEADリクエストでPDFの存在確認"""
    try:
        r = session.head(url, headers=HEADERS, timeout=10, allow_redirects=False)
        return r.status_code == 200 and "pdf" in r.headers.get("content-type", "").lower()
    except Exception:
        return False


async def download_pdf_async(
    session: requests.Session,
    pdf_info: dict,
    semaphore: asyncio.Semaphore,
    check_first: bool = False,
) -> bool:
    async with semaphore:
        school_dir = DOWNLOAD_DIR / sanitize_filename(pdf_info["school_name"]) / pdf_info["year"]
        school_dir.mkdir(parents=True, exist_ok=True)
        save_path = school_dir / pdf_info["filename"]

        if save_path.exists():
            return True

        loop = asyncio.get_event_loop()

        def _download():
            if check_first:
                # HEADで存在確認してからGET
                r_head = session.head(pdf_info["url"], headers=HEADERS, timeout=10, allow_redirects=False)
                if r_head.status_code != 200:
                    return None  # 存在しない
                ct = r_head.headers.get("content-type", "")
                if "pdf" not in ct.lower():
                    return None

            resp = session.get(pdf_info["url"], headers=HEADERS, timeout=60, allow_redirects=False)
            if resp.status_code == 200 and "pdf" in resp.headers.get("content-type", "").lower():
                with open(save_path, "wb") as f:
                    f.write(resp.content)
                return True
            return None  # 存在しない

        try:
            result = await loop.run_in_executor(None, _download)
            if result is True:
                print(f"[DL完了] {pdf_info['school_name']} / {pdf_info['year']} / {pdf_info['filename']}")
                return True
            return False  # 存在しないかエラー
        except Exception as e:
            print(f"[エラー] {pdf_info['url']}: {e}")
            return False


async def run_downloads_for_school(
    school: dict,
    session: requests.Session,
    semaphore: asyncio.Semaphore,
) -> int:
    """1校分の候補URLをスキャンしてダウンロード（学校単位で処理）"""
    candidates = build_candidate_urls(school["id"], school["name"])
    tasks = [download_pdf_async(session, pdf, semaphore, check_first=True) for pdf in candidates]
    results = await asyncio.gather(*tasks)
    return sum(1 for r in results if r)


async def run_downloads_scan(schools: list[dict], session: requests.Session):
    """全校を順番に処理（学校単位でasyncio.gather）"""
    print(f"[ダウンロード先] {DOWNLOAD_DIR.resolve()}")
    print(f"[同時実行数] {MAX_CONCURRENT}")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    total_success = 0
    total = len(schools)

    for i, school in enumerate(schools, 1):
        # 既にフォルダがあればスキップ（スキャン不要）
        school_dir = DOWNLOAD_DIR / sanitize_filename(school["name"])
        if school_dir.exists():
            existing = sum(1 for _ in school_dir.rglob("*.pdf"))
            print(f"[{i:3d}/{total}] {school['name'][:25]:<25} スキップ（既存 {existing} 件）")
            continue

        count = await run_downloads_for_school(school, session, semaphore)
        total_success += count
        if count > 0:
            print(f"[{i:3d}/{total}] {school['name'][:25]:<25} {count} 件ダウンロード")
        else:
            print(f"[{i:3d}/{total}] {school['name'][:25]:<25} PDFなし")

    print(f"\n[完了] 新規ダウンロード: {total_success} 件")
    print(f"[保存先] {DOWNLOAD_DIR.resolve()}")


def main():
    parser = argparse.ArgumentParser(
        description="四谷大塚 中学入試過去問データベース PDFダウンローダー"
    )
    parser.add_argument(
        "--school",
        nargs="+",
        type=int,
        metavar="ID",
        help="ダウンロードする学校IDを指定（省略時は全校）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="ダウンロードせずに候補URL数を表示する",
    )
    parser.add_argument(
        "--mode",
        choices=["page", "scan"],
        default="scan",
        help="page=学校ページから取得（一部学校のみ）/ scan=URLパターンスキャン（全校対応）[デフォルト]",
    )
    args = parser.parse_args()

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    all_schools = get_all_schools(session)

    if args.school:
        school_ids = {str(s) for s in args.school}
        schools = [s for s in all_schools if s["id"] in school_ids]
        if not schools:
            print(f"[エラー] 指定された学校ID {list(school_ids)} が見つかりません。")
            sys.exit(1)
    else:
        schools = all_schools

    if args.mode == "page":
        # 学校ページから取得（認証なしでアクセスできる学校のみ）
        print(f"\n[モード] 学校ページスクレイピング（{len(schools)} 校）")
        all_pdfs = []
        for i, school in enumerate(schools, 1):
            print(f"  [{i:4d}/{len(schools)}] {school['name']:<30}", end="\r")
            pdfs = get_pdf_urls_via_school_page(session, school)
            all_pdfs.extend(pdfs)
        print()
        print(f"[収集完了] {len(all_pdfs)} 件のPDF URLを検出しました。")
    else:
        # URLパターンスキャン（全校対応）
        total_candidates = len(schools) * len(YEARS) * len(SUBJECTS) * len(TYPES)
        print(f"\n[モード] URLパターンスキャン（{len(schools)} 校 × {len(YEARS)} 年度 × {len(SUBJECTS)} 科目 × 2 = {total_candidates} 候補）")
        all_pdfs = []
        for school in schools:
            all_pdfs.extend(build_candidate_urls(school["id"], school["name"]))

    if args.dry_run:
        total_candidates = len(all_pdfs) if args.mode == "page" else len(schools) * len(YEARS) * len(SUBJECTS) * len(TYPES)
        print(f"\n[DRY RUN] 対象校数: {len(schools)} 校 / 候補URL: {total_candidates} 件")
        print("（実際に存在するPDFのみダウンロードされます）")
    elif args.mode == "scan":
        asyncio.run(run_downloads_scan(schools, session))
    else:
        # page モード（学校ページから取得した確定URLを一括ダウンロード）
        async def _run_page():
            semaphore = asyncio.Semaphore(MAX_CONCURRENT)
            tasks = [download_pdf_async(session, pdf, semaphore, check_first=False) for pdf in all_pdfs]
            results = await asyncio.gather(*tasks)
            success = sum(1 for r in results if r)
            print(f"\n[完了] ダウンロード: {success} 件")
            print(f"[保存先] {DOWNLOAD_DIR.resolve()}")
        asyncio.run(_run_page())


if __name__ == "__main__":
    main()
