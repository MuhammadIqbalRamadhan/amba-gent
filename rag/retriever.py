# -*- coding: utf-8 -*-
"""
rag/retriever.py — Retriever: Mencari dan Memformat Hasil RAG

=== APA INI? ===
Kalau indexer.py adalah "pustakawan yang menyusun buku di rak",
maka retriever.py adalah "pustakawan yang MENCARIKAN buku untuk kamu".

Retriever menggunakan index yang sudah dibangun oleh Indexer,
mencari chunks yang paling relevan, dan memformat hasilnya
dalam bentuk yang siap dikirim ke LLM.

=== KENAPA DIPISAH DARI INDEXER? ===
Separation of Concerns:
- Indexer  → tanggung jawab: membaca, memecah, mengindex
- Retriever → tanggung jawab: mencari, memformat, menyajikan

Ini juga memudahkan kalau nanti kita mau ganti strategi pencarian
(misalnya dari TF-IDF ke embedding) tanpa mengubah cara kita
memformat dan menyajikan hasilnya.
"""

from rag.indexer import CodebaseIndexer
from core.logger import debug


class CodebaseRetriever:
    """
    Wrapper tingkat tinggi untuk pencarian codebase.

    Menggabungkan:
    1. Indexing (dilakukan sekali saat init)
    2. Search (dilakukan setiap query)
    3. Formatting (hasil dikemas rapi untuk LLM atau terminal)

    Contoh:
        retriever = CodebaseRetriever("./my-project")
        result_text = retriever.search("authenticate", top_k=5)
        # result_text siap dikirim ke LLM sebagai context
    """

    def __init__(self, project_path="."):
        """
        Inisialisasi retriever dan langsung build index.

        Parameter:
        - project_path: root folder project
        """
        # Buat indexer dan langsung index
        self.indexer = CodebaseIndexer(project_path)
        self._index_count = 0
        self.project_path = project_path

    def build_index(self):
        """
        Bangun (atau rebuild) index codebase.

        Return:
        - String pesan status (berapa file/chunk yang di-index)
        """
        debug("Building RAG index...", tag="RAG")
        self._index_count = self.indexer.build_index()
        stats = self.indexer.get_stats()
        debug(
            f"Index selesai: {stats['total_files']} file, "
            f"{stats['total_chunks']} chunk, {stats['total_words']} kata unik",
            tag="RAG"
        )

        return (
            f"Index selesai! "
            f"{stats['total_files']} file, "
            f"{stats['total_chunks']} chunk, "
            f"{stats['total_words']} kata unik."
        )

    def search(self, query, top_k=5):
        """
        Cari kode yang relevan di codebase.

        Parameter:
        - query: teks pencarian (contoh: "fungsi login", "database connection")
        - top_k: jumlah hasil maksimal

        Return:
        - String yang sudah diformat rapi, siap untuk:
          a. Ditampilkan di terminal (untuk debugging)
          b. Dikirim ke LLM sebagai context (sebagai tool result)

        Alur:
        1. Auto-build index kalau belum ada
        2. Cari di index menggunakan TF-IDF
        3. Format hasilnya jadi teks yang informatif
        """
        # Auto-index kalau belum
        if not self.indexer.is_indexed:
            debug("Index belum ada, auto-building...", tag="RAG")
            self.build_index()

        # Lakukan pencarian
        debug(f"Mencari: \"{query}\" (top_k={top_k})", tag="RAG")
        results = self.indexer.search(query, top_k=top_k)
        debug(f"Ditemukan {len(results)} hasil", tag="RAG")

        # Format hasil
        if not results:
            return f"Tidak ditemukan kode yang relevan untuk \"{query}\" di codebase."

        # Bangun output yang informatif
        lines = [
            f"Ditemukan {len(results)} kode yang relevan untuk \"{query}\":\n"
        ]

        for i, r in enumerate(results, 1):
            lines.append(f"--- Hasil {i} (skor: {r['score']}) ---")
            lines.append(f"File: {r['file']} (baris {r['start_line']}-{r['end_line']})")
            lines.append("```")
            # Tampilkan isi kode (potong kalau terlalu panjang)
            content = r["content"]
            if len(content) > 1500:
                content = content[:1500] + "\n... (dipotong)"
            lines.append(content.rstrip())
            lines.append("```")
            lines.append("")  # Baris kosong

        return "\n".join(lines)

    def get_status(self):
        """
        Return status index untuk informasi.
        """
        return self.indexer.get_stats()
