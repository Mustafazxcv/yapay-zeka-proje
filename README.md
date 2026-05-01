# Öğrenciler

- Mustafa Mete / 2202131015
- Emine Avcu / 2202131006


# Proje Ödevi

[21] Haber Başlığı Çoğaltma Tespiti Problem: Farklı haber kaynaklarında aynı içeriğin farklı başlıklarla yayınlanıp yayınlanmadığını tespit etme Veri Kaynağı: NewsAPI’den toplanan haber başlıkları Adımlar: Başlıkları normalize et (küçük harf, noktalama temizliği vb.). Cosine benzerliği hesapla. %85’ten fazla benzerliği olan başlık çiftlerini işaretle.


## Klasor yapisi

Aciklama:
- Degiskenler `.env` dosyasinda.
- Veri cekme botlari `bots/fetch` altinda klasorlu calistirilir.
- Veri cekme botlari sadece Ingilizce veri toplar ve tum ham veriyi tek dosyada birlestirir (`data/all/headlines_all.json`, `data/all/headlines_all.csv`).

## Kurulum

Proje klasorunde terminal ac:

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## .env ayari

Kok dizindeki `.env` dosyasina hem API anahtarini hem de varsayilan parametreleri yaz:

## Veri cekme botunu calistirma

Asagidaki komutla botu calistir:

```bash
python bots/fetch/newsdata_fetch_bot.py
```

NewsAPI botunu calistirmak icin:

```bash
python bots/fetch/newsapi_fetch_bot.py
```

API kullanmadan, konu bazli Google tarama botunu calistirmak icin:

```bash
python bots/fetch/topic_search_fetch_bot.py
```

Not: Google insan dogrulamasi cikarsa, tarayicida dogrulamayi tamamlayip terminalde Enter'a basin.

Olusan dosyalar:
- `data/all/headlines_all.json`
- `data/all/headlines_all.csv`

## Veri analizi ve cogaltma tespiti (Jupyter)

Ciktilari:
- `data/processed/all/headlines_normalized_all.csv`
- `data/processed/all/headlines_normalized_all.json`
- `data/results/all/duplicate_pairs_all.csv`
- `data/results/all/duplicate_pairs_all.json`