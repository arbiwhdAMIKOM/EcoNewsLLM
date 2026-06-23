import os
import json
import re
import time
import concurrent.futures
from typing import List, Literal

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

from prompts import build_news_analysis_prompt
from taxonomy import (
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
    main_cause: str = Field(
        description=(
            "Penyebab utama yang spesifik dan kontekstual dari isi berita. "
            "Contoh: Aksi profit taking investor, Eskalasi konflik Timur Tengah, "
            "Ekspektasi suku bunga tinggi The Fed."
        )
    )
    impact_explanation: str = Field(
        description="Penjelasan dampak secara kemungkinan, bukan prediksi pasti."
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
        "pertanian & pangan",
        "lainnya",
    ] = Field(description="Kategori utama berita.")
    sentiment: Literal[
        "positif",
        "negatif",
        "netral",
    ] = Field(description="Sentimen berita.")
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


# --- Kata kunci untuk fallback ---
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
    "laba", "rugi", "pendapatan", "revenue", "profit", "dividen", "ipo",
    "akuisisi", "merger", "startup", "umkm", "industri", "manufaktur",
    "retail", "ritel", "perbankan", "bank",
    "energi", "transportasi", "logistik", "properti", "konstruksi",
    "infrastruktur", "pertambangan", "proyek strategis nasional", "psn", "psel",
    "pangan", "beras", "kedelai", "jagung", "gandum", "ayam", "sapi", "protein",
    "swasembada", "pertanian", "peternakan", "perikanan",
]

NON_ECONOMIC_STRONG_KEYWORDS = [
    "artis", "seleb", "film", "musik", "konser", "olahraga", "sepak bola",
    "viral", "gosip", "kriminal", "pembunuhan", "kecelakaan", "penjara",
    "dipenjara", "pidana", "putusan hakim", "sidang", "eks presiden",
]

POLITICAL_PURE_KEYWORDS = [
    "pemilu", "pilpres", "pileg", "pilkada", "masa jabatan", "2 periode",
    "periode kedua", "koalisi", "partai", "parpol", "kudeta", "konflik politik",
    "wacana presiden", "amandemen", "presiden 3 periode",
]

OFFICIAL_OPTIMISTIC_PHRASES = [
    "menteri", "gubernur bi", "gubernur bank indonesia", "pemerintah", "presiden",
    "menko", "jokowi", "prabowo", "optimis", "yakin", "aman", "terkendali",
    "tumbuh", "stabil", "positif",
]

WAR_GEOPOLITICAL_KEYWORDS = [
    "perang", "konflik", "geopolitik", "sanksi", "israel", "iran", "rusia",
    "ukraina", "timur tengah", "palestina", "hamas", "serangan", "invasi",
]


def is_direct_economic_article(article: dict) -> bool:
    title = article.get("title", "")
    content = article.get("content", "")
    source = article.get("source", "")
    text = f"{title} {content} {source}".lower()
    economic_score = sum(1 for keyword in ECONOMIC_RELEVANCE_KEYWORDS if keyword in text)
    has_strong_non_economic = any(keyword in text for keyword in NON_ECONOMIC_STRONG_KEYWORDS)
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
        "impact_explanation": (
            "Berita ini tidak dianalisis lebih lanjut karena tidak memiliki hubungan langsung "
            "dengan ekonomi, bisnis, pasar keuangan, komoditas, atau kebijakan makro."
        ),
        "confidence_score": 0.0,
        "status": "skipped_non_economic",
    }


def fallback_rule_analysis(article: dict) -> dict:
    title = article.get("title", "")
    content = article.get("content", "")
    text = f"{title} {content}".lower()

    # Filter politik murni
    is_political_pure = any(kw in text for kw in POLITICAL_PURE_KEYWORDS)
    has_economic_indicator = any(kw in text for kw in ECONOMIC_RELEVANCE_KEYWORDS)
    if is_political_pure and not has_economic_indicator:
        return non_economic_analysis(article)

    if not is_direct_economic_article(article):
        return non_economic_analysis(article)

    category = "lainnya"
    sentiment = "netral"
    affected_markets = []
    impact_score = 0
    main_cause = "Konteks ekonomi belum spesifik"
    confidence_score = 0.5

    # --- Deteksi kategori ---
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
    if any(word in text for word in ["rupiah", "dolar", "usd", "forex", "kurs", "valas", "mata uang"]):
        category = "forex & valuta asing"
        main_cause = "Pergerakan nilai tukar atau mata uang"
        affected_markets.extend(["mata uang rupiah (IDR)", "mata uang dolar AS (USD)"])
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
    if any(word in text for word in ["pangan", "beras", "kedelai", "jagung", "gandum", "ayam", "sapi", "protein", "swasembada", "pertanian", "peternakan", "perikanan"]):
        category = "pertanian & pangan"
        main_cause = "Perubahan kebijakan atau harga pangan"
        affected_markets.append("komoditas agrikultur (CPO/kopi/gandum/karet)")
        impact_score += 3
    if any(word in text for word in ["inflasi", "cpi"]):
        category = "kebijakan & makro"
        main_cause = "Tekanan inflasi terhadap ekonomi"
        affected_markets.extend(["daya beli & konsumsi masyarakat", "biaya modal & pinjaman usaha"])
        impact_score += 3
    if any(word in text for word in ["suku bunga", "the fed", "bi rate", "bank indonesia", "bank sentral"]):
        category = "kebijakan & makro"
        main_cause = "Ekspektasi kebijakan suku bunga bank sentral"
        affected_markets.extend(["biaya modal & pinjaman usaha", "mata uang rupiah (IDR)", "arus modal asing (capital inflow/outflow)"])
        impact_score += 3
    if any(word in text for word in ["pdb", "makro", "ekonomi domestik", "pertumbuhan ekonomi"]):
        category = "kebijakan & makro"
        main_cause = "Perubahan indikator makroekonomi"
        affected_markets.extend(["daya beli & konsumsi masyarakat", "iklim investasi & penanaman modal (PMA/PMDN)"])
        impact_score += 2
    if any(word in text for word in WAR_GEOPOLITICAL_KEYWORDS):
        if any(word in text for word in ["minyak", "gas", "emas", "rupiah", "dolar", "pasar", "ekonomi", "komoditas", "ekspor", "impor", "rantai pasok"]):
            category = "geopolitik & perang"
            main_cause = "Eskalasi konflik geopolitik yang berpotensi memengaruhi pasar"
            affected_markets.extend(["rantai pasok global (global supply chain)", "komoditas energi (minyak bumi/gas/batu bara)", "komoditas logam mulia (emas/XAU/perak)"])
            impact_score += 4
    if any(word in text for word in ["amerika", "china", "tiongkok", "eropa", "resesi global", "ekonomi global"]):
        category = "ekonomi global"
        main_cause = "Perubahan sentimen ekonomi global"
        affected_markets.extend(["saham global (Wall Street/regional)", "arus modal asing (capital inflow/outflow)"])
        impact_score += 2
    if any(word in text for word in ["umkm", "retail", "ritel", "manufaktur", "perusahaan", "korporasi", "industri", "bisnis", "laba", "pendapatan"]):
        category = "bisnis & korporasi"
        main_cause = "Perubahan kinerja sektor bisnis dan korporasi"
        affected_markets.extend(["sektor retail & perdagangan eceran", "sektor manufaktur & industri pabrik"])
        impact_score += 2
    if any(word in text for word in ["psel", "proyek strategis nasional", "psn", "infrastruktur", "konstruksi"]):
        category = "bisnis & korporasi"
        main_cause = "Pengembangan proyek infrastruktur strategis"
        affected_markets.extend(["saham infrastruktur & konstruksi", "sektor manufaktur & industri pabrik"])
        impact_score += 2

    # --- Sentimen dengan bias pejabat ---
    negative_words = ["melemah", "turun", "anjlok", "tertekan", "konflik", "perang", "krisis", "rugi", "crash", "melambat", "resesi"]
    positive_words = ["menguat", "naik", "rebound", "pulih", "positif", "optimis", "untung", "tumbuh", "meningkat"]

    has_negative = any(word in text for word in negative_words)
    has_positive = any(word in text for word in positive_words)

    has_official_optimist = any(off in text for off in OFFICIAL_OPTIMISTIC_PHRASES)
    has_war = any(war in text for war in WAR_GEOPOLITICAL_KEYWORDS)

    if has_official_optimist and has_war:
        sentiment = "positif"
    elif has_negative and not has_positive:
        sentiment = "negatif"
    elif has_positive and not has_negative:
        sentiment = "positif"
    else:
        sentiment = "netral"

    # --- Confidence berdasarkan data numerik ---
    has_numbers = bool(re.search(r'\d+[.,]?\d*\%?', text))
    confidence_score = 0.9 if has_numbers else 0.5

    # Jika tidak ada pasar terdampak, anggap non-ekonomi
    if not affected_markets:
        return non_economic_analysis(article)

    # Normalisasi skor
    impact_score = min(max(impact_score, 0), 10)
    if impact_score <= 3:
        impact_level = "rendah"
    elif impact_score <= 6:
        impact_level = "sedang"
    else:
        impact_level = "tinggi"

    affected_markets = list(dict.fromkeys(affected_markets))
    summary = article.get("content") or article.get("title") or "Ringkasan belum tersedia."

    return {
        "summary": summary[:250],
        "main_category": category if category in MAIN_CATEGORIES else "lainnya",
        "sentiment": sentiment,
        "impact_level": impact_level,
        "impact_score": impact_score,
        "main_cause": main_cause,
        "affected_markets": affected_markets,
        "impact_explanation": f"Berita ini berpotensi berdampak {impact_level} karena berkaitan dengan {category} dan dapat memengaruhi {', '.join(affected_markets)}.",
        "confidence_score": confidence_score,
    }


def validate_and_fix_result(result: dict, article: dict = None) -> dict:
    # 1. Pastikan kategori dan sentimen valid
    if result.get("main_category") not in MAIN_CATEGORIES:
        result["main_category"] = "lainnya"
    if result.get("sentiment") not in SENTIMENTS:
        result["sentiment"] = "netral"
    if result.get("impact_level") not in IMPACT_LEVELS:
        result["impact_level"] = "rendah"

    # 2. Bersihkan affected_markets
    if not isinstance(result.get("affected_markets"), list):
        result["affected_markets"] = []
    result["affected_markets"] = [m for m in result["affected_markets"] if m in AFFECTED_MARKETS]

    # 3. Skor impact
    try:
        result["impact_score"] = int(result.get("impact_score", 0))
    except Exception:
        result["impact_score"] = 0
    result["impact_score"] = min(max(result["impact_score"], 0), 10)

    # 4. Jika kategori = lainnya, kosongkan pasar dan batasi skor
    if result.get("main_category") == "lainnya":
        result["affected_markets"] = []
        result["impact_score"] = min(result["impact_score"], 2)
        result["sentiment"] = "netral"

    # 5. Filter politik (berdasarkan artikel asli)
    if article:
        title = article.get("title", "")
        content = article.get("content", "")
        text = f"{title} {content}".lower()
        is_political_pure = any(kw in text for kw in POLITICAL_PURE_KEYWORDS)
        has_economic = any(kw in text for kw in ECONOMIC_RELEVANCE_KEYWORDS)
        if is_political_pure and not has_economic:
            return {
                **result,
                "main_category": "lainnya",
                "sentiment": "netral",
                "impact_level": "rendah",
                "impact_score": 0,
                "affected_markets": [],
                "main_cause": "Isu politik tanpa dampak ekonomi langsung",
                "impact_explanation": "Wacana politik tanpa stimulus fiskal/ekonomi nyata tidak berdampak pada pasar.",
                "confidence_score": 0.0,
            }

        # 6. Bias pejabat
        has_official = any(off in text for off in OFFICIAL_OPTIMISTIC_PHRASES)
        has_war = any(war in text for war in WAR_GEOPOLITICAL_KEYWORDS)
        if has_official and has_war and result.get("sentiment") != "positif":
            result["sentiment"] = "positif"
            if "impact_explanation" in result:
                result["impact_explanation"] += " (Catatan: pernyataan resmi optimistis di tengah isu geopolitik menjadi sinyal positif.)"

    # 7. Kalibrasi confidence score
    if article:
        text = f"{article.get('title', '')} {article.get('content', '')}".lower()
        has_numbers = bool(re.search(r'\d+[.,]?\d*\%?', text))
        if has_numbers and result.get("confidence_score", 0) < 0.8:
            result["confidence_score"] = 0.85
        elif not has_numbers and result.get("confidence_score", 0) > 0.7:
            result["confidence_score"] = min(result.get("confidence_score", 0), 0.6)

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
        if result.get("affected_markets"):
            result["impact_explanation"] = "Berita ini dapat memengaruhi pasar atau sektor terkait, tetapi dampaknya perlu dilihat sebagai kemungkinan, bukan prediksi pasti."
        else:
            result["impact_explanation"] = "Berita ini tidak memiliki dampak pasar yang cukup jelas berdasarkan isi berita."

    return result


def analyze_with_gemini(article: dict, max_retries: int = 3) -> dict | None:
    if not GEMINI_API_KEY:
        return None

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = build_news_analysis_prompt(article)

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={
                    "temperature": 0.0,
                    "max_output_tokens": 1024,
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
                wait_time = (2 ** attempt) + 2
                print(f"Peringatan: Gemini API sibuk (Percobaan {attempt + 1}/{max_retries}). Menunggu {wait_time} detik...")
                time.sleep(wait_time)
            else:
                print(f"Error: Kegagalan internal Gemini: {error}")
                break
    return None


def analyze_article(article: dict) -> dict:
    if not is_direct_economic_article(article):
        return {
            **article,
            **non_economic_analysis(article),
        }

    llm_result = analyze_with_gemini(article)
    if llm_result is None:
        llm_result = fallback_rule_analysis(article)

    llm_result = validate_and_fix_result(llm_result, article)
    return {
        **article,
        **llm_result,
        "status": "analyzed",
    }


def analyze_articles(articles: list[dict]) -> list[dict]:
    results = []
    print(f"Memproses {len(articles)} artikel ke Gemini secara paralel...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_article = {executor.submit(analyze_article, art): art for art in articles}
        
        for index, future in enumerate(concurrent.futures.as_completed(future_to_article), start=1):
            article = future_to_article[future]
            try:
                analyzed = future.result()
                results.append(analyzed)
                print(f"Selesai menganalisis {index}/{len(articles)}: {article.get('title', '')[:50]}...")
            except Exception as e:
                print(f"Error: Gagal memproses artikel: {e}")
                results.append({**article, **fallback_rule_analysis(article), "status": "failed_llm"})
                
    return results