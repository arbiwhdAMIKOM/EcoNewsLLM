from src.taxonomy import (
    MAIN_CATEGORIES,
    SENTIMENTS,
    IMPACT_LEVELS,
    AFFECTED_MARKETS,
)


def build_news_analysis_prompt(article: dict) -> str:
    title = article.get("title", "")
    source = article.get("source", "")
    published_at = article.get("published_at", "")
    content = article.get("content", "")[:800]

    prompt = f"""
Kamu adalah analis berita ekonomi dan pasar keuangan.

Analisis HANYA jika berita memiliki hubungan langsung dengan ekonomi, bisnis, pasar modal, forex, crypto, komoditas, energi, perbankan, investasi, kebijakan fiskal/moneter, inflasi, perdagangan, industri, infrastruktur, atau pasar keuangan.

Jangan memaksakan berita umum menjadi berita ekonomi.

--- ATURAN UTAMA ---
1. Jika berita tidak relevan langsung dengan ekonomi/pasar, isi:
   - main_category: "lainnya"
   - sentiment: "netral"
   - impact_level: "rendah"
   - impact_score: 0
   - affected_markets: []
   - main_cause: "Tidak relevan langsung dengan ekonomi atau pasar keuangan"
   - impact_explanation: "Berita ini tidak dianalisis lebih lanjut karena tidak memiliki hubungan langsung dengan ekonomi, bisnis, pasar keuangan, komoditas, atau kebijakan makro."

2. Jangan mengaitkan berita non-ekonomi ke IHSG, arus modal asing, rupiah, emas, minyak, atau pasar lain jika tidak disebutkan jelas.

3. Berita politik, hukum, kriminal, artis, olahraga, hiburan, atau berita umum hanya boleh dianalisis jika isi berita menyebut dampak ekonomi/pasar secara eksplisit.

4. Fokus pada berita yang berdampak sedang sampai tinggi.
   Jika dampak ekonomi sangat kecil atau hanya informasi ringan, gunakan:
   - impact_level: "rendah"
   - impact_score: 0 sampai 3
   - affected_markets: []

5. Jangan memberi rekomendasi beli, jual, atau tahan.
6. Jangan membuat prediksi pasti.
7. Gunakan kata "berpotensi", "kemungkinan", "dapat memengaruhi", atau "berpeluang".
8. Ringkasan maksimal 2 kalimat.
9. main_cause harus spesifik dan sesuai isi berita.
10. affected_markets boleh kosong [] jika dampak pasar tidak jelas.

--- TAKSONOMI ---
main_category hanya boleh dari:
{MAIN_CATEGORIES}

sentiment hanya boleh dari:
{SENTIMENTS}

impact_level hanya boleh dari:
{IMPACT_LEVELS}

affected_markets hanya boleh dari:
{AFFECTED_MARKETS}

--- SKALA IMPACT SCORE ---
0 = tidak relevan / tidak ada dampak ekonomi jelas
1-3 = rendah
4-6 = sedang
7-10 = tinggi

--- DATA BERITA ---
Judul: {title}
Sumber: {source}
Tanggal Publish: {published_at}
Isi Berita: {content}

--- FORMAT OUTPUT ---
Kembalikan HANYA JSON valid. Jangan pakai markdown. Jangan pakai ```json.

{{
  "summary": "Ringkasan maksimal 2 kalimat",
  "main_category": "satu pilihan dari MAIN_CATEGORIES",
  "sentiment": "satu pilihan dari SENTIMENTS",
  "impact_level": "satu pilihan dari IMPACT_LEVELS",
  "impact_score": 0,
  "main_cause": "Penyebab utama yang spesifik",
  "affected_markets": [],
  "impact_explanation": "Penjelasan kemungkinan dampak atau alasan tidak relevan",
  "confidence_score": 0.0
}}
"""
    return prompt.strip()

