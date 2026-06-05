import sqlite3

DB_NAME = "econews.db"

def init_db():
    """Membuat tabel berita jika belum ada"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS berita (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sumber TEXT,
            judul TEXT,
            link TEXT UNIQUE,
            waktu_ambil TEXT,
            isi_berita TEXT,
            status_analisis TEXT DEFAULT 'pending'
        )
    ''')
    conn.commit()
    conn.close()

def simpan_berita(berita_item):
    """Menyimpan berita baru, abaikan jika URL sudah ada (deduplikasi)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO berita (sumber, judul, link, waktu_ambil, isi_berita)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            berita_item['sumber'], 
            berita_item['judul'], 
            berita_item['link'], 
            berita_item['waktu_ambil'], 
            berita_item['isi_berita']
        ))
        conn.commit()
        # Jika rowcount > 0 berarti ada data baru yang masuk
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error simpan ke DB: {e}")
        return False
    finally:
        conn.close()