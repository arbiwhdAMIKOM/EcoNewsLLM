import re

def bersihkan_teks(teks):
    teks = re.sub(r'^[A-Za-z\s]+\s*\([A-Za-z]+\)\s*[-–]\s*', '', teks)
    teks = re.sub(r'Baca [jJ]uga:.*?(?=\n|$)', '', teks)
    teks = re.sub(r'\s+', ' ', teks).strip()
    return teks