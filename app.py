import time
import asyncio
from datetime import datetime
from email.utils import parsedate_to_datetime

import streamlit as st

from scraper import fetch_news
from cleaner import analyze_and_filter_pipeline
from analyzer import analyze_articles

# Konfigurasi
MAX_SECONDS = 15
MIN_IMPACT_SCORE_TO_SHOW = 1

def get_article_date(item: dict) -> str:
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
    try:
        return int(value)
    except Exception:
        return default

def is_valid_output_news(item: dict) -> bool:
    category = item.get("main_category", "")
    impact_score = safe_int(item.get("impact_score", 0))
    if category == "lainnya" or category == "":
        return False
    if impact_score < MIN_IMPACT_SCORE_TO_SHOW:
        return False
    return True

@st.cache_data(ttl=300)
def cached_fetch_news(limit):
    return fetch_news(limit_per_source=limit)

# --- STREAMLIT PAGE CONFIG ---
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

run_button = st.button("Ambil & Analisis Berita")

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

    # Tambahkan tanggal
    for article in articles:
        article["published_at"] = get_article_date(article)

    with st.spinner("Menyaring relevansi berita secara lokal..."):
        filter_start = time.perf_counter()
        impactful_articles, skipped_low_value, skipped_non_economic = analyze_and_filter_pipeline(articles)
        filter_duration = time.perf_counter() - filter_start

    # Potong sesuai max_analyze, tapi jika impactful_articles kurang, ambil semua
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
        # Progress bar untuk analisis paralel
        progress_bar = st.progress(0, text="Menganalisis berita dengan Gemini...")
        status_text = st.empty()

        with st.spinner("Menganalisis berita ekonomi dengan Gemini LLM secara paralel..."):
            llm_start = time.perf_counter()
            
            # Fungsi untuk update progress (opsional, karena analyze_articles berjalan paralel)
            # Kita bisa modifikasi analyzer untuk menerima callback, tapi untuk sekarang kita jalankan biasa.
            try:
                results = analyze_articles(articles_to_analyze)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                results = loop.run_until_complete(analyze_articles(articles_to_analyze))
            
            llm_end = time.perf_counter()
            progress_bar.progress(1.0, text="Selesai!")
            status_text.empty()

        llm_duration = llm_end - llm_start

        # Filter hasil yang valid untuk ditampilkan
        final_results = [item for item in results if is_valid_output_news(item)]
        failed_analysis = [item for item in results if item.get("status") == "failed_llm"]

        # --- METRIK DURASI ---
        st.subheader("⏱️ Waktu Eksekusi")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Waktu Scraper", f"{scraper_duration:.2f} detik")
        with col2:
            st.metric("Waktu Analisis LLM", f"{llm_duration:.2f} detik")
        with col3:
            st.metric("Total Pipeline", f"{(time.perf_counter() - total_start):.2f} detik")
        with col4:
            st.metric("Kecepatan", f"{len(articles_to_analyze)/llm_duration:.1f} artikel/dtk" if llm_duration>0 else "N/A")

        if (time.perf_counter() - total_start) <= MAX_SECONDS:
            st.success(f"✅ Status: LOLOS standar di bawah {MAX_SECONDS} detik! 🔥")
        else:
            st.warning(f"⏳ Status: BELUM LOLOS standar {MAX_SECONDS} detik.")

        st.divider()

        # --- HASIL ANALISIS ---
        st.subheader(f"📊 Hasil Analisis Berita Berdampak ({len(final_results)} dari {len(articles_to_analyze)} dianalisis)")

        if failed_analysis:
            st.warning(f"⚠️ {len(failed_analysis)} berita gagal dianalisis (fallback digunakan).")

        if not final_results:
            st.info("Tidak ada berita dengan tingkat pergerakan pasar aktif yang lolos saringan akhir.")
        else:
            # Tampilkan setiap berita dalam expander
            for index, item in enumerate(final_results, start=1):
                tanggal = get_article_date(item)
                sentiment = item.get("sentiment", "netral").lower()
                # Pilih warna berdasarkan sentimen
                if sentiment == "positif":
                    color = "#28a745"  # hijau
                elif sentiment == "negatif":
                    color = "#dc3545"  # merah
                else:
                    color = "#ffc107"  # kuning

                with st.expander(f"{index}. {item.get('title', 'No Title')}  [Impact: {item.get('impact_level','-').upper()}]", expanded=(index<=3)):
                    # Header dengan warna sentimen
                    st.markdown(f"<span style='color:{color}; font-weight:bold;'>Sentimen: {item.get('sentiment','-')}</span>", unsafe_allow_html=True)
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

    # Tampilkan berita yang diskip (low value)
    if skipped_low_value:
        st.divider()
        st.subheader("🗂️ Berita Edukasi & Korporasi Ringan (Skipped)")
        st.caption("Daftar berita ekonomi ringan, tips finansial, atau rilis internal perusahaan yang sengaja dilewati untuk menghemat token Gemini Anda.")
        with st.expander(f"Lihat {len(skipped_low_value)} berita yang dilewati"):
            for i, art in enumerate(skipped_low_value[:50], start=1):
                st.write(f"**{i}. {art.get('title')}** — _{art.get('source')}_")

else:
    st.info("Klik tombol ** Ambil & Analisis Berita** untuk memulai pipeline.")
