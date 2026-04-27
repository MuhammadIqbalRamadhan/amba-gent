# -*- coding: utf-8 -*-
"""
rag/indexer.py — Codebase Indexer untuk RAG

=== APA ITU RAG? ===
RAG = Retrieval-Augmented Generation
Artinya: "CARI dulu informasi yang relevan, BARU jawab pertanyaan"

Tanpa RAG:
    User: "Di mana fungsi authenticate?"
    LLM: "Saya tidak tahu. Saya tidak bisa melihat kode anda." (halusinasi!)

Dengan RAG:
    User: "Di mana fungsi authenticate?"
    RAG: (cari di index) → ditemukan di auth.py baris 45
    LLM: "Fungsi authenticate ada di auth.py baris 45, mas Rusdi."

=== BAGAIMANA RAG BEKERJA? ===

               ┌─────────────┐
               │  INDEXING    │ (dilakukan 1x saat awal)
               │             │
    Codebase ──→ Baca file   │
               │ Pecah chunk │
               │ Hitung TF-IDF│
               │ Simpan index│
               └──────┬──────┘
                      │
               ┌──────▼──────┐
               │  RETRIEVAL  │ (dilakukan setiap query)
               │             │
    Query ────→ Cari match   │
               │ Ranking     │
               │ Return top-K│
               └──────┬──────┘
                      │
               ┌──────▼──────┐
               │  GENERATION │
               │  (LLM)      │
               └─────────────┘

=== PENDEKATAN KITA: TF-IDF (bukan embedding) ===
Ada 2 cara populer untuk RAG:
1. Embedding-based: ubah teks jadi vektor angka, lalu cari vektor terdekat
   - Butuh model embedding (besar, lambat, perlu API tambahan)
   - Lebih akurat untuk pertanyaan "semantic" (makna mirip tapi kata beda)

2. TF-IDF: hitung frekuensi kata, lalu cari dokumen yang paling cocok
   - Ringan, cepat, TANPA perlu model/API tambahan
   - Sangat bagus untuk pencarian KODE (nama fungsi, variabel pasti cocok)
   - Library bawaan Python, tidak perlu install apapun

Untuk codebase search, TF-IDF sudah sangat efektif!
Karena pencarian kode biasanya exact match (nama fungsi, class, variabel).

=== APA ITU TF-IDF? ===
TF  = Term Frequency  = seberapa sering kata muncul DI DOKUMEN INI
IDF = Inverse Document Frequency = seberapa JARANG kata muncul DI SEMUA DOKUMEN

Contoh:
  Kata "import" → muncul di hampir semua file Python → IDF rendah → tidak penting
  Kata "authenticate" → hanya muncul di 1-2 file → IDF tinggi → sangat penting!

Jadi TF-IDF memberi skor tinggi pada kata yang UNIK dan SPESIFIK.
"""

import os
import math                 # Untuk kalkulasi matematika (log, sqrt)
from collections import Counter  # Untuk menghitung frekuensi kata


from core.constants import INDEXABLE_EXTENSIONS, SKIP_DIRS


class CodebaseIndexer:
    """
    Index seluruh codebase untuk pencarian cepat.

    Cara kerja:
    1. Scan semua file di project
    2. Baca setiap file dan pecah per "chunk" (kelompok baris)
    3. Hitung TF-IDF untuk setiap chunk
    4. Simpan index di memory (siap dicari)

    Contoh:
        indexer = CodebaseIndexer("./my-project")
        indexer.build_index()
        results = indexer.search("authenticate", top_k=5)
    """

    def __init__(self, project_path="."):
        """
        Parameter:
        - project_path: root folder project yang akan di-index
        """
        self.project_path = os.path.abspath(project_path)

        # Index utama — list of chunks
        # Setiap chunk = {
        #     "file": "path/to/file.py",
        #     "start_line": 1,
        #     "end_line": 30,
        #     "content": "...",
        #     "tokens": ["import", "os", "def", "main", ...],
        #     "tf": {"import": 0.05, "os": 0.03, ...}
        # }
        self.chunks = []

        # IDF (Inverse Document Frequency) untuk semua kata
        # {"import": 0.2, "authenticate": 2.5, ...}
        self.idf = {}

        # Status
        self.is_indexed = False

    def build_index(self, chunk_size=30):
        """
        Bangun index dari seluruh codebase.

        === INI ADALAH FUNGSI UTAMA INDEXER ===

        Parameter:
        - chunk_size: jumlah baris per chunk (default 30)

        Alur:
        1. Scan semua file di project
        2. Baca setiap file
        3. Pecah jadi chunks (kelompok N baris)
        4. Tokenize setiap chunk (pecah jadi kata-kata)
        5. Hitung TF untuk setiap chunk
        6. Hitung IDF dari semua chunks
        7. Done! Index siap digunakan.

        Return:
        - Jumlah chunks yang di-index

        === KENAPA PECAH JADI CHUNKS? ===
        Karena kalau file utuh dijadikan 1 dokumen:
        - File besar → terlalu banyak informasi → skor pencarian jadi tidak akurat
        - Kalau ditemukan, kita harus kirim SELURUH file ke LLM (boros token)

        Dengan chunking:
        - Pencarian lebih presisi (chunk mana yang paling relevan)
        - Hemat token (kirim hanya chunk yang cocok, bukan seluruh file)
        """
        self.chunks = []

        # ============================================================
        # LANGKAH 1: Scan dan baca semua file
        # ============================================================
        for root, dirs, files in os.walk(self.project_path):
            # Skip folder yang tidak perlu
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            for filename in files:
                _, ext = os.path.splitext(filename)
                if ext not in INDEXABLE_EXTENSIONS:
                    continue

                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, self.project_path)

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                except (PermissionError, OSError):
                    continue

                # ============================================================
                # LANGKAH 2: Pecah file jadi chunks
                # ============================================================
                # Setiap chunk = kelompok `chunk_size` baris
                # Contoh: file 100 baris dengan chunk_size=30
                #   Chunk 1: baris 1-30
                #   Chunk 2: baris 31-60
                #   Chunk 3: baris 61-90
                #   Chunk 4: baris 91-100
                for i in range(0, len(lines), chunk_size):
                    chunk_lines = lines[i:i + chunk_size]
                    content = "".join(chunk_lines)

                    if not content.strip():
                        continue  # Skip chunk kosong

                    # ============================================================
                    # LANGKAH 3: Tokenize (pecah jadi kata-kata)
                    # ============================================================
                    tokens = self._tokenize(content)

                    if not tokens:
                        continue

                    # ============================================================
                    # LANGKAH 4: Hitung TF (Term Frequency) untuk chunk ini
                    # ============================================================
                    tf = self._compute_tf(tokens)

                    self.chunks.append({
                        "file": rel_path,
                        "start_line": i + 1,
                        "end_line": min(i + chunk_size, len(lines)),
                        "content": content,
                        "tokens": tokens,
                        "tf": tf,
                    })

        # ============================================================
        # LANGKAH 5: Hitung IDF (Inverse Document Frequency)
        # ============================================================
        self._compute_idf()

        self.is_indexed = True
        return len(self.chunks)

    def search(self, query, top_k=5):
        """
        Cari chunks yang paling relevan dengan query.

        Parameter:
        - query: teks pencarian (contoh: "authenticate user login")
        - top_k: jumlah hasil maksimal yang dikembalikan

        Return:
        - List of dict, diurutkan dari paling relevan:
          [
              {"file": "auth.py", "start_line": 45, "end_line": 75,
               "content": "...", "score": 2.8},
              ...
          ]

        === CARA KERJA PENCARIAN ===
        1. Tokenize query
        2. Hitung skor TF-IDF untuk setiap chunk terhadap query
        3. Urutkan dari skor tertinggi
        4. Return top-K hasil

        === RUMUS SKOR ===
        Untuk setiap kata di query:
            skor += TF(kata, chunk) * IDF(kata)

        Semakin tinggi skor → chunk semakin relevan dengan query.
        """
        if not self.is_indexed:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Hitung skor untuk setiap chunk
        scored = []
        for chunk in self.chunks:
            score = 0.0
            for token in query_tokens:
                # TF dari chunk ini × IDF global
                tf_value = chunk["tf"].get(token, 0)
                idf_value = self.idf.get(token, 0)
                score += tf_value * idf_value

            if score > 0:
                scored.append({
                    "file": chunk["file"],
                    "start_line": chunk["start_line"],
                    "end_line": chunk["end_line"],
                    "content": chunk["content"],
                    "score": round(score, 4),
                })

        # Urutkan dari skor tertinggi ke terendah
        scored.sort(key=lambda x: x["score"], reverse=True)

        return scored[:top_k]

    # =========================================
    # METHOD INTERNAL (PRIVATE)
    # =========================================

    def _tokenize(self, text):
        """
        Pecah teks menjadi daftar kata (tokens).

        Contoh:
            "def main_func():" → ["def", "main", "func"]

        Kenapa tidak pakai split() biasa?
        Karena kode program punya simbol-simbol yang bukan kata:
            (), {}, =, :, ;, dll
        Kita perlu membuang simbol dan hanya ambil kata bermakna.

        Aturan tokenisasi kita:
        1. Ubah ke lowercase
        2. Ganti semua non-alfanumerik dengan spasi
        3. Split by spasi
        4. Buang kata pendek (< 2 karakter) — biasanya tidak bermakna
        """
        if not text:
            return []

        # Lowercase
        text = text.lower()

        # Ganti non-alfanumerik dengan spasi
        # "def main_func():" → "def main func   "
        cleaned = ""
        for char in text:
            if char.isalnum() or char == "_":
                cleaned += char
            else:
                cleaned += " "

        # Split dan filter kata pendek
        # ["def", "main", "func", ""] → ["def", "main", "func"]
        tokens = [word for word in cleaned.split() if len(word) >= 2]

        return tokens

    def _compute_tf(self, tokens):
        """
        Hitung TF (Term Frequency) untuk list token.

        TF = jumlah kemunculan kata / total jumlah kata

        Contoh:
            tokens = ["import", "os", "import", "sys"]
            TF("import") = 2/4 = 0.5
            TF("os")     = 1/4 = 0.25
            TF("sys")    = 1/4 = 0.25

        Kenapa dibagi total? Agar fair antara chunk pendek dan panjang.
        Chunk 100 kata yang menyebut "auth" 5x → TF = 0.05
        Chunk 10 kata yang menyebut "auth" 5x  → TF = 0.5 (lebih relevan!)
        """
        if not tokens:
            return {}

        total = len(tokens)
        # Counter menghitung frekuensi setiap element
        # Counter(["a", "b", "a"]) → {"a": 2, "b": 1}
        count = Counter(tokens)

        return {word: freq / total for word, freq in count.items()}

    def _compute_idf(self):
        """
        Hitung IDF (Inverse Document Frequency) untuk semua kata di index.

        IDF = log(total_dokumen / dokumen_yang_mengandung_kata)

        Contoh: 100 chunks total
            "import" muncul di 90 chunks → IDF = log(100/90) = 0.046 (rendah, umum)
            "auth"   muncul di 2 chunks  → IDF = log(100/2)  = 1.699 (tinggi, spesifik!)

        Kata yang JARANG muncul punya IDF TINGGI → lebih penting untuk pencarian.
        Kata yang SERING muncul punya IDF RENDAH → kurang membedakan.

        Ini brilliant karena kata-kata umum seperti "import", "def", "return"
        otomatis diberi bobot rendah, sementara nama fungsi/variabel unik
        mendapat bobot tinggi.
        """
        total_docs = len(self.chunks)
        if total_docs == 0:
            return

        # Hitung berapa banyak chunk yang mengandung setiap kata
        # doc_freq["import"] = 90 (muncul di 90 chunks)
        doc_freq = Counter()
        for chunk in self.chunks:
            # set() = ambil kata unik per chunk (jangan hitung ganda)
            unique_tokens = set(chunk["tokens"])
            for token in unique_tokens:
                doc_freq[token] += 1

        # Hitung IDF
        # +1 di denominator untuk menghindari division by zero
        self.idf = {
            word: math.log(total_docs / (freq + 1))
            for word, freq in doc_freq.items()
        }

    def get_stats(self):
        """
        Return statistik index untuk debugging/informasi.
        """
        if not self.is_indexed:
            return {"status": "belum di-index"}

        # Hitung jumlah file unik yang di-index
        unique_files = set(c["file"] for c in self.chunks)

        return {
            "status": "sudah di-index",
            "total_chunks": len(self.chunks),
            "total_files": len(unique_files),
            "total_words": len(self.idf),
            "project_path": self.project_path,
        }
