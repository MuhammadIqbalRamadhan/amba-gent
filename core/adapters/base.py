# -*- coding: utf-8 -*-
"""
core/adapters/base.py — Base Class & Unified Response

=== APA INI? ===
File ini mendefinisikan "kontrak" (interface) yang HARUS dipatuhi
oleh semua adapter LLM (Anthropic, Gemini, OpenAI, dll).

Ibarat kontrak kerja:
  "Siapapun yang jadi adapter, WAJIB punya method send() dan send_stream(),
   dan WAJIB mengembalikan data dalam format UnifiedResponse."

=== KENAPA PAKAI DATACLASS? ===
Dataclass adalah cara Python untuk membuat class yang fokus menyimpan data.
Tidak perlu menulis __init__() manual — Python membuatnya otomatis.

Contoh:
    @dataclass
    class Buku:
        judul: str
        halaman: int

    b = Buku(judul="Python 101", halaman=200)
    print(b.judul)  # "Python 101"

=== KENAPA PAKAI ABC (Abstract Base Class)? ===
ABC adalah cara Python untuk membuat "interface" — class yang TIDAK BISA
di-instantiate langsung, tapi harus di-inherit dan semua method
abstractnya WAJIB diimplementasi oleh child class.

Kalau child class lupa implement method → Python langsung error saat startup!
Ini mencegah bug di runtime.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Generator
from abc import ABC, abstractmethod


# ============================================================
# UNIFIED RESPONSE — Format standar untuk semua provider
# ============================================================

@dataclass
class UnifiedContentBlock:
    """
    Satu "blok" konten dari response LLM.

    Ada 2 jenis blok:
    1. TEXT block    → LLM menulis teks jawaban
       type="text", text="Halo mas Rusdi..."

    2. TOOL_USE block → LLM ingin memanggil tool
       type="tool_use", tool_name="read_file", tool_input={"path": "main.py"}, tool_use_id="abc123"

    Kenapa pakai block?
    Karena dalam 1 response, LLM bisa mengembalikan CAMPURAN teks + tool call.
    Contoh: "Baik, saya akan baca file tersebut." + [tool_use: read_file]
    """
    type: str                              # "text" atau "tool_use"
    text: Optional[str] = None             # Isi teks (kalau type="text")
    tool_name: Optional[str] = None        # Nama tool (kalau type="tool_use")
    tool_input: Optional[dict] = None      # Parameter tool (kalau type="tool_use")
    tool_use_id: Optional[str] = None      # ID unik tool call (untuk mengirim result)


@dataclass
class UnifiedResponse:
    """
    Response standar dari semua adapter LLM.

    Ini adalah "bahasa universal" antara adapter dan agent_loop.
    Agent_loop HANYA berbicara dalam bahasa UnifiedResponse,
    sehingga tidak peduli apakah di belakangnya Anthropic atau Gemini.

    Fields:
    - stop_reason: "end_turn" (jawaban selesai) atau "tool_use" (mau panggil tool)
    - content: list of UnifiedContentBlock
    - raw_response: response asli dari provider (untuk debugging/logging)
    - usage: informasi penggunaan token

    === FLOW ===
    Anthropic response → AnthropicAdapter.send() → UnifiedResponse → agent_loop
    Gemini response    → GeminiAdapter.send()    → UnifiedResponse → agent_loop
    """
    stop_reason: str                       # "end_turn" atau "tool_use"
    content: List[UnifiedContentBlock]     # List blok konten
    raw_response: object = None            # Response asli (untuk debug)
    input_tokens: int = 0                  # Jumlah token input
    output_tokens: int = 0                 # Jumlah token output


# ============================================================
# BASE ADAPTER — Interface/Kontrak untuk semua adapter
# ============================================================

class BaseLLMAdapter(ABC):
    """
    Abstract Base Class untuk semua LLM adapter.

    === ATURAN ===
    Setiap adapter (Anthropic, Gemini, dll) WAJIB:
    1. Inherit dari class ini
    2. Implement method send()
    3. Implement method send_stream()

    Kalau lupa implement → TypeError saat instantiate!

    === PROPERTY ===
    - provider_name: nama provider (untuk logging)
    - model_name: nama model yang sedang dipakai

    === CONTOH IMPLEMENTASI ===
    class MyAdapter(BaseLLMAdapter):
        @property
        def provider_name(self):
            return "my-llm"

        def send(self, messages, system, tools, max_tokens):
            # ... implementasi ...
            return UnifiedResponse(...)

        def send_stream(self, messages, system, max_tokens):
            # ... implementasi ...
            yield "token"
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Nama provider LLM (contoh: 'anthropic', 'gemini')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Nama model yang sedang dipakai (contoh: 'glm-5', 'gemini-2.0-flash')."""
        pass

    @abstractmethod
    def send(self, messages, system="", tools=None, max_tokens=4096) -> UnifiedResponse:
        """
        Kirim messages ke LLM dan dapatkan response lengkap (non-streaming).

        Parameter:
        - messages : list percakapan [{"role": "user", "content": "..."}]
        - system   : system prompt (instruksi untuk LLM)
        - tools    : list definisi tools (format Anthropic JSON Schema)
        - max_tokens: batas panjang jawaban

        Return:
        - UnifiedResponse yang sudah distandarisasi

        PENTING: Parameter `tools` menggunakan format Anthropic.
        Setiap adapter bertanggung jawab men-translate ke format provider-nya masing-masing.
        """
        pass

    @abstractmethod
    def send_stream(self, messages, system="", max_tokens=4096) -> Generator[str, None, None]:
        """
        Kirim messages ke LLM dan terima jawaban secara streaming.

        Parameter:
        - messages : list percakapan
        - system   : system prompt
        - max_tokens: batas panjang jawaban

        Yield:
        - String token, satu per satu
        """
        pass
