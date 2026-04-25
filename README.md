#Öğrenciler

- Mustafa Mete / 2202131015
- Emine Avcu / 2202131006


# Proje Ödevi

[21] Haber Başlığı Çoğaltma Tespiti Problem: Farklı haber kaynaklarında aynı içeriğin farklı başlıklarla yayınlanıp yayınlanmadığını tespit etme Veri Kaynağı: NewsAPI’den toplanan haber başlıkları Adımlar: Başlıkları normalize et (küçük harf, noktalama temizliği vb.). Cosine benzerliği hesapla. %85’ten fazla benzerliği olan başlık çiftlerini işaretle.


## Klasor yapisi

Aciklama:
- Kod `bots/news_fetch_bot.py` dosyasinda.
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
NEWS_OUT_JSON=data/headlines_raw.json
NEWS_OUT_CSV=data/headlines_raw.csv
NEWS_APPEND_MODE=true
```

## Veri cekme botunu calistirma

Asagidaki komutla botu calistir:

```bash
python bots/news_fetch_bot.py
```

Olusan dosyalar:
- `data/headlines_raw.json`
- `data/headlines_raw.csv`

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

Komut satiri parametreleri:
- `--query`, `--language`, `--country`, `--category`, `--max-pages`
- `--out-json`, `--out-csv`, `--append-mode`, `--no-append-mode`

