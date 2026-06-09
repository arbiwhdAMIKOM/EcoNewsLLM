from src.scraper.py import fetch_news
from src.analyzer import analyze_articles


def main():
    print("Mengambil berita dari RSS/API...")
    articles = fetch_news()

    print(f"Total berita masuk: {len(articles)}")

    if not articles:
        print("Tidak ada berita yang berhasil diambil.")
        return

    print("Menganalisis berita dengan Gemini...")
    results = analyze_articles(articles)

    print("\nHASIL ANALISIS:")
    for item in results:
        print("=" * 60)
        print(f"Judul: {item.get('title')}")
        print(f"Kategori: {item.get('main_category')}")
        print(f"Sentimen: {item.get('sentiment')}")
        print(f"Dampak: {item.get('impact_level')}")
        print(f"Main Cause: {item.get('main_cause')}")
        print(f"Affected Markets: {item.get('affected_markets')}")
        print(f"Summary: {item.get('summary')}")


if __name__ == "__main__":
    main()