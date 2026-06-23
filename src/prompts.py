"""
prompts.py  —  EcoNews LLM  (v4)
Perubahan dari v3:
  - Tambah instruksi "MATRIX ANTI-HALUSINASI KOMODITAS": whitelist berbasis kategori.
    Komoditas energi/logam mulia HANYA boleh muncul jika main_category = komoditas & energi
    atau geopolitik & perang (via jalur transmisi minyak/emas global).
  - Batas affected_markets: maks 3 (bukan 2) — tetap ketat tapi tidak memotong
    berita makro multi-pasar yang legitimate (contoh: BI Rate → rupiah + obligasi + arus modal)
  - Tambah contoh negatif eksplisit untuk berita agrikultur/kebijakan domestik
    agar Gemini tidak "mengarang" jalur transmisi ke emas/energi
"""


def build_news_analysis_prompt(article: dict) -> str:
    title    = article.get("title", "")
    source   = article.get("source", "")
    pub_date = article.get("published_at", "")
    content  = article.get("content", "")[:600]

    prompt = f"""Kamu adalah sistem klasifikasi berita keuangan otomatis. Labeli berita berikut secara cepat dan objektif.

## ATURAN SENTIMEN — ISOLASI DOMESTIK VS GLOBAL
Nilai sentimen berdasarkan DAMPAK LANGSUNG ke pasar/ekonomi Indonesia saja:
- "positif" → ada indikator domestik membaik (IHSG naik, Rupiah menguat, data ekonomi RI bagus)
- "negatif" → ada indikator domestik memburuk (IHSG turun, Rupiah melemah, PHK massal di RI)
- "netral"  → dampak ke Indonesia tidak eksplisit, atau berita murni informatif
PENTING: Berita geopolitik/ekonomi global hanya ubah sentimen ke negatif jika ada kalimat eksplisit dampak ke Indonesia. "Wall Street turun" saja = NETRAL untuk Indonesia.

## MATRIX ANTI-HALUSINASI KOMODITAS (WAJIB DIIKUTI)
Komoditas energi (minyak/gas/batu bara) dan logam mulia (emas/perak) adalah pasar GLOBAL.
Harga mereka diset oleh dinamika internasional — BUKAN kebijakan domestik Indonesia.

ATURAN KETAT:
- "komoditas energi" dan "komoditas logam mulia" HANYA boleh masuk affected_markets jika:
  (a) main_category = "komoditas & energi", ATAU
  (b) main_category = "geopolitik & perang" DAN teks menyebut minyak/emas secara eksplisit
- Untuk semua kategori lain (kebijakan & makro, bisnis & korporasi, ekonomi global, dll):
  DILARANG memasukkan komoditas energi atau logam mulia ke affected_markets

CONTOH KESALAHAN FATAL (JANGAN DILAKUKAN):
✗ Berita "cetak sawah 1 juta hektar" → affected_markets: ["komoditas logam mulia", "komoditas energi"]
  (Sawah tidak punya jalur transmisi ke harga emas atau batu bara global)
✗ Berita "program makan bergizi gratis" → affected_markets: ["komoditas energi"]
  (Program gizi sekolah tidak menggerakkan harga minyak)
✗ Berita "kebijakan transmigrasi" → affected_markets: ["komoditas logam mulia"]
  (Perpindahan penduduk tidak memengaruhi harga emas global)

CONTOH BENAR:
✓ Berita "OPEC potong produksi minyak" → affected_markets: ["komoditas energi (minyak bumi/gas/batu bara)"]
✓ Berita "konflik Iran-Israel eskalasi" → affected_markets: ["komoditas logam mulia", "komoditas energi"]
✓ Berita "sawah/pertanian/pangan" → affected_markets: ["komoditas agrikultur (CPO/kopi/gandum/karet)", "daya beli & konsumsi masyarakat"]

## BATAS AFFECTED_MARKETS
Pilih MAKSIMAL 3 pasar yang paling langsung terdampak.
Prioritaskan pasar yang TERSEBUT EKSPLISIT dalam teks. Jika ragu, kosongkan [].

## ATURAN ANTI-HALUSINASI UMUM
- Berita politik murni (pernyataan tokoh, opini pemilu, isu jabatan) → main_category="lainnya", impact_score=0, affected_markets=[]
- Berita bukan ekonomi/bisnis/keuangan → main_category="lainnya", impact_score=0, affected_markets=[]
- impact_score 7-10 HANYA untuk peristiwa makro sistemik (keputusan BI Rate, resesi, krisis keuangan)
- summary: maks 2 kalimat ringkas
- main_cause: 1 frasa spesifik (contoh: "Stimulus fiskal Rp26T pemerintah", "Keputusan BI Rate naik 25bps")

## SKALA IMPACT SCORE
0   = Tidak ada kaitan ekonomi / berita politik murni
1-3 = Info ringan, tidak langsung menggerakkan pasar
4-6 = Dampak nyata pada satu sektor spesifik
7-10 = Dampak makro sistemik, mengubah tren nasional/global

## RUBRIK CONFIDENCE SCORE
0.9-1.0 = Teks sangat eksplisit: ada angka, nama instrumen, arah pergerakan jelas
0.7-0.8 = Cukup jelas tapi ada 1-2 ambiguitas minor (misal: tidak ada angka spesifik)
0.5-0.6 = Teks ambigu atau berita terlalu singkat
0.3-0.4 = Inferensi tinggi, hampir menebak
0.0-0.2 = Tidak ada informasi ekonomi yang dapat diandalkan

## DATA BERITA
Judul  : {title}
Sumber : {source}
Tanggal: {pub_date}
Konten : {content}"""

    return prompt.strip()