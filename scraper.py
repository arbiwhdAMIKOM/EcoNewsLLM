import feedparser
import requests
from bs4 import BeautifulSoup
import datetime
import concurrent.futures
import time
from typing import List, Dict, Any, Tuple

from database import init_db, simpan_banyak_berita
from cleaner import bersihkan_teks

SOURCES: Dict[str, str] = {
    "CNBC Indonesia": "https://www.cnbcindonesia.com/news/rss",
    "Antara News": "https://www.antaranews.com/rss/ekonomi.xml",
    "Detik Finance": "https://finance.detik.com/rss",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines",
    "KataData": "https://katadata.co.id/rss/finansial",
    "Bloomberg Tech": "https://www.bloombergtechnoz.com/rss",
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss",
    "Investing Global": "https://id.investing.com/rss/news_25.rss",
    "Investing Indo": "https://id.investing.com/rss/news_14.rss",
    "Investing Insider": "https://id.investing.com/rss/news_357.rss",
    "Investing Emiten": "https://id.investing.com/rss/news_356.rss",
}

def scrape_full_text(url: str, source_name: str) -> Tuple[str, str]:
    """Ekstraksi DOM HTML artikel spesifik berdasarkan target media."""
    headers: Dict[str, str] = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    try:
        response = requests.get(url, headers=headers, timeout=3)
        if response.status_code != 200:
            return "", f"HTTP {response.status_code}"

        soup = BeautifulSoup(response.text, 'html.parser')

        if source_name == "CNBC Indonesia":
            article_div = soup.find('div', class_='detail_text')
            paragraphs = article_div.find_all('p') if article_div else soup.find_all('p')
        elif "Kontan" in source_name:
            article_div = soup.find('div', class_='txt-article') or soup.find('div', id='body-page')
            paragraphs = article_div.find_all('p') if article_div else soup.find_all('p')
        else:
            paragraphs = soup.find_all('p')

        full_text = " ".join([p.get_text().strip() for p in paragraphs])
        return full_text[:3000], ""

    except requests.exceptions.Timeout:
        return "", "Timeout"
    except Exception:
        return "", "Parsing Error"

def ambil_daftar_artikel_dari_rss(name: str, rss_url: str, limit_per_source: int) -> Tuple[List[Dict[str, Any]], str, str]:
    """Stage 1: Fetch RSS feed metadata (I/O Bound)."""
    hasil_rss: List[Dict[str, Any]] = []
    headers: Dict[str, str] = {'User-Agent': 'Mozilla/5.0', 'Accept': '*/*'}

    try:
        response = requests.get(rss_url, headers=headers, timeout=3)
        if response.status_code == 200:
            feed = feedparser.parse(response.content)
            entries = feed.entries[:limit_per_source]

            print(f"[RSS] {name:<20} : {len(entries)} artikel ditemukan")

            for entry in entries:
                hasil_rss.append({
                    "sumber": name,
                    "judul": entry.title,
                    "link": entry.link,
                    "waktu_ambil": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "isi_berita": ""
                })
            return hasil_rss, name, ""
        else:
            print(f"[RSS] {name:<20} : Skipped (HTTP {response.status_code})")
            return [], name, f"HTTP {response.status_code}"

    except requests.exceptions.Timeout:
        print(f"[RSS] {name:<20} : Skipped (Timeout)")
        return [], name, "Timeout"
    except Exception:
        print(f"[RSS] {name:<20} : Skipped (Request Error)")
        return [], name, "Request Error"

def lengkapi_isi_berita(berita_item: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str]:
    judul_potong = berita_item['judul'][:35] + "..." if len(berita_item['judul']) > 35 else berita_item['judul']
    print(f"[HTML] Ekstrak dari {berita_item['sumber']:<18} -> {judul_potong}")

    isi_teks, err = scrape_full_text(berita_item["link"], berita_item["sumber"])
    
    # Proses pembersihan teks dilakukan di sini sebelum masuk ke database
    if isi_teks:
        isi_teks = bersihkan_teks(isi_teks)
        
    berita_item["isi_berita"] = isi_teks
    return berita_item, berita_item["sumber"], err

def eksekusi_super_cepat(limit_per_source: int = 3) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Orkestrasi Two-Stage Parallelization beserta Error Tracking."""
    semua_artikel_mentah: List[Dict[str, Any]] = []
    error_log: List[str] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        pekerjaan_rss = [
            executor.submit(ambil_daftar_artikel_dari_rss, name, url, limit_per_source)
            for name, url in SOURCES.items()
        ]
        for future in concurrent.futures.as_completed(pekerjaan_rss):
            hasil, nama, err = future.result()
            if err:
                error_log.append(f"RSS {nama} : {err}")
            else:
                semua_artikel_mentah.extend(hasil)

    print(f"\n--- Beralih ke Ekstraksi Teks HTML Penuh ({len(semua_artikel_mentah)} artikel) ---")

    hasil_final: List[Dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        pekerjaan_artikel = [
            executor.submit(lengkapi_isi_berita, item)
            for item in semua_artikel_mentah
        ]
        for future in concurrent.futures.as_completed(pekerjaan_artikel):
            item_selesai, nama, err = future.result()
            if err:
                judul_pendek = item_selesai['judul'][:20] + "..."
                error_log.append(f"HTML {nama} ({judul_pendek}) : {err}")
            elif item_selesai["isi_berita"].strip():
                hasil_final.append(item_selesai)

    return hasil_final, error_log

if __name__ == "__main__":
    init_db()
    mulai_total = time.time()

    print("\n============================================================")
    print("MEMULAI PIPELINE EKSTRAKSI DATA BERITA EKONOMI")
    print("============================================================")

    hasil, laporan_error = eksekusi_super_cepat(limit_per_source=2)
    waktu_scraping = time.time() - mulai_total

    print("\n============================================================")
    print(f"HASIL EKSTRAKSI : {len(hasil)} artikel valid (Waktu I/O: {waktu_scraping:.2f} detik)")

    if hasil:
        mulai_db = time.time()
        berita_baru_count = simpan_banyak_berita(hasil)
        waktu_db = time.time() - mulai_db
        print(f"DATABASE PROSES : Menyimpan {berita_baru_count} data baru ({waktu_db:.4f} detik)")
    else:
        print("DATABASE PROSES : Tidak ada data baru yang berhasil diekstrak.")

    if laporan_error:
        print(f"\nLAPORAN KENDALA JARINGAN ({len(laporan_error)} Item Skipped):")
        for err in laporan_error:
            print(f"- {err}")

    total_waktu = time.time() - mulai_total
    print("============================================================")
    print(f"TOTAL EKSEKUSI  : {total_waktu:.2f} detik")
    print("============================================================\n")