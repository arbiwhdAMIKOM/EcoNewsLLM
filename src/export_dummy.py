import sqlite3
import json

conn = sqlite3.connect('econews.db')
cursor = conn.cursor()
cursor.execute("SELECT sumber, judul, isi_berita FROM berita LIMIT 3")
rows = cursor.fetchall()
conn.close()

data = [{"sumber": r[0], "judul": r[1], "isi_berita": r[2]} for r in rows]

with open('dummy_data.json', 'w') as f:
    json.dump(data, f, indent=4)