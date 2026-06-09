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
    content = article.get("content", "")[:1000]

    prompt = f"""
Kamu adalah analis berita ekonomi dan pasar keuangan senior yang bertugas melakukan ekstraksi data teks menjadi format JSON terstruktur yang valid.

Analisis berita di bawah ini dengan mengikuti instruksi, aturan, dan batasan taksonomi yang telah ditentukan.

--- TAKSONOMI PILIHAN ---
Pilih nilai untuk 'main_category' hanya dari daftar ini:
{MAIN_CATEGORIES}

Pilih nilai untuk 'sentiment' hanya dari daftar ini:
{SENTIMENTS}

Pilih nilai untuk 'impact_level' hanya dari daftar ini:
{IMPACT_LEVELS}

Pilih nilai untuk 'affected_markets' bisa lebih dari satu dalam bentuk array, tetapi hanya dari daftar ini:
{AFFECTED_MARKETS}

--- ATURAN ANALISIS & KONTEN ---
1. Ringkasan berita ('summary') maksimal berisi 2 kalimat yang padat informasi.
2. Jangan memberikan rekomendasi beli, jual, atau tahan terhadap instrumen apa pun.
3. Jangan membuat prediksi masa depan yang bersifat pasti atau absolut.
4. Gunakan kata-kata berbasis probabilitas seperti "berpotensi", "kemungkinan", "berpeluang", atau "dapat memengaruhi".
5. Jika berita kurang jelas, di luar topik, atau tidak berdampak signifikan pada ekonomi, gunakan:
   - main_category: "lainnya"
   - sentiment: "netral"
   - impact_level: "rendah"
6. Tentukan 'impact_score' dengan nilai integer dari 0 sampai 10:
   - 0 sampai 3 = rendah
   - 4 sampai 6 = sedang
   - 7 sampai 10 = tinggi
7. Field 'main_cause' harus berupa frasa singkat yang spesifik dan kontekstual berdasarkan isi berita.
8. Field 'main_cause' tidak boleh memakai label umum seperti "inflasi", "suku bunga", atau "geopolitik" saja.
9. Contoh main_cause yang baik:
   - "Aksi profit taking investor"
   - "Eskalasi konflik di Timur Tengah"
   - "Ekspektasi suku bunga tinggi The Fed"
   - "Pelemahan permintaan global"
   - "Kenaikan harga minyak mentah"
10. Pada field 'impact_explanation', jelaskan kemungkinan dampak berita terhadap pasar/sektor yang terdampak, bukan prediksi pasti.
11. Pada field 'confidence_score', isi angka desimal 0 sampai 1 untuk menunjukkan tingkat keyakinan analisis.

--- DATA BERITA ---
Judul: {title}
Sumber: {source}
Tanggal Publish: {published_at}
Isi Berita: {content}

--- FORMAT OUTPUT ---
Kembalikan hasil analisis HANYA dalam format JSON valid.
Jangan tambahkan teks penjelasan, markdown, atau tanda ```json.

{{
  "summary": "Ringkasan berita maksimal 2 kalimat",
  "main_category": "Isi dengan satu pilihan dari MAIN_CATEGORIES",
  "sentiment": "Isi dengan satu pilihan dari SENTIMENTS",
  "impact_level": "Isi dengan satu pilihan dari IMPACT_LEVELS",
  "impact_score": 0,
  "main_cause": "Frasa singkat penyebab utama yang spesifik dan kontekstual",
  "affected_markets": ["Pilihan 1 dari AFFECTED_MARKETS", "Pilihan 2 dari AFFECTED_MARKETS"],
  "impact_explanation": "Penjelasan kemungkinan dampak berita terhadap pasar atau sektor yang terdampak",
  "confidence_score": 0.0
}}
"""
    return prompt.strip()
