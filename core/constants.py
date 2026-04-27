# -*- coding: utf-8 -*-
"""
core/constants.py — Daftar konstanta general yang digunakan lintas modul.
Berisi daftar ekstensi file, direktori yang dilewati, dan konfigurasi statis lainnya.
"""

# Daftar ektensi file yang relevan untuk proses percarian dan indexing (RAG) codebase.
# Sangat komprehensif agar mencakup hampir semua bahasa pemrograman dan format konfigurasi awam.
INDEXABLE_EXTENSIONS = {
    # Web & Scripts
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".php", ".rb", ".pl", ".lua", ".sh", ".bash", ".zsh", ".bat", ".cmd", ".ps1",

    # Systems & Compiled
    ".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".m", ".mm",
    ".cs", ".java", ".kt", ".kts", ".scala", ".groovy",
    ".go", ".rs", ".swift", ".dart", ".rmd",

    # Configs & Data
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".env.example",
    ".xml", ".csv", ".sql", ".graphql", ".gql",
    
    # Docs
    ".md", ".txt", ".rst",
}

# Alias jika modul lain membutuhkan nama SEARCHABLE_EXTENSIONS
SEARCHABLE_EXTENSIONS = INDEXABLE_EXTENSIONS

# Direktori yang secara default di-skip agar tidak memberatkan indexer dan pencarian kode
SKIP_DIRS = {
    # VCS
    ".git", ".svn", ".hg",
    
    # Python
    "__pycache__", "venv", ".venv", "env", ".env_dir", ".tox", ".pytest_cache", "eggs", ".eggs", "dist", "build",
    
    # Node / Web Frameworks
    "node_modules", ".history", ".next", ".nuxt", "coverage", ".cache", "bower_components",
    
    # Java / C# / Builders PHP dll
    "target", "bin", "obj", "out", "vendor",
    
    # OS / IDE / Logs
    ".vscode", ".idea", ".eclipse", ".vs", "tmp", "temp", "logs", ".serverless",
}
