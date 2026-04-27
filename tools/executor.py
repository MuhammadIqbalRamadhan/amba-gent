# -*- coding: utf-8 -*-
"""
tools/executor.py — Tool Executor (Dispatcher)

=== APA INI? ===
File ini adalah "penghubung" antara LLM dan fungsi-fungsi tool kita.

Ketika LLM bilang: "panggil tool read_file dengan parameter path='main.py'"
Executor yang menerjemahkan itu menjadi pemanggilan fungsi Python yang benar:
    file_tools.read_file(path="main.py")

=== KONSEP: DISPATCHER PATTERN ===
Dispatcher = penerjemah antara "nama" dan "fungsi".
Kita buat dictionary yang memetakan:
    "read_file"      → fungsi read_file()
    "write_file"     → fungsi write_file()
    "list_directory"  → fungsi list_directory()
    "search_code"    → fungsi search_code()

Ini mirip seperti switchboard operator telepon jaman dulu:
Kamu bilang "sambungkan ke nomor 123", operator menyambungkan ke jalur yang benar.

=== KENAPA PAKAI DICTIONARY, BUKAN IF-ELSE? ===
Bisa saja pakai if-else:
    if name == "read_file":
        return read_file(...)
    elif name == "write_file":
        return write_file(...)

Tapi dictionary lebih bersih, lebih cepat, dan lebih mudah di-extend.
Mau tambah tool baru? Cukup tambah 1 baris di dictionary.
"""

from tools.file_tools import read_file, write_file, list_directory
from tools.search_tools import search_code
from rag.retriever import CodebaseRetriever
from core.logger import debug


# ============================================================
# RAG: Inisialisasi retriever (1x, dipakai terus)
# ============================================================
debug("Inisialisasi RAG CodebaseRetriever...", tag="RAG")
_retriever = CodebaseRetriever(".")
debug("RAG retriever siap (index akan dibuild saat pertama kali search)", tag="RAG")


def _search_codebase(query, top_k=5):
    """
    Wrapper function untuk search_codebase tool.
    """
    debug(f"search_codebase dipanggil: query=\"{query}\", top_k={top_k}", tag="RAG")
    result = _retriever.search(query, top_k=top_k)
    debug(f"search_codebase selesai: {len(result)} karakter hasil", tag="RAG")
    return result


# ============================================================
# TOOL REGISTRY — Peta nama tool ke fungsi Python
# ============================================================
# Key   = nama tool (harus sama persis dengan yang di definitions.py)
# Value = referensi ke fungsi Python (TANPA tanda kurung!)
#
# Perhatikan: kita menyimpan REFERENSI fungsi, bukan MEMANGGIL fungsi.
#   read_file     → referensi (benar ✓)
#   read_file()   → memanggil (salah ✗)
# ============================================================

TOOL_REGISTRY = {
    "read_file": read_file,
    "write_file": write_file,
    "list_directory": list_directory,
    "search_code": search_code,
    "search_codebase": _search_codebase,
}

debug(f"Tool registry siap: {list(TOOL_REGISTRY.keys())}", tag="EXECUTOR")


def execute_tool(tool_name, tool_input):
    """
    Eksekusi sebuah tool berdasarkan nama dan inputnya.
    Sekarang dengan debug logging lengkap.
    """
    debug(f"─── Eksekusi Tool Dimulai ───", tag="EXECUTOR")
    debug(f"  Tool name  : {tool_name}", tag="EXECUTOR")
    debug(f"  Tool input : {tool_input}", tag="EXECUTOR")

    # Cek apakah tool terdaftar
    if tool_name not in TOOL_REGISTRY:
        debug(f"  ❌ Tool '{tool_name}' TIDAK DITEMUKAN di registry!", tag="EXECUTOR")
        return f"Error: Tool '{tool_name}' tidak dikenali"

    # Ambil referensi fungsi dari registry
    func = TOOL_REGISTRY[tool_name]
    debug(f"  Fungsi ditemukan: {func.__name__}()", tag="EXECUTOR")

    try:
        # Eksekusi!
        debug(f"  ⏳ Mengeksekusi {tool_name}...", tag="EXECUTOR")
        result = func(**tool_input)

        # Log hasil (potong kalau terlalu panjang)
        result_len = len(result) if isinstance(result, str) else len(str(result))
        debug(f"  ✅ Selesai! Panjang hasil: {result_len} karakter", tag="EXECUTOR")

        if result_len <= 300:
            debug(f"  Hasil lengkap: {result}", tag="EXECUTOR")
        else:
            debug(f"  Preview hasil: {str(result)[:300]}...", tag="EXECUTOR")

        return result

    except TypeError as e:
        debug(f"  ❌ PARAMETER ERROR: {e}", tag="EXECUTOR")
        debug(f"  Ini biasanya karena LLM mengirim parameter yang tidak cocok", tag="EXECUTOR")
        return f"Error parameter tool '{tool_name}': {e}"

    except Exception as e:
        debug(f"  ❌ RUNTIME ERROR: {e}", tag="EXECUTOR")
        return f"Error menjalankan tool '{tool_name}': {e}"
