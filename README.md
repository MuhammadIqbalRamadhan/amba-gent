# 🤖 Amba-gent

Amba-gent adalah asisten AI Engineer pribadi berbasis *Command Line Interface* (CLI) yang terintegrasi langsung dengan mesin komputer dan proyek yang sedang Anda kerjakan. Didesain secara spesifik layaknya rekan kerja *Full-Stack Developer*, Amba-gent mampu memahami, mencari, dan mengedit file secara mandiri di dalam proyek Anda dengan arsitektur *Agentic Loop*.

---

## ✨ Fitur Utama

- **🧠 Agentic Loop Execution**
  Berbeda dari sekadar model chatbot standar, Amba-gent bekerja layaknya agen. Untuk satu kueri pengguna seperti "Perbaiki bug auth", agen mampu berpikir, menemukan file konfigurasi yang tepat, membaca kodenya, merancang aksi, menimpa file dengan kode perbaikan, dan merangkum hasil kerja secara sirkular.

- **🛠️ Penggunaan Tool Lokal Otomatis (*Tool Calling*)**
  Dilengkapi beragam tool khusus untuk membaca dan mengubah *file-system*:
  - **`read_file`**: Membaca isi detail code dalam suatu modul.
  - **`write_file`**: Membuat file baru atau menimpa modifikasi kode.
  - **`list_directory`**: Menjelajahi struktur file (seperti tree explorer) dari direktori tertentu.
  - **`search_code`**: Fitur *Find in Files* (Grep literal) untuk mencari teks secara case-insensitive lintas direktori kode.

- **📚 TF-IDF RAG Engine (`search_codebase`)**
  Amba-gent dibekali mesin berbasis Retrieval-Augmented Generation secara mandiri dengan algoritma *TF-IDF* tanpa bergantung pada service vektor luar. Agent dapat mengekstrak logika dari dokumen-dokumen yang secara *semantik* sangat krusial dengan mem-parsing kode.

- **🛡️ Fitur Keamanan dan HitL (Human-in-the-loop)**
  Amba-gent transparan! Jika memutuskan untuk mengubah isi project (memanggil file berisiko tinggi seperti `write_file`), mesin akan mengonfirmasi tindakan tersebut kepada user via prompt. Anda tidak perlu khawatir agent tiba-tiba merusak komponen krusial.

- **🧠 Smart Context Management**
  Otomatis mengatur dan memangkas ukuran token LLM. Jika sejarah percakapan / memori terminal menjadi terlalu besar, arsitektur *Context Window* akan membuang memori paling usang secara aman, menjamin respon tetap konstan.

- **🐛 Transparansi Pikiran (Watchlist & Debug Mode)**
  Sebuah sakelar toggle `DEBUG_MODE=True`, memperbolehkan pengguna melihat visualisasi bagaimana "otak" representatif mesin menganalisis problem dari 1 hingga proses pengembalian pesan secara elegan.

- **🌊 Streaming Output (Typewriter Effect)**
  Tampilan jawaban akhir AI diproses secara elegan dengan memberikan efek "mengetik" menggunakan sinkronisasi waktu dan *Rich Live* render, memberikan Anda *User Experience* interaksi natural alih-alih menampilkan blok teks kaku.

- **💾 Manajemen Sesi Persisten (Auto-Save)**
  Setiap interaksi obrolan akan otomatis tersimpan ke dalam format penyimpanan lokal di `sessions/`. Anda dapat menggunakan perintah argument `--resume` untuk meneruskan konteks riwayat percakapan secara mulus meskipun aplikasi sempat tertutup!

- **🤖 Deteksi Lingkungan Project (Auto-Context)**
  Sistem dibekali kemampuan "merasakan" direktori kerjanya secara mandiri. AI mendeteksi status Git-enabled maupun bahasa dominan (Python, JS, etc.) yang sedang diawasi lalu menyuntikkan *system prompt* yang dinamis dan relevan terhadap kode Anda secara cerdas.

## 🚀 Persiapan dan Cara Instalasi

Pastikan Anda memiliki instalasi Python 3.11 atau ke atas.

1. **Persiapkan Environment**
   Setel *virtual environment* Python agar dependensi lebih tertata:
   ```bash
   python -m venv venv
   # Source activate di Windows:
   .\venv\Scripts\activate
   ```

2. **Dapatkan Dependencies yang Diperlukan**
   Sistem mewajibkan library berikut (seperti Rich, ZhipuAI, dll):
   ```bash
   pip install typer zhipuai python-dotenv rich
   ```

3. **Konfigurasi Lingkungan (Env)**
   Silakan duplikasikan `.env-example` menjadi `.env` dan letakkan credential / API Key Zhipu / GLM4 ke dalam file tersebut sebelum eksekusi.

4. **Jalankan Amba-gent**
   ```bash
   # Masuk ke portal Amba-gent dan mulai task baru
   py -3 main.py

   # Atau, teruskan percakapan sebelumnya jika ada project yang belum tuntas:
   py -3 main.py --resume
   ```

   **💡 TIPS PRO (Penggunaan Lintas-Project):** Anda telah dapat memanggil `amba-gent` langsung di PowerShell manapun menggunakan ALIAS GLOBAL! 
   Hanya dengan mengetikkan perintah `ambagent` di dalam terminal dari modul lain yang sedang Anda kerjakan, AI akan datang dan menganalisa direktori spesifik tersebut seketika.

5. Interaksikan langsung dengan mengetik instruksi. Anda bisa menggunakan *"Tolong beri komentar di auth.py"* atau *"Cari modul untuk parsing log"*. 

---
*Amba-gent – A Personal AI Engineer crafted specially for Mas Rusdi.*