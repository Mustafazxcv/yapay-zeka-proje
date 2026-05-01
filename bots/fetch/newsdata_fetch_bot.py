import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests


API_URL = "https://newsdata.io/api/1/news"


def env_str(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "evet", "yes", "on"}


def load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def fetch_news(
    api_key: str,
    query: str,
    language: str,
    country: str,
    category: str,
    max_pages: int,
):
    headlines = []
    next_page = None
    request_count = 0
    limit_info = {"limit": None, "remaining": None, "retry_after": None}

    for _ in range(max_pages):
        params = {
            "apikey": api_key,
            "q": query,
            "language": language,
        }
        if country:
            params["country"] = country
        if category:
            params["category"] = category
        if next_page:
            params["page"] = next_page

        response = requests.get(API_URL, params=params, timeout=30)
        request_count += 1

        limit_info["limit"] = response.headers.get("X-RateLimit-Limit")
        limit_info["remaining"] = response.headers.get("X-RateLimit-Remaining")
        limit_info["retry_after"] = response.headers.get("Retry-After")

        if response.status_code == 429:
            print(
                "Uyari: API limiti asildi (429). Daha fazla veri cekilemedi, mevcut veriler kaydedilecek.",
                file=sys.stderr,
            )
            break

        response.raise_for_status()
        payload = response.json()

        for item in payload.get("results", []):
            title = item.get("title")
            if not title:
                continue
            headlines.append(
                {
                    "title": title.strip(),
                    "source": item.get("source_id"),
                    "link": item.get("link"),
                    "pubDate": item.get("pubDate"),
                    "fetchedAt": datetime.now(timezone.utc).isoformat(),
                }
            )

        next_page = payload.get("nextPage")
        if not next_page:
            break

    return headlines, request_count, limit_info


def count_existing_records(path: str) -> int:
    file_path = Path(path)
    if not file_path.exists():
        return 0
    try:
        with file_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, list):
            return len(data)
    except (json.JSONDecodeError, OSError):
        return 0
    return 0


def load_existing_records(path: str):
    file_path = Path(path)
    if not file_path.exists():
        return []
    try:
        with file_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        return []
    return []


def deduplicate_records(records):
    unique = []
    seen = set()
    for item in records:
        key = (
            (item.get("title") or "").strip().lower(),
            (item.get("source") or "").strip().lower(),
            (item.get("link") or "").strip().lower(),
            (item.get("pubDate") or "").strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def write_csv(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["title", "source", "link", "pubDate", "fetchedAt"],
        )
        writer.writeheader()
        writer.writerows(data)


def main():
    load_env_file(".env")

    parser = argparse.ArgumentParser(
        description="NewsData.io'dan basliklari cekip data klasorune kaydeder."
    )
    parser.add_argument("--api-key", default=os.getenv("NEWSDATA_API_KEY"))
    parser.add_argument("--query", default=env_str("NEWS_QUERY", "technology"))
    parser.add_argument("--language", default=env_str("NEWS_LANGUAGE", "en"))
    parser.add_argument("--country", default=env_str("NEWS_COUNTRY", "us"))
    parser.add_argument("--category", default=env_str("NEWS_CATEGORY", ""))
    parser.add_argument("--max-pages", type=int, default=env_int("NEWS_MAX_PAGES", 3))
    parser.add_argument(
        "--out-json", default=env_str("NEWS_OUT_JSON", "data/all/headlines_all.json")
    )
    parser.add_argument(
        "--out-csv", default=env_str("NEWS_OUT_CSV", "data/all/headlines_all.csv")
    )
    parser.add_argument(
        "--append-mode",
        default=env_bool("NEWS_APPEND_MODE", True),
        action=argparse.BooleanOptionalAction,
        help="Aciksa mevcut dosyadaki veriler korunur, yeni veriler eklenir ve tekrarlar temizlenir.",
    )

    args = parser.parse_args()
    args.language = "en"
    args.country = "us"

    if not args.api_key:
        print(
            "Hata: API anahtari eksik.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        headlines, request_count, limit_info = fetch_news(
            api_key=args.api_key,
            query=args.query,
            language=args.language,
            country=args.country,
            category=args.category,
            max_pages=args.max_pages,
        )
    except requests.exceptions.RequestException as exc:
        print(f"Hata: API istegi basarisiz oldu: {exc}", file=sys.stderr)
        sys.exit(1)

    if not headlines:
        print("Hic yeni baslik cekilemedi.")
        if limit_info["retry_after"]:
            print(f"Tahmini bekleme suresi (saniye): {limit_info['retry_after']}")
        existing_count = count_existing_records(args.out_json)
        if existing_count > 0:
            print(f"Not: Daha once kaydedilmis {existing_count} baslik mevcut ({args.out_json}).")
        if limit_info["limit"] is not None and limit_info["remaining"] is not None:
            print(f"Toplam kredi/limit: {limit_info['limit']}")
            print(f"Kalan kredi/limit: {limit_info['remaining']}")
        return

    print("Bu calismada cekilen basliklar:")
    for i, item in enumerate(headlines, start=1):
        print(f"{i}. {item['title']}")

    if args.append_mode:
        existing_records = load_existing_records(args.out_json)
        combined_records = existing_records + headlines
        merged_records = deduplicate_records(combined_records)
        added_count = len(merged_records) - len(existing_records)
        duplicate_count = len(combined_records) - len(merged_records)
        write_json(Path(args.out_json), merged_records)
        write_csv(Path(args.out_csv), merged_records)
        print(f"Bu calismada {len(headlines)} adet baslik cekildi.")
        print(f"Tekrarsiz yeni eklenen kayit: {added_count}")
        print(f"Temizlenen tekrar sayisi: {duplicate_count}")
        print(f"Toplam havuz boyutu: {len(merged_records)}")
    else:
        write_json(Path(args.out_json), headlines)
        write_csv(Path(args.out_csv), headlines)
        print(f"{len(headlines)} adet baslik cekildi.")

    print(f"Gonderilen API istek sayisi: {request_count}")
    print(f"Kaydedildi: {args.out_json}")
    print(f"Kaydedildi: {args.out_csv}")

    if limit_info["limit"] is not None and limit_info["remaining"] is not None:
        print(f"Toplam kredi/limit: {limit_info['limit']}")
        print(f"Kalan kredi/limit: {limit_info['remaining']}")
        try:
            used = int(limit_info["limit"]) - int(limit_info["remaining"])
            print(f"Kullanilan kredi/limit: {used}")
        except ValueError:
            pass
    else:
        print(
            "Not: API kredi (limit/kalan) bilgisi bu istekte header olarak donmedi."
        )


if __name__ == "__main__":
    main()
