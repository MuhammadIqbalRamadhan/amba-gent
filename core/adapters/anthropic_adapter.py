# -*- coding: utf-8 -*-
"""
core/adapters/anthropic_adapter.py — Adapter untuk Anthropic API (Claude/GLM)

=== APA INI? ===
File ini berisi implementasi adapter untuk provider Anthropic.
Ini adalah "penerjemah" antara format API Anthropic dan format universal Amba-Gent.

Provider Anthropic dipakai untuk:
- Claude (claude-3.5-sonnet, claude-3-opus, dll)
- GLM-5 (via proxy API z.ai)

=== FLOW DATA ===

  1. agent_loop memanggil adapter.send(messages, tools, ...)
  2. AnthropicAdapter men-translate ke format Anthropic API
  3. Anthropic API mengembalikan response (TextBlock, ToolUseBlock)
  4. AnthropicAdapter men-translate response → UnifiedResponse
  5. agent_loop menerima UnifiedResponse (format standar)

=== KENAPA MEMISAHKAN KE ADAPTER? ===
Sebelumnya, logika Anthropic langsung di llm_client.py.
Dengan memisahkannya, kita bisa menambah provider baru (Gemini, OpenAI)
TANPA mengubah agent_loop sama sekali!
"""

from anthropic import Anthropic
from core.adapters.base import BaseLLMAdapter, UnifiedResponse, UnifiedContentBlock
from core.logger import debug


class AnthropicAdapter(BaseLLMAdapter):
    """
    Adapter untuk Anthropic API (Claude, GLM via proxy).

    === PERBEDAAN DENGAN LLMClient LAMA ===
    Hampir sama! Bedanya:
    1. Sekarang return UnifiedResponse, bukan raw Anthropic response
    2. Inherit dari BaseLLMAdapter (ada kontrak yang harus dipenuhi)
    3. Model dan API key diambil dari parameter, bukan global config

    Contoh:
        adapter = AnthropicAdapter(
            api_key="sk-...",
            base_url="https://api.anthropic.com",
            model="claude-3.5-sonnet"
        )
        response = adapter.send(messages, system="...", tools=[...])
        # response.stop_reason = "end_turn" atau "tool_use"
    """

    def __init__(self, api_key, base_url, model):
        """
        Parameter:
        - api_key  : API key untuk Anthropic (atau proxy seperti z.ai)
        - base_url : URL endpoint API
        - model    : nama model (contoh: "glm-5", "claude-3.5-sonnet")
        """
        debug(f"Membuat koneksi ke Anthropic API...", tag="LLM")
        debug(f"  Base URL : {base_url}", tag="LLM")
        debug(f"  Model    : {model}", tag="LLM")

        # Buat instance Anthropic client
        # Client ini yang berkomunikasi langsung dengan server Anthropic
        self.client = Anthropic(api_key=api_key, base_url=base_url)
        self._model = model
        debug("Koneksi Anthropic berhasil dibuat ✓", tag="LLM")

    # === PROPERTY (getter) ===
    # Property adalah cara membuat "variabel read-only" di Python
    # Diakses seperti variabel biasa: adapter.provider_name
    # Tapi sebenarnya memanggil fungsi di belakang layar

    @property
    def provider_name(self) -> str:
        """Mengembalikan nama provider untuk logging."""
        return "anthropic"

    @property
    def model_name(self) -> str:
        """Mengembalikan nama model yang sedang dipakai."""
        return self._model

    def send(self, messages, system="", tools=None, max_tokens=4096) -> UnifiedResponse:
        """
        Kirim messages ke Anthropic API dan kembalikan UnifiedResponse.

        === INI ADALAH JANTUNG ADAPTER ===
        Langkah-langkahnya:
        1. Siapkan parameter untuk Anthropic API
        2. Kirim request
        3. Terima response (format Anthropic: TextBlock, ToolUseBlock)
        4. Convert ke UnifiedResponse (format universal Amba-Gent)
        5. Return

        Kenapa convert?
        Karena agent_loop tidak boleh tahu tentang TextBlock/ToolUseBlock.
        Agent_loop hanya tahu UnifiedContentBlock — format yang SAMA
        untuk semua provider.
        """
        try:
            # === LOG: Apa yang akan dikirim ===
            debug(f"[Anthropic] Mengirim request...", tag="LLM")
            debug(f"  Jumlah messages : {len(messages)}", tag="LLM")
            debug(f"  System prompt   : {len(system)} karakter", tag="LLM")
            debug(f"  Tools disertakan: {len(tools) if tools else 0} tools", tag="LLM")
            debug(f"  Max tokens      : {max_tokens}", tag="LLM")

            # Siapkan parameter API call
            # **params = "unpack" dictionary jadi keyword arguments
            # Contoh: func(**{"a": 1, "b": 2}) sama dengan func(a=1, b=2)
            params = {
                "model": self._model,
                "max_tokens": max_tokens,
                "messages": messages,
            }

            # System prompt opsional — hanya tambahkan kalau ada
            if system:
                params["system"] = system

            # Tools opsional — hanya tambahkan kalau ada
            # Format tools sudah dalam format Anthropic JSON Schema
            # (karena kita pakai format Anthropic sebagai "bahasa standar" tools)
            if tools:
                params["tools"] = tools

            # === KIRIM KE API ===
            debug("Menunggu response dari Anthropic API...", tag="LLM")
            response = self.client.messages.create(**params)

            # === LOG: Response diterima ===
            debug(f"[Anthropic] Response diterima ✓", tag="LLM")
            debug(f"  Stop reason     : {response.stop_reason}", tag="LLM")
            debug(f"  Content blocks  : {len(response.content)} block(s)", tag="LLM")

            # Log detail setiap block
            for i, block in enumerate(response.content):
                if hasattr(block, "text"):
                    preview = block.text[:80] + "..." if len(block.text) > 80 else block.text
                    debug(f"  Block {i}: [TEXT] \"{preview}\"", tag="LLM")
                elif block.type == "tool_use":
                    debug(f"  Block {i}: [TOOL_USE] {block.name}(input={block.input})", tag="LLM")

            # Log token usage
            if hasattr(response, "usage") and response.usage:
                debug(
                    f"  Token usage: input={response.usage.input_tokens}, "
                    f"output={response.usage.output_tokens}",
                    tag="LLM"
                )

            # === CONVERT: Anthropic Response → UnifiedResponse ===
            # Ini adalah inti dari Adapter Pattern!
            # Kita "terjemahkan" format Anthropic ke format universal
            return self._to_unified(response)

        except Exception as e:
            debug(f"❌ Anthropic API ERROR: {e}", tag="LLM")
            raise ConnectionError(f"Gagal menghubungi Anthropic: {e}")

    def send_stream(self, messages, system="", max_tokens=4096):
        """
        Streaming response dari Anthropic API.

        Yield token satu per satu (untuk efek typewriter).
        Streaming TIDAK bisa dipakai untuk tool calling,
        hanya untuk menampilkan jawaban akhir.
        """
        try:
            debug("[Anthropic] Memulai streaming...", tag="LLM")

            params = {
                "model": self._model,
                "max_tokens": max_tokens,
                "messages": messages,
            }

            if system:
                params["system"] = system

            # .stream() mengembalikan context manager
            # yang menghasilkan potongan teks satu per satu
            with self.client.messages.stream(**params) as stream:
                for text in stream.text_stream:
                    yield text  # Kirim token ke pemanggil

            debug("[Anthropic] Streaming selesai ✓", tag="LLM")

        except Exception as e:
            debug(f"❌ Anthropic Streaming ERROR: {e}", tag="LLM")
            raise ConnectionError(f"Gagal streaming dari Anthropic: {e}")

    # =========================================
    # HELPER: Convert Anthropic → Unified
    # =========================================

    def _to_unified(self, response) -> UnifiedResponse:
        """
        Convert Anthropic API response → UnifiedResponse.

        === MAPPING FORMAT ===

        Anthropic TextBlock      → UnifiedContentBlock(type="text", text="...")
        Anthropic ToolUseBlock   → UnifiedContentBlock(type="tool_use", tool_name=..., ...)

        Anthropic stop_reason:
          "end_turn"  → "end_turn"  (langsung pass-through)
          "tool_use"  → "tool_use"  (langsung pass-through)

        Kenapa Anthropic stop_reason bisa langsung dipakai?
        Karena format Anthropic kita jadikan "standar" —
        adapter lain (Gemini) yang harus menyesuaikan ke format ini.
        """
        # Convert setiap content block
        unified_blocks = []
        for block in response.content:
            if hasattr(block, "text"):
                # TextBlock → text content
                unified_blocks.append(UnifiedContentBlock(
                    type="text",
                    text=block.text,
                ))
            elif block.type == "tool_use":
                # ToolUseBlock → tool_use content
                unified_blocks.append(UnifiedContentBlock(
                    type="tool_use",
                    tool_name=block.name,
                    tool_input=block.input,
                    tool_use_id=block.id,
                ))

        # Ambil token usage
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage") and response.usage:
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

        return UnifiedResponse(
            stop_reason=response.stop_reason,  # "end_turn" atau "tool_use"
            content=unified_blocks,
            raw_response=response,              # Simpan response asli untuk debug
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
