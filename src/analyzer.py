import os
import json
import re
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
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


class NewsAnalysis(BaseModel):
    summary: str = Field(description="Ringkasan berita maksimal 2 kalimat.")

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

    sentiment: Literal[
        "positif",
        "negatif",
        "netral",
    ] = Field(description="Sentimen berita.")

    impact_level: Literal[
        "rendah",
        "sedang",
        "tinggi",
    ] = Field(description="Tingkat dampak pasar.")

    impact_score: int = Field(
        ge=0,
        le=10,
        description="Skor dampak pasar dari 0 sampai 10.",
    )

    main_cause: str = Field(
        description=(
            "Penyebab utama yang spesifik dan kontekstual dari isi berita. "
            "Contoh: Aksi profit taking investor, Eskalasi konflik Timur Tengah, "
            "Ekspektasi suku bunga tinggi The Fed."
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
    ] = Field(description="Pasar atau sektor yang terdampak dari berita.")

    impact_explanation: str = Field(
        description="Penjelasan dampak secara kemungkinan, bukan prediksi pasti."
    )

    confidence_score: float = Field(
        ge=0,
        le=1,
        description="Tingkat keyakinan analisis dari 0 sampai 1.",
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


def fallback_rule_analysis(article: dict) -> dict:
    text = " ".join(
        [
            article.get("title", ""),
            article.get("content", ""),
        ]
    ).lower()

    category = "lainnya"
    sentiment = "netral"
    affected_markets = []
    impact_score = 2
    main_cause = "Konteks ekonomi umum"

    if any(word in text for word in ["ihsg", "saham", "bursa", "emiten", "reksa dana", "obligasi"]):
        category = "saham & pasar modal"
        main_cause = "Pergerakan pasar modal domestik"
        affected_markets.append("saham domestik (IHSG)")
        impact_score += 2

    if any(word in text for word in ["profit taking", "ambil untung", "aksi ambil untung"]):
        category = "saham & pasar modal"
        main_cause = "Aksi profit taking investor"
        affected_markets.append("saham domestik (IHSG)")
        impact_score += 2

    if any(word in text for word in ["rupiah", "dolar", "usd", "forex", "kurs", "valas"]):
        category = "forex & valuta asing"
        main_cause = "Pergerakan nilai tukar rupiah terhadap dolar AS"
        affected_markets.extend([
            "mata uang rupiah (IDR)",
            "mata uang dolar AS (USD)",
        ])
        impact_score += 2

    if any(word in text for word in ["bitcoin", "btc"]):
        category = "crypto & aset digital"
        main_cause = "Pergerakan harga Bitcoin"
        affected_markets.append("pasar bitcoin (BTC)")
        impact_score += 2

    if any(word in text for word in ["ethereum", "eth"]):
        category = "crypto & aset digital"
        main_cause = "Pergerakan harga Ethereum"
        affected_markets.append("pasar ethereum (ETH)")
        impact_score += 2

    if any(word in text for word in ["crypto", "kripto", "altcoin", "blockchain"]):
        category = "crypto & aset digital"
        main_cause = "Sentimen pasar aset digital"
        affected_markets.append("pasar koin alternatif (altcoins)")
        impact_score += 2

    if any(word in text for word in ["emas", "gold", "xau", "perak"]):
        category = "komoditas & energi"
        main_cause = "Pergerakan harga emas sebagai aset safe haven"
        affected_markets.append("komoditas logam mulia (emas/XAU/perak)")
        impact_score += 2

    if any(word in text for word in ["minyak", "oil", "gas", "batu bara", "batubara", "energi", "opec"]):
        category = "komoditas & energi"
        main_cause = "Pergerakan harga komoditas energi"
        affected_markets.append("komoditas energi (minyak bumi/gas/batu bara)")
        impact_score += 2

    if any(word in text for word in ["inflasi", "cpi"]):
        category = "kebijakan & makro"
        main_cause = "Tekanan inflasi terhadap ekonomi"
        affected_markets.extend([
            "daya beli & konsumsi masyarakat",
            "biaya modal & pinjaman usaha",
        ])
        impact_score += 3

    if any(word in text for word in ["suku bunga", "the fed", "bi rate", "bank indonesia", "bank sentral"]):
        category = "kebijakan & makro"
        main_cause = "Ekspektasi kebijakan suku bunga bank sentral"
        affected_markets.extend([
            "biaya modal & pinjaman usaha",
            "mata uang rupiah (IDR)",
            "arus modal asing (capital inflow/outflow)",
        ])
        impact_score += 3

    if any(word in text for word in ["pdb", "makro", "ekonomi domestik"]):
        category = "kebijakan & makro"
        main_cause = "Perubahan indikator makroekonomi"
        affected_markets.extend([
            "daya beli & konsumsi masyarakat",
            "iklim investasi & penanaman modal (PMA/PMDN)",
        ])
        impact_score += 2

    if any(word in text for word in ["perang", "konflik", "geopolitik", "sanksi", "israel", "iran", "rusia", "ukraina", "timur tengah"]):
        category = "geopolitik & perang"
        main_cause = "Eskalasi konflik geopolitik"
        affected_markets.extend([
            "rantai pasok global (global supply chain)",
            "komoditas energi (minyak bumi/gas/batu bara)",
            "komoditas logam mulia (emas/XAU/perak)",
        ])
        impact_score += 4

    if any(word in text for word in ["amerika", "china", "tiongkok", "eropa", "resesi global", "ekonomi global"]):
        category = "ekonomi global"
        main_cause = "Perubahan sentimen ekonomi global"
        affected_markets.extend([
            "saham global (Wall Street/regional)",
            "arus modal asing (capital inflow/outflow)",
        ])
        impact_score += 2

    if any(word in text for word in ["umkm", "retail", "manufaktur", "perusahaan", "korporasi", "industri", "bisnis"]):
        category = "bisnis & korporasi"
        main_cause = "Perubahan kinerja sektor bisnis dan korporasi"
        affected_markets.extend([
            "sektor retail & perdagangan eceran",
            "sektor manufaktur & industri pabrik",
        ])
        impact_score += 2

    negative_words = [
        "melemah",
        "turun",
        "anjlok",
        "tertekan",
        "konflik",
        "perang",
        "krisis",
        "rugi",
        "crash",
        "melambat",
        "resesi",
    ]

    positive_words = [
        "menguat",
        "naik",
        "rebound",
        "pulih",
        "positif",
        "optimis",
        "untung",
        "tumbuh",
        "meningkat",
    ]

    if any(word in text for word in negative_words):
        sentiment = "negatif"
    elif any(word in text for word in positive_words):
        sentiment = "positif"

    impact_score = min(max(impact_score, 0), 10)

    if impact_score <= 3:
        impact_level = "rendah"
    elif impact_score <= 6:
        impact_level = "sedang"
    else:
        impact_level = "tinggi"

    affected_markets = list(dict.fromkeys(affected_markets))

    if not affected_markets:
        affected_markets = ["arus modal asing (capital inflow/outflow)"]

    summary = article.get("content") or article.get("title") or "Ringkasan belum tersedia."

    return {
        "summary": summary[:250],
        "main_category": category if category in MAIN_CATEGORIES else "lainnya",
        "sentiment": sentiment,
        "impact_level": impact_level,
        "impact_score": impact_score,
        "main_cause": main_cause,
        "affected_markets": affected_markets,
        "impact_explanation": (
            f"Berita ini berpotensi berdampak {impact_level} karena berkaitan "
            f"dengan {category} dan dapat memengaruhi {', '.join(affected_markets)}."
        ),
        "confidence_score": 0.55,
    }


def validate_and_fix_result(result: dict) -> dict:
    if result.get("main_category") not in MAIN_CATEGORIES:
        result["main_category"] = "lainnya"

    if result.get("sentiment") not in SENTIMENTS:
        result["sentiment"] = "netral"

    if result.get("impact_level") not in IMPACT_LEVELS:
        result["impact_level"] = "rendah"

    if not isinstance(result.get("affected_markets"), list):
        result["affected_markets"] = ["arus modal asing (capital inflow/outflow)"]

    result["affected_markets"] = [
        market for market in result["affected_markets"]
        if market in AFFECTED_MARKETS
    ]

    if not result["affected_markets"]:
        result["affected_markets"] = ["arus modal asing (capital inflow/outflow)"]

    try:
        result["impact_score"] = int(result.get("impact_score", 0))
    except Exception:
        result["impact_score"] = 0

    result["impact_score"] = min(max(result["impact_score"], 0), 10)

    try:
        result["confidence_score"] = float(result.get("confidence_score", 0))
    except Exception:
        result["confidence_score"] = 0.0

    result["confidence_score"] = min(max(result["confidence_score"], 0), 1)

    if not result.get("summary"):
        result["summary"] = "Ringkasan belum tersedia."

    if not result.get("main_cause"):
        result["main_cause"] = "Penyebab utama belum dapat diidentifikasi secara spesifik."

    if not result.get("impact_explanation"):
        result["impact_explanation"] = (
            "Berita ini dapat memengaruhi pasar atau sektor terkait, tetapi dampaknya perlu dilihat "
            "sebagai kemungkinan, bukan prediksi pasti."
        )

    return result


def analyze_with_gemini(article: dict) -> dict | None:
    if not GEMINI_API_KEY:
        return None

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = build_news_analysis_prompt(article)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={
                "temperature": 0.1,
                "max_output_tokens": 500,
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
        print(f"Gemini JSON error: {error}")
        return None


def analyze_article(article: dict) -> dict:
    llm_result = analyze_with_gemini(article)

    if llm_result is None:
        llm_result = fallback_rule_analysis(article)

    llm_result = validate_and_fix_result(llm_result)

    return {
        **article,
        **llm_result,
    }


def analyze_articles(articles: list[dict]) -> list[dict]:
    results = []

    for index, article in enumerate(articles, start=1):
        title = article.get("title", "")
        print(f"Analisis berita {index}/{len(articles)}: {title[:80]}")
        analyzed = analyze_article(article)
        results.append(analyzed)

    return results