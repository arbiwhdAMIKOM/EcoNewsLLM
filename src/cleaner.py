import re

# --- Fungsi pembersihan teks ---
def bersihkan_teks(teks):
    teks = re.sub(r'^[A-Za-z\s]+\s*\([A-Za-z]+\)\s*[-–]\s*', '', teks)
    teks = re.sub(r'Baca [jJ]uga:.*?(?=\n|$)', '', teks)
    teks = re.sub(r'\s+', ' ', teks).strip()
    return teks

# --- Daftar kata kunci (diperluas) ---
ECONOMIC_KEYWORDS = [
    "ihsg", "saham", "bursa", "emiten", "investor", "obligasi",
    "reksa dana", "pasar modal", "wall street", "nasdaq", "dow jones",
    "rupiah", "dolar", "usd", "kurs", "valas", "mata uang",
    "bank indonesia", "the fed", "suku bunga", "inflasi", "deflasi",
    "bitcoin", "btc", "ethereum", "eth", "crypto", "kripto", "aset digital",
    "emas", "gold", "xau", "minyak", "gas", "batu bara", "batubara",
    "nikel", "tembaga", "cpo", "komoditas",
    "ekonomi", "pdb", "pertumbuhan ekonomi", "ekspor", "impor",
    "neraca perdagangan", "cadangan devisa", "pajak", "apbn",
    "subsidi", "investasi", "pma", "pmdn",
    "laba", "rugi", "pendapatan", "revenue", "profit", "dividen",
    "ipo", "akuisisi", "merger", "startup", "umkm", "industri",
    "manufaktur", "retail", "ritel", "perbankan", "bank",
    "energi", "transportasi", "logistik", "properti", "konstruksi",
    "infrastruktur", "pertambangan", "psn", "psel",
    # tambahan untuk pangan
    "pangan", "beras", "kedelai", "jagung", "gandum", "ayam", "sapi", "protein",
    "swasembada", "pangan", "pertanian", "peternakan", "perikanan",
]

NON_ECONOMIC_KEYWORDS = [
    "artis", "seleb", "film", "musik", "konser", "olahraga",
    "sepak bola", "viral", "gosip", "kriminal", "pembunuhan",
    "kecelakaan", "penjara", "dipenjara", "pidana", "putusan hakim",
    "sidang", "eks presiden",
]

POLITICAL_PURE_KEYWORDS = [
    "pemilu", "pilpres", "pileg", "pilkada", "masa jabatan", "2 periode",
    "periode kedua", "koalisi", "partai", "parpol", "kudeta", "konflik politik",
    "wacana presiden", "amandemen", "presiden 3 periode",
]

FISCAL_KEYWORDS = [
    "stimulus", "subsidi", "pajak", "apbn", "belanja", "anggaran",
    "defisit", "utang", "pinjaman", "kucuran dana", "bantuan sosial",
    "program", "proyek", "infrastruktur", "psn",
]

IMPACT_KEYWORDS = [
    "melemah", "menguat", "naik", "turun", "anjlok", "tertekan",
    "rebound", "merosot", "melonjak", "tumbuh", "melambat",
    "inflasi", "suku bunga", "the fed", "bank indonesia", "bi rate",
    "rupiah", "dolar", "usd", "kurs",
    "ihsg", "saham", "bursa", "wall street", "nasdaq", "dow jones",
    "investor", "asing", "capital outflow", "capital inflow",
    "minyak", "emas", "xau", "batu bara", "batubara", "nikel",
    "komoditas", "energi",
    "bitcoin", "btc", "ethereum", "eth", "crypto", "kripto",
    "ekspor", "impor", "neraca perdagangan", "pdb",
    "cadangan devisa", "apbn", "pajak", "subsidi",
    "konflik", "perang", "geopolitik", "sanksi",
    "rusia", "ukraina", "iran", "israel", "timur tengah",
    "laba", "rugi", "pendapatan", "dividen", "ipo", "akuisisi",
    "merger", "bangkrut", "pailit",
]

LOW_VALUE_KEYWORDS = [
    "tips", "cara", "simak", "kenali", "apa bedanya", "daftar lengkap",
    "ini dia", "viral", "profil", "biodata", "sejarah", "pengertian",
]

# --- Normalisasi ---
def normalize_text(teks):
    teks = str(teks).lower()
    teks = bersihkan_teks(teks)
    teks = re.sub(r"\s+", " ", teks)
    return teks.strip()

def normalize_title(title):
    """Normalisasi judul untuk deduplikasi."""
    t = str(title).lower()
    t = re.sub(r'[^a-z0-9]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def deduplicate_articles(articles):
    """Hapus artikel dengan judul yang sama (case-insensitive, normalized)."""
    seen = set()
    unique = []
    for art in articles:
        norm = normalize_title(art.get('title', ''))
        if norm and norm not in seen:
            seen.add(norm)
            unique.append(art)
    return unique

# --- Fungsi filter ---
def is_economic_news(article):
    title = article.get("title", "")
    content = article.get("content", "")
    source = article.get("source", "")
    text = normalize_text(f"{title} {content} {source}")

    # Deteksi non-ekonomi kuat
    for keyword in NON_ECONOMIC_KEYWORDS:
        if keyword in text:
            return False

    # Deteksi politik murni (tanpa fiskal)
    has_political = any(kw in text for kw in POLITICAL_PURE_KEYWORDS)
    has_fiscal = any(kw in text for kw in FISCAL_KEYWORDS)
    if has_political and not has_fiscal:
        return False

    # Cek kata kunci ekonomi
    for keyword in ECONOMIC_KEYWORDS:
        if keyword in text:
            return True

    return False

def is_potentially_impactful_news(article):
    title = article.get("title", "")
    content = article.get("content", "")
    text = normalize_text(f"{title} {content}")

    # Lewati berita ringan (tips, edukasi)
    for kw in LOW_VALUE_KEYWORDS:
        if kw in text:
            return False

    impact_score = 0

    # Bobot lebih untuk kata kunci kuat (geopolitik, energi, makro)
    strong_keywords = [
        "perang", "konflik", "geopolitik", "sanksi", "iran", "israel", "rusia", "ukraina",
        "opec", "minyak", "gas", "batu bara", "energi", "emas", "xau",
        "suku bunga", "the fed", "bi rate", "inflasi", "resesi",
        "pertumbuhan ekonomi", "pdb", "ekspor", "impor", "neraca perdagangan",
        "ihsg", "saham", "wall street", "nasdaq", "dow jones",
        "swasembada", "protein", "pangan", "pertanian", "peternakan"   # tambahan pangan
    ]
    for kw in strong_keywords:
        if kw in text:
            impact_score += 2

    # Kata kunci umum dari IMPACT_KEYWORDS
    for kw in IMPACT_KEYWORDS:
        if kw in text:
            impact_score += 1

    # Bonus data numerik
    if re.search(r'\d+[.,]?\d*\%?', text):
        impact_score += 2

    # Penalti politik murni
    has_political = any(kw in text for kw in POLITICAL_PURE_KEYWORDS)
    has_fiscal = any(kw in text for kw in FISCAL_KEYWORDS)
    if has_political and not has_fiscal:
        impact_score = 0

    # Threshold 4 agar lolos untuk berita geopolitik penting
    return impact_score >= 4

def filter_economic_articles(articles):
    economic = []
    skipped = []
    for art in articles:
        if is_economic_news(art):
            economic.append(art)
        else:
            skipped.append(art)
    return economic, skipped

def filter_potentially_impactful_articles(articles):
    impactful = []
    low_value = []
    for art in articles:
        if is_potentially_impactful_news(art):
            impactful.append(art)
        else:
            low_value.append(art)
    return impactful, low_value

# --- Pipeline utama ---
def analyze_and_filter_pipeline(articles):
    # 1. Deduplikasi
    articles = deduplicate_articles(articles)
    # 2. Filter ekonomi vs non-ekonomi
    economic_articles, non_economic_articles = filter_economic_articles(articles)
    # 3. Filter berdampak vs low-value
    impactful_articles, low_value_articles = filter_potentially_impactful_articles(economic_articles)
    return impactful_articles, low_value_articles, non_economic_articles