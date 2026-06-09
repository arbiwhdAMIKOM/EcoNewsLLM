import time
from src.analyzer import analyze_article


sample_article = {
    "title": "IHSG Melemah karena Investor Melakukan Aksi Ambil Untung",
    "source": "Contoh Market News",
    "published_at": "2026-06-06",
    "url": "https://contoh.com/ihsg-profit-taking",
    "content": (
        "IHSG melemah setelah sejumlah investor melakukan aksi ambil untung "
        "pada saham-saham perbankan dan teknologi. Pelaku pasar juga masih "
        "menunggu rilis data inflasi terbaru yang dapat memengaruhi arah "
        "kebijakan suku bunga."
    ),
}


if __name__ == "__main__":
    start_time = time.time()

    result = analyze_article(sample_article)

    end_time = time.time()
    duration = end_time - start_time

    print("\nHASIL ANALISIS LLM")
    print("=" * 50)

    print(f"Judul: {result.get('title')}")
    print(f"Sumber: {result.get('source')}")
    print(f"Tanggal: {result.get('published_at')}")
    print("-" * 50)

    print(f"Summary: {result.get('summary')}")
    print(f"Main Category: {result.get('main_category')}")
    print(f"Sentiment: {result.get('sentiment')}")
    print(f"Impact Level: {result.get('impact_level')}")
    print(f"Impact Score: {result.get('impact_score')}")
    print(f"Main Cause: {result.get('main_cause')}")
    print(f"Affected Markets: {result.get('affected_markets')}")
    print(f"Impact Explanation: {result.get('impact_explanation')}")
    print(f"Confidence Score: {result.get('confidence_score')}")

    print("=" * 50)
    print(f"Waktu eksekusi: {duration:.2f} detik")

    if duration <= 15:
        print("Status: Lolos target di bawah 15 detik")
    else:
        print("Status: Belum lolos, proses masih di atas 15 detik")