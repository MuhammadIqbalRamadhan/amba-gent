# -*- coding: utf-8 -*-
"""
main.py — Entry Point untuk Amba-Gent

CARA PAKAI:
    py -3 main.py              ← mulai sesi baru
    py -3 main.py --resume     ← lanjutkan sesi terakhir
"""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
import argparse
import sys

from core.llm_client import create_llm_client
from core.adapters.base import content_to_dict
from core.context import ContextManager
from core.session import SessionManager
from core.project import detect_project, generate_project_context
from core.logger import debug, debug_separator, console
from config import DEBUG, DEFAULT_PROVIDER
from tools.definitions import TOOLS, DANGEROUS_TOOLS
from tools.executor import execute_tool


def parse_args():
    parser = argparse.ArgumentParser(
        prog="amba-gent",
        description="Amba-Gent — AI Coding Agent dengan multi-LLM support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Contoh:\n"
            "  py -3 main.py                                        Mulai sesi baru (provider default)\n"
            "  py -3 main.py --resume                               Lanjutkan sesi terakhir\n"
            "  py -3 main.py --provider gemini --model gemini-2.0-flash   Switch ke Gemini\n"
            "  py -3 main.py --provider anthropic --model glm-5           Switch ke Anthropic\n"
            "  py -3 main.py --debug                                Aktifkan debug mode\n"
            "\n"
            "NOTE: --provider dan --model HARUS dipakai bersamaan untuk switch LLM."
        ),
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Lanjutkan sesi percakapan terakhir yang tersimpan",
    )
    parser.add_argument(
        "--provider",
        choices=["anthropic", "gemini"],
        default=None,
        help=f"Pilih LLM provider (default: {DEFAULT_PROVIDER})",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override nama model (contoh: gemini-2.0-flash, claude-sonnet-4-6)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Aktifkan debug mode (tampilkan log detail)",
    )

    return parser.parse_args()


# ============================================================
# SYSTEM PROMPT — sekarang dengan project context
# ============================================================

BASE_SYSTEM_PROMPT = """Kamu adalah amba-gent, asisten AI pribadi yang sangat cerdas, ahli dalam Full-Stack Development, serta mahir dalam analisis sistem.

ATURAN KOMUNIKASI (WAJIB DITAATI):
1. Panggilan Pengguna: Kamu WAJIB memanggil pengguna dengan sebutan "mas rusdi" di setiap awal, tengah, atau akhir kalimat yang relevan. Dilarang keras menggunakan sebutan "bro", "kak", "bapak", atau "anda".
2. Gaya Bahasa: Gunakan bahasa Indonesia yang santai, sopan, dan kolaboratif layaknya rekan kerja sesama programmer. Gunakan istilah teknis (seperti deploy, bug, refactor, state) secara natural.
3. Karakter: Kamu proaktif, teliti, dan *to-the-point*. Jika kode pengguna ada yang kurang optimal, beri tahu dengan sopan alasannya.

ATURAN EKSEKUSI (WAJIB DITAATI):
1. BACA INTENT PENGGUNA (ADAPTIF):
   - MODE EKSEKUSI: Jika user meminta tindakan langsung (contoh: "tolong ubah UI", "fix bug ini", "tambahkan fitur"), EKSEKUSI DULU, JELASKAN NANTI. Jangan pernah menjawab dengan daftar rencana atau bilang "saya akan...". Langsung panggil tools (read_file, search_code, write_file) secara berurutan. Analisis = aksi, bukan omongan.
   - MODE DISKUSI: Jika user secara eksplisit mengajak diskusi, bertanya konsep, atau memberi instruksi "jangan ngoding dulu/jangan eksekusi", maka TAHAN SEMUA TOOLS. Jadilah teman diskusi yang baik dan jangan memanggil fungsi modifikasi file sampai user memberikan lampu hijau.
2. KONFIRMASI HANYA UNTUK HAL BERISIKO: Minta konfirmasi hanya sebelum write_file (sudah otomatis via diff preview). Untuk baca, cari, dan analisis — langsung eksekusi tanpa izin.
3. JAWAB SINGKAT: Setelah proses eksekusi kode selesai, rangkum hasilnya dalam 1-3 kalimat pendek. Jangan ulangi apa yang sudah jelas terlihat dari kode atau diff preview.

KEMAMPUAN TOOLS:
Kamu punya akses ke beberapa tools untuk membaca dan memodifikasi kode:
- read_file: Baca isi file
- write_file: Tulis/buat file (menampilkan diff preview otomatis)
- list_directory: Lihat isi folder
- search_code: Cari teks di dalam project (exact match)
- search_codebase: Cari kode yang relevan secara semantik (RAG)

Gunakan tools ini secara proaktif ketika berada di MODE EKSEKUSI. Jangan minta user untuk menunjukkan isi file — langsung baca sendiri pakai tool!
"""


# Inisialisasi global
ctx_manager = ContextManager(max_tokens=128000, reserve_for_response=4096)
session_mgr = SessionManager()


def build_system_prompt():
    """
    Fungsi untuk membangun "System Prompt".
    
    Apa itu System Prompt?
    Ini adalah instruksi rahasia utama yang dibaca oleh AI SEBELUM dia menjawab chat Anda.
    Di sini kita menggabungkan instruksi standar Amba-gent (BASE_SYSTEM_PROMPT) dengan 
    informasi otomatis tentang deteksi framework proyek Anda (project_context_info).
    Dengan trik ini, AI selalu tahu apakah Anda sedang ngoding pakai Python, PHP, JS, dll.
    """
    project_info = detect_project(".")
    project_context = generate_project_context(project_info)
    return BASE_SYSTEM_PROMPT + project_context


def stream_display(jawaban):
    """
    Tampilkan jawaban dengan efek streaming (typewriter effect).

    MENGAPA MENGGUNAKAN SIMULASI TYPEWRITER?
    Secara bawaan, LLM bisa mengirim respon sepotong-sepotong (streaming).
    Namun, karena Amba-Gent memakai alat/tools, agen BISA SAJA perlu memanggil tool 
    terlebih dulu lalu mengamati hasilnya. 
    
    Kita HARUS menunggu agen untuk BENAR-BENAR SELESAI bekerja menyusun jawaban akhir.
    Setelah jawaban selesai dievaluasi penuh, barulah jawaban utuh tersebut dipotong 
    kecil-kecil dan dicetak otomatis dengan efek animasi "mengetik" menggunakan 
    bantuan library "Rich Live".
    Hal ini menjamin UX (User Experience) yang mulus layaknya sedang dichat oleh orang asli!

    Parameter:
    - jawaban: Keseluruhan jawaban gabungan (string) yang akan dirender secara stream.
    """
    import time

    debug("🌊 Menampilkan jawaban dengan streaming effect...", tag="STREAM")

    console.print()
    console.print("[bold green]Amba-Gent >[/bold green]")

    # Pecah jawaban menjadi "chunks" (potongan-potongan kecil)
    # Simulasi streaming: tampilkan sedikit demi sedikit
    chunk_size = 15  # Karakter per chunk
    displayed = ""

    with Live(Text(""), console=console, refresh_per_second=15) as live:
        for i in range(0, len(jawaban), chunk_size):
            displayed += jawaban[i:i + chunk_size]
            live.update(Markdown(displayed))
            time.sleep(0.02)  # Delay kecil untuk efek "mengetik"

    console.print()  # Baris kosong
    debug(f"Streaming display selesai: {len(jawaban)} karakter", tag="STREAM")


def agent_loop(llm, messages, system_prompt):
    """
    AGENT LOOP (Siklus Agen) — Inilah Jantung Utama aplikasi Amba-gent!

    PERBEDAAN "Chatbot biasa" dengan "AI AGENT":
    - Chatbot: Anda bertanya -> AI langsung menjawab (1 Fase).
    - AI Agent: Anda bertanya -> AI mikir -> AI mutusin panggil Tool (misal baca database) -> 
      Aplikasi nge-return data -> AI mikir lagi dari awal -> Baru AI jawab berdasar data.
      
    Fungsi siklus (while loop) ini mengawal proses mandiri di atas terus berputar maju 
    sampai akhirnya LLM berkata "Oke aku sudah punya jawaban akhir" (end_turn).
    """
    loop_count = 0
    MAX_LOOPS = 50  # Guard: cegah infinite loop

    while True:
        loop_count += 1
        if loop_count > MAX_LOOPS:
            debug(f"⚠️ Max loops ({MAX_LOOPS}) tercapai, force stop.", tag="AGENT")
            console.print("[yellow]Agent loop mencapai batas iterasi. Menghentikan...[/yellow]")
            return "(Agent dihentikan karena terlalu banyak iterasi)"
        debug_separator(f"AGENT LOOP — Iterasi #{loop_count}")

        # STEP 1: Context Management
        debug("📋 [STEP 1] Memeriksa context window...", tag="AGENT")
        ctx_result = ctx_manager.prepare_messages(messages, system_prompt)
        safe_messages = ctx_result["messages"]

        debug(
            f"📊 Token: ~{ctx_result['tokens_used']:,} / {ctx_result['tokens_budget']:,} "
            f"| Messages: {ctx_result['final_count']}/{ctx_result['original_count']}"
            f"{' (DIPANGKAS!)' if ctx_result['was_trimmed'] else ''}",
            tag="AGENT"
        )

        # STEP 2: Kirim ke LLM (non-streaming karena perlu cek tool_use)
        debug("📤 [STEP 2] Mengirim messages ke LLM...", tag="AGENT")
        with console.status("[bold green]Tunggu sebentar ya mas rusdi...", spinner="dots"):
            response = llm.send(
                messages=safe_messages,
                system=system_prompt,
                tools=TOOLS,
            )
        debug(f"📥 Response diterima: stop_reason=\"{response.stop_reason}\"", tag="AGENT")

        # STEP 3: Menganalisa hasil tanggapan (Response) dari LLM
        # Nilai properti "stop_reason" mengisyaratkan kenapa LLM berhenti menjerit text.

        # --- Kasus A: LLM Memutuskan Selesai Menjawab (end_turn) ---
        # Ini berarti AI merasa sudah menyelesaikan tugas, dan teks "content" balasan
        # merupakan text manusia murni (bukan kode instruksi tool).
        if response.stop_reason == "end_turn":
            debug("✅ [STEP 3a] stop_reason=end_turn → jawaban akhir", tag="AGENT")

            jawaban = ""
            for block in response.content:
                if hasattr(block, "text") and block.text:
                    jawaban += block.text

            messages.append({"role": "assistant", "content": content_to_dict(response.content)})
            debug_separator("AGENT LOOP SELESAI")

            if not jawaban:
                debug(f"⚠️ end_turn tapi tidak ada text. Blocks: {len(response.content)}", tag="AGENT")
                debug(f"  Block types: {[b.type for b in response.content]}", tag="AGENT")
                return "(Agent selesai tapi tidak ada respon teks. Coba ulangi pertanyaan mas rusdi.)"

            return jawaban

        # --- Kasus B: LLM Ingin Menggunakan Alat Bantu (tool_use) ---
        # Ini artinya AI sedang "berpikir" dan menyuruh kita:
        # "Tolong program, tolong jalankan perintah tool X pakai parameter Y untukku!"
        if response.stop_reason == "tool_use":
            debug("⚙️ [STEP 3b] stop_reason=tool_use → eksekusi tool", tag="AGENT")

            tool_blocks = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if hasattr(b, "text") and b.text]
            debug(f"  Content blocks: {len(tool_blocks)} tool_use, {len(text_blocks)} text", tag="AGENT")

            messages.append({"role": "assistant", "content": content_to_dict(response.content)})

            for block in text_blocks:
                debug(f"  💭 Pemikiran LLM: \"{block.text[:100]}...\"", tag="AGENT")
                console.print(f"[dim italic]{block.text}[/dim italic]")

            tool_results = []

            for idx, block in enumerate(tool_blocks, 1):
                tool_name = block.tool_name
                tool_input = block.tool_input
                tool_use_id = block.tool_use_id

                debug_separator(f"TOOL #{idx}: {tool_name}")
                debug(f"  Nama : {tool_name}", tag="AGENT")
                debug(f"  Input: {_format_params(tool_input)}", tag="AGENT")

                if tool_name in DANGEROUS_TOOLS:
                    debug(f"  ⚠️ Tool berbahaya! Minta konfirmasi...", tag="AGENT")
                    if not _ask_confirmation(tool_name, tool_input):
                        debug(f"  ❌ User menolak!", tag="AGENT")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "_tool_name": tool_name,
                            "content": "User menolak eksekusi tool ini."
                        })
                        continue
                    debug(f"  ✅ User menyetujui", tag="AGENT")

                debug(f"  ⏳ Mengeksekusi...", tag="AGENT")
                result = execute_tool(tool_name, tool_input)

                original_len = len(result)
                result = ctx_manager.truncate_text(result, max_chars=50000)
                if len(result) < original_len:
                    debug(f"  ✂️ Truncated: {original_len} → {len(result)} chars", tag="AGENT")

                preview = result[:200] + "..." if len(result) > 200 else result
                debug(f"  📄 Preview: {preview}", tag="AGENT")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "_tool_name": tool_name,
                    "content": result,
                })

            debug(f"📤 [STEP 4] Mengirim {len(tool_results)} tool result(s) ke LLM...", tag="AGENT")
            messages.append({"role": "user", "content": tool_results})
            debug("🔄 Mengulang agent loop...", tag="AGENT")
            continue

        # --- Kasus C: tidak dikenali ---
        debug(f"⚠️ stop_reason tidak dikenali: \"{response.stop_reason}\"", tag="AGENT")
        jawaban = ""
        for block in response.content:
            if hasattr(block, "text") and block.text:
                jawaban += block.text
        messages.append({"role": "assistant", "content": content_to_dict(response.content)})
        return jawaban if jawaban else f"(stop_reason tidak dikenali: {response.stop_reason})"


def _format_params(params):
    """Format parameter tool agar mudah dibaca."""
    parts = []
    for key, value in params.items():
        str_value = str(value)
        if len(str_value) > 50:
            str_value = str_value[:50] + "..."
        parts.append(f'{key}="{str_value}"')
    return ", ".join(parts)


def _ask_confirmation(tool_name, tool_input):
    """Minta konfirmasi user sebelum menjalankan tool berbahaya."""
    console.print(f"\n  [bold red]⚠️  Tool '{tool_name}' akan mengubah file![/bold red]")

    # Khusus untuk write_file, tampilkan diff preview (seperti git log)
    if tool_name == "write_file" and "path" in tool_input and "content" in tool_input:
        path = tool_input["path"]
        new_content = str(tool_input["content"])
        
        console.print(f"  [yellow]  path: {path}[/yellow]")
        
        import os
        from tools.file_tools import generate_diff
        
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    old_content = f.read()
                
                diff_text = generate_diff(old_content, new_content, path)
                
                if diff_text == "(tidak ada perubahan)":
                    console.print(f"  [dim italic]  (Isi file sama persis, tidak ada perubahan)[/dim italic]")
                else:
                    console.print(f"  [bold cyan]=== DIFF PREVIEW ===[/bold cyan]")
                    # Tampilkan diff dengan pewarnaan ala Git
                    for line in diff_text.splitlines():
                        if line.startswith("+") and not line.startswith("+++"):
                            console.print(f"  [green]{line}[/green]")
                        elif line.startswith("-") and not line.startswith("---"):
                            console.print(f"  [red]{line}[/red]")
                        elif line.startswith("@@"):
                            console.print(f"  [cyan]{line}[/cyan]")
                        else:
                            console.print(f"  {line}")
                            
            except Exception as e:
                console.print(f"  [dim]  Gagal membaca preview diff: {e}[/dim]")
        else:
            console.print(f"  [bold green]  [NEW FILE] File baru akan dibuat.[/bold green]")
            
    else:
        # Fallback untuk tool lain (kalau ada)
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
    """
    Entry point utama amba-gent.
    """
    args = parse_args()

    # Debug flag: CLI flag override .env
    if args.debug:
        import config
        config.DEBUG = True

    # Validasi: --provider dan --model harus dipakai bersamaan
    has_provider = args.provider is not None
    has_model = args.model is not None
    if has_provider != has_model:
        console.print("[bold red]Error:[/bold red] --provider dan --model HARUS dipakai bersamaan.")
        console.print("[dim]Contoh: py -3 main.py --provider gemini --model gemini-2.0-flash[/dim]")
        sys.exit(1)

    debug_separator("AMBA-GENT STARTUP")
    debug(f"Debug mode: {'AKTIF ✅' if DEBUG else 'NONAKTIF'}", tag="STARTUP")

    # Provider & model — pakai default kalau tidak di-specify
    provider = args.provider or DEFAULT_PROVIDER
    debug(f"Provider: {provider}, Model: {args.model or 'default'}", tag="STARTUP")

    # Deteksi project
    debug("Mendeteksi jenis project...", tag="STARTUP")
    system_prompt = build_system_prompt()

    # Tampilkan header
    project_info = detect_project(".")
    console.print(
        Panel.fit(
            "[bold cyan]🤖 Amba-Gent[/bold cyan] — AI Coding Agent\n"
            "[dim]Ketik pesan untuk mulai. Ketik 'exit' untuk keluar.[/dim]\n"
            "[dim]Agent bisa membaca, menulis, dan mencari kode di project kamu.[/dim]\n"
            f"[dim]Project: {project_info['summary']}[/dim]",
            border_style="cyan",
        )
    )

    # Inisialisasi LLM client via factory
    debug("Inisialisasi LLM client...", tag="STARTUP")
    try:
        llm = create_llm_client(provider=provider, model=args.model)
        console.print("[green]✓ Terhubung ke LLM[/green]")
        console.print(f"[dim]  Provider  : {llm.provider_name}[/dim]")
        console.print(f"[dim]  Model     : {llm.model_name}[/dim]")
        console.print(f"[dim]  Tools aktif: {', '.join(t['name'] for t in TOOLS)}[/dim]")
        console.print(f"[dim]  Debug mode : {'AKTIF' if DEBUG else 'NONAKTIF'}[/dim]\n")
    except Exception as e:
        debug(f"❌ Gagal koneksi: {e}", tag="STARTUP")
        console.print(f"[bold red]✗ Gagal koneksi:[/bold red] {e}")
        return

    # Session management
    messages = []

    if args.resume:
        debug("Mode resume: memuat session terakhir...", tag="SESSION")
        loaded = session_mgr.load_latest()
        if loaded:
            messages = loaded["messages"]
            console.print(f"[green]✓ Session dilanjutkan:[/green] {loaded['id']} ({len(messages)} messages)")
        else:
            console.print("[yellow]Tidak ada session sebelumnya. Memulai sesi baru.[/yellow]")
            session_mgr.new_session()
    else:
        session_mgr.new_session()

    debug("Chat loop dimulai...", tag="STARTUP")

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

        debug_separator("INPUT USER BARU")
        debug(f"User input: \"{user_input[:100]}{'...' if len(user_input) > 100 else ''}\"", tag="AGENT")

        messages.append({"role": "user", "content": user_input})

        try:
            jawaban = agent_loop(llm, messages, system_prompt)

            stream_display(jawaban)

            session_mgr.save(messages)
            debug("Session auto-saved ✓", tag="SESSION")

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
