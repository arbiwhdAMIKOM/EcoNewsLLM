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
        status_analisis TEXT DEFAULT 'pending',
        hasil_analisis TEXT
        )
    ''')
    conn.commit()
    conn.close()

def simpan_banyak_berita(list_berita):
    """Menyimpan banyak berita sekaligus (Bulk Insert) untuk performa maksimal"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    berita_baru_count = 0
    
    try:
        for item in list_berita:
            cursor.execute('''
                INSERT OR IGNORE INTO berita (sumber, judul, link, waktu_ambil, isi_berita)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                item['sumber'], 
                item['judul'], 
                item['link'], 
                item['waktu_ambil'], 
                item['isi_berita']
            ))
            # Jika ada row yang terpengaruh, berarti itu data baru (bukan duplikat)
            if cursor.rowcount > 0:
                berita_baru_count += 1
                
        # Commit (simpan permanen) semua data sekaligus di akhir
        conn.commit()
        return berita_baru_count
    except Exception as e:
        print(f"Error Bulk Insert ke DB: {e}")
        return 0
    finally:
        conn.close()