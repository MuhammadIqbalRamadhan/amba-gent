# -*- coding: utf-8 -*-
"""
core/llm_client.py — Wrapper untuk berkomunikasi dengan LLM

=== PERUBAHAN DI PHASE 3 ===
Di Phase 1, class ini cuma kirim pesan biasa (teks masuk, teks keluar).
Sekarang kita tambahkan kemampuan TOOL CALLING:
- Method send() sekarang menerima parameter tools=[]
- Method baru: send_with_tools() — kirim pesan + daftar tools yang tersedia

=== ALUR TOOL CALLING ===
1. Kita kirim messages + tools ke LLM
2. LLM bisa merespons dengan 2 cara:
   a. "end_turn"  → LLM menjawab dengan teks biasa (selesai)
   b. "tool_use"  → LLM minta kita eksekusi tool tertentu (belum selesai!)
3. Kalau "tool_use", kita perlu:
   - Eksekusi tool di Python
   - Kirim hasilnya balik ke LLM
   - LLM melanjutkan proses
4. Loop ini bisa berulang: LLM bisa panggil banyak tools sebelum akhirnya menjawab
"""

from anthropic import Anthropic
from config import API_KEY, BASE_URL, MODEL
from core.logger import debug


class LLMClient:
    """
    Wrapper class untuk Anthropic API — dengan Tool Calling + debug logging.
    """

    def __init__(self):
        # Buat koneksi ke Anthropic API (1x saja, reuse terus)
        debug("Membuat koneksi ke Anthropic API...", tag="LLM")
        debug(f"  Base URL : {BASE_URL}", tag="LLM")
        debug(f"  Model    : {MODEL}", tag="LLM")
        self.client = Anthropic(api_key=API_KEY, base_url=BASE_URL)
        self.model = MODEL
        debug("Koneksi berhasil dibuat ✓", tag="LLM")

    def send(self, messages, system="", tools=None, max_tokens=4096):
        """
        Kirim messages ke LLM — sekarang dengan debug logging lengkap.

        Parameter:
        - messages : list percakapan
        - system   : system prompt
        - tools    : list definisi tools
        - max_tokens: batas panjang jawaban

        Return:
        - response object dari Anthropic API

        === YANG BERUBAH DARI PHASE 1 ===
        Dulu: client.messages.create(model, max_tokens, system, messages)
        Sekarang: + tools parameter

        === TENTANG RESPONSE ===
        Response punya 2 field penting:
        - response.stop_reason:
            "end_turn"  = LLM selesai menjawab (ada teks jawaban)
            "tool_use"  = LLM ingin memanggil tool (belum selesai!)
        - response.content:
            List berisi "blok" konten. Setiap blok bisa:
            - TextBlock  → teks jawaban (type="text")
            - ToolUseBlock → permintaan tool (type="tool_use")
        """
        try:
            # === LOG: Apa yang akan dikirim ke LLM ===
            debug(f"Mengirim request ke LLM...", tag="LLM")
            debug(f"  Jumlah messages : {len(messages)}", tag="LLM")
            debug(f"  System prompt   : {len(system)} karakter", tag="LLM")
            debug(f"  Tools disertakan: {len(tools) if tools else 0} tools", tag="LLM")
            debug(f"  Max tokens      : {max_tokens}", tag="LLM")

            # Siapkan parameter untuk API call
            params = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": messages,
            }

            if system:
                params["system"] = system

            if tools:
                params["tools"] = tools

            # === LOG: Kirim ke API ===
            debug("Menunggu response dari LLM API...", tag="LLM")
            response = self.client.messages.create(**params)

            # === LOG: Response diterima ===
            debug(f"Response diterima dari LLM ✓", tag="LLM")
            debug(f"  Stop reason     : {response.stop_reason}", tag="LLM")
            debug(f"  Content blocks  : {len(response.content)} block(s)", tag="LLM")

            # Log detail setiap content block
            for i, block in enumerate(response.content):
                if hasattr(block, "text"):
                    preview = block.text[:80] + "..." if len(block.text) > 80 else block.text
                    debug(f"  Block {i}: [TEXT] \"{preview}\"", tag="LLM")
                elif block.type == "tool_use":
                    debug(f"  Block {i}: [TOOL_USE] {block.name}(input={block.input})", tag="LLM")

            # Log usage (token usage) kalau tersedia
            if hasattr(response, "usage") and response.usage:
                debug(
                    f"  Token usage: input={response.usage.input_tokens}, "
                    f"output={response.usage.output_tokens}",
                    tag="LLM"
                )

            return response

        except Exception as e:
            debug(f"❌ API ERROR: {e}", tag="LLM")
            raise ConnectionError(f"Gagal menghubungi LLM: {e}")

    def get_text_response(self, messages, system=""):
        """
        Shortcut untuk chat simple tanpa tools.
        """
        debug("get_text_response() dipanggil (mode simple chat)", tag="LLM")
        response = self.send(messages, system)
        return response.content[0].text
