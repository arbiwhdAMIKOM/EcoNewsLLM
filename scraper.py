import feedparser
import requests
from bs4 import BeautifulSoup
import datetime

from database import init_db, simpan_berita

# Daftar sumber RSS yang akan (intinya sumber berita ekonomi Indonesia)
SOURCES = {
    "CNBC Indonesia": "https://www.cnbcindonesia.com/news/rss",
    "Antara News": "https://www.antaranews.com/rss/ekonomi.xml",
    "Detik Finance": "https://finance.detik.com/rss",
    "MarketWatch (REALTIME)": "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines"
}

def scrape_full_text(url, source_name):
    """Fungsi mengambil teks lengkap artikel dengan header browser penuh"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        if source_name == "CNBC Indonesia":
            article_div = soup.find('div', class_='detail_text')
            paragraphs = article_div.find_all('p') if article_div else soup.find_all('p')
        elif "Kontan" in source_name:
            article_div = soup.find('div', class_='txt-article') or soup.find('div', id='body-page')
            paragraphs = article_div.find_all('p') if article_div else soup.find_all('p')
        else:
            # Untuk Detik atau sumber lainnya, ambil paragraf standar
            paragraphs = soup.find_all('p')
            
        full_text = " ".join([p.get_text().strip() for p in paragraphs])
        return full_text[:3000]
    except Exception as e:
        print(f"Gagal scrape teks dari {url}: {e}")
        return ""

def ambil_semua_berita(limit_per_source=3):
    daftar_berita_hari_ini = []
    
    # Header diperketat agar menyerupai browser Mac/Windows asli
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    for name, rss_url in SOURCES.items():
        print(f"\nMenghubungkan ke RSS {name}...")
        
        try:
            response = requests.get(rss_url, headers=headers, timeout=10)
            
            # DIAGNOSTIK: Tampilkan respon server di terminal kamu
            print(f"-> Respon Server {name}: {response.status_code}")
            
            if response.status_code != 200:
                print(f"-> Server {name} memblokir akses (Bukan salah kodemu, tapi sistem keamanan mereka).")
                continue
                
            feed = feedparser.parse(response.content)
            entries = feed.entries[:limit_per_source]
            print(f"-> Menemukan {len(entries)} berita terbaru dari {name}.")
            
            for entry in entries:
                print(f"   - Mengambil konten: {entry.title}")
                isi_lengkap = scrape_full_text(entry.link, name)
                
                berita_item = {
                    "sumber": name,
                    "judul": entry.title,
                    "link": entry.link,
                    "waktu_ambil": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "isi_berita": isi_lengkap
                }
                daftar_berita_hari_ini.append(berita_item)
                
        except Exception as e:
            print(f"Gagal terhubung ke RSS {name}: {e}")
            
    return daftar_berita_hari_ini

if __name__ == "__main__":
    init_db() 

    hasil = ambil_semua_berita(limit_per_source=2)
    print(f"\n=== TOTAL BERITA YANG BERHASIL DIAMBIL: {len(hasil)} ===")

    berita_baru_count = 0
    for item in hasil:
        terimpan = simpan_berita(item)
        if terimpan:
            berita_baru_count += 1

    print(f"-> Berhasil menyimpan {berita_baru_count} berita baru ke database.")