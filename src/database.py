import os
import json
import sqlite3
from typing import List, Dict, Any

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "econews.db")

def get_connection():
    """Membuat koneksi ke SQLite dengan toleransi antrean (timeout) yang tinggi."""
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Membuat tabel berita dengan skema terintegrasi (Hulu + Hilir AI)."""
    query = """
    CREATE TABLE IF NOT EXISTS berita (
        url TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        source TEXT,
        content TEXT,
        published_at TEXT,
        
        -- Hasil Analisis AI Gemini
        summary TEXT,
        main_category TEXT,
        sentiment TEXT,
        impact_level TEXT,
        impact_score INTEGER,
        main_cause TEXT,
        affected_markets TEXT, -- Disimpan sebagai JSON String
        impact_explanation TEXT,
        confidence_score REAL,
        
        -- Manajemen Status Pipeline
        status_analisis TEXT DEFAULT 'pending'
    );
    """
    conn = get_connection()
    try:
        conn.execute(query)
        conn.commit()
    finally:
        conn.close()

def simpan_banyak_berita(berita_list: List[Dict[str, Any]]) -> int:
    """Menyimpan data mentah dari scraper. Proteksi URL Unik aktif (Anti-Duplikat)."""
    query = """
    INSERT OR IGNORE INTO berita (title, source, url, content, published_at, status_analisis)
    VALUES (?, ?, ?, ?, ?, 'pending')
    """
    conn = get_connection()
    berita_baru = 0
    try:
        cursor = conn.cursor()
        for item in berita_list:
            cursor.execute(query, (
                item.get("title"),
                item.get("source"),
                item.get("url"),
                item.get("content"),
                item.get("published_at")
            ))
            if cursor.rowcount > 0:
                berita_baru += 1
        conn.commit()
        return berita_baru
    finally:
        conn.close()

def update_analisis_berita(url: str, ai_result: Dict[str, Any]):
    """Memperbarui baris berita dengan hasil ekstraksi terstruktur dari Gemini."""
    query = """
    UPDATE berita SET 
        summary = ?,
        main_category = ?,
        sentiment = ?,
        impact_level = ?,
        impact_score = ?,
        main_cause = ?,
        affected_markets = ?, -- Hasil dumps JSON string
        impact_explanation = ?,
        confidence_score = ?,
        status_analisis = ?
    WHERE url = ?
    """

    status = ai_result.get("status", "processed")
    
    affected_markets_json = json.dumps(ai_result.get("affected_markets", []))

    conn = get_connection()
    try:
        conn.execute(query, (
            ai_result.get("summary"),
            ai_result.get("main_category"),
            ai_result.get("sentiment"),
            ai_result.get("impact_level"),
            ai_result.get("impact_score"),
            ai_result.get("main_cause"),
            affected_markets_json,
            ai_result.get("impact_explanation"),
            ai_result.get("confidence_score"),
            status,
            url
        ))
        conn.commit()
    finally:
        conn.close()

def ambil_data_untuk_dashboard() -> List[Dict[str, Any]]:
    """Mengambil data siap pakai untuk visualisasi dashboard Streamlit."""
    query = """
    SELECT * FROM berita 
    WHERE status_analisis = 'processed' 
    AND impact_level IN ('sedang', 'tinggi')
    ORDER BY published_at DESC
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Rekonstruksi data string JSON kembali menjadi List Python asli
        hasil = []
        for row in rows:
            data = dict(row)
            try:
                data["affected_markets"] = json.loads(data["affected_markets"])
            except:
                data["affected_markets"] = []
            hasil.append(data)
            
        return hasil
    finally:
        conn.close()