# -*- coding: utf-8 -*-
"""
core/adapters/ — Multi-LLM Adapter Package

=== APA ITU ADAPTER PATTERN? ===
Bayangkan kamu punya charger HP Apple (Lightning) dan Samsung (USB-C).
Keduanya punya fungsi sama: mengisi daya HP. Tapi colokan fisiknya beda.
"Adapter" adalah alat yang menyatukan kedua colokan itu ke format universal.

Dalam konteks Amba-Gent:
- Anthropic API punya format request/response sendiri (TextBlock, ToolUseBlock)
- Google Gemini API punya format sendiri (Part, FunctionCall, FunctionResponse)

Adapter Pattern menyatukan keduanya ke format yang SAMA (UnifiedResponse),
sehingga agent_loop di main.py TIDAK PERLU TAHU provider mana yang dipakai.

=== ARSITEKTUR ===

    main.py
      │
      ▼
    create_llm_client(provider="anthropic")
      │
      ├──> AnthropicAdapter  ──> Anthropic API ──> UnifiedResponse
      │
      └──> GeminiAdapter     ──> Google Gemini API ──> UnifiedResponse
      │
      ▼
    agent_loop(adapter, ...)  ← Tidak peduli provider mana!

=== FILE DALAM PACKAGE INI ===
- base.py             → UnifiedResponse + BaseLLMAdapter (kontrak/interface)
- anthropic_adapter.py → Implementasi untuk Anthropic/Claude API
- gemini_adapter.py    → Implementasi untuk Google Gemini API
"""

from core.adapters.base import BaseLLMAdapter, UnifiedResponse, UnifiedContentBlock
