# -*- coding: utf-8 -*-
"""
core/session.py — Session Management (Simpan & Resume Percakapan)

=== MASALAH YANG DISELESAIKAN ===
Sebelumnya, setiap kali amba-gent ditutup, semua percakapan HILANG.
User harus mulai dari awal lagi. Ini tidak praktis!

Dengan Session Management:
- Percakapan otomatis disimpan ke file JSON
- Saat amba-gent dibuka lagi, bisa melanjutkan percakapan terakhir
- Bisa juga memulai sesi baru

=== BAGAIMANA CARA KERJANYA? ===

    ┌─────────────┐      ┌──────────────────┐
    │  amba-gent   │ ──── │  sessions/       │
    │  (memory)    │ save │  session_001.json│
    │  messages[]  │ ────→│  session_002.json│
    │              │ load │  ...             │
    │              │ ←────│                  │
    └─────────────┘      └──────────────────┘

=== FORMAT FILE SESSION ===
{
    "id": "20260427_110500",
    "created_at": "2026-04-27 11:05:00",
    "updated_at": "2026-04-27 11:30:00",
    "messages": [ ... list percakapan ... ]
}

=== KENAPA JSON DAN BUKAN DATABASE? ===
1. JSON mudah dibaca manusia (bisa buka di notepad)
2. Tidak perlu install dependency tambahan
3. Cukup untuk skala percakapan CLI agent
4. Kalau nanti butuh lebih advanced → migrasi ke SQLite

=== LOKASI FILE ===
Sessions disimpan di folder "sessions/" di root project.
Folder ini otomatis dibuat kalau belum ada.
"""

import os
import json
from datetime import datetime
from core.logger import debug


# Folder tempat menyimpan sessions
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sessions")


class SessionManager:
    """
    Mengelola penyimpanan dan pemuatan session percakapan.

    Cara pakai:
        sm = SessionManager()

        # Mulai sesi baru
        sm.new_session()

        # Simpan messages
        sm.save(messages)

        # Load sesi terakhir
        messages = sm.load_latest()

        # Lihat semua sesi
        sessions = sm.list_sessions()
    """

    def __init__(self):
        """Inisialisasi SessionManager. Buat folder sessions/ kalau belum ada."""

        # os.makedirs() dengan exist_ok=True = buat folder, tapi jangan error kalau sudah ada
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        debug(f"Session directory: {SESSIONS_DIR}", tag="SESSION")

        # ID sesi aktif (format: YYYYMMDD_HHMMSS)
        self.current_session_id = None

    def new_session(self):
        """
        Buat session baru dengan ID berdasarkan waktu sekarang.

        ID format: "20260427_110500" (tanggal_jam)
        Ini memastikan setiap session punya ID unik dan terurut kronologis.
        """
        # datetime.now() = waktu saat ini
        # strftime() = format waktu jadi string
        self.current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug(f"Sesi baru dibuat: {self.current_session_id}", tag="SESSION")
        return self.current_session_id

    def save(self, messages):
        """
        Simpan messages ke file JSON.

        Parameter:
        - messages: list percakapan yang akan disimpan

        CATATAN PENTING:
        Messages dari Anthropic API mengandung object Python (TextBlock, ToolUseBlock)
        yang tidak bisa langsung di-serialize ke JSON. Kita perlu konversi dulu ke
        format yang JSON-friendly.
        """
        if not self.current_session_id:
            self.new_session()

        filepath = os.path.join(SESSIONS_DIR, f"{self.current_session_id}.json")

        # Konversi messages ke format yang bisa di-serialize JSON
        serializable_messages = self._serialize_messages(messages)

        data = {
            "id": self.current_session_id,
            "created_at": self.current_session_id,  # Dari ID (sudah berisi timestamp)
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message_count": len(messages),
            "messages": serializable_messages,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            # indent=2 = buat JSON rapih dan mudah dibaca
            # ensure_ascii=False = supaya karakter Indonesia tidak jadi \uXXXX
            json.dump(data, f, indent=2, ensure_ascii=False)

        debug(f"Session disimpan: {filepath} ({len(messages)} messages)", tag="SESSION")

    def load_latest(self):
        """
        Muat session terakhir (paling baru berdasarkan nama file).

        Return:
        - list messages kalau ada session, atau None kalau kosong

        Cara kerja:
        1. List semua file .json di folder sessions/
        2. Urutkan berdasarkan nama (karena ID berisi timestamp, otomatis kronologis)
        3. Ambil yang terakhir (terbaru)
        4. Baca dan return messages-nya
        """
        sessions = self.list_sessions()

        if not sessions:
            debug("Tidak ada session yang tersimpan", tag="SESSION")
            return None

        # Ambil session terbaru (terakhir di list setelah diurutkan)
        latest = sessions[-1]
        debug(f"Memuat session terbaru: {latest['id']}", tag="SESSION")

        return self._load_session_file(latest["filepath"])

    def list_sessions(self):
        """
        Tampilkan daftar semua session yang tersimpan.

        Return:
        - List of dict, masing-masing berisi:
          {"id": "...", "filepath": "...", "message_count": ..., "updated_at": "..."}
        """
        if not os.path.exists(SESSIONS_DIR):
            return []

        sessions = []

        # Cari semua file .json di folder sessions/
        for filename in sorted(os.listdir(SESSIONS_DIR)):
            if not filename.endswith(".json"):
                continue

            filepath = os.path.join(SESSIONS_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                sessions.append({
                    "id": data.get("id", filename),
                    "filepath": filepath,
                    "message_count": data.get("message_count", 0),
                    "updated_at": data.get("updated_at", "?"),
                })
            except (json.JSONDecodeError, KeyError):
                continue  # Skip file yang rusak

        debug(f"Ditemukan {len(sessions)} session tersimpan", tag="SESSION")
        return sessions

    def _load_session_file(self, filepath):
        """
        Muat messages dari file session JSON.

        Return:
        - dict {"messages": [...], "id": "..."}
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.current_session_id = data.get("id")
            messages = data.get("messages", [])
            debug(f"Session loaded: {self.current_session_id} ({len(messages)} messages)", tag="SESSION")
            return {"messages": messages, "id": self.current_session_id}

        except Exception as e:
            debug(f"❌ Gagal load session: {e}", tag="SESSION")
            return None

    def _serialize_messages(self, messages):
        """
        Konversi messages ke format yang bisa di-serialize ke JSON.

        Kenapa perlu ini?
        Messages dari Anthropic API mengandung object Python khusus:
        - TextBlock(text="...", type="text")
        - ToolUseBlock(id="...", name="...", input={...}, type="tool_use")

        Object ini tidak bisa langsung json.dump(). Kita perlu ubah ke dict biasa.

        Contoh:
            Sebelum: [TextBlock(text="halo"), ToolUseBlock(name="read_file", ...)]
            Sesudah: [{"type":"text","text":"halo"}, {"type":"tool_use","name":"read_file",...}]
        """
        result = []

        for msg in messages:
            serialized = {"role": msg.get("role", "user")}

            content = msg.get("content", "")

            # Kasus 1: Content string biasa
            if isinstance(content, str):
                serialized["content"] = content

            # Kasus 2: Content list (bisa berisi TextBlock, ToolUseBlock, atau dict)
            elif isinstance(content, list):
                serialized_content = []

                for item in content:
                    if isinstance(item, dict):
                        # Sudah dalam format dict (misalnya tool_result)
                        serialized_content.append(item)
                    elif hasattr(item, "type"):
                        # Anthropic API object → konversi ke dict
                        if item.type == "text":
                            serialized_content.append({
                                "type": "text",
                                "text": getattr(item, "text", ""),
                            })
                        elif item.type == "tool_use":
                            serialized_content.append({
                                "type": "tool_use",
                                "id": getattr(item, "id", ""),
                                "name": getattr(item, "name", ""),
                                "input": getattr(item, "input", {}),
                            })
                        else:
                            serialized_content.append({"type": item.type, "data": str(item)})
                    else:
                        serialized_content.append(str(item))

                serialized["content"] = serialized_content
            else:
                serialized["content"] = str(content)

            result.append(serialized)

        return result
