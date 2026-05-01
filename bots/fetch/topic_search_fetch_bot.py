import argparse
import csv
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


GOOGLE_SEARCH_URL = "https://www.google.com/search"
GOOGLE_NEWS_RSS_SEARCH_URL = "https://news.google.com/rss/search"


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


def parse_topics(raw_topics: str):
    parts = [item.strip() for item in (raw_topics or "").split(",")]
    topics = [item for item in parts if item]
    unique_topics = []
    seen = set()
    for topic in topics:
        key = topic.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_topics.append(topic)
    return unique_topics


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


def record_key(item):
    return (
        (item.get("title") or "").strip().lower(),
        (item.get("source") or "").strip().lower(),
        (item.get("link") or "").strip().lower(),
        (item.get("pubDate") or "").strip(),
    )


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


def normalize_google_result_url(raw_url: str) -> str:
    if not raw_url:
        return ""
    parsed = urlparse(raw_url)
    if parsed.path == "/url":
        qs = parse_qs(parsed.query)
        real_urls = qs.get("q", [])
        if real_urls:
            return real_urls[0].strip()
    return raw_url.strip()


def fetch_google_search_page(topic: str, language: str, country: str, start: int, num: int):
    params = {
        "q": topic,
        "hl": language,
        "gl": country,
        "num": num,
        "start": start,
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(GOOGLE_SEARCH_URL, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text


def build_google_search_url(topic: str, language: str, country: str, start: int, num: int) -> str:
    return (
        f"{GOOGLE_SEARCH_URL}?q={topic}"
        f"&hl={language}"
        f"&gl={country}"
        f"&num={num}"
        f"&start={start}"
    )


def try_accept_google_consent(page):
    # Farkli bolgelerde farkli metinlerle gelen consent popup'larini gecmeye calisir.
    consent_selectors = [
        "button[aria-label*='Accept']",
        "button[aria-label*='I agree']",
        "button:has-text('Accept all')",
        "button:has-text('I agree')",
        "button:has-text('Kabul et')",
    ]
    for selector in consent_selectors:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=1000):
                btn.click(timeout=1000)
                time.sleep(1.0)
                return
        except Exception:
            continue


def is_human_verification_page(html_text: str) -> bool:
    lowered = (html_text or "").lower()
    markers = [
        "unusual traffic",
        "verify you are human",
        "i'm not a robot",
        "our systems have detected unusual traffic",
        "recaptcha",
    ]
    return any(marker in lowered for marker in markers)


def fetch_google_search_page_chromium(page, topic: str, language: str, country: str, start: int, num: int):
    url = build_google_search_url(topic, language, country, start, num)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try_accept_google_consent(page)

    # "Insan gibi" davranis icin kisa rastgele scroll + bekleme.
    for _ in range(2):
        page.mouse.wheel(0, random.randint(400, 900))
        time.sleep(random.uniform(0.5, 1.2))

    html_text = page.content()
    if is_human_verification_page(html_text):
        print(
            "\nDogrulama ekrani algilandi. Tarayicida dogrulamayi tamamla, sonra terminalde Enter'a bas.",
            file=sys.stderr,
        )
        input("Devam etmek icin Enter...")
        time.sleep(1.0)
        html_text = page.content()
    return html_text


def parse_google_results(html_text: str):
    soup = BeautifulSoup(html_text, "html.parser")
    records = []
    seen_links = set()

    # Google HTML yapisi degisebildigi icin /url?q=... kalibini yakalayarak parse ediyoruz.
    for link_tag in soup.select("a[href]"):
        raw_href = link_tag.get("href", "")
        if not raw_href.startswith("/url?"):
            continue
        link = normalize_google_result_url(raw_href)
        if not link.startswith("http"):
            continue
        if link in seen_links:
            continue

        title = link_tag.get_text(" ", strip=True)
        if not title:
            continue

        seen_links.add(link)
        records.append(
            {
                "title": title,
                "source": "google_search",
                "link": link,
                "pubDate": "",
                "fetchedAt": datetime.now(timezone.utc).isoformat(),
            }
        )
    return records


def fetch_google_news_rss(topic: str, language: str, country: str, max_items: int):
    rss_url = (
        f"{GOOGLE_NEWS_RSS_SEARCH_URL}?q={topic}"
        f"&hl={language}&gl={country}&ceid={country}:{language}"
    )
    response = requests.get(rss_url, timeout=30)
    response.raise_for_status()

    root = ElementTree.fromstring(response.content)
    channel = root.find("channel")
    if channel is None:
        return []

    records = []
    for item in channel.findall("item")[:max_items]:
        title_node = item.find("title")
        link_node = item.find("link")
        date_node = item.find("pubDate")
        source_node = item.find("source")

        title = (title_node.text or "").strip() if title_node is not None else ""
        link = (link_node.text or "").strip() if link_node is not None else ""
        pub_date = (date_node.text or "").strip() if date_node is not None else ""
        source = (source_node.text or "").strip() if source_node is not None else "google_news_rss"

        if not title or not link:
            continue
        records.append(
            {
                "title": title,
                "source": source,
                "link": link,
                "pubDate": pub_date,
                "fetchedAt": datetime.now(timezone.utc).isoformat(),
            }
        )
    return records


def fetch_from_topics(
    topics,
    language: str,
    country: str,
    results_per_page: int,
    max_requests_per_topic: int,
    show_browser: bool,
    existing_keys,
    on_new_records=None,
):
    headlines = []
    request_count = 0
    seen_keys = set(existing_keys)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not show_browser)
        context = browser.new_context(locale="en-US")
        page = context.new_page()

        for topic in topics:
            print(f"\n=== Konu: {topic} ===")
            page_idx = 0
            empty_streak = 0
            while page_idx < max_requests_per_topic:
                start = page_idx * results_per_page
                try:
                    html_text = fetch_google_search_page_chromium(
                        page=page,
                        topic=topic,
                        language=language,
                        country=country,
                        start=start,
                        num=results_per_page,
                    )
                    request_count += 1
                    records = parse_google_results(html_text)
                    if not records:
                        print(f"Sayfa {page_idx + 1}: normal Google sonuc yok, RSS fallback deneniyor.")
                        try:
                            records = fetch_google_news_rss(
                                topic=topic,
                                language=language,
                                country=country,
                                max_items=results_per_page,
                            )
                        except requests.exceptions.RequestException as rss_exc:
                            print(f"RSS fallback hatasi: {rss_exc}", file=sys.stderr)
                            records = []
                        except ElementTree.ParseError as rss_exc:
                            print(f"RSS parse hatasi: {rss_exc}", file=sys.stderr)
                            records = []

                        if not records:
                            empty_streak += 1
                            print(f"Sayfa {page_idx + 1}: fallback de bos.")
                            if empty_streak >= 2:
                                print("Arka arkaya bos sonuc alindi, bu konu icin tarama durduruldu.")
                                break
                            page_idx += 1
                            continue

                    fresh_records = []
                    for item in records:
                        key = record_key(item)
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        fresh_records.append(item)

                    if not fresh_records:
                        empty_streak += 1
                        print(
                            f"Sayfa {page_idx + 1}: yeni sonuc yok (tum sonuclar zaten kayitli)."
                        )
                        if empty_streak >= 2:
                            print("Arka arkaya yeni sonuc gelmedi, bu konu icin tarama durduruldu.")
                            break
                        page_idx += 1
                        continue

                    print(f"Sayfa {page_idx + 1}: {len(fresh_records)} yeni sonuc bulundu.")
                    for idx, item in enumerate(fresh_records, start=1):
                        print(f"  {idx}. {item['title']}")
                        print(f"     -> {item['link']}")
                    headlines.extend(fresh_records)
                    if on_new_records is not None:
                        on_new_records(fresh_records)
                    empty_streak = 0
                    page_idx += 1
                except PlaywrightTimeoutError as exc:
                    print(
                        f"Uyari: '{topic}' icin sayfa {page_idx + 1} timeout: {exc}",
                        file=sys.stderr,
                    )
                    break
                except Exception as exc:
                    print(
                        f"Uyari: '{topic}' icin sayfa {page_idx + 1} cekilemedi: {exc}",
                        file=sys.stderr,
                    )
                    break

        context.close()
        browser.close()

    return headlines, request_count


def main():
    load_env_file(".env")

    parser = argparse.ArgumentParser(description="Google arama sonuclarini konu konu gezip kaydeder.")
    parser.add_argument(
        "--topics",
        default=env_str("TOPIC_RSS_TOPICS", "technology,artificial intelligence"),
        help="Virgulle ayrilmis konu listesi. Ornek: technology,artificial intelligence",
    )
    parser.add_argument("--language", default=env_str("TOPIC_RSS_LANGUAGE", "en"))
    parser.add_argument("--country", default=env_str("TOPIC_RSS_COUNTRY", "US"))
    parser.add_argument(
        "--results-per-page",
        type=int,
        default=env_int("TOPIC_RSS_RESULTS_PER_PAGE", 10),
    )
    parser.add_argument(
        "--max-requests-per-topic",
        type=int,
        default=env_int("TOPIC_RSS_MAX_REQUESTS_PER_TOPIC", 200),
        help="Guvenlik limiti. Sonuc geldigi surece tarar, bu limite ulasinca durur.",
    )
    parser.add_argument(
        "--pages-per-topic",
        type=int,
        default=None,
        help="Geriye donuk uyumluluk. Verilirse max-requests-per-topic yerine kullanilir.",
    )
    parser.add_argument(
        "--out-json",
        default=env_str("TOPIC_RSS_OUT_JSON", "data/all/headlines_all.json"),
    )
    parser.add_argument(
        "--out-csv",
        default=env_str("TOPIC_RSS_OUT_CSV", "data/all/headlines_all.csv"),
    )
    parser.add_argument(
        "--append-mode",
        default=env_bool("TOPIC_RSS_APPEND_MODE", True),
        action=argparse.BooleanOptionalAction,
        help="Aciksa mevcut dosyadaki veriler korunur, yeni veriler eklenir ve tekrarlar temizlenir.",
    )
    parser.add_argument(
        "--show-browser",
        default=env_bool("TOPIC_RSS_SHOW_BROWSER", True),
        action=argparse.BooleanOptionalAction,
        help="Aciksa Chromium penceresi gorunur.",
    )
    args = parser.parse_args()
    args.language = "en"
    args.country = "US"

    topics = parse_topics(args.topics)
    if not topics:
        print(
            "Hata: En az bir konu verilmelidir. --topics ile konu listesi girin.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.max_requests_per_topic < 1:
        print("Hata: --max-requests-per-topic en az 1 olmalidir.", file=sys.stderr)
        sys.exit(1)

    if args.pages_per_topic is not None:
        if args.pages_per_topic < 1:
            print("Hata: --pages-per-topic en az 1 olmalidir.", file=sys.stderr)
            sys.exit(1)
        args.max_requests_per_topic = args.pages_per_topic

    if args.results_per_page < 1 or args.results_per_page > 100:
        print("Hata: --results-per-page 1 ile 100 arasinda olmalidir.", file=sys.stderr)
        sys.exit(1)

    try:
        existing_records = load_existing_records(args.out_json) if args.append_mode else []
        existing_keys = {record_key(item) for item in existing_records}
        current_records = list(existing_records) if args.append_mode else []

        def autosave_new_records(new_records):
            nonlocal current_records
            current_records.extend(new_records)
            current_records = deduplicate_records(current_records)
            write_json(Path(args.out_json), current_records)
            write_csv(Path(args.out_csv), current_records)
            print(
                f"Otomatik kayit yapildi: +{len(new_records)} yeni kayit, toplam {len(current_records)}"
            )

        headlines, request_count = fetch_from_topics(
            topics=topics,
            language=args.language,
            country=args.country,
            results_per_page=args.results_per_page,
            max_requests_per_topic=args.max_requests_per_topic,
            show_browser=args.show_browser,
            existing_keys=existing_keys,
            on_new_records=autosave_new_records,
        )
    except Exception as exc:
        print(f"Hata: RSS veri cekme basarisiz oldu: {exc}", file=sys.stderr)
        sys.exit(1)

    headlines = deduplicate_records(headlines)
    if not headlines:
        print("Hic yeni baslik cekilemedi. Konu listesi veya internet baglantisini kontrol edin.")
        return

    print("Bu calismada cekilen basliklar:")
    for i, item in enumerate(headlines, start=1):
        print(f"{i}. {item['title']}")

    if args.append_mode:
        merged_records = current_records
        added_count = len(merged_records) - len(existing_records)
        duplicate_count = (len(existing_records) + len(headlines)) - len(merged_records)
        write_json(Path(args.out_json), merged_records)
        write_csv(Path(args.out_csv), merged_records)
        print(f"Bu calismada {len(headlines)} adet baslik cekildi.")
        print(f"Tekrarsiz yeni eklenen kayit: {added_count}")
        print(f"Temizlenen tekrar sayisi: {duplicate_count}")
        print(f"Toplam havuz boyutu: {len(merged_records)}")
    else:
        final_records = current_records if current_records else headlines
        write_json(Path(args.out_json), final_records)
        write_csv(Path(args.out_csv), final_records)
        print(f"{len(final_records)} adet baslik cekildi.")

    print(f"Gonderilen Google istek sayisi: {request_count}")
    print(f"Konu sayisi: {len(topics)}")
    print(f"Kaydedildi: {args.out_json}")
    print(f"Kaydedildi: {args.out_csv}")


if __name__ == "__main__":
    main()
