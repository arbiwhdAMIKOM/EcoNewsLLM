"""
analyzer.py  —  EcoNews LLM  (v4)
Perubahan dari v3:

1. build_news_analysis_prompt menerima flag `_no_commodity_context` dari cleaner.
   Jika flag aktif, prompt mendapat satu baris peringatan tambahan yang sangat
   spesifik: "Artikel ini TIDAK mengandung sinyal komoditas — DILARANG memilih
   komoditas energi atau logam mulia di affected_markets."
   Ini adalah lapisan kedua setelah instruksi matrix di prompts.py.

2. validate_and_fix_result: tambah post-processing guard komoditas.
   Setelah LLM menjawab, jika main_category bukan komoditas/geopolitik,
   secara paksa hapus "komoditas energi" dan "komoditas logam mulia" dari
   affected_markets. Ini adalah jaring pengaman terakhir yang bersifat deterministik.

3. Batas 3 affected_markets di-enforce di validate_and_fix_result:
   Jika LLM tetap mengembalikan > 3, ambil 3 pertama (urutan LLM dianggap
   prioritas tertinggi).

4. Semua optimasi v2/v3 dipertahankan.
"""

import os
import json
import re
import time
import concurrent.futures
from typing import List, Literal

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

from src.prompts import build_news_analysis_prompt
from src.taxonomy import (
    MAIN_CATEGORIES,
    SENTIMENTS,
    IMPACT_LEVELS,
    AFFECTED_MARKETS,
)

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

_gemini_client: genai.Client | None = None

def _get_client() -> genai.Client | None:
    global _gemini_client
    if _gemini_client is None and GEMINI_API_KEY:
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client


# ── Pasar komoditas yang hanya valid untuk kategori tertentu ──────────────────
_COMMODITY_MARKETS = {
    "komoditas energi (minyak bumi/gas/batu bara)",
    "komoditas logam mulia (emas/XAU/perak)",
    "komoditas logam industri (nikel/tembaga/biji besi)",
    "komoditas agrikultur (CPO/kopi/gandum/karet)",
}

_COMMODITY_ALLOWED_CATEGORIES = {
    "komoditas & energi",
    "geopolitik & perang",  # valid: konflik → minyak/emas
    "ekonomi global",       # valid: resesi global → komoditas
}


class NewsAnalysis(BaseModel):
    summary: str = Field(
        description="Ringkasan berita maksimal 2 kalimat. Fokus pada fakta utama, bukan parafrase judul."
    )
    main_cause: str = Field(
        description=(
            "Penyebab utama dalam 1 frasa spesifik dan kontekstual. "
            "Contoh: 'Aksi profit taking investor', 'Keputusan BI Rate naik 25bps', "
            "'Stimulus fiskal Rp26T pemerintah', 'Eskalasi konflik Timur Tengah'."
        )
    )
    main_category: Literal[
        "saham & pasar modal",
        "forex & valuta asing",
        "crypto & aset digital",
        "komoditas & energi",
        "kebijakan & makro",
        "geopolitik & perang",
        "ekonomi global",
        "bisnis & korporasi",
        "lainnya",
    ] = Field(description="Kategori utama berita.")
    sentiment: Literal["positif", "negatif", "netral"] = Field(
        description=(
            "Sentimen berdasarkan dampak LANGSUNG ke pasar/ekonomi Indonesia. "
            "Geopolitik/ekonomi global hanya ubah sentimen ke negatif jika ada "
            "kalimat eksplisit dampak ke Indonesia."
        )
    )
    affected_markets: List[
        Literal[
            "saham domestik (IHSG)",
            "saham global (Wall Street/regional)",
            "obligasi & surat utang negara (SBN/bonds)",
            "reksa dana & instrumen investasi",
            "saham perbankan & keuangan",
            "saham teknologi & digital",
            "saham properti & real estate",
            "saham infrastruktur & konstruksi",
            "saham transportasi & logistik",
            "saham barang konsumsi (staples/discretionary)",
            "mata uang rupiah (IDR)",
            "mata uang dolar AS (USD)",
            "mata uang utama global (EUR/GBP/JPY/dll)",
            "mata uang negara berkembang (emerging currencies)",
            "pasar bitcoin (BTC)",
            "pasar ethereum (ETH)",
            "pasar koin alternatif (altcoins)",
            "pasar stablecoin",
            "komoditas energi (minyak bumi/gas/batu bara)",
            "komoditas logam mulia (emas/XAU/perak)",
            "komoditas logam industri (nikel/tembaga/biji besi)",
            "komoditas agrikultur (CPO/kopi/gandum/karet)",
            "daya beli & konsumsi masyarakat",
            "biaya modal & pinjaman usaha",
            "sektor ketenagakerjaan & upah",
            "iklim investasi & penanaman modal (PMA/PMDN)",
            "sektor manufaktur & industri pabrik",
            "sektor retail & perdagangan eceran",
            "sektor pariwisata, perhotelan & kuliner",
            "sektor UMKM & ekonomi kreatif",
            "arus modal asing (capital inflow/outflow)",
            "neraca perdagangan & ekspor-impor",
            "rantai pasok global (global supply chain)",
        ]
    ] = Field(
        description=(
            "Maksimal 3 pasar yang paling langsung terdampak. "
            "Prioritaskan yang tersebut eksplisit dalam teks. "
            "Komoditas energi/logam mulia HANYA jika main_category = komoditas & energi "
            "atau geopolitik & perang dengan sebutan minyak/emas eksplisit."
        )
    )
    impact_level: Literal["rendah", "sedang", "tinggi"] = Field(
        description="Tingkat dampak pasar."
    )
    impact_score: int = Field(
        ge=0, le=10,
        description="Skor dampak 0-10. Skor 7-10 HANYA untuk peristiwa makro sistemik.",
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0,
        description=(
            "Keyakinan analisis: "
            "0.9-1.0 = teks sangat eksplisit (angka, instrumen, arah jelas); "
            "0.7-0.8 = cukup jelas, 1-2 ambiguitas minor; "
            "0.5-0.6 = teks ambigu atau terlalu singkat; "
            "0.3-0.4 = inferensi tinggi; "
            "0.0-0.2 = tidak ada info ekonomi yang dapat diandalkan."
        ),
    )


def extract_json(text: str) -> dict | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


ECONOMIC_RELEVANCE_KEYWORDS = [
    "ihsg", "saham", "bursa", "emiten", "investor", "obligasi", "reksa dana",
    "pasar modal", "wall street", "nasdaq", "dow jones", "s&p",
    "rupiah", "dolar", "usd", "kurs", "valas", "mata uang", "bank indonesia",
    "the fed", "suku bunga", "inflasi", "deflasi", "cadangan devisa",
    "bitcoin", "btc", "ethereum", "eth", "crypto", "kripto", "aset digital",
    "emas", "gold", "xau", "minyak", "gas", "batu bara", "batubara",
    "nikel", "tembaga", "cpo", "komoditas",
    "ekonomi", "pdb", "pertumbuhan ekonomi", "ekspor", "impor",
    "neraca perdagangan", "pajak", "apbn", "subsidi", "investasi", "pma", "pmdn",
    "stimulus", "fiskal", "anggaran", "defisit", "surplus", "sbn", "sukuk",
    "laba", "rugi", "pendapatan", "revenue", "profit", "dividen", "ipo",
    "akuisisi", "merger", "startup", "umkm", "industri", "manufaktur",
    "retail", "ritel", "perbankan", "bank",
    "energi", "transportasi", "logistik", "properti", "konstruksi",
    "infrastruktur", "pertambangan", "proyek strategis nasional", "psn", "psel",
]

NON_ECONOMIC_STRONG_KEYWORDS = [
    "artis", "seleb", "film", "musik", "konser", "olahraga", "sepak bola",
    "viral", "gosip", "kriminal", "pembunuhan", "kecelakaan", "penjara",
    "dipenjara", "pidana", "putusan hakim", "sidang", "eks presiden",
]


def is_direct_economic_article(article: dict) -> bool:
    title   = article.get("title", "")
    content = article.get("content", "")
    source  = article.get("source", "")
    text    = f"{title} {content} {source}".lower()
    economic_score = sum(1 for kw in ECONOMIC_RELEVANCE_KEYWORDS if kw in text)
    has_strong_non_economic = any(kw in text for kw in NON_ECONOMIC_STRONG_KEYWORDS)
    if economic_score == 0:
        return False
    if has_strong_non_economic and economic_score < 2:
        return False
    return True


def non_economic_analysis(article: dict) -> dict:
    title = article.get("title", "")
    return {
        "summary": title or "Berita tidak memiliki ringkasan ekonomi yang relevan.",
        "main_category": "lainnya",
        "sentiment": "netral",
        "impact_level": "rendah",
        "impact_score": 0,
        "main_cause": "Tidak relevan langsung dengan ekonomi atau pasar keuangan",
        "affected_markets": [],
        "confidence_score": 1.0,
        "status": "skipped_non_economic",
    }


def fallback_rule_analysis(article: dict) -> dict:
    if not is_direct_economic_article(article):
        return non_economic_analysis(article)

    text = " ".join([article.get("title", ""), article.get("content", "")]).lower()
    category         = "lainnya"
    sentiment        = "netral"
    affected_markets = []
    impact_score     = 0
    main_cause       = "Konteks ekonomi belum spesifik"

    if any(w in text for w in ["ihsg", "saham", "bursa", "emiten", "reksa dana"]):
        category = "saham & pasar modal"
        main_cause = "Pergerakan pasar modal domestik"
        affected_markets.append("saham domestik (IHSG)")
        impact_score += 2
    if any(w in text for w in ["rupiah", "dolar", "usd", "kurs", "valas"]):
        category = "forex & valuta asing"
        main_cause = "Pergerakan nilai tukar atau mata uang"
        affected_markets.extend(["mata uang rupiah (IDR)", "mata uang dolar AS (USD)"])
        impact_score += 2
    if any(w in text for w in ["bitcoin", "btc"]):
        category = "crypto & aset digital"
        main_cause = "Pergerakan harga Bitcoin"
        affected_markets.append("pasar bitcoin (BTC)")
        impact_score += 2
    # Komoditas hanya jika ada sinyal nyata (bukan sekadar kata "ekonomi")
    if any(w in text for w in ["minyak", "opec", "brent", "wti", "gas", "batu bara", "batubara"]):
        category = "komoditas & energi"
        main_cause = "Pergerakan harga komoditas energi"
        affected_markets.append("komoditas energi (minyak bumi/gas/batu bara)")
        impact_score += 2
    if any(w in text for w in ["harga emas", "xau", "gold", "perak", "silver"]):
        category = "komoditas & energi"
        main_cause = "Pergerakan harga emas sebagai aset safe haven"
        affected_markets.append("komoditas logam mulia (emas/XAU/perak)")
        impact_score += 2
    if any(w in text for w in ["inflasi", "cpi"]):
        category = "kebijakan & makro"
        main_cause = "Tekanan inflasi terhadap ekonomi"
        affected_markets.extend(["daya beli & konsumsi masyarakat", "biaya modal & pinjaman usaha"])
        impact_score += 3
    if any(w in text for w in ["suku bunga", "the fed", "bi rate", "bank indonesia"]):
        category = "kebijakan & makro"
        main_cause = "Ekspektasi kebijakan suku bunga bank sentral"
        affected_markets.extend(["biaya modal & pinjaman usaha", "mata uang rupiah (IDR)", "arus modal asing (capital inflow/outflow)"])
        impact_score += 3
    if any(w in text for w in ["stimulus", "fiskal", "apbn", "anggaran", "subsidi", "sbn", "sukuk"]):
        category = "kebijakan & makro"
        main_cause = "Kebijakan fiskal atau stimulus pemerintah"
        affected_markets.extend(["iklim investasi & penanaman modal (PMA/PMDN)", "daya beli & konsumsi masyarakat"])
        impact_score += 4
    if any(w in text for w in ["perang", "konflik", "geopolitik", "sanksi"]):
        if any(w in text for w in ["minyak", "gas", "emas", "rupiah", "pasar", "komoditas"]):
            category = "geopolitik & perang"
            main_cause = "Eskalasi konflik geopolitik yang berpotensi memengaruhi pasar"
            affected_markets.extend(["rantai pasok global (global supply chain)", "komoditas energi (minyak bumi/gas/batu bara)"])
            impact_score += 4
    if any(w in text for w in ["umkm", "retail", "ritel", "manufaktur", "korporasi", "laba"]):
        category = "bisnis & korporasi"
        main_cause = "Perubahan kinerja sektor bisnis dan korporasi"
        affected_markets.extend(["sektor retail & perdagangan eceran", "sektor manufaktur & industri pabrik"])
        impact_score += 2

    negative_words = ["melemah", "turun", "anjlok", "tertekan", "krisis", "rugi", "melambat", "resesi"]
    positive_words = ["menguat", "naik", "rebound", "pulih", "optimis", "tumbuh", "meningkat", "stimulus"]

    if any(w in text for w in negative_words):
        sentiment = "negatif"
    elif any(w in text for w in positive_words):
        sentiment = "positif"

    impact_score = min(max(impact_score, 0), 10)
    impact_level = "rendah" if impact_score <= 3 else ("sedang" if impact_score <= 6 else "tinggi")
    affected_markets = list(dict.fromkeys(affected_markets))[:3]  # Batas 3

    if not affected_markets:
        return non_economic_analysis(article)

    summary = article.get("content") or article.get("title") or "Ringkasan belum tersedia."
    return {
        "summary": summary[:250],
        "main_category": category if category in MAIN_CATEGORIES else "lainnya",
        "sentiment": sentiment,
        "impact_level": impact_level,
        "impact_score": impact_score,
        "main_cause": main_cause,
        "affected_markets": affected_markets,
        "confidence_score": 0.40,
    }


def validate_and_fix_result(result: dict, article: dict | None = None) -> dict:
    """
    Post-processing deterministik setelah LLM menjawab.
    Jaring pengaman terakhir — tidak bisa di-bypass oleh output LLM.
    """
    if result.get("main_category") not in MAIN_CATEGORIES:
        result["main_category"] = "lainnya"
    if result.get("sentiment") not in SENTIMENTS:
        result["sentiment"] = "netral"
    if result.get("impact_level") not in IMPACT_LEVELS:
        result["impact_level"] = "rendah"
    if not isinstance(result.get("affected_markets"), list):
        result["affected_markets"] = []

    # Validasi label taksonomi
    result["affected_markets"] = [m for m in result["affected_markets"] if m in AFFECTED_MARKETS]

    # ── GUARD: Batas 3 affected_markets (enforce deterministik) ──────────────
    if len(result["affected_markets"]) > 3:
        result["affected_markets"] = result["affected_markets"][:3]

    # ── GUARD: Hapus komoditas energi/logam mulia jika kategori tidak valid ───
    # Ini jaring pengaman terakhir — LLM tetap bisa halusinasi komoditas
    # meski sudah ada instruksi di prompt. Guard ini memblok secara deterministik.
    category = result.get("main_category", "")
    if category not in _COMMODITY_ALLOWED_CATEGORIES:
        # Hapus komoditas energi dan logam mulia
        result["affected_markets"] = [
            m for m in result["affected_markets"]
            if m not in {"komoditas energi (minyak bumi/gas/batu bara)", "komoditas logam mulia (emas/XAU/perak)"}
        ]
        # Komoditas industri & agrikultur masih boleh untuk kategori kebijakan/bisnis
        # (nikel → industri manufaktur, CPO → kebijakan ekspor) — tidak diblok

    # ── GUARD: Kategori "lainnya" → reset total ───────────────────────────────
    if category == "lainnya":
        result["affected_markets"] = []
        result["impact_score"] = min(result.get("impact_score", 0), 2)

    try:
        result["impact_score"] = int(result.get("impact_score", 0))
    except Exception:
        result["impact_score"] = 0
    result["impact_score"] = min(max(result["impact_score"], 0), 10)

    result["impact_level"] = (
        "rendah" if result["impact_score"] <= 3 else
        ("sedang" if result["impact_score"] <= 6 else "tinggi")
    )

    try:
        result["confidence_score"] = float(result.get("confidence_score", 0))
    except Exception:
        result["confidence_score"] = 0.0
    result["confidence_score"] = min(max(result["confidence_score"], 0), 1)

    if not result.get("summary"):
        result["summary"] = "Ringkasan belum tersedia."
    if not result.get("main_cause"):
        result["main_cause"] = "Penyebab utama belum dapat diidentifikasi secara spesifik."

    return result


def analyze_with_gemini(article: dict, max_retries: int = 3) -> dict | None:
    client = _get_client()
    if not client:
        return None

    # Ambil flag dari cleaner — artikel tanpa sinyal komoditas mendapat peringatan ekstra
    no_commodity_ctx = article.get("_no_commodity_context", False)

    base_prompt = build_news_analysis_prompt(article)

    # Lapisan kedua anti-halusinasi komoditas: injeksi peringatan kontekstual
    if no_commodity_ctx:
        commodity_warning = (
            "\n\n⚠️ PERINGATAN KONTEKS: Artikel ini TIDAK mengandung kata kunci komoditas "
            "(minyak, opec, brent, tambang, harga emas, xau, batu bara). "
            "DILARANG KERAS memilih 'komoditas energi' atau 'komoditas logam mulia' "
            "di affected_markets untuk berita ini."
        )
        prompt = base_prompt + commodity_warning
    else:
        prompt = base_prompt

    for attempt in range(max_retries):
        try:
            response = _get_client().models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={
                    "temperature": 0.0,
                    "max_output_tokens": 512,
                    "response_mime_type": "application/json",
                    "response_schema": NewsAnalysis,
                },
            )

            if hasattr(response, "parsed") and response.parsed:
                if isinstance(response.parsed, NewsAnalysis):
                    return response.parsed.model_dump()
                if isinstance(response.parsed, dict):
                    return NewsAnalysis.model_validate(response.parsed).model_dump()

            return NewsAnalysis.model_validate_json(response.text).model_dump()

        except Exception as error:
            error_msg = str(error).lower()
            if "429" in error_msg or "503" in error_msg or "exhausted" in error_msg or "overloaded" in error_msg:
                wait_time = 2 ** attempt
                print(f"Peringatan: Gemini API sibuk ({attempt + 1}/{max_retries}). Menunggu {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"Error: Kegagalan internal Gemini: {error}")
                break
    return None


def analyze_article(article: dict) -> dict:
    if not is_direct_economic_article(article):
        return {**article, **non_economic_analysis(article)}

    llm_result = analyze_with_gemini(article)
    if llm_result is None:
        llm_result = fallback_rule_analysis(article)

    # Teruskan artikel asli ke validator untuk akses flag _no_commodity_context
    llm_result = validate_and_fix_result(llm_result, article=article)
    return {**article, **llm_result, "status": "analyzed"}


def analyze_articles(articles: list[dict]) -> list[dict]:
    results = []
    print(f"Memproses {len(articles)} artikel ke Gemini secara paralel...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_article = {executor.submit(analyze_article, art): art for art in articles}

        for index, future in enumerate(concurrent.futures.as_completed(future_to_article), start=1):
            article = future_to_article[future]
            try:
                analyzed = future.result()
                results.append(analyzed)
                print(f"[{index}/{len(articles)}] {article.get('title', '')[:60]}")
            except Exception as e:
                print(f"Error: Gagal memproses artikel: {e}")
                results.append({
                    **article,
                    **fallback_rule_analysis(article),
                    "status": "failed_llm",
                })

    return results