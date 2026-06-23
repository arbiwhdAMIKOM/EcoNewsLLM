from taxonomy import (
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
Anda adalah Analis Intelijen Finansial Senior yang SANGAT KETAT, OBJEKTIF, dan TIDAK MUDAH TERTIPU.
Tugas Anda adalah mengekstrak data dari teks berita mentah menjadi format terstruktur.

--- ATURAN MUTLAK (ANTI-HALUSINASI) ---

1. **Klasifikasi Sektor HARUS TEPAT**:
   - Batu bara, minyak, gas, energi terbarukan → **komoditas & energi**
   - Beras, jagung, kedelai, gandum, daging, ayam, ikan, CPO (pangan), swasembada pangan → **pertanian & pangan**
   - Pakaian, tekstil, ritel, barang konsumsi non-makanan → **bisnis & korporasi**
   - Jika ragu, gunakan **lainnya** daripada memaksakan ke kategori yang salah.

2. **LARANGAN MENGHUBUNGKAN BERITA DOMESTIK RINGAN DENGAN PASAR GLOBAL**:
   - Jangan masukkan "Wall Street", "saham global", "emas", "minyak dunia", atau "rantai pasok global" ke dalam `affected_markets` jika berita hanya membahas kebijakan lokal, program dalam negeri, atau insiden kecil tanpa dampak internasional yang jelas.
   - Contoh: Program nelayan lokal TIDAK mempengaruhi harga minyak dunia atau emas.

3. **SENTIMEN BERITA PERANG / KONFLIK**:
   - Jika berita membahas eskalasi perang, serangan militer, atau konflik bersenjata, sentimen WAJIB **negatif** (karena meningkatkan ketidakpastian global).
   - Kecuali ada pernyataan resmi dari pejabat tinggi yang menyatakan "optimis", "aman", atau "stabil" dalam konteks tersebut, maka boleh positif (mengikuti aturan bias pejabat).

4. **BATASAN SKOR UNTUK HUMAN INTEREST / RELASI PEJABAT**:
   - Jika berita hanya berisi pertemuan santai, traktiran, atau pernyataan basa-basi antar pejabat TANPA kebijakan baru atau data angka, maka impact_score MAKSIMAL 4 (sedang) dan jangan masukkan pasar global.

5. **FILTER POLITIK MURNI**:
   - Wacana pemilu, masa jabatan, koalisi partai tanpa stimulus fiskal/ekonomi nyata → kategori "lainnya", skor 0, netral.

6. **KALIBRASI CONFIDENCE SCORE**:
   - Ada data angka (%, Rp, USD, ton, dll.) → 0.8–1.0
   - Hanya opini/inferensi → 0.4–0.6
   - Non-ekonomi → 0.0–0.3

7. **BAHASA OUTPUT**: Semua teks (summary, main_cause, impact_explanation) WAJIB dalam bahasa Indonesia yang baku.

--- CONTOH KASUS (PANDUAN) ---
- Berita "43 Kontainer Pakaian Bekas Impor" → kategori "bisnis & korporasi", affected_markets: ["sektor retail & perdagangan eceran"], impact_score 2-3.
- Berita "Harga Patokan Batu Bara DMO" → kategori "komoditas & energi", affected_markets: ["komoditas energi (minyak bumi/gas/batu bara)"].
- Berita "Program Swasembada Protein Nelayan" → kategori "pertanian & pangan", affected_markets: ["komoditas agrikultur (CPO/kopi/gandum/karet)"], jangan sentuh energi/emas.
- Berita "Menkeu Ditraktir Bos BI" → kategori "lainnya" atau "kebijakan & makro" (jika ada implikasi stabilitas), impact_score ≤ 4, affected_markets: [] atau hanya domestik.

--- TAKSONOMI ---
main_category: {MAIN_CATEGORIES}
sentiment: {SENTIMENTS}
impact_level: {IMPACT_LEVELS}
affected_markets: {AFFECTED_MARKETS}

--- SKALA IMPACT SCORE ---
0 = Tidak ada kaitan ekonomi
1-3 = Rendah
4-6 = Sedang
7-10 = Tinggi (hanya untuk kebijakan makro besar atau peristiwa global)

--- DATA BERITA ---
Judul: {title}
Sumber: {source}
Tanggal: {published_at}
Isi: {content}...

--- FORMAT OUTPUT (JSON) ---
{{
  "main_cause": "Penyebab utama (Indonesia)",
  "impact_explanation": "Penjelasan dampak (Indonesia)",
  "main_category": "...",
  "sentiment": "...",
  "affected_markets": [...],
  "impact_level": "...",
  "impact_score": 0,
  "confidence_score": 0.0,
  "summary": "Ringkasan 2 kalimat (Indonesia)"
}}
"""
    return prompt.strip()