
import time
import re
from datetime import datetime
from email.utils import parsedate_to_datetime

from src.scraper import fetch_news
from src.analyzer import analyze_articles


MAX_SECONDS = 15
MAX_ANALYZE = 10
MIN_IMPACT_SCORE_TO_SHOW = 4


DIRECT_ECONOMIC_KEYWORDS = [
    "ihsg", "saham", "bursa", "emiten", "investor", "obligasi",
    "reksa dana", "pasar modal", "wall street", "nasdaq", "dow jones",

    "rupiah", "dolar", "usd", "kurs", "valas", "mata uang",
    "bank indonesia", "the fed", "suku bunga", "inflasi", "deflasi",

    "bitcoin", "btc", "ethereum", "eth", "crypto", "kripto", "aset digital",

    "emas", "gold", "xau", "minyak", "bbm", "batu bara", "batubara",
    "nikel", "tembaga", "cpo", "komoditas",

    "ekonomi", "pdb", "pertumbuhan ekonomi", "ekspor", "impor",
    "neraca perdagangan", "cadangan devisa", "pajak", "apbn",
    "subsidi", "investasi", "pma", "pmdn", "bank dunia",

    "laba", "rugi", "pendapatan", "revenue", "profit", "dividen",
    "ipo", "akuisisi", "merger", "startup", "umkm", "industri",
    "manufaktur", "ritel", "retail", "perbankan", "bank",

    "energi", "transportasi", "logistik", "properti", "konstruksi",
    "infrastruktur", "pertambangan",
]


IMPACT_KEYWORDS = [
    "melemah", "menguat", "naik", "turun", "anjlok", "tertekan",
    "rebound", "merosot", "melonjak", "tumbuh", "melambat",

    "inflasi", "suku bunga", "the fed", "bank indonesia", "bi rate",
    "rupiah", "dolar", "usd", "kurs",

    "ihsg", "saham", "bursa", "wall street", "nasdaq", "dow jones",
    "investor", "asing", "capital outflow", "capital inflow",

    "minyak", "emas", "xau", "bbm", "batu bara", "batubara", "nikel",
    "komoditas", "energi",

    "bitcoin", "btc", "ethereum", "eth", "crypto", "kripto",

    "ekspor", "impor", "neraca perdagangan", "pdb",
    "cadangan devisa", "apbn", "pajak", "subsidi", "bank dunia",

    "konflik", "perang", "geopolitik", "sanksi",
    "rusia", "ukraina", "iran", "israel", "timur tengah",

    "laba", "rugi", "pendapatan", "dividen", "ipo", "akuisisi",
    "merger", "bangkrut", "pailit",
]


LOW_VALUE_KEYWORDS = [
    "profil", "riwayat", "sosok", "pahlawan", "istri",
    "mengenal lembaga", "tugas dan wewenang", "kilas balik",
    "apa bedanya", "sejarah", "biodata", "tokoh",
    "eks presiden", "penjara", "dipenjara", "pidana",
    "sidang", "putusan hakim", "artis", "seleb",
    "olahraga", "sepak bola", "film", "musik", "konser",
    "harta kekayaan", "segini harta kekayaan",
]


def normalize_text(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def keyword_in_text(keyword: str, text: str) -> bool:
    keyword = keyword.lower()

    if " " in keyword:
        return keyword in text

    pattern = r"\b" + re.escape(keyword) + r"\b"
    return re.search(pattern, text) is not None


def count_keywords(text: str, keywords: list[str]) -> int:
    return sum(1 for keyword in keywords if keyword_in_text(keyword, text))


def should_send_to_llm(article: dict) -> bool:
    title = article.get("title", "")
    content = article.get("content", "")
    source = article.get("source", "")

    text = normalize_text(f"{title} {content} {source}")

    economic_score = count_keywords(text, DIRECT_ECONOMIC_KEYWORDS)
    impact_score = count_keywords(text, IMPACT_KEYWORDS)
    low_value_score = count_keywords(text, LOW_VALUE_KEYWORDS)

    # Kalau tidak ada sinyal ekonomi sama sekali, jangan kirim ke Gemini
    if economic_score == 0:
        return False

    # Kalau berita profil/riwayat/politik ringan, skip kecuali punya sinyal impact kuat
    if low_value_score > 0 and impact_score < 3:
        return False

    # Minimal harus punya 2 sinyal dampak biar token tidak boros
    if impact_score < 2:
        return False

    return True


def is_medium_or_high_impact(item: dict) -> bool:
    category = item.get("main_category", "")
    impact_level = str(item.get("impact_level", "")).lower()

    try:
        impact_score = int(item.get("impact_score", 0))
    except Exception:
        impact_score = 0

    if category == "lainnya":
        return False

    if impact_level not in ["sedang", "tinggi"]:
        return False

    if impact_score < MIN_IMPACT_SCORE_TO_SHOW:
        return False

    return True


def get_article_date(item: dict) -> str:
    date_value = (
        item.get("published_at")
        or item.get("published")
        or item.get("updated")
        or item.get("pubDate")
        or item.get("tanggal")
        or item.get("date")
        or item.get("published_date")
        or item.get("created_at")
        or ""
    )

    if date_value:
        try:
            return parsedate_to_datetime(str(date_value)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(date_value)

    parsed_date = item.get("published_parsed") or item.get("updated_parsed")

    if parsed_date:
        try:
            return datetime.fromtimestamp(time.mktime(parsed_date)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return ""

    return ""


def main():
    total_start = time.perf_counter()
    llm_duration = 0

    print("Mengambil berita dari scraper...")
    scraper_start = time.perf_counter()

    articles = fetch_news(limit_per_source=5)

    scraper_end = time.perf_counter()
    scraper_duration = scraper_end - scraper_start

    print(f"Total berita dari scraper: {len(articles)}")
    print(f"Waktu pencarian/scraper: {scraper_duration:.2f} detik")

    if not articles:
        print("Tidak ada berita yang berhasil diambil.")
        return

    for article in articles:
        article["published_at"] = get_article_date(article)

    # ============================================================
    # FILTER SEBELUM LLM
    # Berita non-ekonomi, low value, dan tidak berdampak tidak masuk Gemini.
    # ============================================================
    articles_to_analyze = [
        article for article in articles
        if should_send_to_llm(article)
    ]

    articles_to_analyze = articles_to_analyze[:MAX_ANALYZE]

    print(f"Berita yang layak dikirim ke Gemini: {len(articles_to_analyze)}")

    if not articles_to_analyze:
        print("\nTidak ada berita ekonomi berdampak yang layak dianalisis.")
        print("Gemini tidak dijalankan, token aman.")
        return

    # ============================================================
    # BAGIAN ANALYZE / ANALISIS LLM
    # Hanya kandidat ekonomi berdampak yang masuk Gemini.
    # ============================================================
    print("\nMenganalisis berita ekonomi berdampak dengan Gemini...")
    llm_start = time.perf_counter()

    results = analyze_articles(articles_to_analyze)

    llm_end = time.perf_counter()
    llm_duration = llm_end - llm_start

    # ============================================================
    # FILTER SETELAH LLM
    # Yang tampil hanya dampak sedang - tinggi.
    # ============================================================
    final_results = [
        item for item in results
        if is_medium_or_high_impact(item)
    ]

    total_end = time.perf_counter()
    total_duration = total_end - total_start

    if not final_results:
        print("\nTidak ada berita dengan dampak sedang atau tinggi yang layak ditampilkan.")
        print("Hasil dampak rendah disembunyikan.")
    else:
        print("\nHASIL ANALISIS BERITA EKONOMI DAMPAK SEDANG - TINGGI:")
        for item in final_results:
            tanggal = get_article_date(item) or "-"

            print("=" * 60)
            print(f"Judul: {item.get('title')}")
            print(f"Sumber: {item.get('source')}")
            print(f"Tanggal: {tanggal}")
            print(f"URL: {item.get('url')}")
            print(f"Kategori: {item.get('main_category')}")
            print(f"Sentimen: {item.get('sentiment')}")
            print(f"Dampak: {item.get('impact_level')}")
            print(f"Skor Dampak: {item.get('impact_score')}")
            print(f"Main Cause: {item.get('main_cause')}")
            print(f"Affected Markets: {item.get('affected_markets')}")
            print(f"Summary: {item.get('summary')}")
            print(f"Impact Explanation: {item.get('impact_explanation')}")
            print(f"Confidence Score: {item.get('confidence_score')}")

    print("\nWAKTU EKSEKUSI")
    print("=" * 60)
    print(f"Waktu pencarian/scraper : {scraper_duration:.2f} detik")
    print(f"Waktu analisis LLM      : {llm_duration:.2f} detik")
    print(f"Total waktu pipeline    : {total_duration:.2f} detik")

    print("\nEFISIENSI TOKEN")
    print("=" * 60)
    print(f"Total berita dari scraper        : {len(articles)}")
    print(f"Berita dikirim ke Gemini         : {len(articles_to_analyze)}")
    print(f"Berita tampil di output          : {len(final_results)}")

    if total_duration <= MAX_SECONDS:
        print("\nStatus: LOLOS standar di bawah 15 detik")
    else:
        print("\nStatus: BELUM LOLOS, masih di atas 15 detik")


if __name__ == "__main__":
    main()

