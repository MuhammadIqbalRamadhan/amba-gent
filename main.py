# -*- coding: utf-8 -*-
"""
main.py — Entry Point untuk Amba-Gent

Agent loop dengan centralized debug logging.
Semua debug log sekarang menggunakan core/logger.py (dikontrol dari .env).

CARA PAKAI:
    py -3 main.py
"""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from core.llm_client import LLMClient
from core.context import ContextManager
from core.logger import debug, debug_separator, console
from config import DEBUG
from tools.definitions import TOOLS, DANGEROUS_TOOLS
from tools.executor import execute_tool


# System prompt — instruksi untuk LLM
SYSTEM_PROMPT = """Kamu adalah amba-gent, asisten AI pribadi yang sangat cerdas, ahli dalam Full-Stack Development, serta mahir dalam analisis sistem.

ATURAN KOMUNIKASI (WAJIB DITAATI):
1. Panggilan Pengguna: Kamu WAJIB memanggil pengguna dengan sebutan "mas rusdi" di setiap awal, tengah, atau akhir kalimat yang relevan. Dilarang keras menggunakan sebutan "bro", "kak", "bapak", atau "anda".
2. Gaya Bahasa: Gunakan bahasa Indonesia yang santai, sopan, dan kolaboratif layaknya rekan kerja sesama programmer. Gunakan istilah teknis (seperti deploy, bug, refactor, state) secara natural.
3. Karakter: Kamu proaktif, teliti, dan *to-the-point*. Jika kode pengguna ada yang kurang optimal, beri tahu dengan sopan alasannya.

KEMAMPUAN TOOLS:
Kamu punya akses ke beberapa tools untuk membaca dan memodifikasi kode:
- read_file: Baca isi file
- write_file: Tulis/buat file
- list_directory: Lihat isi folder
- search_code: Cari teks di dalam project (exact match)
- search_codebase: Cari kode yang relevan secara semantik (RAG)

Gunakan tools ini secara proaktif ketika user meminta bantuan terkait kode.
Jangan minta user untuk menunjukkan isi file — langsung baca sendiri pakai tool!
"""


# Inisialisasi context manager
ctx_manager = ContextManager(max_tokens=128000, reserve_for_response=4096)


def agent_loop(llm, messages):
    """
    AGENT LOOP — Jantung dari amba-gent.
    Sekarang setiap langkah di-log ke debug output.
    """
    loop_count = 0  # Hitung berapa kali loop berputar

    while True:
        loop_count += 1
        debug_separator(f"AGENT LOOP — Iterasi #{loop_count}")

        # ============================================================
        # STEP 1: Context Management
        # ============================================================
        debug("📋 [STEP 1] Memeriksa context window...", tag="AGENT")
        ctx_result = ctx_manager.prepare_messages(messages, SYSTEM_PROMPT)
        safe_messages = ctx_result["messages"]

        debug(
            f"📊 Token: ~{ctx_result['tokens_used']:,} / {ctx_result['tokens_budget']:,} "
            f"| Messages: {ctx_result['final_count']}/{ctx_result['original_count']}"
            f"{' (DIPANGKAS!)' if ctx_result['was_trimmed'] else ''}",
            tag="AGENT"
        )

        # ============================================================
        # STEP 2: Kirim messages ke LLM
        # ============================================================
        debug("📤 [STEP 2] Mengirim messages ke LLM...", tag="AGENT")
        with console.status("[bold green]Tunggu sebentar ya mas rusdi...", spinner="dots"):
            response = llm.send(
                messages=safe_messages,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
            )
        debug(f"📥 Response diterima: stop_reason=\"{response.stop_reason}\"", tag="AGENT")

        # ============================================================
        # STEP 3: Proses response
        # ============================================================

        # --- Kasus A: LLM selesai menjawab ---
        if response.stop_reason == "end_turn":
            debug("✅ [STEP 3a] stop_reason=end_turn → LLM selesai, menyiapkan jawaban...", tag="AGENT")

            jawaban = ""
            for block in response.content:
                if hasattr(block, "text"):
                    jawaban += block.text

            debug(f"Panjang jawaban: {len(jawaban)} karakter", tag="AGENT")
            messages.append({"role": "assistant", "content": response.content})
            debug_separator("AGENT LOOP SELESAI")

            return jawaban

        # --- Kasus B: LLM mau pakai tool ---
        if response.stop_reason == "tool_use":
            debug("⚙️ [STEP 3b] stop_reason=tool_use → LLM ingin pakai tool!", tag="AGENT")

            # Hitung berapa tool yang diminta
            tool_blocks = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if hasattr(b, "text") and b.text]
            debug(f"  Content blocks: {len(tool_blocks)} tool_use, {len(text_blocks)} text", tag="AGENT")

            # Simpan response LLM ke history
            messages.append({"role": "assistant", "content": response.content})

            # Tampilkan teks "pemikiran" LLM kalau ada
            for block in text_blocks:
                debug(f"  💭 Pemikiran LLM: \"{block.text[:100]}...\"", tag="AGENT")
                console.print(f"[dim italic]{block.text}[/dim italic]")

            # Proses setiap tool
            tool_results = []

            for idx, block in enumerate(tool_blocks, 1):
                tool_name = block.name
                tool_input = block.input
                tool_use_id = block.id

                debug_separator(f"TOOL #{idx}: {tool_name}")
                debug(f"  Nama      : {tool_name}", tag="AGENT")
                debug(f"  Input     : {_format_params(tool_input)}", tag="AGENT")
                debug(f"  Tool ID   : {tool_use_id}", tag="AGENT")

                # Cek apakah tool berbahaya
                if tool_name in DANGEROUS_TOOLS:
                    debug(f"  ⚠️ Tool '{tool_name}' masuk kategori DANGEROUS!", tag="AGENT")
                    debug(f"  Meminta konfirmasi user...", tag="AGENT")

                    if not _ask_confirmation(tool_name, tool_input):
                        debug(f"  ❌ User MENOLAK eksekusi tool!", tag="AGENT")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": "User menolak eksekusi tool ini."
                        })
                        continue
                    else:
                        debug(f"  ✅ User MENYETUJUI eksekusi tool", tag="AGENT")

                # Eksekusi tool
                debug(f"  ⏳ Mengeksekusi {tool_name}...", tag="AGENT")
                result = execute_tool(tool_name, tool_input)

                # Truncate hasil kalau terlalu panjang
                original_len = len(result)
                result = ctx_manager.truncate_text(result, max_chars=50000)
                if len(result) < original_len:
                    debug(f"  ✂️ Hasil di-truncate: {original_len} → {len(result)} karakter", tag="AGENT")

                # Preview hasil di debug
                preview = result[:200] + "..." if len(result) > 200 else result
                debug(f"  📄 Preview: {preview}", tag="AGENT")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result,
                })

            # Kirim hasil tool ke LLM
            debug(f"📤 [STEP 4] Mengirim {len(tool_results)} tool result(s) ke LLM...", tag="AGENT")
            messages.append({"role": "user", "content": tool_results})
            debug("🔄 Mengulang agent loop (LLM akan membaca hasil tool)...", tag="AGENT")
            continue

        # --- Kasus C: stop_reason tidak dikenali ---
        debug(f"⚠️ stop_reason tidak dikenali: \"{response.stop_reason}\"", tag="AGENT")
        jawaban = ""
        for block in response.content:
            if hasattr(block, "text"):
                jawaban += block.text
        messages.append({"role": "assistant", "content": response.content})
        return jawaban if jawaban else "(Tidak ada respon)"


def _format_params(params):
    """Format parameter tool agar mudah dibaca di terminal."""
    parts = []
    for key, value in params.items():
        str_value = str(value)
        if len(str_value) > 50:
            str_value = str_value[:50] + "..."
        parts.append(f'{key}="{str_value}"')
    return ", ".join(parts)


def _ask_confirmation(tool_name, tool_input):
    """Minta konfirmasi user sebelum menjalankan tool yang berbahaya."""
    console.print(f"\n  [bold red]⚠️  Tool '{tool_name}' akan mengubah file![/bold red]")

    for key, value in tool_input.items():
        if key == "content":
            preview = str(value)[:100] + "..." if len(str(value)) > 100 else value
            console.print(f"  [yellow]  {key}: {preview}[/yellow]")
        else:
            console.print(f"  [yellow]  {key}: {value}[/yellow]")

    try:
        jawab = console.input("  [bold]Lanjutkan? (y/n): [/bold]")
        return jawab.strip().lower() in ("y", "yes", "ya")
    except (KeyboardInterrupt, EOFError):
        return False


def main():
    """Entry point utama amba-gent."""

    debug_separator("AMBA-GENT STARTUP")
    debug(f"Debug mode: {'AKTIF ✅' if DEBUG else 'NONAKTIF'}", tag="STARTUP")

    # Tampilkan header
    console.print(
        Panel.fit(
            "[bold cyan]🤖 Amba-Gent[/bold cyan] — AI Coding Agent\n"
            "[dim]Ketik pesan untuk mulai. Ketik 'exit' untuk keluar.[/dim]\n"
            "[dim]Agent bisa membaca, menulis, dan mencari kode di project kamu.[/dim]",
            border_style="cyan",
        )
    )

    # Inisialisasi LLM client
    debug("Inisialisasi LLM client...", tag="STARTUP")
    try:
        llm = LLMClient()
        console.print("[green]✓ Terhubung ke LLM[/green]")
        console.print(f"[dim]  Tools aktif: {', '.join(t['name'] for t in TOOLS)}[/dim]")
        console.print(f"[dim]  Debug mode : {'AKTIF' if DEBUG else 'NONAKTIF'}[/dim]\n")
        debug(f"Tools terdaftar: {[t['name'] for t in TOOLS]}", tag="STARTUP")
    except Exception as e:
        debug(f"❌ Gagal koneksi: {e}", tag="STARTUP")
        console.print(f"[bold red]✗ Gagal koneksi:[/bold red] {e}")
        return

    # Conversation history
    messages = []
    debug("Chat loop dimulai, menunggu input user...", tag="STARTUP")

    while True:
        try:
            user_input = console.input("[bold cyan]Kamu > [/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Sampai jumpa! 👋[/dim]")
            break

        if user_input.strip().lower() in ("exit", "quit", "q"):
            console.print("[dim]Sampai jumpa! 👋[/dim]")
            break

        if not user_input.strip():
            continue

        # Log input user
        debug_separator("INPUT USER BARU")
        debug(f"User input: \"{user_input[:100]}{'...' if len(user_input) > 100 else ''}\"", tag="AGENT")
        debug(f"Panjang input: {len(user_input)} karakter", tag="AGENT")

        messages.append({"role": "user", "content": user_input})
        debug(f"Total messages di history: {len(messages)}", tag="AGENT")

        try:
            jawaban = agent_loop(llm, messages)

            console.print()
            console.print("[bold green]Amba-Gent >[/bold green]")
            console.print(Markdown(jawaban))
            console.print()

        except ConnectionError as e:
            debug(f"❌ ConnectionError: {e}", tag="AGENT")
            console.print(f"\n[bold red]Error:[/bold red] {e}\n")
            messages.pop()
        except Exception as e:
            debug(f"❌ Unexpected error: {e}", tag="AGENT")
            console.print(f"\n[bold red]Error:[/bold red] {e}\n")
            messages.pop()


if __name__ == "__main__":
    main()
