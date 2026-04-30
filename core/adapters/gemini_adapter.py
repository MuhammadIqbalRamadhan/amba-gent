# -*- coding: utf-8 -*-
"""
core/adapters/gemini_adapter.py — Adapter untuk Google Gemini API

=== APA INI? ===
Adapter ini menghubungkan Amba-Gent dengan Google Gemini API.
Tantangan utamanya: format API Gemini SANGAT BERBEDA dari Anthropic.

=== PERBEDAAN FORMAT ===

  ANTHROPIC                           GEMINI
  ─────────                           ──────
  messages = [                        contents = [
    {"role": "user",                    {"role": "user",
     "content": "halo"}                  "parts": [{"text": "halo"}]}
  ]                                   ]

  system = "kamu adalah..."           system_instruction = "kamu adalah..."

  tools = [                           tools = [FunctionDeclaration(
    {"name": "read_file",               name="read_file",
     "description": "...",               description="...",
     "input_schema": {...}}              parameters={...}
  ]                                   )]

  response.stop_reason = "tool_use"   response.function_calls = [...]
  response.content = [ToolUseBlock]   response.parts = [FunctionCall]

=== TUGAS ADAPTER ===
Menerjemahkan SEMUA perbedaan di atas secara transparan,
sehingga agent_loop tidak perlu tahu format Gemini sama sekali!

=== LIBRARY YANG DIPAKAI ===
google-genai (SDK terbaru Google, bukan google-generativeai yang lama)
Install: pip install google-genai
"""

from google import genai
from google.genai import types

from core.adapters.base import BaseLLMAdapter, UnifiedResponse, UnifiedContentBlock
from core.logger import debug


class GeminiAdapter(BaseLLMAdapter):
    """
    Adapter untuk Google Gemini API.

    === CARA KERJA ===
    1. Terima messages dalam format Anthropic (yang kita pakai sebagai standar)
    2. Convert ke format Gemini (Contents, Parts, FunctionDeclaration)
    3. Kirim ke Gemini API
    4. Convert response Gemini → UnifiedResponse
    5. Return ke agent_loop

    Contoh:
        adapter = GeminiAdapter(api_key="AI...", model="gemini-2.0-flash")
        response = adapter.send(messages, system="...", tools=[...])
    """

    def __init__(self, api_key, model):
        """
        Parameter:
        - api_key : Gemini API key (dari Google AI Studio)
        - model   : nama model (contoh: "gemini-2.0-flash", "gemini-1.5-pro")
        """
        debug(f"Membuat koneksi ke Google Gemini API...", tag="LLM")
        debug(f"  Model    : {model}", tag="LLM")

        # google-genai menggunakan Client object
        # Berbeda dari Anthropic yang langsung Anthropic(api_key=...)
        self.client = genai.Client(api_key=api_key)
        self._model = model
        debug("Koneksi Gemini berhasil dibuat ✓", tag="LLM")

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    def send(self, messages, system="", tools=None, max_tokens=4096) -> UnifiedResponse:
        """
        Kirim messages ke Gemini API dan kembalikan UnifiedResponse.

        === LANGKAH-LANGKAH ===
        1. Convert messages Anthropic → Gemini contents
        2. Convert tools Anthropic → Gemini FunctionDeclarations
        3. Kirim ke API dengan automatic_function_calling DISABLED
           (karena kita mau handle tool calling MANUAL di agent_loop)
        4. Convert response Gemini → UnifiedResponse
        """
        try:
            debug(f"[Gemini] Mengirim request...", tag="LLM")
            debug(f"  Jumlah messages : {len(messages)}", tag="LLM")
            debug(f"  System prompt   : {len(system)} karakter", tag="LLM")
            debug(f"  Tools disertakan: {len(tools) if tools else 0} tools", tag="LLM")

            # === STEP 1: Convert messages ===
            # Format Anthropic: [{"role": "user", "content": "..."}]
            # Format Gemini: [Content(role="user", parts=[Part(text="...")])]
            gemini_contents = self._convert_messages(messages)

            # === STEP 2: Convert tools ===
            # Format Anthropic: [{"name": "...", "input_schema": {...}}]
            # Format Gemini: [Tool(function_declarations=[FunctionDeclaration(...)])]
            gemini_tools = self._convert_tools(tools) if tools else None

            # === STEP 3: Buat config ===
            # GenerateContentConfig mengatur perilaku API
            config = types.GenerateContentConfig(
                # max_output_tokens = batas karakter jawaban
                max_output_tokens=max_tokens,
            )

            # System instruction (sama dengan system prompt di Anthropic)
            if system:
                config.system_instruction = system

            # Tambahkan tools ke config
            if gemini_tools:
                config.tools = gemini_tools
                # DISABLE automatic function calling!
                # Kenapa? Karena kita INGIN handle tool calling sendiri di agent_loop
                # Kalau automatic=ON, SDK Gemini akan coba eksekusi tool sendiri
                # (tapi dia tidak tahu fungsi Python kita yang sebenarnya)
                config.automatic_function_calling = types.AutomaticFunctionCallingConfig(
                    disable=True
                )

            # === STEP 4: Kirim ke API ===
            debug("Menunggu response dari Gemini API...", tag="LLM")
            response = self.client.models.generate_content(
                model=self._model,
                contents=gemini_contents,
                config=config,
            )

            debug(f"[Gemini] Response diterima ✓", tag="LLM")

            # Log token usage
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                um = response.usage_metadata
                debug(
                    f"  Token usage: input={um.prompt_token_count}, "
                    f"output={um.candidates_token_count}",
                    tag="LLM"
                )

            # === STEP 5: Convert ke UnifiedResponse ===
            return self._to_unified(response)

        except Exception as e:
            debug(f"❌ Gemini API ERROR: {e}", tag="LLM")
            raise ConnectionError(f"Gagal menghubungi Gemini: {e}")

    def send_stream(self, messages, system="", max_tokens=4096):
        """
        Streaming response dari Gemini API.

        Gemini streaming menggunakan generate_content_stream()
        yang mengembalikan iterator of chunks.
        """
        try:
            debug("[Gemini] Memulai streaming...", tag="LLM")

            gemini_contents = self._convert_messages(messages)

            config = types.GenerateContentConfig(
                max_output_tokens=max_tokens,
            )
            if system:
                config.system_instruction = system

            # stream=True otomatis di method generate_content_stream
            for chunk in self.client.models.generate_content_stream(
                model=self._model,
                contents=gemini_contents,
                config=config,
            ):
                # Setiap chunk bisa mengandung teks
                if chunk.text:
                    yield chunk.text

            debug("[Gemini] Streaming selesai ✓", tag="LLM")

        except Exception as e:
            debug(f"❌ Gemini Streaming ERROR: {e}", tag="LLM")
            raise ConnectionError(f"Gagal streaming dari Gemini: {e}")

    # =========================================================
    # CONVERTER: Anthropic Format → Gemini Format
    # =========================================================
    # Inilah bagian "penerjemah" yang paling penting!
    # Semua perbedaan format diselesaikan di sini.
    # =========================================================

    def _convert_messages(self, messages):
        """
        Convert messages format Anthropic → format Gemini.

        === FORMAT ANTHROPIC ===
        [
            {"role": "user", "content": "halo"},
            {"role": "assistant", "content": [TextBlock(...), ToolUseBlock(...)]},
            {"role": "user", "content": [{"type": "tool_result", ...}]}
        ]

        === FORMAT GEMINI ===
        [
            Content(role="user", parts=[Part(text="halo")]),
            Content(role="model", parts=[Part(text="..."), Part(function_call=...)]),
            Content(role="user", parts=[Part(function_response=...)])
        ]

        Perbedaan kunci:
        1. role "assistant" di Anthropic = "model" di Gemini
        2. content string → Part(text=...)
        3. ToolUseBlock → Part(function_call=...)
        4. tool_result → Part(function_response=...)
        """
        gemini_contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Gemini pakai "model" bukan "assistant"
            if role == "assistant":
                role = "model"

            parts = []

            # --- Kasus 1: content berupa string biasa ---
            if isinstance(content, str):
                parts.append(types.Part(text=content))

            # --- Kasus 2: content berupa list (blocks/tool_results) ---
            elif isinstance(content, list):
                for item in content:
                    # Sub-kasus A: tool_result (dict dari agent_loop)
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        # Anthropic tool_result → Gemini FunctionResponse
                        parts.append(types.Part(
                            function_response=types.FunctionResponse(
                                name=item.get("_tool_name", "unknown"),
                                response={"result": item.get("content", "")}
                            )
                        ))

                    # Sub-kasus B: text dict
                    elif isinstance(item, dict) and item.get("type") == "text":
                        text_val = item.get("text", "")
                        if text_val:
                            parts.append(types.Part(text=text_val))

                    # Sub-kasus C: tool_use dict (dari session resume)
                    elif isinstance(item, dict) and item.get("type") == "tool_use":
                        parts.append(types.Part(
                            function_call=types.FunctionCall(
                                name=item.get("name", ""),
                                args=item.get("input", {}),
                            )
                        ))

                    # Sub-kasus D: Anthropic API object (TextBlock, ToolUseBlock)
                    elif hasattr(item, "type"):
                        if item.type == "text" and hasattr(item, "text"):
                            parts.append(types.Part(text=item.text))
                        elif item.type == "tool_use":
                            # ToolUseBlock → FunctionCall
                            parts.append(types.Part(
                                function_call=types.FunctionCall(
                                    name=item.name,
                                    args=item.input if isinstance(item.input, dict) else {},
                                )
                            ))
                    else:
                        # Fallback: convert ke string
                        parts.append(types.Part(text=str(item)))

            # Jangan tambahkan message kosong (Gemini akan error)
            if parts:
                gemini_contents.append(
                    types.Content(role=role, parts=parts)
                )

        return gemini_contents

    def _convert_tools(self, anthropic_tools):
        """
        Convert tools format Anthropic JSON Schema → Gemini FunctionDeclaration.

        === FORMAT ANTHROPIC ===
        {
            "name": "read_file",
            "description": "Baca isi file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path file"}
                },
                "required": ["path"]
            }
        }

        === FORMAT GEMINI ===
        FunctionDeclaration(
            name="read_file",
            description="Baca isi file",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "path": {"type": "STRING", "description": "Path file"}
                },
                "required": ["path"]
            }
        )

        Perbedaan kecil:
        - Anthropic: "input_schema" → Gemini: "parameters"
        - Anthropic: "string" (lowercase) → Gemini: "STRING" (uppercase)
        """
        if not anthropic_tools:
            return None

        declarations = []

        for tool in anthropic_tools:
            # Ambil parameter dari input_schema Anthropic
            schema = tool.get("input_schema", {})

            # Convert tipe data ke uppercase (syarat Gemini)
            converted_params = self._convert_schema_types(schema)

            decl = types.FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description", ""),
                parameters=converted_params,
            )
            declarations.append(decl)

        debug(f"[Gemini] Converted {len(declarations)} tool declarations", tag="LLM")

        # Gemini membungkus declarations dalam Tool object
        return [types.Tool(function_declarations=declarations)]

    def _convert_schema_types(self, schema):
        """
        Convert JSON Schema type names ke format Gemini (uppercase).

        "string"  → "STRING"
        "integer" → "INTEGER"
        "number"  → "NUMBER"
        "boolean" → "BOOLEAN"
        "object"  → "OBJECT"
        "array"   → "ARRAY"

        Kenapa Gemini pakai uppercase?
        Ini konvensi protobuf (protocol buffers) yang dipakai Google internally.
        """
        if not schema or not isinstance(schema, dict):
            return schema

        result = {}

        for key, value in schema.items():
            if key == "type" and isinstance(value, str):
                # Convert type ke uppercase
                result["type"] = value.upper()
            elif key == "properties" and isinstance(value, dict):
                # Rekursif: convert properties di dalamnya juga
                result["properties"] = {
                    prop_name: self._convert_schema_types(prop_value)
                    for prop_name, prop_value in value.items()
                }
            elif key == "items" and isinstance(value, dict):
                # Untuk array items
                result["items"] = self._convert_schema_types(value)
            else:
                # Key lain langsung copy (required, description, dll)
                result[key] = value

        return result

    # =========================================================
    # CONVERTER: Gemini Response → UnifiedResponse
    # =========================================================

    def _to_unified(self, response) -> UnifiedResponse:
        """
        Convert Gemini response → UnifiedResponse.

        === MAPPING ===

        Gemini: response.candidates[0].content.parts
          Part(text="...")           → UnifiedContentBlock(type="text")
          Part(function_call=...)   → UnifiedContentBlock(type="tool_use")

        Gemini TIDAK punya "stop_reason" yang sama seperti Anthropic.
        Kita harus MENDETEKSI sendiri:
        - Ada function_call? → stop_reason = "tool_use"
        - Tidak ada?         → stop_reason = "end_turn"

        Gemini juga TIDAK punya tool_use_id bawaan.
        Kita generate ID sendiri menggunakan format: "gemini_call_0", "gemini_call_1", ...
        """
        unified_blocks = []
        has_function_call = False

        # Counter untuk generate tool_use_id
        # (Anthropic punya ID unik per tool call, Gemini tidak)
        call_counter = 0

        # Gemini response ada di response.candidates[0].content.parts
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:

                # --- Kasus 1: Teks biasa ---
                if part.text:
                    debug(f"  [Gemini] Part: TEXT \"{part.text[:80]}...\"", tag="LLM")
                    unified_blocks.append(UnifiedContentBlock(
                        type="text",
                        text=part.text,
                    ))

                # --- Kasus 2: Function call (tool_use) ---
                elif part.function_call:
                    has_function_call = True
                    fc = part.function_call

                    # Generate ID unik untuk tool call ini
                    tool_id = f"gemini_call_{call_counter}"
                    call_counter += 1

                    debug(f"  [Gemini] Part: FUNCTION_CALL {fc.name}(args={fc.args})", tag="LLM")

                    unified_blocks.append(UnifiedContentBlock(
                        type="tool_use",
                        tool_name=fc.name,
                        tool_input=dict(fc.args) if fc.args else {},
                        tool_use_id=tool_id,
                    ))

        # Tentukan stop_reason
        # Gemini tidak punya field ini secara eksplisit, jadi kita deduksi
        stop_reason = "tool_use" if has_function_call else "end_turn"
        debug(f"  [Gemini] Deduced stop_reason: {stop_reason}", tag="LLM")

        # Token usage
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            input_tokens = getattr(um, "prompt_token_count", 0) or 0
            output_tokens = getattr(um, "candidates_token_count", 0) or 0

        return UnifiedResponse(
            stop_reason=stop_reason,
            content=unified_blocks,
            raw_response=response,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
