# -*- coding: utf-8 -*-
"""
config.py — Konfigurasi Amba-Gent

PELAJARAN:
- Jangan pernah hardcode API key di source code
- Gunakan python-dotenv untuk load dari file .env
- Kalau .env tidak ada atau key kosong, program langsung error (fail fast)
"""

import os
from dotenv import load_dotenv

# Load variabel dari file .env ke os.environ
load_dotenv()

# Ambil config dari environment variables
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL = os.getenv("MODEL", "glm-5")  # default "glm-5" kalau tidak diset

# DEBUG mode — diambil dari .env, default False kalau tidak diset
# os.getenv() return string, jadi kita konversi ke boolean
# "true" (case-insensitive) → True, selain itu → False
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Validasi: pastikan config penting terisi
if not API_KEY:
    raise ValueError("❌ API_KEY belum diset! Cek file .env kamu.")
if not BASE_URL:
    raise ValueError("❌ BASE_URL belum diset! Cek file .env kamu.")
