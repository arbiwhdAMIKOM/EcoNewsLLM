import re
from typing import Tuple, List, Set

# --- KOMPILASI REGEX SEJAK AWAL (MENGHEMAT CPU & MEMORI) ---
# Menghapus prefiks lokasi media, contoh: "JAKARTA (AFP) -" atau "LONDON (Reuters) -"
RE_PREFIX = re.compile(r'^[A-Za-z\s]+\s*\([A-Za-z\s]+\)\s*[-–]\s*')
# Menghapus baris rekomendasi bacaan lain dari portal berita
RE_BACA_JUGA = re.compile(r'baca [jJ]uga:.*?(?=\n|$)', re.IGNORECASE)
# Membersihkan spasi ganda, baris baru, dan tab menjadi satu spasi tunggal
RE_SPACES = re.compile(r'\s+')
# Tokenisasi kata bersih (mengambil kata alfanumerik untuk exact matching)
RE_WORDS = re.compile(r'\b[a-z0-9\-]+\b')


def bersihkan_teks(teks: str) -> str:
    """
    Melakukan normalisasi teks awal dengan membuang sampah editor
    dan merapikan spasi sebelum dianalisis lebih lanjut.
    """
    if not teks:
        return ""
    teks = RE_PREFIX.sub('', teks)
    teks = RE_BACA_JUGA.sub('', teks)
    teks = RE_SPACES.sub(' ', teks).strip()
    return teks


# --- DAFTAR KATA KUNCI EKONOMI PRESISI TINGGI (EXACT MATCHING) ---
# Hanya mencocokkan kata utuh untuk menghindari kecocokan parsial yang salah
ECONOMIC_KEYWORDS_SINGLE: Set[str] = {
    "ihsg", "saham", "bursa", "emiten", "investor", "obligasi", "rupiah", "dolar", "usd", 
    "kurs", "valas", "inflasi", "deflasi", "bitcoin", "btc", "ethereum", "eth", "crypto", 
    "kripto", "emas", "xau", "minyak", "gas", "nikel", "tembaga", "cpo", "komoditas", "ekonomi", 
    "pdb", "ekspor", "impor", "pajak", "apbn", "subsidi", "investasi", "pma", "pmdn", 
    "laba", "rugi", "profit", "dividen", "ipo", "akuisisi", "merger", "bangkrut", "pailit",
    "fomc", "bonds", "brent", "wti", "rebound", "danantara", "deposito", "funding", "perbankan", 
    "finansial", "fiskal", "devisa", "treasury", "ekuitas", "manufaktur", "retail", "ritel",
    "perusahaan", "korporasi", "industri", "transportasi", "logistik", "properti", "konstruksi",
    "infrastruktur", "pertambangan", "psn", "psel"
}

# Kata kunci ekonomi yang berupa frasa (lebih dari satu kata) tetap menggunakan pencarian teks
ECONOMIC_KEYWORDS_MULTI: List[str] = [
    "reksa dana", "pasar modal", "wall street", "nasdaq", "dow jones", "mata uang", 
    "bank indonesia", "the fed", "suku bunga", "aset digital", "batu bara", "batubara", 
    "pertumbuhan ekonomi", "neraca perdagangan", "cadangan devisa", "gagal bayar", 
    "capital outflow", "capital inflow", "fed rate", "bi rate", "net buy", "net sell",
    "private placement", "rights issue", "proyek strategis nasional"
]


# --- DAFTAR HITAM BERITA NON-EKONOMI (HARD BLOCK) ---
# Berita hiburan, gaya hidup, olahraga, atau kriminalitas murni harus disingkirkan tanpa ampun
STRICT_NON_ECONOMIC_SINGLE: Set[str] = {
    "artis", "seleb", "selebritis", "film", "musik", "konser", "olahraga", "skandal",
    "gosip", "pembunuhan", "kecelakaan", "biodata", "pacar", "menikah", "liga", "klub",
    "perceraian", "sinopsis", "drama", "lagu", "piala", "juara", "atlet", "wasit", 
    "gaming", "game", "siber", "hacker", "pencurian", "perampokan", "bencana", "banjir", 
    "gempa", "cuaca", "kuliner", "resep", "wisata", "sidang", "kriminal", "penjara", 
    "dipenjara", "pidana", "putusan hakim", "eks presiden"
}


# --- KATA KUNCI PENYARING ARTIKEL EDUKASI / TIPS RINGKASAN (LOW VALUE) ---
LOW_VALUE_KEYWORDS_SINGLE: Set[str] = {
    "tips", "cara", "simak", "kenali", "panduan", "edukasi", "kamus", "istilah",
    "belajar", "mengenal", "rekomendasi", "pemula", "definisi", "pengertian",
    "apa bedanya", "daftar lengkap", "ini dia", "viral", "profil", "biodata", "sejarah"
}


# --- PEMICU REAKSI PASAR AKTIF (MARKET DRIVERS) ---
MARKET_DRIVERS_SINGLE: Set[str] = {
    "melemah", "menguat", "naik", "naikkan", "turun", "turunkan", "anjlok", "tertekan", 
    "merosot", "melonjak", "tumbuh", "melambat", "konflik", "perang", "geopolitik", "sanksi",
    "suspensi", "delisting", "borong", "rebutan", "diserbu", "longsor", "perkasa", "pangkas",
    "cetak", "rebound"
}


def prepare_article_tokens(article: dict) -> Tuple[str, Set[str]]:
    """
    Mempersiapkan teks artikel secara terpadu.
    Mengembalikan teks yang telah dibersihkan beserta set kata uniknya untuk dicocokkan.
    """
    title = article.get("title", "")
    content = article.get("content", "")[:800]  # Batasi panjang bacaan lokal demi efisiensi
    source = article.get("source", "")
    
    combined_clean = bersihkan_teks(f"{title} {content} {source}").lower()
    # Ekstraksi kata-kata utuh secara presisi menggunakan regex
    tokens = set(RE_WORDS.findall(combined_clean))
    
    return combined_clean, tokens


def analyze_and_filter_pipeline(articles: list) -> Tuple[list, list, list]:
    """
    Pipeline penyaringan berita satu langkah (single-pass) berkinerja tinggi.
    Memisahkan seluruh daftar artikel ke dalam 3 kategori secara akurat.
    """
    impactful_to_gemini = []
    low_impact_or_saved = []
    discarded_non_economic = []

    # Kata kunci mitigasi penyelamat berita ekonomi riil dari industri kreatif/bisnis
    savior_keywords = {"saham", "laba", "investasi", "akuisisi", "omset", "pendapatan", "obligasi", "emiten"}

    for article in articles:
        text, tokens = prepare_article_tokens(article)
        
        # 1. Penyaringan Berita Non-Ekonomi Ketat
        has_strict_non_economic = not tokens.isdisjoint(STRICT_NON_ECONOMIC_SINGLE)
        has_savior = not tokens.isdisjoint(savior_keywords)

        # Jika mengandung kata non-ekonomi DAN tidak terselamatkan oleh aksi bisnis utama -> Buang
        if has_strict_non_economic and not has_savior:
            discarded_non_economic.append(article)
            continue

        # 2. Cek Relevansi Ekonomi Riil Secara Presisi
        has_economic_single = not tokens.isdisjoint(ECONOMIC_KEYWORDS_SINGLE)
        has_economic_multi = any(kw in text for kw in ECONOMIC_KEYWORDS_MULTI)
        
        if not (has_economic_single or has_economic_multi):
            discarded_non_economic.append(article)
            continue

        # 3. Filter Artikel Rendah Nilai Informasi (Artikel Edukasi/Tips Ringan)
        has_low_value = not tokens.isdisjoint(LOW_VALUE_KEYWORDS_SINGLE)
        if has_low_value:
            low_impact_or_saved.append(article)
            continue

        # 4. Filter Kekuatan Reaksi Pasar (Aset Kuat + Penggerak Aktif)
        # Menilai apakah ada nama instrumen pasar keuangan aktif dalam berita
        financial_assets_single = {
            "ihsg", "saham", "rupiah", "dolar", "usd", "kurs", "bitcoin", "btc", 
            "ethereum", "eth", "emas", "xau", "minyak", "inflasi", "bonds", "obligasi",
            "danantara", "emiten", "laba", "dividen"
        }
        
        financial_assets_multi = ["suku bunga", "net buy", "private placement"]
        
        has_asset_single = not tokens.isdisjoint(financial_assets_single)
        has_asset_multi = any(kw in text for kw in financial_assets_multi)
        
        has_asset = has_asset_single or has_asset_multi
        has_driver = not tokens.isdisjoint(MARKET_DRIVERS_SINGLE)

        # Lolos ke pipeline LLM Gemini hanya jika ada subjek aset ekonomi sekaligus predikat aksi/gejolak pasar
        if has_asset and has_driver:
            impactful_to_gemini.append(article)
        else:
            low_impact_or_saved.append(article)

    return impactful_to_gemini, low_impact_or_saved, discarded_non_economic