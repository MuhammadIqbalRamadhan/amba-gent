# -*- coding: utf-8 -*-
"""
core/context.py — Context Window Manager

=== MASALAH YANG DISELESAIKAN ===
Setiap LLM punya batas "context window" — jumlah maksimal token yang bisa diproses
dalam satu kali request. Kalau kita kirim pesan yang terlalu panjang, akan terjadi:
  - Error "context length exceeded"
  - Atau LLM "lupa" informasi di awal percakapan

Contoh batas context window:
  - GPT-4: 128K tokens (~96.000 kata)
  - Claude: 200K tokens (~150.000 kata)
  - glm-5: bervariasi, kita estimasi 128K tokens

=== APA ITU TOKEN? ===
Token BUKAN sama dengan karakter atau kata.
Token adalah potongan teks terkecil yang dipahami LLM.

Contoh tokenisasi:
  "Hello world"     → ["Hello", " world"]           → 2 tokens
  "programming"     → ["programm", "ing"]            → 2 tokens
  "Halo mas Rusdi"  → ["H", "alo", " mas", " Rus", "di"] → 5 tokens (kurang lebih)

Aturan praktis: 1 token ≈ 4 karakter (dalam bahasa Inggris)
Untuk bahasa Indonesia, bisa 1 token ≈ 3 karakter (karena lebih jarang di training data)

=== STRATEGI YANG KITA PAKAI ===
1. Token Counting   — hitung estimasi jumlah token sebelum kirim
2. Sliding Window   — kalau kepenuhan, hapus percakapan lama
3. Truncation       — potong pesan yang terlalu panjang (misal isi file besar)

=== KENAPA PAKAI ESTIMASI, BUKAN TOKENIZER ASLI? ===
Tokenizer asli (seperti tiktoken) cuma untuk model OpenAI.
Untuk model lain (Claude, glm-5), kita pakai estimasi sederhana.
Estimasi ini cukup akurat untuk tujuan kita: mencegah error context overflow.
"""

from core.logger import debug


class ContextManager:
    """
    Mengelola ukuran context window agar tidak melebihi batas LLM.

    Cara kerja:
    1. Sebelum kirim messages ke LLM, panggil prepare_messages()
    2. ContextManager akan:
       a. Hitung total token dari semua messages
       b. Kalau melebihi batas → hapus messages lama (sliding window)
       c. Messages terbaru + system prompt selalu dipertahankan
    3. Return messages yang sudah "dipangkas" dan aman dikirim

    Contoh:
        ctx = ContextManager(max_tokens=128000)
        safe_messages = ctx.prepare_messages(messages)  # Dipangkas kalau perlu
    """

    def __init__(self, max_tokens=128000, reserve_for_response=4096):
        """
        Parameter:
        - max_tokens: batas total context window LLM
        - reserve_for_response: token yang "disisakan" untuk jawaban LLM

        Kenapa reserve_for_response?
        Context window = input + output.
        Kalau kita habiskan semua untuk input, LLM tidak punya ruang untuk menjawab!

        Contoh:
          max_tokens = 128000
          reserve_for_response = 4096
          budget_for_input = 128000 - 4096 = 123904 tokens
        """
        self.max_tokens = max_tokens
        self.reserve_for_response = reserve_for_response

        # Budget yang tersedia untuk messages kita
        self.input_budget = max_tokens - reserve_for_response
        debug(
            f"ContextManager siap: max={max_tokens:,}, reserve={reserve_for_response:,}, "
            f"budget input={self.input_budget:,} tokens",
            tag="CONTEXT"
        )

    # =========================================
    # ESTIMASI TOKEN
    # =========================================

    def estimate_tokens(self, text):
        """
        Estimasi jumlah token dari sebuah teks.

        Aturan praktis:
        - Bahasa Inggris: 1 token ≈ 4 karakter
        - Bahasa Indonesia: 1 token ≈ 3 karakter (lebih boros)
        - Kode program: 1 token ≈ 3.5 karakter (banyak simbol)

        Kita pakai rata-rata 3.5 karakter per token sebagai estimasi aman.
        Lebih baik overestimate (hitung lebih banyak) daripada underestimate.

        Contoh:
            estimate_tokens("Hello world")  → 4 (11 chars / 3.5 ≈ 3.14 → 4)
        """
        if not text:
            return 0

        # Konversi ke string kalau bukan string (misal list, dict)
        if not isinstance(text, str):
            text = str(text)

        # Rumus estimasi: jumlah karakter / 3.5, dibulatkan ke atas
        # int() membulatkan ke bawah, jadi kita tambah 1 untuk safety margin
        return int(len(text) / 3.5) + 1

    def estimate_message_tokens(self, message):
        """
        Estimasi token untuk satu message ({"role": ..., "content": ...}).

        Kenapa bukan cuma menghitung content?
        Karena setiap message juga mengonsumsi token untuk metadata:
        - Role ("user", "assistant") = beberapa token
        - Formatting overhead = beberapa token tambahan

        Kita tambahkan 4 token overhead per message sebagai estimasi.

        CATATAN PENTING:
        Content bisa berupa:
        - String biasa: "Halo mas Rusdi"
        - List of blocks: [{"type": "tool_result", ...}]  ← dari tool results
        - List of objects: [TextBlock(...), ToolUseBlock(...)]  ← dari API response

        Kita perlu handle semua format ini.
        """
        overhead = 4  # Token overhead untuk role, formatting, dll

        content = message.get("content", "")

        # Kasus 1: Content adalah string biasa
        if isinstance(content, str):
            return self.estimate_tokens(content) + overhead

        # Kasus 2: Content adalah list (tool results atau content blocks)
        if isinstance(content, list):
            total = 0
            for item in content:
                if isinstance(item, dict):
                    # Tool result: {"type": "tool_result", "content": "..."}
                    total += self.estimate_tokens(str(item))
                else:
                    # Content block object (TextBlock, ToolUseBlock)
                    total += self.estimate_tokens(str(item))
            return total + overhead

        # Kasus 3: Content format lain → konversi ke string
        return self.estimate_tokens(str(content)) + overhead

    def count_total_tokens(self, messages, system_prompt=""):
        """
        Hitung total estimasi token dari semua messages + system prompt.

        Return: integer jumlah token

        Ini berguna untuk debugging dan monitoring.
        Kita tampilkan ini di debug log agar mas Rusdi bisa lihat
        berapa banyak token yang dipakai setiap request.
        """
        total = 0

        # Hitung token system prompt
        if system_prompt:
            total += self.estimate_tokens(system_prompt)

        # Hitung token semua messages
        for msg in messages:
            total += self.estimate_message_tokens(msg)

        return total

    # =========================================
    # STRATEGI PEMANGKASAN
    # =========================================

    def prepare_messages(self, messages, system_prompt=""):
        """
        Siapkan messages agar aman dikirim ke LLM (tidak melebihi context window).

        === INI ADALAH FUNGSI UTAMA CONTEXT MANAGER ===

        Alur:
        1. Hitung total token
        2. Kalau masih dalam budget → return messages apa adanya
        3. Kalau melebihi budget → pangkas messages lama (sliding window)

        Parameter:
        - messages: list semua messages percakapan
        - system_prompt: system prompt (selalu dipertahankan, tidak dipotong)

        Return:
        - dict dengan:
            - "messages": list messages yang sudah dipangkas (atau utuh)
            - "original_count": jumlah messages asli
            - "final_count": jumlah messages setelah pangkas
            - "tokens_used": estimasi total token
            - "tokens_budget": budget yang tersedia
            - "was_trimmed": True/False apakah dipangkas

        === STRATEGI: SLIDING WINDOW ===
        Cara kerja sliding window:
        - Pertahankan pesan PERTAMA (biasanya pesan user yang memulai sesi)
        - HAPUS pesan-pesan LAMA di tengah (yang sudah tidak terlalu relevan)
        - Pertahankan pesan TERBARU (yang paling relevan)

        Analogi: bayangkan kamu baca buku tebal. Kamu ingat bab pertama
        dan beberapa bab terakhir, tapi lupa bab-bab di tengah.
        Begitulah cara kerja sliding window.

        Visualisasi:
            [msg1] [msg2] [msg3] [msg4] [msg5] [msg6] [msg7] [msg8]
                      ↑ hapus yang lama ↑
            ═══════════════════════════════════════════════
            [msg1] [msg7] [msg8]  ← yang dikirim ke LLM
        """
        system_tokens = self.estimate_tokens(system_prompt) if system_prompt else 0
        available_budget = self.input_budget - system_tokens

        # Hitung total token messages saat ini
        total_tokens = sum(self.estimate_message_tokens(m) for m in messages)

        # Kalau masih muat → kembalikan apa adanya
        if total_tokens <= available_budget:
            debug(
                f"Context OK: {total_tokens:,} tokens, {len(messages)} messages (muat semua)",
                tag="CONTEXT"
            )
            return {
                "messages": messages,
                "original_count": len(messages),
                "final_count": len(messages),
                "tokens_used": total_tokens + system_tokens,
                "tokens_budget": self.input_budget,
                "was_trimmed": False,
            }

        # === SLIDING WINDOW: Pangkas messages lama ===
        debug(
            f"⚠️ Context OVERFLOW: {total_tokens:,} > {available_budget:,} tokens. Memangkas...",
            tag="CONTEXT"
        )
        # Strategi: pertahankan pesan pertama + pesan-pesan terbaru

        trimmed = []

        # Langkah 1: Selalu pertahankan pesan pertama (context awal)
        if messages:
            trimmed.append(messages[0])
            first_msg_tokens = self.estimate_message_tokens(messages[0])
            remaining_budget = available_budget - first_msg_tokens
        else:
            remaining_budget = available_budget

        # Langkah 2: Dari belakang, tambahkan messages selama masih muat
        # reversed() = iterasi dari belakang ke depan
        recent_messages = []
        for msg in reversed(messages[1:]):  # Skip pesan pertama (sudah ditambahkan)
            msg_tokens = self.estimate_message_tokens(msg)
            if msg_tokens <= remaining_budget:
                recent_messages.insert(0, msg)  # Tambahkan di depan (agar urutan benar)
                remaining_budget -= msg_tokens
            else:
                break  # Sudah tidak muat, berhenti

        trimmed.extend(recent_messages)

        # Hitung ulang total token
        final_tokens = sum(self.estimate_message_tokens(m) for m in trimmed)

        debug(
            f"Setelah pangkas: {len(messages)} → {len(trimmed)} messages, "
            f"{total_tokens:,} → {final_tokens:,} tokens",
            tag="CONTEXT"
        )

        return {
            "messages": trimmed,
            "original_count": len(messages),
            "final_count": len(trimmed),
            "tokens_used": final_tokens + system_tokens,
            "tokens_budget": self.input_budget,
            "was_trimmed": True,
        }

    # =========================================
    # UTILITY: TRUNCATE TEKS PANJANG
    # =========================================

    def truncate_text(self, text, max_chars=50000):
        """
        Potong teks yang terlalu panjang (misalnya isi file besar).

        Kapan dipakai?
        Ketika tool read_file membaca file yang sangat besar (ribuan baris),
        kita perlu memotongnya agar tidak memakan terlalu banyak context.

        Parameter:
        - text: string yang mungkin terlalu panjang
        - max_chars: batas maksimal karakter (default 50000 ≈ 14K tokens)

        Return:
        - Teks yang sudah dipotong (kalau perlu) + pesan pemberitahuan
        """
        if len(text) <= max_chars:
            return text  # Tidak perlu dipotong

        # Potong dan tambahkan pemberitahuan
        truncated = text[:max_chars]
        remaining_chars = len(text) - max_chars
        truncated += (
            f"\n\n... [DIPOTONG: {remaining_chars} karakter tersisa. "
            f"File terlalu besar untuk ditampilkan seluruhnya.] ..."
        )
        return truncated
