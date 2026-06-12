import re


def bersihkan_teks(teks):
    teks = re.sub(r'^[A-Za-z\s]+\s*\([A-Za-z]+\)\s*[-–]\s*', '', teks)
    teks = re.sub(r'Baca [jJ]uga:.*?(?=\n|$)', '', teks)
    teks = re.sub(r'\s+', ' ', teks).strip()
    return teks


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
]


NON_ECONOMIC_KEYWORDS = [
    "artis", "seleb", "film", "musik", "konser", "olahraga",
    "sepak bola", "viral", "gosip", "kriminal", "pembunuhan",
    "kecelakaan", "penjara", "dipenjara", "pidana", "putusan hakim",
    "sidang", "eks presiden",
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


def normalize_text(teks):
    teks = str(teks).lower()
    teks = bersihkan_teks(teks)
    teks = re.sub(r"\s+", " ", teks)
    return teks.strip()


def is_economic_news(article):
    title = article.get("title", "")
    content = article.get("content", "")
    source = article.get("source", "")

    text = normalize_text(f"{title} {content} {source}")

    for keyword in NON_ECONOMIC_KEYWORDS:
        if keyword in text:
            return False

    for keyword in ECONOMIC_KEYWORDS:
        if keyword in text:
            return True

    return False


def is_potentially_impactful_news(article):
    title = article.get("title", "")
    content = article.get("content", "")

    text = normalize_text(f"{title} {content}")

    # Skip berita ekonomi yang cuma edukatif/tips/penjelasan ringan
    for keyword in LOW_VALUE_KEYWORDS:
        if keyword in text:
            return False

    impact_score = 0

    for keyword in IMPACT_KEYWORDS:
        if keyword in text:
            impact_score += 1

    # Minimal punya 2 sinyal dampak biar layak masuk Gemini
    return impact_score >= 2


def filter_economic_articles(articles):
    economic_articles = []
    skipped_articles = []

    for article in articles:
        if is_economic_news(article):
            economic_articles.append(article)
        else:
            skipped_articles.append(article)

    return economic_articles, skipped_articles


def filter_potentially_impactful_articles(articles):
    impactful_articles = []
    low_value_articles = []

    for article in articles:
        if is_potentially_impactful_news(article):
            impactful_articles.append(article)
        else:
            low_value_articles.append(article)

    return impactful_articles, low_value_articles