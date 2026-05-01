import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from newsapi import NewsApiClient


SUPPORTED_NEWSAPI_LANGUAGES = {
    "ar",
    "de",
    "en",
    "es",
    "fr",
    "he",
    "it",
    "nl",
    "no",
    "pt",
    "ru",
    "sv",
    "ud",
    "zh",
}


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


def fetch_newsapi(
    api_key: str,
    query: str,
    language: str,
    country: str,
    category: str,
    page_size: int,
    max_pages: int,
):
    client = NewsApiClient(api_key=api_key)
    headlines = []
    request_count = 0
    limit_info = {"retry_after": None, "upgrade_required": False}
    normalized_language = (language or "").strip().lower()
    use_language = normalized_language if normalized_language in SUPPORTED_NEWSAPI_LANGUAGES else None

    if normalized_language and not use_language:
        print(
            "NewsAPI bu dil kodunu desteklemiyor. Dil filtresi kapatilarak devam edilecek."
        )

    for page in range(1, max_pages + 1):
        try:
            if query:
                payload = client.get_top_headlines(
                    q=query,
                    language=use_language,
                    page_size=page_size,
                    page=page,
                )
            else:
                payload = client.get_top_headlines(
                    country=country or None,
                    category=category or None,
                    page_size=page_size,
                    page=page,
                )
            request_count += 1
        except Exception as exc:
            error_text = str(exc).lower()
            if "426" in error_text:
                limit_info["upgrade_required"] = True
                print(
                    "NewsAPI paketi bu istek tipi icin yetersiz (426 Upgrade Required).",
                    file=sys.stderr,
                )
                break
            if "429" in error_text:
                print(
                    "NewsAPI limiti asildi (429). Daha fazla veri cekilemedi.",
                    file=sys.stderr,
                )
                break
            raise

        articles = payload.get("articles", [])
        if not articles:
            break

        for item in articles:
            title = item.get("title")
            if not title:
                continue
            source_name = ""
            source_obj = item.get("source")
            if isinstance(source_obj, dict):
                source_name = source_obj.get("name", "")

            headlines.append(
                {
                    "title": title.strip(),
                    "source": source_name,
                    "link": item.get("url"),
                    "pubDate": item.get("publishedAt"),
                    "fetchedAt": datetime.now(timezone.utc).isoformat(),
                }
            )

    return headlines, request_count, limit_info


def fetch_newsapi_from_sources(
    api_key: str,
    language: str,
    country: str,
    max_sources: int,
    page_size: int,
):
    client = NewsApiClient(api_key=api_key)
    headlines = []
    request_count = 0
    limit_info = {"retry_after": None, "upgrade_required": False}

    try:
        sources_payload = client.get_sources(
            language=language or None,
            country=country or None,
        )
        request_count += 1
    except Exception as exc:
        error_text = str(exc).lower()
        if "426" in error_text:
            limit_info["upgrade_required"] = True
            print(
                "Kaynak listesini cekmek icin paket yetersiz (426).",
                file=sys.stderr,
            )
            return headlines, request_count, limit_info
        if "429" in error_text:
            print("Kaynak listesi cekerken API limiti asildi (429).", file=sys.stderr)
            return headlines, request_count, limit_info
        raise

    source_ids = [
        item.get("id", "").strip()
        for item in sources_payload.get("sources", [])
        if item.get("id")
    ][:max_sources]

    for sid in source_ids:
        try:
            payload = client.get_top_headlines(
                sources=sid,
                page_size=page_size,
                page=1,
            )
            request_count += 1
        except Exception as exc:
            error_text = str(exc).lower()
            if "426" in error_text:
                limit_info["upgrade_required"] = True
                print(
                    "Kaynak bazli cekim bu istekte paket gerektiriyor (426).",
                    file=sys.stderr,
                )
                break
            if "429" in error_text:
                print("Kaynak bazli cekimde API limiti asildi (429).", file=sys.stderr)
                break
            continue

        for item in payload.get("articles", []):
            title = item.get("title")
            if not title:
                continue
            source_name = ""
            source_obj = item.get("source")
            if isinstance(source_obj, dict):
                source_name = source_obj.get("name", "")
            headlines.append(
                {
                    "title": title.strip(),
                    "source": source_name,
                    "link": item.get("url"),
                    "pubDate": item.get("publishedAt"),
                    "fetchedAt": datetime.now(timezone.utc).isoformat(),
                }
            )

    return headlines, request_count, limit_info


def main():
    load_env_file(".env")

    parser = argparse.ArgumentParser(
        description="NewsAPI'den başlıkları cekip data klasorune kaydeder."
    )
    parser.add_argument("--api-key", default=os.getenv("NEWSAPI_API_KEY"))
    parser.add_argument("--query", default=env_str("NEWSAPI_QUERY", "technology"))
    parser.add_argument("--language", default=env_str("NEWSAPI_LANGUAGE", "en"))
    parser.add_argument("--country", default=env_str("NEWSAPI_COUNTRY", "us"))
    parser.add_argument("--category", default=env_str("NEWSAPI_CATEGORY", ""))
    parser.add_argument("--page-size", type=int, default=env_int("NEWSAPI_PAGE_SIZE", 50))
    parser.add_argument("--max-pages", type=int, default=env_int("NEWSAPI_MAX_PAGES", 3))
    parser.add_argument("--max-sources", type=int, default=env_int("NEWSAPI_MAX_SOURCES", 20))
    parser.add_argument(
        "--out-json", default=env_str("NEWSAPI_OUT_JSON", "data/all/headlines_all.json")
    )
    parser.add_argument(
        "--out-csv", default=env_str("NEWSAPI_OUT_CSV", "data/all/headlines_all.csv")
    )
    parser.add_argument(
        "--append-mode",
        default=env_bool("NEWSAPI_APPEND_MODE", True),
        action=argparse.BooleanOptionalAction,
        help="Aciksa mevcut dosyadaki veriler korunur, yeni veriler eklenir ve tekrarlar temizlenir.",
    )
    parser.add_argument(
        "--expand-sources",
        default=env_bool("NEWSAPI_EXPAND_SOURCES", True),
        action=argparse.BooleanOptionalAction,
        help="Aciksa kaynak listesi uzerinden ek basliklar cekerek veri hacmini artirir.",
    )
    args = parser.parse_args()
    args.language = "en"
    args.country = "us"

    if not args.api_key:
        print(
            "Hata: NewsAPI anahtari eksik.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        headlines, request_count, limit_info = fetch_newsapi(
            api_key=args.api_key,
            query=args.query,
            language=args.language,
            country=args.country,
            category=args.category,
            page_size=args.page_size,
            max_pages=args.max_pages,
        )
    except Exception as exc:
        print(f"Hata: NewsAPI istegi basarisiz oldu: {exc}", file=sys.stderr)
        sys.exit(1)

    if not headlines and args.query:
        print(
            "Bilgi: Sorgu modunda sonuc bulunamadi. Ulke/kategori moduyla tekrar deneniyor."
        )
        try:
            fallback_headlines, fallback_request_count, fallback_limit_info = fetch_newsapi(
                api_key=args.api_key,
                query="",
                language=args.language,
                country=args.country,
                category=args.category,
                page_size=args.page_size,
                max_pages=args.max_pages,
            )
            headlines = fallback_headlines
            request_count += fallback_request_count
            limit_info = fallback_limit_info
        except Exception as exc:
            print(f"Hata: Fallback istegi de basarisiz oldu: {exc}", file=sys.stderr)
            sys.exit(1)

    if not headlines:
        print("Hic yeni baslik cekilemedi.")
        if limit_info.get("upgrade_required"):
            print(
                "Not: NewsAPI mevcut planda bu endpoint/istekleri engelliyor.
            )
        if limit_info["retry_after"]:
            print(f"Tahmini bekleme suresi (saniye): {limit_info['retry_after']}")
        if not args.expand_sources:
            return

    if args.expand_sources:
        print("Bilgi: Kaynak bazli genisletme modu calisiyor.")
        try:
            source_headlines, source_request_count, source_limit_info = fetch_newsapi_from_sources(
                api_key=args.api_key,
                language=args.language,
                country=args.country,
                max_sources=args.max_sources,
                page_size=args.page_size,
            )
            headlines.extend(source_headlines)
            request_count += source_request_count
            if source_limit_info.get("upgrade_required"):
                limit_info["upgrade_required"] = True
        except Exception as exc:
            print(f"Hata: Kaynak bazli genisletme basarisiz oldu: {exc}", file=sys.stderr)

    headlines = deduplicate_records(headlines)
    if not headlines:
        print("Hic yeni baslik cekilemedi.")
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


if __name__ == "__main__":
    main()
