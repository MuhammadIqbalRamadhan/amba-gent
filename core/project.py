# -*- coding: utf-8 -*-
"""
core/project.py — Project Auto-Detection

=== MASALAH YANG DISELESAIKAN ===
Amba-gent tidak tahu project apa yang sedang dipakai user.
Kalau tahu jenis project-nya, amba-gent bisa:
- Menyesuaikan bahasa/istilah yang dipakai
- Memberikan saran yang lebih spesifik
- Menginformasikan ke LLM tentang tech stack yang dipakai

=== CARA KERJA ===
Deteksi jenis project berdasarkan file-file yang ada di root folder:

    package.json       → Node.js / JavaScript
    requirements.txt   → Python
    composer.json      → PHP (Laravel, dll)
    go.mod             → Go
    Cargo.toml         → Rust
    pom.xml            → Java (Maven)
    Gemfile            → Ruby (Rails)

Deteksi framework juga berdasarkan file spesifik:
    next.config.*      → Next.js
    nuxt.config.*      → Nuxt.js
    manage.py          → Django
    artisan            → Laravel

=== KENAPA PENTING? ===
System prompt yang tahu konteks project akan menghasilkan jawaban LLM
yang jauh lebih relevan dan akurat.

Contoh tanpa auto-detect:
    LLM: "Untuk install library, gunakan pip install..."
    (padahal project-nya Node.js!)

Contoh dengan auto-detect:
    LLM: "Untuk install library, gunakan npm install..."
    (karena tahu project-nya Node.js dari package.json)
"""

import os
from core.logger import debug


# === DETEKSI BAHASA / RUNTIME ===
# Format: (nama_file, bahasa, runtime)
LANGUAGE_MARKERS = [
    # Python
    ("requirements.txt", "Python", "Python/pip"),
    ("setup.py", "Python", "Python/setuptools"),
    ("pyproject.toml", "Python", "Python/poetry"),
    ("Pipfile", "Python", "Python/pipenv"),

    # JavaScript / Node.js
    ("package.json", "JavaScript/TypeScript", "Node.js/npm"),
    ("yarn.lock", "JavaScript/TypeScript", "Node.js/yarn"),
    ("pnpm-lock.yaml", "JavaScript/TypeScript", "Node.js/pnpm"),
    ("bun.lockb", "JavaScript/TypeScript", "Bun"),

    # PHP
    ("composer.json", "PHP", "PHP/Composer"),

    # Go
    ("go.mod", "Go", "Go"),

    # Rust
    ("Cargo.toml", "Rust", "Rust/Cargo"),

    # Java
    ("pom.xml", "Java", "Java/Maven"),
    ("build.gradle", "Java/Kotlin", "Gradle"),

    # Ruby
    ("Gemfile", "Ruby", "Ruby/Bundler"),

    # .NET / C#
    ("*.csproj", "C#", ".NET"),
    ("*.sln", "C#", ".NET"),
]

# === DETEKSI FRAMEWORK ===
# Format: (nama_file, nama_framework)
FRAMEWORK_MARKERS = [
    # JavaScript Frameworks
    ("next.config.js", "Next.js"),
    ("next.config.mjs", "Next.js"),
    ("next.config.ts", "Next.js"),
    ("nuxt.config.js", "Nuxt.js"),
    ("nuxt.config.ts", "Nuxt.js"),
    ("vite.config.js", "Vite"),
    ("vite.config.ts", "Vite"),
    ("angular.json", "Angular"),
    ("svelte.config.js", "SvelteKit"),
    ("astro.config.mjs", "Astro"),

    # Python Frameworks
    ("manage.py", "Django"),
    ("app.py", "Flask"),
    ("fastapi", "FastAPI"),  # biasanya di import, tapi cek folder juga

    # PHP Frameworks
    ("artisan", "Laravel"),
    ("wp-config.php", "WordPress"),

    # Mobile
    ("pubspec.yaml", "Flutter/Dart"),
    ("android/", "Android"),
    ("ios/", "iOS"),

    # DevOps
    ("Dockerfile", "Docker"),
    ("docker-compose.yml", "Docker Compose"),
    ("docker-compose.yaml", "Docker Compose"),
    (".github/workflows", "GitHub Actions"),
]


def detect_project(path="."):
    """
    Deteksi jenis project berdasarkan file-file yang ada.

    Parameter:
    - path: root folder project (default: folder saat ini)

    Return:
    - dict berisi informasi project:
      {
          "languages": ["Python"],
          "runtimes": ["Python/pip"],
          "frameworks": ["Django"],
          "has_git": True,
          "summary": "Python project menggunakan Django"
      }
    """
    abs_path = os.path.abspath(path)
    debug(f"Mendeteksi project di: {abs_path}", tag="PROJECT")

    # Ambil daftar file di root project
    try:
        entries = os.listdir(abs_path)
    except OSError:
        debug("❌ Gagal membaca direktori project", tag="PROJECT")
        return {"languages": [], "runtimes": [], "frameworks": [], "has_git": False, "summary": "Tidak terdeteksi"}

    entries_lower = {e.lower() for e in entries}  # Set untuk lookup cepat

    # --- Deteksi bahasa/runtime ---
    languages = []
    runtimes = []

    for marker_file, language, runtime in LANGUAGE_MARKERS:
        if marker_file.startswith("*"):
            # Wildcard match (*.csproj, *.sln)
            ext = marker_file[1:]  # ".csproj"
            if any(e.endswith(ext) for e in entries):
                if language not in languages:
                    languages.append(language)
                if runtime not in runtimes:
                    runtimes.append(runtime)
        else:
            if marker_file.lower() in entries_lower:
                if language not in languages:
                    languages.append(language)
                if runtime not in runtimes:
                    runtimes.append(runtime)

    # --- Deteksi framework ---
    frameworks = []

    for marker_file, framework in FRAMEWORK_MARKERS:
        # Cek file atau folder
        marker_path = os.path.join(abs_path, marker_file)
        if os.path.exists(marker_path):
            if framework not in frameworks:
                frameworks.append(framework)

    # --- Deteksi Git ---
    has_git = os.path.exists(os.path.join(abs_path, ".git"))

    # --- Bangun summary ---
    parts = []
    if languages:
        parts.append(f"{'/'.join(languages)} project")
    if frameworks:
        parts.append(f"menggunakan {', '.join(frameworks)}")
    if has_git:
        parts.append("(Git enabled)")

    summary = " ".join(parts) if parts else "Project type tidak terdeteksi"

    result = {
        "languages": languages,
        "runtimes": runtimes,
        "frameworks": frameworks,
        "has_git": has_git,
        "summary": summary,
    }

    debug(f"Hasil deteksi: {summary}", tag="PROJECT")
    debug(f"  Languages : {languages}", tag="PROJECT")
    debug(f"  Runtimes  : {runtimes}", tag="PROJECT")
    debug(f"  Frameworks: {frameworks}", tag="PROJECT")
    debug(f"  Git       : {has_git}", tag="PROJECT")

    return result


def generate_project_context(project_info):
    """
    Buat teks context project untuk ditambahkan ke system prompt.

    Teks ini akan dikirim ke LLM agar dia tahu konteks project user.

    Parameter:
    - project_info: dict dari detect_project()

    Return:
    - String konteks untuk sisipkan ke system prompt

    Contoh output:
        "PROJECT CONTEXT:
         Bahasa: Python
         Runtime: Python/pip
         Framework: Django
         Git: aktif"
    """
    if not project_info["languages"]:
        return ""  # Tidak ada yang terdeteksi, jangan tambah context

    lines = ["\nPROJECT CONTEXT (informasi project yang sedang dikerjakan user):"]
    lines.append(f"- Bahasa: {', '.join(project_info['languages'])}")

    if project_info["runtimes"]:
        lines.append(f"- Runtime/Package Manager: {', '.join(project_info['runtimes'])}")

    if project_info["frameworks"]:
        lines.append(f"- Framework: {', '.join(project_info['frameworks'])}")

    if project_info["has_git"]:
        lines.append("- Git: aktif (project menggunakan version control)")

    lines.append("Gunakan informasi ini untuk memberikan saran yang sesuai dengan tech stack user.")

    return "\n".join(lines)
