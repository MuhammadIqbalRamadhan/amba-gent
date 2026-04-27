# -*- coding: utf-8 -*-
"""
tools/search_tools.py — Fungsi untuk mencari kode di dalam project

=== APA INI? ===
Tool ini seperti Ctrl+Shift+F di VS Code — mencari teks di seluruh project.
Ketika LLM ingin tahu "di mana fungsi X didefinisikan" atau "file mana yang
menggunakan variabel Y", LLM akan memanggil tool search_code.

=== KENAPA INI PENTING UNTUK AGENT? ===
Agent yang baik perlu bisa "menjelajahi" codebase, bukan cuma baca file
yang di-specify user. Tanpa search, agent hanya bisa baca file yang dia
sudah tahu namanya. Dengan search, agent bisa MENEMUKAN file yang relevan.
"""

import os  # Untuk operasi file system


from core.constants import SEARCHABLE_EXTENSIONS, SKIP_DIRS


def search_code(query, path="."):
    """
    Cari teks di dalam file-file project (mirip grep/Ctrl+Shift+F).

    Parameter:
    - query: teks yang dicari (case-insensitive)
    - path: folder tempat mencari (default: '.' = seluruh project)

    Return:
    - String berisi daftar hasil pencarian (file, baris, isi)
    - Maksimal 30 hasil agar tidak terlalu panjang untuk LLM

    Contoh output:
        Ditemukan 3 hasil untuk "def main":

        📄 main.py (baris 34):
           def main():

        📄 tools/file_tools.py (baris 15):
           def main_handler():

    PELAJARAN:
    - os.walk() = menjelajahi folder secara rekursif (masuk ke subfolder)
    - enumerate() = loop dengan nomor index (untuk nomor baris)
    - case-insensitive search = cocokkan huruf besar/kecil
    """
    try:
        abs_path = os.path.abspath(path)

        if not os.path.exists(abs_path):
            return f"Error: Path '{path}' tidak ditemukan"

        results = []       # Menampung semua hasil
        max_results = 30   # Batas maksimal hasil (agar tidak terlalu panjang)

        # ----------------------------------------------------------
        # os.walk() adalah cara Python menjelajahi folder secara rekursif.
        # Dia mengembalikan 3 nilai untuk setiap folder yang dikunjungi:
        #   root    = path folder saat ini
        #   dirs    = list subfolder di dalam root
        #   files   = list file di dalam root
        #
        # Contoh kalau struktur:
        #   project/
        #   ├── main.py
        #   └── core/
        #       └── llm_client.py
        #
        # Walk akan mengunjungi:
        #   1. root="project", dirs=["core"], files=["main.py"]
        #   2. root="project/core", dirs=[], files=["llm_client.py"]
        # ----------------------------------------------------------
        for root, dirs, files in os.walk(abs_path):

            # Skip folder yang tidak perlu (in-place modification)
            # dirs[:] = ... akan memodifikasi list dirs secara langsung,
            # sehingga os.walk() tidak akan masuk ke folder yang di-skip
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            # Cek setiap file di folder ini
            for filename in files:
                # Ambil ekstensi file (contoh: ".py", ".js")
                _, ext = os.path.splitext(filename)

                # Skip file yang bukan kode
                if ext not in SEARCHABLE_EXTENSIONS:
                    continue

                # Baca file dan cari query
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        # enumerate(f, 1) = baca baris per baris, mulai dari nomor 1
                        for line_num, line in enumerate(f, 1):
                            # Cek apakah query ada di baris ini (case-insensitive)
                            if query.lower() in line.lower():
                                # Buat path relatif agar lebih pendek
                                rel_path = os.path.relpath(filepath, abs_path)

                                results.append({
                                    "file": rel_path,
                                    "line": line_num,
                                    "content": line.rstrip()  # Hapus whitespace di akhir baris
                                })

                                # Berhenti kalau sudah cukup hasil
                                if len(results) >= max_results:
                                    break

                except (PermissionError, UnicodeDecodeError):
                    # Skip file yang tidak bisa dibaca
                    continue

            # Cek lagi setelah setiap folder
            if len(results) >= max_results:
                break

        # ----------------------------------------------------------
        # FORMAT HASIL
        # ----------------------------------------------------------
        if not results:
            return f"Tidak ditemukan hasil untuk \"{query}\" di {path}"

        # Bangun string output
        output_lines = [f"Ditemukan {len(results)} hasil untuk \"{query}\":\n"]

        for r in results:
            output_lines.append(f"  {r['file']} (baris {r['line']}):")
            output_lines.append(f"    {r['content']}")
            output_lines.append("")  # Baris kosong sebagai separator

        if len(results) >= max_results:
            output_lines.append(f"... (hasil dipotong, maksimal {max_results})")

        return "\n".join(output_lines)

    except Exception as e:
        return f"Error saat mencari '{query}': {e}"
