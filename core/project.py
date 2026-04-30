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
import json
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

    entries_lower = {e.lower() for e in entries}

    # --- Deteksi bahasa/runtime ---
    languages = []
    runtimes = []

    for marker_file, language, runtime in LANGUAGE_MARKERS:
        if marker_file.startswith("*"):
            ext = marker_file[1:]
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

    # --- Deteksi framework dari file markers ---
    frameworks = []

    for marker_file, framework in FRAMEWORK_MARKERS:
        marker_path = os.path.join(abs_path, marker_file)
        if os.path.exists(marker_path):
            if framework not in frameworks:
                frameworks.append(framework)

    # --- Deteksi framework dari package.json dependencies ---
    for fw in _detect_from_package_json(abs_path):
        if fw not in frameworks:
            frameworks.append(fw)

    # --- Deteksi dari Python ecosystem ---
    for fw in _detect_from_requirements_txt(abs_path):
        if fw not in frameworks:
            frameworks.append(fw)
    for fw in _detect_from_pyproject_toml(abs_path):
        if fw not in frameworks:
            frameworks.append(fw)

    # --- Deteksi dari PHP ecosystem ---
    for fw in _detect_from_composer_json(abs_path):
        if fw not in frameworks:
            frameworks.append(fw)

    # --- Deteksi dari Go ecosystem ---
    for fw in _detect_from_go_mod(abs_path):
        if fw not in frameworks:
            frameworks.append(fw)

    # --- Deteksi dari Rust ecosystem ---
    for fw in _detect_from_cargo_toml(abs_path):
        if fw not in frameworks:
            frameworks.append(fw)

    # --- Deteksi dari Ruby ecosystem ---
    for fw in _detect_from_gemfile(abs_path):
        if fw not in frameworks:
            frameworks.append(fw)

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


def _detect_from_package_json(abs_path):
    """
    Deteksi framework dari package.json dependencies & devDependencies.

    Banyak JS framework tidak punya config file khusus (express, react, etc).
    Cara paling akurat: baca package.json, cek nama package di dependencies.

    Return: list of framework names
    """
    pkg_path = os.path.join(abs_path, "package.json")
    if not os.path.exists(pkg_path):
        return []

    try:
        with open(pkg_path, "r", encoding="utf-8") as f:
            pkg = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    # Gabungkan dependencies + devDependencies
    all_deps = set()
    for key in ("dependencies", "devDependencies"):
        deps = pkg.get(key, {})
        all_deps.update(deps.keys())

    if not all_deps:
        return []

    # Mapping: package name → framework
    PACKAGE_TO_FRAMEWORK = {
        # Full-stack / SSR frameworks
        "next": "Next.js",
        "nuxt": "Nuxt.js",
        "@remix-run/react": "Remix",
        "@sveltejs/kit": "SvelteKit",
        "astro": "Astro",
        "@angular/core": "Angular",
        "@nestjs/core": "NestJS",

        # Backend frameworks
        "express": "Express.js",
        "fastify": "Fastify",
        "koa": "Koa",
        "hono": "Hono",
        "hapi": "Hapi",
        "@hapi/hapi": "Hapi",
        "adonisjs": "AdonisJS",
        "sails": "Sails.js",
        "@feathersjs/feathers": "FeathersJS",
        "strapi": "Strapi",
        "@trpc/server": "tRPC",

        # Frontend / UI frameworks
        "react": "React",
        "react-dom": "React",
        "vue": "Vue.js",
        "svelte": "Svelte",
        "solid-js": "SolidJS",
        "preact": "Preact",
        "@ember/-application": "Ember.js",

        # Build tools
        "vite": "Vite",
        "webpack": "Webpack",
        "esbuild": "esbuild",
        "parcel": "Parcel",
        "rollup": "Rollup",
        "turbo": "Turborepo",

        # Testing
        "jest": "Jest",
        "vitest": "Vitest",
        "mocha": "Mocha",
        "cypress": "Cypress",
        "@playwright/test": "Playwright",

        # Database / ORM
        "prisma": "Prisma",
        "@prisma/client": "Prisma",
        "drizzle-orm": "Drizzle",
        "mongoose": "Mongoose/MongoDB",
        "typeorm": "TypeORM",
        "sequelize": "Sequelize",

        # CSS
        "tailwindcss": "Tailwind CSS",
        "@chakra-ui/react": "Chakra UI",
        "@mui/material": "Material UI",
    }

    detected = []
    for pkg_name, framework in PACKAGE_TO_FRAMEWORK.items():
        if pkg_name in all_deps:
            if framework not in detected:
                detected.append(framework)

    return detected


def _detect_from_requirements_txt(abs_path):
    """Detect Python frameworks from requirements.txt or requirements-dev.txt."""
    results = []
    for filename in ("requirements.txt", "requirements-dev.txt", "requirements_dev.txt"):
        req_path = os.path.join(abs_path, filename)
        if not os.path.exists(req_path):
            continue
        try:
            with open(req_path, "r", encoding="utf-8", errors="ignore") as f:
                pkgs = set()
                for line in f:
                    line = line.strip().lower()
                    if not line or line.startswith("#") or line.startswith("-"):
                        continue
                    name = line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].split("!")[0].split("[")[0].strip()
                    if name:
                        pkgs.add(name)
        except OSError:
            continue

        PY_PACKAGE_MAP = {
            "django": "Django",
            "flask": "Flask",
            "fastapi": "FastAPI",
            "starlette": "Starlette",
            "sanic": "Sanic",
            "tornado": "Tornado",
            "aiohttp": "aiohttp",
            "bottle": "Bottle",
            "pyramid": "Pyramid",
            "falcon": "Falcon",
            "quart": "Quart",
            "litestar": "Litestar",
            "celery": "Celery",
            "scrapy": "Scrapy",
            "sqlalchemy": "SQLAlchemy",
            "django-rest-framework": "DRF",
            "djangorestframework": "DRF",
            "flask-restful": "Flask-RESTful",
            "flask-sqlalchemy": "Flask-SQLAlchemy",
            "pydantic": "Pydantic",
            "pytest": "pytest",
            "selenium": "Selenium",
            "beautifulsoup4": "BeautifulSoup",
            "scikit-learn": "scikit-learn",
            "sklearn": "scikit-learn",
            "tensorflow": "TensorFlow",
            "torch": "PyTorch",
            "transformers": "Hugging Face",
            "pandas": "Pandas",
            "numpy": "NumPy",
            "matplotlib": "Matplotlib",
            "pillow": "Pillow",
            "requests": "Requests",
            "httpx": "HTTPX",
            "alembic": "Alembic",
            "uvicorn": "Uvicorn",
            "gunicorn": "Gunicorn",
            "poetry": "Poetry",
        }

        for pkg, fw in PY_PACKAGE_MAP.items():
            if pkg in pkgs and fw not in results:
                results.append(fw)

    return results


def _detect_from_pyproject_toml(abs_path):
    """Detect Python frameworks from pyproject.toml dependencies."""
    toml_path = os.path.join(abs_path, "pyproject.toml")
    if not os.path.exists(toml_path):
        return []

    try:
        with open(toml_path, "r", encoding="utf-8") as f:
            content = f.read().lower()
    except OSError:
        return []

    PY_MARKERS = {
        "django": "Django",
        "flask": "Flask",
        "fastapi": "FastAPI",
        "starlette": "Starlette",
        "sanic": "Sanic",
        "tornado": "Tornado",
        "celery": "Celery",
        "sqlalchemy": "SQLAlchemy",
        "pydantic": "Pydantic",
        "pytest": "pytest",
        "scikit-learn": "scikit-learn",
        "tensorflow": "TensorFlow",
        "torch": "PyTorch",
        "pandas": "Pandas",
        "numpy": "NumPy",
    }

    results = []
    for marker, fw in PY_MARKERS.items():
        if marker in content and fw not in results:
            results.append(fw)

    return results


def _detect_from_composer_json(abs_path):
    """Detect PHP frameworks from composer.json."""
    composer_path = os.path.join(abs_path, "composer.json")
    if not os.path.exists(composer_path):
        return []

    try:
        with open(composer_path, "r", encoding="utf-8") as f:
            pkg = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    all_deps = set()
    for key in ("require", "require-dev"):
        deps = pkg.get(key, {})
        all_deps.update(deps.keys())

    PHP_PACKAGE_MAP = {
        "laravel/framework": "Laravel",
        "laravel/lumen-framework": "Lumen",
        "symfony/symfony": "Symfony",
        "symfony/console": "Symfony",
        "codeigniter4/framework": "CodeIgniter 4",
        "codeigniter/framework": "CodeIgniter 3",
        "slim/slim": "Slim",
        "slim/pdo": "Slim",
        "yiisoft/yii2": "Yii2",
        "cakephp/cakephp": "CakePHP",
        "zendframework/zendframework": "Zend/Laminas",
        "laminas/laminas-mvc": "Laminas",
        "filp/whoops": "Whoops",
        "phpunit/phpunit": "PHPUnit",
        "pestphp/pest": "Pest",
        "doctrine/orm": "Doctrine ORM",
        "illuminate/database": "Laravel Eloquent",
        "twig/twig": "Twig",
        "blade": "Blade",
        "guzzlehttp/guzzle": "Guzzle",
        "nesbot/carbon": "Carbon",
        "vlucas/phpdotenv": "PHP dotenv",
    }

    results = []
    for pkg_name, fw in PHP_PACKAGE_MAP.items():
        if pkg_name.lower() in {d.lower() for d in all_deps} and fw not in results:
            results.append(fw)

    return results


def _detect_from_go_mod(abs_path):
    """Detect Go frameworks from go.mod."""
    go_mod_path = os.path.join(abs_path, "go.mod")
    if not os.path.exists(go_mod_path):
        return []

    try:
        with open(go_mod_path, "r", encoding="utf-8") as f:
            content = f.read().lower()
    except OSError:
        return []

    GO_MARKERS = {
        "gin-gonic/gin": "Gin",
        "gorilla/mux": "Gorilla Mux",
        "fiber": "Fiber",
        "echo": "Echo",
        "chi": "Chi",
        "mux": "Gorilla Mux",
        "go-kit": "Go Kit",
        "grpc": "gRPC",
        "gorm.io": "GORM",
        "entgo.io": "Ent",
        "sqlx": "sqlx",
        "cobra": "Cobra",
        "viper": "Viper",
        "go.uber.org/zap": "Zap",
        "sirupsen/logrus": "Logrus",
        "testify": "Testify",
    }

    results = []
    for marker, fw in GO_MARKERS.items():
        if marker in content and fw not in results:
            results.append(fw)

    return results


def _detect_from_cargo_toml(abs_path):
    """Detect Rust frameworks from Cargo.toml."""
    cargo_path = os.path.join(abs_path, "Cargo.toml")
    if not os.path.exists(cargo_path):
        return []

    try:
        with open(cargo_path, "r", encoding="utf-8") as f:
            content = f.read().lower()
    except OSError:
        return []

    RUST_MARKERS = {
        "actix-web": "Actix Web",
        "axum": "Axum",
        "rocket": "Rocket",
        "warp": "Warp",
        "tide": "Tide",
        "poem": "Poem",
        "salvo": "Salvo",
        "tokio": "Tokio",
        "async-std": "async-std",
        "serde": "Serde",
        "diesel": "Diesel",
        "sqlx": "SQLx",
        "sea-orm": "SeaORM",
        "reqwest": "Reqwest",
        "clap": "Clap",
        "tauri": "Tauri",
    }

    results = []
    for marker, fw in RUST_MARKERS.items():
        if marker in content and fw not in results:
            results.append(fw)

    return results


def _detect_from_gemfile(abs_path):
    """Detect Ruby frameworks from Gemfile."""
    gemfile_path = os.path.join(abs_path, "Gemfile")
    if not os.path.exists(gemfile_path):
        return []

    try:
        with open(gemfile_path, "r", encoding="utf-8") as f:
            content = f.read().lower()
    except OSError:
        return []

    RUBY_MARKERS = {
        "rails": "Ruby on Rails",
        "sinatra": "Sinatra",
        "hanami": "Hanami",
        "grape": "Grape",
        "roda": "Roda",
        "padrino": "Padrino",
        "cuba": "Cuba",
        "rspec": "RSpec",
        "cucumber": "Cucumber",
        "sidekiq": "Sidekiq",
        "devise": "Devise",
        "pundit": "Pundit",
        "activerecord": "ActiveRecord",
        "pg": "PostgreSQL (Ruby)",
        "mysql2": "MySQL (Ruby)",
        "redis": "Redis (Ruby)",
    }

    results = []
    for marker, fw in RUBY_MARKERS.items():
        if marker in content and fw not in results:
            results.append(fw)

    return results


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
