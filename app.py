import time
import asyncio  # Wajib ditambahkan untuk menjembatani kode async analyzer
from datetime import datetime
from email.utils import parsedate_to_datetime

import streamlit as st

from src.scraper import fetch_news
# Menggunakan pipeline baru yang ringkas dan cepat
from src.cleaner import analyze_and_filter_pipeline
from src.analyzer import analyze_articles


MAX_SECONDS = 15
# Set minimal skor dampak ke 1 agar dampak Rendah, Sedang, dan Tinggi semuanya lolos ke layar
MIN_IMPACT_SCORE_TO_SHOW = 1


def get_article_date(item: dict) -> str:
    """Mengambil tanggal publikasi artikel dari berbagai kemungkinan format field RSS."""
    date_value = (
        item.get("published_at")
        or item.get("published")
        or item.get("updated")
        or item.get("pubDate")
        or item.get("tanggal")
        or item.get("date")
        or item.get("published_date")
        or item.get("created_at")
        or ""
    )

    if date_value:
        try:
            return parsedate_to_datetime(str(date_value)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(date_value)

    parsed_date = item.get("published_parsed") or item.get("updated_parsed")

    if parsed_date:
        try:
            return datetime.fromtimestamp(time.mktime(parsed_date)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return "-"

    return "-"


def safe_int(value, default=0):
    """Konversi nilai ke integer secara aman."""
    try:
        return int(value)
    except Exception:
        return default


def is_valid_output_news(item: dict) -> bool:
    """Memeriksa apakah artikel layak ditampilkan di panel utama."""
    category = item.get("main_category", "")
    impact_score = safe_int(item.get("impact_score", 0))

    # Blokir berita tidak berguna: kategori "lainnya" atau yang sama sekali tidak memiliki skor dampak
    if category == "lainnya" or category == "":
        return False

    if impact_score < MIN_IMPACT_SCORE_TO_SHOW:
        return False

    return True


# Optimasi Kecepatan Scraper: Cache data selama 5 menit agar tidak membebani network saat tuning UI
@st.cache_data(ttl=300)
def cached_fetch_news(limit):
    return fetch_news(limit_per_source=limit)


# --- CONFIGURATION STREAMLIT ---
st.set_page_config(
    page_title="EcoNews LLM",
    page_icon="📰",
    layout="wide",
)

st.title("📰 EcoNews LLM")
st.caption("Dashboard analisis berita makro ekonomi dan pasar keuangan menggunakan Gemini LLM")

with st.sidebar:
    st.header("Pengaturan")

    limit_per_source = st.number_input(
        "Jumlah berita per sumber",
        min_value=1,
        max_value=100,
        value=10,
        step=1,
    )

    max_analyze = st.number_input(
        "Maksimal berita dikirim ke LLM",
        min_value=1,
        max_value=100,
        value=10,
        step=1,
    )

    st.info(
        "Sistem ini menggunakan feed khusus ekonomi makro dan bursa sehingga menghemat kuota token Anda secara maksimal."
    )

run_button = st.button("🚀 Ambil & Analisis Berita")

if run_button:
    total_start = time.perf_counter()
    llm_duration = 0

    with st.spinner("Mengambil berita dari bursa & makro ekonomi..."):
        scraper_start = time.perf_counter()
        articles = cached_fetch_news(limit_per_source)
        scraper_end = time.perf_counter()

    scraper_duration = scraper_end - scraper_start

    if not articles:
        st.error("Tidak ada berita ekonomi yang berhasil diambil.")
        st.stop()

    for article in articles:
        article["published_at"] = get_article_date(article)

 
    with st.spinner("Menyaring relevansi berita secara lokal..."):
        filter_start = time.perf_counter()
        
        impactful_articles, skipped_low_value, skipped_non_economic = analyze_and_filter_pipeline(articles)
        
        filter_duration = time.perf_counter() - filter_start


    articles_to_analyze = impactful_articles[:max_analyze]

    st.success(f"Berhasil mengambil {len(articles)} berita khusus ekonomi dari scraper.")
    st.write(f"Berita ekonomi lolos filter: **{len(impactful_articles) + len(skipped_low_value)}**")
    st.write(f"Berita kandidat berdampak dikirim ke Gemini: **{len(articles_to_analyze)}**")

    if not articles_to_analyze:
        st.warning("Tidak ada kandidat berita makro ekonomi aktif yang lolos saringan awal untuk dianalisis oleh Gemini.")
        
        st.subheader("⏱️ Waktu Eksekusi")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Waktu Scraper", f"{scraper_duration:.2f} detik")
        with col2:
            st.metric("Waktu Analisis LLM", "0.00 detik")
        with col3:
            st.metric("Total Pipeline", f"{(time.perf_counter() - total_start):.2f} detik")
            
    else:

        with st.spinner("Menganalisis berita ekonomi dengan Gemini LLM secara paralel..."):
            llm_start = time.perf_counter()
            
            try:
                results = analyze_articles(articles_to_analyze)
            except RuntimeError:
                # Skenario cadangan jika loop stream utama sudah berjalan di thread terpisah
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                results = loop.run_until_complete(analyze_articles(articles_to_analyze))
                
            llm_end = time.perf_counter()
        llm_duration = llm_end - llm_start

        final_results = [
            item for item in results
            if is_valid_output_news(item)
        ]

        # --- PANEL METRIK DURASI ---
        st.subheader("⏱️ Waktu Eksekusi")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Waktu Scraper", f"{scraper_duration:.2f} detik")
        with col2:
            st.metric("Waktu Analisis LLM (Paralel)", f"{llm_duration:.2f} detik")
        with col3:
            st.metric("Total Pipeline", f"{(time.perf_counter() - total_start):.2f} detik")

        if (time.perf_counter() - total_start) <= MAX_SECONDS:
            st.success(f"Status: LOLOS standar di bawah {MAX_SECONDS} detik! 🔥")
        else:
            st.warning(f"Status: BELUM LOLOS standar {MAX_SECONDS} detik.")

        st.divider()

        # --- PANEL OUTPUT HASIL ---
        st.subheader("📊 Hasil Analisis Berita Berdampak")

        if not final_results:
            st.info("Tidak ada berita dengan tingkat pergerakan pasar aktif yang lolos saringan akhir.")
        else:
            for index, item in enumerate(final_results, start=1):
                tanggal = get_article_date(item)

                with st.container(border=True):
                    st.markdown(f"### {index}. {item.get('title', '-')} ({item.get('impact_level', 'rendah').upper()})")
                    st.write(f"**Sumber:** {item.get('source', '-')} | **Tanggal:** {tanggal}")
                    st.write(f"**URL:** {item.get('url', '-')}")

                    col_a, col_b, col_c, col_d = st.columns(4)
                    with col_a:
                        st.metric("Kategori", item.get("main_category", "-"))
                    with col_b:
                        st.metric("Sentimen", item.get("sentiment", "-"))
                    with col_c:
                        st.metric("Dampak", item.get("impact_level", "-"))
                    with col_d:
                        st.metric("Skor Dampak", item.get("impact_score", "-"))

                    st.write("**Main Cause:**")
                    st.write(item.get("main_cause", "-"))

                    affected_markets = item.get("affected_markets", [])
                    if affected_markets:
                        st.write("**Affected Markets:**")
                        if isinstance(affected_markets, list):
                            if len(affected_markets) == 1 and affected_markets[0] == "tidak ada dampak pasar langsung":
                                st.write("_Tidak ada pasar keuangan global/domestik yang bergejolak langsung._")
                            else:
                                for market in affected_markets:
                                    st.write(f"- {market}")
                        else:
                            st.write(affected_markets)

                    st.write("**Summary:**")
                    st.write(item.get("summary", "-"))

                    st.write("**Confidence Score:**")
                    st.write(f"{item.get('confidence_score', 0.0):.2f}")


    if skipped_low_value:
        st.divider()
        st.subheader("🗂️ Berita Edukasi & Korporasi Ringan (Skipped)")
        st.caption("Daftar berita ekonomi ringan, tips finansial, atau rilis internal perusahaan yang sengaja dilewati untuk menghemat token Gemini Anda.")
        
        for i, art in enumerate(skipped_low_value[:15], start=1):
            st.write(f"**{i}. {art.get('title')}** — _{art.get('source')}_")

else:
    st.info("Klik tombol **🚀 Ambil & Analisis Berita** untuk memulai pipeline.")