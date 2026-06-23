"""
cleaner.py  —  EcoNews LLM  (v4)
Perubahan dari v3:

1. TAMBAH POLITIK_OPINI_KEYWORDS_SINGLE & _MULTI (blacklist baru)
   Menangkap berita politik seremonial/opini jabatan yang lolos sensor sebelumnya:
   - Frasa single: "pemilu", "pilkada", "pilpres", "koalisi", "oposisi", dll
   - Frasa multi-kata: "2 periode", "komentari isu", "maju lagi", "pencalonan", dll
   Berita yang match blacklist ini langsung ke discarded_non_economic KECUALI
   ada savior keyword ekonomi yang kuat (akuisisi, obligasi, dll).

2. TAMBAH COMMODITY_OVER_TAG_GUARD di post-filter
   Setelah artikel lolos ke impactful_to_gemini, tambahkan flag
   `_suspected_non_commodity` jika artikel BUKAN tentang komoditas tapi
   mengandung kata komoditas secara insidental (contoh: "cetak sawah" → tidak
   punya "minyak", "opec", "tambang", "harga emas" → flag dikirim ke Gemini
   sebagai context hint di article metadata).
   Analyzer akan meneruskan flag ini ke prompt sebagai peringatan tambahan.

3. Memperluas MARKET_DRIVERS_SINGLE dengan kata kerja kebijakan yang selama ini
   menyebabkan berita stimulus/fiskal ter-flag sebagai "tidak ada driver":
   sudah dilakukan di v3, dipertahankan di sini.
"""

import re
from typing import Tuple, List, Set

RE_PREFIX    = re.compile(r'^[A-Za-z\s]+\s*\([A-Za-z\s]+\)\s*[-–]\s*')
RE_BACA_JUGA = re.compile(r'baca [jJ]uga:.*?(?=\n|$)', re.IGNORECASE)
RE_SPACES    = re.compile(r'\s+')
RE_WORDS     = re.compile(r'\b[a-z0-9\-]+\b')


def bersihkan_teks(teks: str) -> str:
    if not teks:
        return ""
    teks = RE_PREFIX.sub('', teks)
    teks = RE_BACA_JUGA.sub('', teks)
    teks = RE_SPACES.sub(' ', teks).strip()
    return teks


# ── KATA KUNCI EKONOMI ────────────────────────────────────────────────────────
ECONOMIC_KEYWORDS_SINGLE: Set[str] = {
    "ihsg", "saham", "bursa", "emiten", "investor", "obligasi", "rupiah", "dolar", "usd",
    "kurs", "valas", "inflasi", "deflasi", "bitcoin", "btc", "ethereum", "eth", "crypto",
    "kripto", "emas", "xau", "minyak", "gas", "nikel", "tembaga", "cpo", "komoditas", "ekonomi",
    "pdb", "ekspor", "impor", "pajak", "apbn", "subsidi", "investasi", "pma", "pmdn",
    "laba", "rugi", "profit", "dividen", "ipo", "akuisisi", "merger", "bangkrut", "pailit",
    "fomc", "bonds", "brent", "wti", "rebound", "danantara", "deposito", "funding", "perbankan",
    "finansial", "fiskal", "devisa", "treasury", "ekuitas", "manufaktur", "retail", "ritel",
    "perusahaan", "korporasi", "industri", "transportasi", "logistik", "properti", "konstruksi",
    "infrastruktur", "pertambangan", "psn", "psel", "stimulus", "anggaran", "belanja",
    "pendapatan", "penerimaan", "defisit", "surplus", "utang", "sbn", "sukuk",
}

ECONOMIC_KEYWORDS_MULTI: List[str] = [
    "reksa dana", "pasar modal", "wall street", "nasdaq", "dow jones", "mata uang",
    "bank indonesia", "the fed", "suku bunga", "aset digital", "batu bara", "batubara",
    "pertumbuhan ekonomi", "neraca perdagangan", "cadangan devisa", "gagal bayar",
    "capital outflow", "capital inflow", "fed rate", "bi rate", "net buy", "net sell",
    "private placement", "rights issue", "proyek strategis nasional",
    "kebijakan fiskal", "kebijakan moneter", "stimulus fiskal", "paket stimulus",
    "pemotongan anggaran", "pemangkasan anggaran", "efisiensi anggaran",
]

# ── POLICY BYPASS — kebijakan/fiskal langsung ke Gemini tanpa syarat driver ───
POLICY_BYPASS_SINGLE: Set[str] = {
    "apbn", "fiskal", "stimulus", "anggaran", "defisit", "surplus",
    "subsidi", "pajak", "sbn", "sukuk", "obligasi", "penerimaan",
    "belanja", "utang", "pmdn", "pma",
}

POLICY_BYPASS_MULTI: List[str] = [
    "bi rate", "suku bunga", "kebijakan moneter", "kebijakan fiskal",
    "stimulus fiskal", "paket stimulus", "pemangkasan anggaran",
    "pemotongan anggaran", "efisiensi anggaran", "bank indonesia",
    "the fed", "proyek strategis nasional", "dana desa", "transfer daerah",
]

# ── BLACKLIST NON-EKONOMI KERAS ───────────────────────────────────────────────
STRICT_NON_ECONOMIC_SINGLE: Set[str] = {
    "artis", "seleb", "selebritis", "film", "musik", "konser", "olahraga", "skandal",
    "gosip", "pembunuhan", "kecelakaan", "biodata", "pacar", "menikah", "liga", "klub",
    "perceraian", "sinopsis", "drama", "lagu", "piala", "juara", "atlet", "wasit",
    "gaming", "game", "siber", "hacker", "pencurian", "perampokan", "bencana", "banjir",
    "gempa", "cuaca", "kuliner", "resep", "wisata", "sidang", "kriminal", "penjara",
    "dipenjara", "pidana", "putusan hakim", "eks presiden",
}

# ── BLACKLIST POLITIK OPINI/SEREMONIAL (BARU di v4) ──────────────────────────
# Berita pernyataan tokoh, spekulasi jabatan, dan opini pemilu tidak punya
# nilai ekonomi — buang sebelum memakan token LLM.
POLITIK_OPINI_SINGLE: Set[str] = {
    "pemilu", "pilkada", "pilpres", "koalisi", "oposisi", "partai",
    "capres", "cawapres", "calon", "kampanye", "politikus", "legislatif",
    "parlemen", "dpr", "dprd", "mpr", "fraksi", "parpol",
}

POLITIK_OPINI_MULTI: List[str] = [
    "2 periode", "dua periode", "komentari isu", "maju lagi", "pencalonan",
    "isu jabatan", "reshuffle kabinet", "pernyataan politik", "obrolan politik",
    "opini pemilu", "suara partai", "elektabilitas", "survei politik",
    "masa jabatan", "perpanjangan jabatan", "presiden 3 periode",
]

# Savior: jika ada kata bisnis/ekonomi kuat, berita politik bisa lolos
# (contoh: berita "reshuffle kabinet + menteri keuangan baru" → ada dampak ekonomi)
POLITIK_ECONOMIC_SAVIOR: Set[str] = {
    "anggaran", "apbn", "fiskal", "investasi", "obligasi", "pasar", "ihsg",
    "rupiah", "ekonomi", "bank", "menteri keuangan", "menkeu", "bapenas",
}

# ── BLACKLIST RENDAH NILAI ────────────────────────────────────────────────────
LOW_VALUE_KEYWORDS_SINGLE: Set[str] = {
    "tips", "cara", "simak", "kenali", "panduan", "edukasi", "kamus", "istilah",
    "belajar", "mengenal", "rekomendasi", "pemula", "definisi", "pengertian",
    "apa bedanya", "daftar lengkap", "ini dia", "viral", "profil", "biodata", "sejarah",
}

# ── MARKET DRIVERS ────────────────────────────────────────────────────────────
MARKET_DRIVERS_SINGLE: Set[str] = {
    "melemah", "menguat", "naik", "naikkan", "turun", "turunkan", "anjlok", "tertekan",
    "merosot", "melonjak", "tumbuh", "melambat", "konflik", "perang", "geopolitik", "sanksi",
    "suspensi", "delisting", "borong", "rebutan", "diserbu", "longsor", "perkasa", "pangkas",
    "cetak", "rebound", "gelontorkan", "kucurkan", "alokasikan", "tetapkan", "putuskan",
    "potong", "tambah", "kurangi", "revisi", "rilis", "umumkan",
}

# ── COMMODITY CONTEXT SIGNALS — untuk flag anti-over-tagging ─────────────────
# Jika artikel TIDAK mengandung sinyal ini, maka hampir pasti bukan berita
# komoditas murni → Gemini diberi warning via metadata artikel
COMMODITY_CONTEXT_SIGNALS: Set[str] = {
    "minyak", "opec", "brent", "wti", "tambang", "pertambangan", "ore",
    "harga emas", "xau", "gold", "perak", "silver", "nikel", "tembaga",
    "batu bara", "batubara", "lng", "lpg", "kilang", "eksplorasi",
}


def prepare_article_tokens(article: dict) -> Tuple[str, Set[str]]:
    title   = article.get("title", "")
    content = article.get("content", "")[:800]
    source  = article.get("source", "")
    combined_clean = bersihkan_teks(f"{title} {content} {source}").lower()
    tokens = set(RE_WORDS.findall(combined_clean))
    return combined_clean, tokens


def analyze_and_filter_pipeline(articles: list) -> Tuple[list, list, list]:
    """
    Pipeline penyaringan satu-langkah (single-pass).
    Mengembalikan (impactful_to_gemini, low_impact_or_saved, discarded_non_economic).

    Alur keputusan:
      1. Hard-block non-ekonomi (hiburan, kriminal, olahraga)
      2. Hard-block politik opini/seremonial (BARU v4) — kecuali ada savior ekonomi kuat
      3. Cek relevansi ekonomi minimal
      4. Skip artikel edukasi/tips rendah nilai
      5a. Policy bypass → langsung Gemini
      5b. Market driver (aset + kata kerja) → Gemini
      5c. Sisanya → low_impact_or_saved
      6. Flag artikel non-komoditas (BARU v4) sebagai hint ke Gemini
    """
    impactful_to_gemini    = []
    low_impact_or_saved    = []
    discarded_non_economic = []

    savior_keywords = {
        "saham", "laba", "investasi", "akuisisi", "omset", "pendapatan", "obligasi", "emiten",
    }

    financial_assets_single: Set[str] = {
        "ihsg", "saham", "rupiah", "dolar", "usd", "kurs", "bitcoin", "btc",
        "ethereum", "eth", "emas", "xau", "minyak", "inflasi", "bonds", "obligasi",
        "danantara", "emiten", "laba", "dividen",
    }
    financial_assets_multi: List[str] = ["suku bunga", "net buy", "private placement"]

    for article in articles:
        text, tokens = prepare_article_tokens(article)

        # ── STEP 1: Hard-block non-ekonomi (hiburan/kriminal/olahraga) ───────
        has_strict_non_eco = not tokens.isdisjoint(STRICT_NON_ECONOMIC_SINGLE)
        has_savior = not tokens.isdisjoint(savior_keywords)
        if has_strict_non_eco and not has_savior:
            discarded_non_economic.append(article)
            continue

        # ── STEP 2: Hard-block politik opini/seremonial (BARU v4) ────────────
        has_politik_single = not tokens.isdisjoint(POLITIK_OPINI_SINGLE)
        has_politik_multi  = any(kw in text for kw in POLITIK_OPINI_MULTI)
        if has_politik_single or has_politik_multi:
            # Lolos hanya jika ada savior ekonomi kuat (contoh: berita menkeu baru)
            has_politik_savior = not tokens.isdisjoint(POLITIK_ECONOMIC_SAVIOR)
            politik_savior_multi = any(kw in text for kw in ["menteri keuangan", "menkeu", "bank sentral"])
            if not (has_politik_savior or politik_savior_multi):
                discarded_non_economic.append(article)
                continue

        # ── STEP 3: Cek relevansi ekonomi minimal ────────────────────────────
        has_economic_single = not tokens.isdisjoint(ECONOMIC_KEYWORDS_SINGLE)
        has_economic_multi  = any(kw in text for kw in ECONOMIC_KEYWORDS_MULTI)
        if not (has_economic_single or has_economic_multi):
            discarded_non_economic.append(article)
            continue

        # ── STEP 4: Skip artikel rendah nilai ────────────────────────────────
        has_low_value = not tokens.isdisjoint(LOW_VALUE_KEYWORDS_SINGLE)
        if has_low_value:
            low_impact_or_saved.append(article)
            continue

        # ── STEP 5a: Policy bypass → langsung Gemini ─────────────────────────
        has_policy_single = not tokens.isdisjoint(POLICY_BYPASS_SINGLE)
        has_policy_multi  = any(kw in text for kw in POLICY_BYPASS_MULTI)
        if has_policy_single or has_policy_multi:
            # Flag komoditas: apakah artikel ini punya sinyal komoditas nyata?
            has_commodity_signal = not tokens.isdisjoint(COMMODITY_CONTEXT_SIGNALS)
            if not has_commodity_signal:
                article = {**article, "_no_commodity_context": True}
            impactful_to_gemini.append(article)
            continue

        # ── STEP 5b: Market driver (aset + kata kerja penggerak) ─────────────
        has_asset_single = not tokens.isdisjoint(financial_assets_single)
        has_asset_multi  = any(kw in text for kw in financial_assets_multi)
        has_asset  = has_asset_single or has_asset_multi
        has_driver = not tokens.isdisjoint(MARKET_DRIVERS_SINGLE)

        if has_asset and has_driver:
            has_commodity_signal = not tokens.isdisjoint(COMMODITY_CONTEXT_SIGNALS)
            if not has_commodity_signal:
                article = {**article, "_no_commodity_context": True}
            impactful_to_gemini.append(article)
        else:
            low_impact_or_saved.append(article)

    return impactful_to_gemini, low_impact_or_saved, discarded_non_economic