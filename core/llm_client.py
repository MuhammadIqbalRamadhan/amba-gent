# -*- coding: utf-8 -*-
"""
core/llm_client.py — Wrapper untuk berkomunikasi dengan LLM

===  UPDATE: STREAMING ===
Sekarang ada 2 cara kirim pesan ke LLM:
1. send()        — non-streaming, dapat response utuh (dipakai untuk tool calling)
2. send_stream() — streaming, jawaban muncul token-per-token (dipakai saat end_turn)

Kenapa perlu 2 method?
- Tool calling butuh response utuh (untuk baca ToolUseBlock)
- Tapi jawaban akhir enaknya streaming (biar user tidak nunggu lama)
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

    def send_stream(self, messages, system="", max_tokens=4096):
        """
        Kirim messages ke LLM dan terima jawaban secara STREAMING.

        === APA ITU STREAMING? ===
        Tanpa streaming :
            User menunggu 5 detik... → semua teks muncul sekaligus. Lambat!

        Dengan streaming:
            Teks muncul satu-per-satu seperti diketik. Terasa cepat dan interaktif!

        Streaming bekerja seperti air yang mengalir dari keran:
        - Non-stream = tunggu ember penuh baru dikasih
        - Stream = air langsung mengalir saat keran dibuka

        === KAPAN DIPAKAI? ===
        Hanya untuk menampilkan jawaban AKHIR (setelah semua tool selesai).
        TIDAK bisa dipakai saat tool calling karena kita butuh response utuh.

        === CARA KERJA ===
        Menggunakan "generator" Python (fungsi dengan yield).
        yield = kirim data satu-per-satu, TANPA menunggu selesai.

        Contoh:
            for token in llm.send_stream(messages, system):
                print(token, end="")  # cetak token satu per satu

        Parameter:
        - messages : list percakapan
        - system   : system prompt
        - max_tokens: batas panjang jawaban

        Yield:
        - String token (potongan teks kecil, biasanya 1-5 kata)
        """
        try:
            debug("Memulai streaming response dari LLM...", tag="LLM")

            # Siapkan parameter
            params = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": messages,
            }

            if system:
                params["system"] = system

            # === STREAMING API ===
            # .stream() mengembalikan context manager yang menghasilkan event
            # Setiap event bisa berisi:
            # - text delta (potongan teks baru)
            # - content block start/stop
            # - message start/stop
            with self.client.messages.stream(**params) as stream:
                for text in stream.text_stream:
                    # text = potongan kecil teks (misal "Halo ", "mas ", "Rusdi")
                    yield text  # Langsung kirim ke pemanggil

            debug("Streaming selesai ✓", tag="LLM")

        except Exception as e:
            debug(f"❌ Streaming API ERROR: {e}", tag="LLM")
            raise ConnectionError(f"Gagal streaming dari LLM: {e}")

    def get_text_response(self, messages, system=""):
        """
        Shortcut untuk chat simple tanpa tools.
        """
        debug("get_text_response() dipanggil (mode simple chat)", tag="LLM")
        response = self.send(messages, system)
        return response.content[0].text
