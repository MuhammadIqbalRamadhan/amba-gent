# -*- coding: utf-8 -*-
"""
core/logger.py -- Centralized Debug Logger untuk Amba-Gent

Semua debug log di seluruh project menggunakan fungsi debug() dari file ini.
Dikontrol oleh DEBUG=true/false di .env.

Tag menunjukkan asal module:
    [LLM]       -> core/llm_client.py
    [EXECUTOR]  -> tools/executor.py
    [RAG]       -> rag/retriever.py
    [CONTEXT]   -> core/context.py
    [AGENT]     -> main.py (agent loop)
    [STARTUP]   -> main.py (inisialisasi)
    [SESSION]   -> core/session.py
    [PROJECT]   -> core/project.py
    [FILE]      -> tools/file_tools.py
    [STREAM]    -> main.py (streaming display)
"""

import sys
import os

# Force UTF-8 output di Windows agar emoji tidak error
# Windows legacy terminal pakai cp1252 yang tidak support emoji
if sys.platform == "win32":
    # Set environment variable agar Python pakai UTF-8
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    # Reconfigure stdout/stderr ke UTF-8 kalau memungkinkan
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from rich.console import Console
from config import DEBUG

# Console instance yang di-share oleh semua module
# force_terminal=True memastikan Rich selalu output warna
# highlight=False mencegah Rich auto-highlight angka/URL yang tidak diinginkan
console = Console(force_terminal=True, highlight=False)


def debug(msg, tag="GENERAL"):
    """
    Cetak pesan debug ke terminal (hanya kalau DEBUG=true di .env).

    Parameter:
    - msg: pesan yang ingin ditampilkan (string)
    - tag: label asal module (string), contoh: "LLM", "RAG", "AGENT"

    Contoh:
        debug("Mengirim 5 messages ke LLM", tag="LLM")
        ->  DEBUG [LLM] Mengirim 5 messages ke LLM
    """
    if not DEBUG:
        return

    # Sanitize msg: replace problematic characters for legacy Windows terminals
    safe_msg = _sanitize_for_terminal(msg)

    console.print(
        f"[dim white on magenta] DEBUG [/dim white on magenta] "
        f"[bold yellow][{tag}][/bold yellow] "
        f"[dim italic]{safe_msg}[/dim italic]"
    )


def debug_separator(label=""):
    """Cetak garis pemisah untuk memudahkan pembacaan log debug."""
    if not DEBUG:
        return

    if label:
        safe_label = _sanitize_for_terminal(label)
        console.print(f"[dim]{'-' * 12} {safe_label} {'-' * 12}[/dim]")
    else:
        console.print(f"[dim]{'-' * 40}[/dim]")


def _sanitize_for_terminal(text):
    """
    Bersihkan karakter yang tidak bisa di-encode oleh Windows legacy terminal.

    Windows cmd/PowerShell sering pakai encoding cp1252 yang tidak support:
    - Emoji (checkmark, arrows, dll)
    - Box-drawing characters
    - Beberapa karakter Unicode lainnya

    Solusi: encode/decode dengan errors='replace' → karakter bermasalah
    diganti dengan '?' supaya tidak crash.
    """
    try:
        # Coba encode ke terminal encoding, replace yang gagal
        return text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
            sys.stdout.encoding or "utf-8", errors="replace"
        )
    except Exception:
        # Kalau masih gagal, fallback ke ASCII
        return text.encode("ascii", errors="replace").decode("ascii")
