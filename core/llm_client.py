# -*- coding: utf-8 -*-
"""
core/llm_client.py — Factory Function untuk membuat LLM Adapter

=== DULU (SEBELUM MULTI-LLM) ===
File ini berisi class LLMClient yang langsung connect ke Anthropic.
Agent loop memanggil: llm = LLMClient()

=== SEKARANG (MULTI-LLM) ===
File ini berisi FACTORY FUNCTION: create_llm_client(provider, model)
Factory function = fungsi yang MEMBUAT dan MENGEMBALIKAN object.

Dia memilih adapter yang tepat berdasarkan provider:
  provider="anthropic" → AnthropicAdapter
  provider="gemini"    → GeminiAdapter

Agent loop sekarang memanggil: llm = create_llm_client("anthropic", "glm-5")

=== APA ITU FACTORY PATTERN? ===
Bayangkan kamu pesan kopi di kafe:
- Kamu bilang: "Saya mau Americano" (provider="americano")
- Barista (factory) yang memutuskan:
    - Ambil espresso machine
    - Tambah air panas
    - return Americano

Kamu tidak perlu tahu cara buatnya. Cukup bilang apa yang kamu mau!

Dalam kode kita:
- main.py bilang: create_llm_client("gemini", "gemini-2.0-flash")
- Factory yang memutuskan: import GeminiAdapter, buat instance, return
- main.py terima object yang siap pakai, tanpa tahu detail pembuatannya
"""

from core.logger import debug
from config import API_KEY, BASE_URL, MODEL, GEMINI_API_KEY, GEMINI_MODEL


def create_llm_client(provider="anthropic", model=None):
    """
    Factory function — buat LLM adapter sesuai provider yang diminta.

    Parameter:
    - provider: "anthropic" atau "gemini"
    - model: nama model (opsional, kalau None pakai default dari .env)

    Return:
    - Instance adapter (AnthropicAdapter atau GeminiAdapter)
      yang siap dipakai oleh agent_loop

    Raises:
    - ValueError: kalau provider tidak dikenali
    - ValueError: kalau API key untuk provider tersebut tidak diset

    Contoh:
        llm = create_llm_client("anthropic", "glm-5")
        llm = create_llm_client("gemini", "gemini-2.0-flash")
        llm = create_llm_client("gemini")  # pakai default GEMINI_MODEL dari .env
    """
    debug(f"Factory: membuat adapter untuk provider='{provider}'", tag="LLM")

    # === ANTHROPIC ===
    if provider == "anthropic":
        # Validasi: pastikan API key sudah diset
        if not API_KEY:
            raise ValueError(
                "❌ API_KEY belum diset di .env! "
                "Diperlukan untuk provider 'anthropic'."
            )
        if not BASE_URL:
            raise ValueError(
                "❌ BASE_URL belum diset di .env! "
                "Diperlukan untuk provider 'anthropic'."
            )

        # Import adapter (lazy import = import hanya saat dibutuhkan)
        # Kenapa lazy import? Agar kalau user hanya pakai Gemini,
        # library anthropic tidak perlu di-load ke memori
        from core.adapters.anthropic_adapter import AnthropicAdapter

        # Pakai model dari parameter CLI, atau fallback ke .env
        final_model = model or MODEL

        debug(f"Factory: AnthropicAdapter(model={final_model})", tag="LLM")
        return AnthropicAdapter(
            api_key=API_KEY,
            base_url=BASE_URL,
            model=final_model,
        )

    # === GEMINI ===
    elif provider == "gemini":
        # Validasi: pastikan Gemini API key sudah diset
        if not GEMINI_API_KEY:
            raise ValueError(
                "❌ GEMINI_API_KEY belum diset di .env! "
                "Dapatkan API key gratis di: https://aistudio.google.com/apikey"
            )

        from core.adapters.gemini_adapter import GeminiAdapter

        # Pakai model dari parameter CLI, atau fallback ke .env
        final_model = model or GEMINI_MODEL

        debug(f"Factory: GeminiAdapter(model={final_model})", tag="LLM")
        return GeminiAdapter(
            api_key=GEMINI_API_KEY,
            model=final_model,
        )

    # === PROVIDER TIDAK DIKENALI ===
    else:
        available = "anthropic, gemini"
        raise ValueError(
            f"❌ Provider '{provider}' tidak dikenali! "
            f"Provider yang tersedia: {available}"
        )
