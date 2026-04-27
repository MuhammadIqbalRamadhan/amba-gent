# -*- coding: utf-8 -*-
"""
core/logger.py — Centralized Debug Logger untuk Amba-Gent

=== APA INI? ===
File ini menyediakan SATU TEMPAT untuk semua debug logging di seluruh project.
Sebelumnya, fungsi print_debug() hanya ada di main.py.
Sekarang kita pindahkan ke sini agar SEMUA module bisa pakai.

=== KENAPA CENTRALIZED? ===
Kalau setiap file punya print_debug() sendiri-sendiri:
- Susah mengubah format log (harus edit banyak file)
- Susah matikan debug (harus edit banyak file)
- Tidak konsisten (tiap file format beda-beda)

Dengan centralized logger:
- Ubah format di 1 tempat → semua module ikut berubah
- Settings DEBUG dari .env → 1x cek, berlaku di mana-mana
- Konsisten: semua log tampil dengan format yang sama

=== CARA PAKAI DI MODULE LAIN ===
    from core.logger import debug

    debug("🔍 Sedang membaca file...", tag="FILE_TOOLS")
    #  DEBUG [FILE_TOOLS] 🔍 Sedang membaca file...

=== KENAPA PAKAI TAG? ===
Tag menunjukkan dari module MANA log itu berasal.
Ini penting untuk debugging — supaya mas Rusdi tahu
log mana dari file mana. Contoh:
    DEBUG [LLM]       → dari core/llm_client.py
    DEBUG [EXECUTOR]  → dari tools/executor.py
    DEBUG [RAG]       → dari rag/retriever.py
    DEBUG [CONTEXT]   → dari core/context.py
    DEBUG [AGENT]     → dari main.py (agent loop)
"""

from rich.console import Console
from config import DEBUG

# Console instance yang di-share oleh semua module
# Kenapa tidak buat Console() baru di setiap file?
# Karena Rich Console menyimpan state (width, color support, dll).
# Lebih efisien dan konsisten pakai satu instance.
console = Console()


def debug(msg, tag="GENERAL"):
    """
    Cetak pesan debug ke terminal (hanya kalau DEBUG=true di .env).

    Parameter:
    - msg: pesan yang ingin ditampilkan (string)
    - tag: label asal module (string), contoh: "LLM", "RAG", "AGENT"

    Format output:
         DEBUG [TAG] pesan di sini

    Warna:
    - Label " DEBUG " → background magenta (mencolok, mudah dikenali)
    - Tag [TAG]       → kuning (menunjukkan asal module)
    - Pesan           → dim italic (tidak mengganggu output utama)

    Contoh:
        debug("Mengirim 5 messages ke LLM", tag="LLM")
        →  DEBUG [LLM] Mengirim 5 messages ke LLM
    """
    if not DEBUG:
        return  # Kalau DEBUG=false di .env, langsung return (tidak cetak apapun)

    console.print(
        f"[dim white on magenta] DEBUG [/dim white on magenta] "
        f"[bold yellow][{tag}][/bold yellow] "
        f"[dim italic]{msg}[/dim italic]"
    )


def debug_separator(label=""):
    """
    Cetak garis pemisah untuk memudahkan pembacaan log debug.

    Contoh output:
        ──────────── AGENT LOOP DIMULAI ────────────

    Berguna untuk memisahkan "sesi" dalam debug log,
    misalnya setiap kali agent loop berputar.
    """
    if not DEBUG:
        return

    if label:
        console.print(f"[dim]{'─' * 12} {label} {'─' * 12}[/dim]")
    else:
        console.print(f"[dim]{'─' * 40}[/dim]")
