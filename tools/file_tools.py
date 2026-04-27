# -*- coding: utf-8 -*-
"""
tools/file_tools.py — Fungsi-fungsi untuk membaca & menulis file

=== APA INI? ===
File ini berisi IMPLEMENTASI NYATA dari tools yang sudah kita definisikan
di definitions.py. Kalau definitions.py itu "menu restoran" (deskripsi),
maka file ini adalah "dapur" (yang benar-benar memasak).

Ketika LLM bilang "panggil read_file dengan path='main.py'",
Python akan menjalankan fungsi read_file() di file ini.

=== KENAPA DIPISAH DARI DEFINITIONS? ===
Separation of Concerns:
- definitions.py  → untuk LLM (deskripsi tools dalam JSON Schema)
- file_tools.py   → untuk Python (implementasi fungsi yang sebenarnya)
Kalau mau tambah tool baru, edit 2 file: definisi + implementasi.
"""

import os      # Untuk operasi file system (cek file ada, path, dll)
import difflib  # () Untuk generate diff preview
from core.logger import debug


def read_file(path):
    """
    Baca isi sebuah file dan kembalikan sebagai string.

    Parameter:
    - path: lokasi file (relatif atau absolut)

    Return:
    - String isi file, atau pesan error kalau file tidak ditemukan

    Contoh pemakaian:
        result = read_file("main.py")
        # result = "import typer\nimport os\n..."

    PELAJARAN:
    - Selalu gunakan encoding='utf-8' agar karakter Indonesia/emoji tidak error
    - Selalu tangkap exception (FileNotFoundError, dll) — jangan biarkan program crash
    - Return error sebagai string (bukan raise exception) agar LLM bisa membaca
      pesan error dan mencoba cara lain
    """
    try:
        # Konversi path relatif ke path absolut agar tidak bingung
        # Contoh: "main.py" → "C:/laragon/www/amba-gent/main.py"
        abs_path = os.path.abspath(path)

        # Cek apakah file ada
        if not os.path.exists(abs_path):
            return f"Error: File '{path}' tidak ditemukan di {abs_path}"

        # Cek apakah itu benar-benar file (bukan folder)
        if not os.path.isfile(abs_path):
            return f"Error: '{path}' adalah direktori, bukan file"

        # Baca isi file
        # 'r' = read mode (hanya baca, tidak bisa tulis)
        # encoding='utf-8' = standar encoding untuk teks modern
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()

        return content

    except PermissionError:
        return f"Error: Tidak punya izin untuk membaca file '{path}'"
    except Exception as e:
        return f"Error membaca file '{path}': {e}"


def write_file(path, content):
    """
    Tulis content ke sebuah file.

    Parameter:
    - path: lokasi file yang akan ditulis
    - content: isi lengkap yang akan ditulis ke file

    Return:
    - Pesan sukses atau error

    ⚠️ PERINGATAN:
    Fungsi ini akan MENIMPA seluruh isi file jika file sudah ada!
    Makanya di definitions.py, write_file masuk kategori DANGEROUS_TOOLS
    dan butuh konfirmasi user dulu.

    PELAJARAN:
    - os.makedirs() dengan exist_ok=True untuk buat folder parent otomatis
    - Selalu tulis dengan encoding='utf-8'
    """
    try:
        abs_path = os.path.abspath(path)

        # () Diff Preview — kalau file sudah ada, tunjukkan perubahan
        diff_text = ""
        if os.path.exists(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    old_content = f.read()
                # Generate diff hanya kalau isi berubah
                if old_content != content:
                    diff_text = generate_diff(old_content, content, path)
                    debug(f"Diff generated untuk {path}", tag="FILE")
                else:
                    debug(f"File {path} tidak berubah, skip write", tag="FILE")
                    return f"File '{path}' tidak berubah — isi sama persis."
            except Exception:
                pass  # Gagal baca file lama, lanjut saja

        # Buat folder parent kalau belum ada
        parent_dir = os.path.dirname(abs_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        # Tulis ke file
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)

        debug(f"File ditulis: {abs_path} ({len(content)} karakter)", tag="FILE")

        # Sertakan diff di response agar user/LLM bisa lihat perubahannya
        result = f"Berhasil menulis ke file '{path}' ({len(content)} karakter)"
        if diff_text:
            result += f"\n\n=== DIFF PREVIEW ===\n{diff_text}"
        return result

    except PermissionError:
        return f"Error: Tidak punya izin untuk menulis ke '{path}'"
    except Exception as e:
        return f"Error menulis file '{path}': {e}"


def list_directory(path="."):
    """
    List semua file dan folder di dalam sebuah direktori.

    Parameter:
    - path: lokasi direktori (default: '.' = direktori saat ini)

    Return:
    - String berisi daftar isi direktori, satu per baris
    - Folder ditandai dengan [DIR], file ditandai dengan ukurannya

    Contoh output:
        [DIR]  core/
        [DIR]  tools/
        [FILE] main.py (2.5 KB)
        [FILE] config.py (0.7 KB)

    PELAJARAN:
    - os.listdir() = daftar nama file/folder di sebuah direktori
    - os.path.isdir() = cek apakah sesuatu adalah folder
    - os.path.getsize() = ukuran file dalam bytes
    - sorted() = mengurutkan list (folder dulu, baru file)
    """
    try:
        abs_path = os.path.abspath(path)

        if not os.path.exists(abs_path):
            return f"Error: Direktori '{path}' tidak ditemukan"

        if not os.path.isdir(abs_path):
            return f"Error: '{path}' adalah file, bukan direktori"

        # Ambil daftar isi direktori
        entries = os.listdir(abs_path)

        if not entries:
            return f"Direktori '{path}' kosong"

        # Pisahkan folder dan file, lalu format masing-masing
        lines = []

        # Urutkan: folder dulu (abjad), lalu file (abjad)
        dirs = sorted([e for e in entries if os.path.isdir(os.path.join(abs_path, e))])
        files = sorted([e for e in entries if os.path.isfile(os.path.join(abs_path, e))])

        # Tambahkan folder (skip folder yang biasa di-ignore)
        skip_dirs = {".git", "__pycache__", "node_modules", ".history", "venv", ".venv"}
        for d in dirs:
            if d in skip_dirs:
                continue  # Lewati folder yang tidak penting
            lines.append(f"[DIR]  {d}/")

        # Tambahkan file dengan ukurannya
        for f in files:
            filepath = os.path.join(abs_path, f)
            size = os.path.getsize(filepath)

            # Format ukuran agar mudah dibaca manusia
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / (1024 * 1024):.1f} MB"

            lines.append(f"[FILE] {f} ({size_str})")

        # Gabungkan semua baris dengan newline
        # Header menunjukkan path lengkap untuk kejelasan
        header = f"Isi direktori: {abs_path}\n"
        return header + "\n".join(lines)

    except PermissionError:
        return f"Error: Tidak punya izin untuk membaca direktori '{path}'"
    except Exception as e:
        return f"Error membaca direktori '{path}': {e}"


def generate_diff(old_content, new_content, filename="file"):
    """
    Generate unified diff antara konten lama vs konten baru.

    === APA ITU DIFF? ===
    Diff = tampilan perubahan antara 2 versi file.
    Mirip seperti yang kamu lihat di GitHub atau git diff.

    Format:
    - Baris yang dihapus ditandai dengan "-" (merah di terminal)
    - Baris yang ditambah ditandai dengan "+" (hijau di terminal)
    - Baris yang tidak berubah ditandai dengan " " (spasi)

    Contoh output:
        --- file.py (sebelum)
        +++ file.py (sesudah)
        @@ -1,3 +1,4 @@
         import os
        -import sys
        +import sys
        +import json
         def main():

    Parameter:
    - old_content: isi file sebelum diubah
    - new_content: isi file sesudah diubah
    - filename: nama file (untuk header diff)

    Return:
    - String diff dalam format unified, atau pesan "tidak ada perubahan"

    === LIBRARY DIFFLIB ===
    difflib adalah library BAWAAN Python (tidak perlu pip install).
    unified_diff() menghasilkan format yang sama seperti `git diff`.
    """
    # splitlines(keepends=True) = pecah per baris, pertahankan newline
    # Ini penting agar diff bisa menampilkan baris mana yang berubah
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    # unified_diff() menghasilkan generator (iterable) baris-baris diff
    # fromfile/tofile = label untuk header
    # n=3 = tampilkan 3 baris context di sekitar perubahan
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"{filename} (sebelum)",
        tofile=f"{filename} (sesudah)",
        n=3,  # jumlah baris context
    )

    # Gabungkan semua baris diff jadi satu string
    diff_text = "".join(diff)

    if not diff_text:
        return "(tidak ada perubahan)"

    # Batasi panjang diff agar tidak terlalu panjang
    max_diff_len = 3000
    if len(diff_text) > max_diff_len:
        diff_text = diff_text[:max_diff_len] + "\n... (diff terlalu panjang, dipotong)"

    return diff_text

