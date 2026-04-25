# Öğrenciler

- Mustafa Mete / 2202131015
- Emine Avcu / 2202131006


# Proje Ödevi

[21] Haber Başlığı Çoğaltma Tespiti Problem: Farklı haber kaynaklarında aynı içeriğin farklı başlıklarla yayınlanıp yayınlanmadığını tespit etme Veri Kaynağı: NewsAPI’den toplanan haber başlıkları Adımlar: Başlıkları normalize et (küçük harf, noktalama temizliği vb.). Cosine benzerliği hesapla. %85’ten fazla benzerliği olan başlık çiftlerini işaretle.


## Klasor yapisi

Aciklama:
- Değişkenler `.env` dosyasinda.
- Cekilen veriler `data/` klasorune kaydedilir.

## Kurulum

Proje klasorunde terminal ac:

```bash
pip install -r requirements.txt
```

## .env ayari

Kok dizindeki `.env` dosyasina hem API anahtarini hem de varsayilan parametreleri yaz:

```env
NEWSDATA_API_KEY=BURAYA_API_KEYINI_YAZ
NEWS_QUERY=ekonomi
NEWS_LANGUAGE=tr
NEWS_COUNTRY=tr
NEWS_CATEGORY=
NEWS_MAX_PAGES=3
NEWS_OUT_JSON=data/headlines_newsdata.json
NEWS_OUT_CSV=data/headlines_newsdata.csv
NEWS_APPEND_MODE=true

NEWSAPI_API_KEY=BURAYA_NEWSAPI_KEY_YAZ
NEWSAPI_QUERY=teknoloji
NEWSAPI_LANGUAGE=tr
NEWSAPI_COUNTRY=tr
NEWSAPI_CATEGORY=
NEWSAPI_PAGE_SIZE=50
NEWSAPI_MAX_PAGES=3
NEWSAPI_OUT_JSON=data/headlines_newsapi.json
NEWSAPI_OUT_CSV=data/headlines_newsapi.csv
NEWSAPI_APPEND_MODE=true
```

## Veri cekme botunu calistirma

Asagidaki komutla botu calistir:

```bash
python bots/newsdata_fetch_bot.py
```

NewsAPI botunu calistirmak icin:

```bash
python bots/newsapi_fetch_bot.py
```

Olusan dosyalar:
- `data/headlines_newsdata.json`
- `data/headlines_newsdata.csv`
- `data/headlines_newsapi.json`
- `data/headlines_newsapi.csv`

## Parametreler

`.env` degiskenleri:
- `NEWS_QUERY`: aranacak konu
- `NEWS_LANGUAGE`: dil kodu
- `NEWS_COUNTRY`: ulke kodu
- `NEWS_CATEGORY`: kategori (bos birakilabilir)
- `NEWS_MAX_PAGES`: cekilecek sayfa sayisi
- `NEWS_OUT_JSON`: JSON cikti yolu
- `NEWS_OUT_CSV`: CSV cikti yolu
- `NEWS_APPEND_MODE`: `true` ise eski veriye ekler ve tekrar kayitlari temizler
- `NEWSAPI_API_KEY`: NewsAPI anahtari
- `NEWSAPI_QUERY`: aranacak konu (bos ise ulke/kategori ile ceker)
- `NEWSAPI_LANGUAGE`: dil kodu
- `NEWSAPI_COUNTRY`: ulke kodu
- `NEWSAPI_CATEGORY`: kategori
- `NEWSAPI_PAGE_SIZE`: sayfa basi haber sayisi
- `NEWSAPI_MAX_PAGES`: cekilecek sayfa sayisi
- `NEWSAPI_OUT_JSON`: NewsAPI JSON cikti yolu
- `NEWSAPI_OUT_CSV`: NewsAPI CSV cikti yolu
- `NEWSAPI_APPEND_MODE`: ekleme + tekrar temizleme modu

Komut satiri parametreleri:
- `--query`, `--language`, `--country`, `--category`, `--max-pages`
- `--out-json`, `--out-csv`, `--append-mode`, `--no-append-mode`

