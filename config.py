# -*- coding: utf-8 -*-
"""
config.py — Konfigurasi Amba-Gent

=== MULTI-PROVIDER SUPPORT ===
Sekarang Amba-Gent mendukung banyak LLM provider!
Setiap provider punya API key-nya sendiri:
  - ANTHROPIC: API_KEY + BASE_URL
  - GEMINI: GEMINI_API_KEY

User tidak wajib punya SEMUA API key.
Cukup punya key untuk provider yang mau dipakai.
Validasi dilakukan di masing-masing adapter, bukan di sini.

PELAJARAN:
- Jangan pernah hardcode API key di source code
- Gunakan python-dotenv untuk load dari file .env
- Provider default bisa diset di .env atau override via CLI
"""

import os
from dotenv import load_dotenv

# Load variabel dari file .env ke os.environ
load_dotenv()

# ============================================================
# ANTHROPIC CONFIG (provider default)
# ============================================================
# API key dan base URL untuk Anthropic (atau proxy seperti z.ai)
API_KEY = os.getenv("API_KEY", "")
BASE_URL = os.getenv("BASE_URL", "")
MODEL = os.getenv("MODEL", "glm-5")  # Default model Anthropic

# ============================================================
# GEMINI CONFIG
# ============================================================
# API key dari Google AI Studio (https://aistudio.google.com/apikey)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")  # Default model Gemini

# ============================================================
# PROVIDER DEFAULT
# ============================================================
# Provider mana yang dipakai kalau user tidak specify via CLI
# Bisa di-override dengan: py -3 main.py --provider=gemini
DEFAULT_PROVIDER = os.getenv("PROVIDER", "anthropic")

# ============================================================
# DEBUG MODE
# ============================================================
# Diambil dari .env, default False kalau tidak diset
# os.getenv() return string, jadi kita konversi ke boolean
# "true" (case-insensitive) → True, selain itu → False
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# ============================================================
# VALIDASI RINGAN — Cek minimal ada 1 provider yang terisi
# ============================================================
# Tidak lagi raise error di sini — validasi detail dilakukan
# di masing-masing adapter saat runtime.
# Ini hanya warning awal kalau KEDUA provider tidak diset.
if not API_KEY and not GEMINI_API_KEY:
    print("⚠️  WARNING: Tidak ada API key yang diset di .env!")
    print("   Set API_KEY (Anthropic) atau GEMINI_API_KEY (Gemini) di file .env")
