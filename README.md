# Amba-Gent

AI Coding Agent berbasis CLI yang terintegrasi langsung dengan file-system dan proyek Anda. Bekerja layaknya rekan kerja Full-Stack Developer mampu membaca, mencari, dan mengedit file secara mandiri lewat arsitektur Agentic Loop.

---

## Fitur

### Multi-LLM Provider

Support Anthropic dan Google Gemini via adapter pattern. Setiap provider punya adapter sendiri yang menerjemahkan format API ke `UnifiedResponse` standar.

```bash
# Default (Anthropic via proxy)
py -3 main.py

# Switch ke Gemini
py -3 main.py --provider gemini --model gemini-2.0-flash

# Switch ke Anthropic dengan model spesifik
py -3 main.py --provider anthropic --model glm-5
```

> **Note:** `--provider` dan `--model` HARUS dipakai bersamaan untuk switch LLM.

### Agentic Loop

Bukan chatbot biasa. Satu query bisa trigger multiple tool calls secara sirkular sampai tugas selesai. Contoh: "Fix bug auth" → agent cari file → baca kode → analisa → tulis perbaikan → rangkum hasil.

### Tool Calling

| Tool | Fungsi | Konfirmasi |
|------|--------|-----------|
| `read_file` | Baca isi file | Tidak |
| `write_file` | Tulis/buat file + diff preview | Ya |
| `list_directory` | Jelajahi struktur folder | Tidak |
| `search_code` | Grep literal case-insensitive | Tidak |
| `search_codebase` | Semantic search via TF-IDF RAG | Tidak |

### RAG (Retrieval-Augmented Generation) Engine

Pencarian semantik berbasis TF-IDF yang berjalan sepenuhnya lokal tanpa model embedding atau API eksternal.

**Cara kerja:**

```
INDEXING (sekali saat startup)
  Codebase → scan file → pecah per 30 baris (chunk) → tokenize → hitung TF-IDF → simpan di memory

RETRIEVAL (setiap query via search_codebase)
  Query → tokenize → skor TF-IDF per chunk → ranking → return top-K hasil
```

**Kenapa TF-IDF bukan embedding?**
- Pencarian kode kebanyakan exact match (nama fungsi, variabel, class)
- TF-IDF ringan, cepat, zero dependency
- Embedding butuh model tambahan, lebih berat, untuk kode tidak se-signifikan

**Konsep TF-IDF:**
- **TF (Term Frequency)** = seberapa sering kata muncul di chunk ini
- **IDF (Inverse Document Frequency)** = seberapa jarang kata di seluruh codebase
- Kata unik (`authenticate`) → skor tinggi. Kata umum (`import`) → skor rendah

**File yang di-index:** 40+ ekstensi meliputi Python, JS/TS, Go, Rust, Java, C/C++, PHP, Ruby, config files (JSON, YAML, TOML), SQL, Markdown, dan lainnya.

**Folder yang di-skip:** `.git`, `node_modules`, `venv`, `__pycache__`, `build`, `dist`, `vendor`, `.vscode`, `.idea`, dan lainnya.

**Contoh:**
```
User: "Di mana logika authentication?"
→ search_codebase("authentication logic")
→ RAG: ditemukan di auth.py baris 45-75 (skor 2.8)
→ LLM jawab berdasarkan kode yang ditemukan
```

### Smart Context Management

Otomatis atur dan pangkas token. History percakapan terlalu panjang → context window buang pesan paling usang, respon tetap stabil.

### Session Management (Auto-Save)

Percakapan otomatis tersimpan di `sessions/`. Gunakan `--resume` untuk lanjutkan.

### Diff Preview

Sebelum `write_file` dieksekusi, tampil diff ala git baris merah (dihapus), hijau (ditambah). User konfirmasi (y/n) dulu.

### Project Auto-Detection

Deteksi otomatis: Git status, bahasa dominan (Python, JS, etc.), framework. Info disuntikkan ke system prompt.

### Streaming Output

Jawaban ditampilkan dengan typewriter effect via Rich Live render.

---

## CLI Reference

```
usage: amba-gent [-h] [--resume] [--provider {anthropic,gemini}] [--model MODEL] [--debug]

options:
  -h, --help            show this help message and exit
  --resume              Lanjutkan sesi percakapan terakhir yang tersimpan
  --provider            Pilih LLM provider: anthropic, gemini
  --model MODEL         Override nama model
  --debug               Aktifkan debug mode
```

Contoh:
```bash
py -3 main.py                                              # Sesi baru, provider default
py -3 main.py --resume                                     # Lanjutkan sesi terakhir
py -3 main.py --provider gemini --model gemini-2.0-flash   # Switch ke Gemini
py -3 main.py --provider anthropic --model glm-5           # Switch ke Anthropic
py -3 main.py --debug                                      # Debug mode
```

---

## Instalasi

**Prasyarat:** Python 3.11+

1. **Clone & masuk direktori**
   ```bash
   git clone <repo-url> amba-gent && cd amba-gent
   ```

2. **Virtual environment**
   ```bash
   py -3 -m venv venv
   .\venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   py -3 -m pip install anthropic python-dotenv rich google-genai
   ```

4. **Konfigurasi `.env`**
   ```bash
   cp .env-example .env
   ```
   Edit `.env`:
   ```env
   # Anthropic (atau proxy)
   API_KEY=your-key-here
   BASE_URL=https://api.z.ai/api/anthropic
   MODEL=glm-5

   # Gemini (opsional — cukup isi salah satu)
   GEMINI_API_KEY=your-gemini-key
   GEMINI_MODEL=gemini-2.0-flash

   # Provider default
   PROVIDER=anthropic

   # Debug
   DEBUG=false
   ```

5. **Jalankan**
   ```bash
   py -3 main.py
   ```

---

## Arsitektur

```
main.py                  Entry point + argparse CLI
config.py                Env config (multi-provider)
core/
  adapters/
    base.py              BaseLLMAdapter (ABC) + UnifiedResponse
    anthropic_adapter.py Adapter untuk Anthropic API
    gemini_adapter.py    Adapter untuk Google Gemini API
  llm_client.py          Factory: create_llm_client(provider, model)
  context.py             Context window management
  session.py             Session save/load (JSON)
  project.py             Auto-detect project type
  logger.py              Debug logger
tools/
  definitions.py         Tool schema (JSON Schema)
  executor.py            Tool execution dispatcher
  file_tools.py          File ops (read, write, diff)
  search_tools.py        Grep + RAG search
rag/
  indexer.py             TF-IDF indexer (chunking, tokenizing, scoring)
  retriever.py           Search wrapper + result formatter
```

**Flow:**
```
User input → agent_loop → LLM (via adapter) → tool_use? → execute → loop
                         ↓ end_turn
                         → stream_display → user
```

---

*Amba-Gent — Personal AI Engineer for Mas Rusdi.*
