# -*- coding: utf-8 -*-
"""
tools/definitions.py — Definisi Tools untuk Amba-Gent

=== APA ITU TOOL CALLING? ===
Tool calling adalah cara agar LLM bisa "bertindak" di dunia nyata.
Normalnya LLM cuma bisa ngobrol (input teks → output teks).
Dengan tool calling, LLM bisa bilang:
    "Saya ingin membaca file main.py"
Dan kita (Python) yang menjalankan aksi itu, lalu kirim hasilnya balik ke LLM.

=== BAGAIMANA CARA KERJANYA? ===
1. Kita definisikan daftar tools dalam format JSON Schema
2. JSON Schema itu kita kirim ke LLM bersamaan dengan pesan user
3. LLM membaca deskripsi tools dan MEMUTUSKAN SENDIRI tool mana yang perlu dipanggil
4. LLM mengembalikan response berisi: "panggil tool X dengan parameter Y"
5. Kita eksekusi tool tersebut di Python
6. Hasil tool dikirim balik ke LLM
7. LLM pakai hasil itu untuk menjawab user

=== APA ITU JSON SCHEMA? ===
JSON Schema adalah format standar untuk mendeskripsikan struktur data.
LLM membaca deskripsi ini untuk mengerti:
- Nama tool apa yang tersedia
- Apa fungsi setiap tool
- Parameter apa yang dibutuhkan
- Tipe data parameter (string, integer, dll)

Contoh JSON Schema sederhana:
{
    "name": "read_file",                    ← nama tool
    "description": "Baca isi sebuah file",  ← LLM baca ini untuk memutuskan
    "input_schema": {                       ← parameter yang diperlukan
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path ke file yang ingin dibaca"
            }
        },
        "required": ["path"]                ← parameter wajib diisi
    }
}
"""


# ============================================================
# DEFINISI SEMUA TOOLS
# ============================================================
# Setiap tool adalah dictionary yang mengikuti format Anthropic API.
# "description" sangat penting! LLM membaca ini untuk memutuskan
# kapan harus menggunakan tool tersebut.
# Tulis deskripsi yang jelas dan spesifik.
# ============================================================

TOOLS = [
    # ----------------------------------------------------------
    # TOOL 1: read_file — Baca isi sebuah file
    # ----------------------------------------------------------
    # Kapan LLM akan pakai tool ini?
    # Ketika user bilang: "lihat isi main.py", "baca file config",
    # "apa isi dari script.js", dll
    {
        "name": "read_file",
        "description": (
            "Baca dan kembalikan seluruh isi sebuah file. "
            "Gunakan tool ini ketika perlu melihat kode atau isi file. "
            "Path bisa relatif (dari working directory) atau absolut."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path ke file yang ingin dibaca. Contoh: 'main.py' atau 'src/utils.py'"
                }
            },
            "required": ["path"]  # Wajib diisi oleh LLM
        }
    },

    # ----------------------------------------------------------
    # TOOL 2: write_file — Tulis/overwrite isi file
    # ----------------------------------------------------------
    # Kapan LLM akan pakai tool ini?
    # Ketika user bilang: "buatkan file baru", "ubah kode di main.py",
    # "tambahkan function baru di utils.py", dll
    #
    # ⚠️ TOOL INI BERBAHAYA — bisa menimpa file!
    # Makanya nanti di main.py kita tambahkan konfirmasi dulu sebelum eksekusi
    {
        "name": "write_file",
        "description": (
            "Tulis content ke sebuah file. Jika file sudah ada, isinya akan ditimpa. "
            "Jika file belum ada, file baru akan dibuat. "
            "PENTING: Selalu tulis SELURUH isi file, bukan hanya bagian yang berubah."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path file yang akan ditulis. Contoh: 'output.py'"
                },
                "content": {
                    "type": "string",
                    "description": "Isi lengkap file yang akan ditulis"
                }
            },
            "required": ["path", "content"]
        }
    },

    # ----------------------------------------------------------
    # TOOL 3: list_directory — List isi sebuah folder
    # ----------------------------------------------------------
    # Kapan LLM akan pakai tool ini?
    # Ketika user bilang: "lihat struktur project", "ada file apa aja",
    # "list isi folder src", dll
    {
        "name": "list_directory",
        "description": (
            "Tampilkan daftar semua file dan folder di dalam sebuah direktori. "
            "Berguna untuk memahami struktur project. "
            "Jika path tidak diberikan, akan menampilkan isi direktori saat ini."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path ke direktori. Default: '.' (direktori saat ini)"
                }
            },
            "required": []  # Path opsional, default ke '.'
        }
    },

    # ----------------------------------------------------------
    # TOOL 4: search_code — Cari teks di dalam file-file project
    # ----------------------------------------------------------
    # Kapan LLM akan pakai tool ini?
    # Ketika user bilang: "cari fungsi calculate", "di mana variabel ini dipakai",
    # "grep TODO di project", dll
    {
        "name": "search_code",
        "description": (
            "Cari teks atau pattern di dalam file-file project (mirip grep). "
            "Mengembalikan nama file, nomor baris, dan isi baris yang cocok. "
            "Berguna untuk menemukan di mana suatu fungsi, variabel, atau teks berada."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Teks atau kata kunci yang dicari"
                },
                "path": {
                    "type": "string",
                    "description": "Folder atau file tempat mencari. Default: '.' (seluruh project)"
                }
            },
            "required": ["query"]
        }
    },

    # ----------------------------------------------------------
    # TOOL 5: search_codebase — Pencarian semantik di seluruh codebase (RAG)
    # ----------------------------------------------------------
    # Kapan LLM akan pakai tool ini?
    # Ketika user bilang: "cari kode tentang authentication",
    # "di mana logika payment dihandle", "tunjukkan kode yang
    # berhubungan dengan database"
    #
    # Bedanya dengan search_code:
    # - search_code     = exact text match (grep) — cari kata persis
    # - search_codebase = semantic search (RAG) — cari berdasarkan relevansi/makna
    #
    # Contoh:
    #   search_code("authenticate")      → cari file yang mengandung kata "authenticate"
    #   search_codebase("login process") → cari kode yang BERHUBUNGAN dengan login
    {
        "name": "search_codebase",
        "description": (
            "Cari kode yang relevan di seluruh codebase menggunakan pencarian semantik (RAG). "
            "Berbeda dengan search_code yang mencari teks persis, tool ini mencari "
            "berdasarkan relevansi/makna. Gunakan untuk memahami arsitektur atau menemukan "
            "kode terkait suatu konsep. Contoh query: 'fungsi authentication', 'database connection'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Deskripsi kode yang dicari. Contoh: 'fungsi login' atau 'error handling'"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Jumlah hasil maksimal. Default: 5"
                }
            },
            "required": ["query"]
        }
    },
]


# ============================================================
# DAFTAR TOOLS YANG BUTUH KONFIRMASI USER
# ============================================================
# Tools ini bisa mengubah/menghapus data, jadi kita minta
# persetujuan user dulu sebelum eksekusi.
# Tools yang hanya "baca" (read_file, list_directory, search_code)
# aman dieksekusi langsung tanpa konfirmasi.
# ============================================================

DANGEROUS_TOOLS = {"write_file"}
# Pakai set (bukan list) karena pengecekan "in" lebih cepat di set.
# set = koleksi unik, dicek dengan hash → O(1)
# list = dicek satu per satu → O(n)
