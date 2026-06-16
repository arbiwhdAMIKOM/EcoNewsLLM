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
    # TRUNCATION: Potong 800 karakter sudah sangat optimal untuk hemat token
    content = article.get("content", "")[:800]

    prompt = f"""
Kamu adalah Analis Intelijen Finansial Senior yang SANGAT KETAT, OBJEKTIF, dan TIDAK MUDAH TERTIPU.
Tugasmu mengekstrak data dari teks berita mentah menjadi format terstruktur.

--- ATURAN MUTLAK (ANTI-HALUSINASI) ---
1. JANGAN MEMAKSAKAN KONTEKS: Jika berita ini adalah politik murni, hukum, kriminal, artis, olahraga, atau hiburan TANPA menyebutkan dampak ekonomi/pasar secara eksplisit, KAMU WAJIB MENGISI:
   - main_category: "lainnya"
   - sentiment: "netral"
   - affected_markets: []
   - impact_score: 0
   - impact_level: "rendah"
   - impact_explanation: "Berita non-ekonomi, tidak ada dampak pasar keuangan yang terdeteksi."

2. JANGAN MENEBAK PASAR: Jangan pernah memasukkan IHSG, Emas, Rupiah, atau pasar lainnya ke dalam "affected_markets" JIKA TIDAK TERTULIS atau TERIMPLIKASI SANGAT KUAT di dalam teks. Jika ragu, kosongkan array [].

3. NO FINANCIAL ADVICE: Jangan memberi rekomendasi beli/jual/tahan, dan gunakan bahasa probabilitas ("berpotensi", "berpeluang"), bukan prediksi pasti.

--- TAKSONOMI (PILIHAN WAJIB) ---
main_category HANYA boleh dari:
{MAIN_CATEGORIES}

sentiment HANYA boleh dari:
{SENTIMENTS}

impact_level HANYA boleh dari:
{IMPACT_LEVELS}

affected_markets HANYA boleh dari:
{AFFECTED_MARKETS}

--- SKALA IMPACT SCORE ---
0 = Tidak ada kaitan dengan ekonomi/pasar sama sekali
1-3 = Rendah (Info ekonomi ringan, tidak menggerakkan pasar)
4-6 = Sedang (Berdampak pada satu sektor spesifik)
7-10 = Tinggi (Berdampak makro, mengubah tren nasional/global)

--- DATA BERITA ---
Judul: {title}
Sumber: {source}
Tanggal Publish: {published_at}
Isi Berita: {content}...

--- FORMAT OUTPUT (CHAIN OF THOUGHT) ---
Kembalikan HANYA JSON valid. Jangan pakai markdown ```json. 
PENTING: Pikirkan 'main_cause' dan 'impact_explanation' TERLEBIH DAHULU sebelum memberikan skor.

{{
  "summary": "Ringkasan padat maksimal 2 kalimat.",
  "main_cause": "Akar masalah atau pemicu utama dari berita ini.",
  "impact_explanation": "Argumen analisismu mengapa berita ini berdampak atau tidak berdampak.",
  "main_category": "satu pilihan dari taksonomi MAIN_CATEGORIES",
  "sentiment": "satu pilihan dari taksonomi SENTIMENTS",
  "affected_markets": ["daftar dari taksonomi AFFECTED_MARKETS, boleh [] jika tidak ada"],
  "impact_level": "satu pilihan dari taksonomi IMPACT_LEVELS",
  "impact_score": 0,
  "confidence_score": 0.9
}}
"""
    return prompt.strip()