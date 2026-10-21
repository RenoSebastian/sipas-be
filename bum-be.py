#!/usr/bin/env python3
# bum-be.py — Codebase Aggregator for SIPAS Backend (Python / FastAPI / SQLAlchemy / PostGIS)
import os
import sys
import re
import argparse
import fnmatch
import io
import tokenize
from pathlib import Path
from typing import Any, Set, List, Tuple


def _reconfigure_stream_encoding(stream: Any) -> None:
    """Mengatur encoding stream konsol ke UTF-8 untuk mencegah UnicodeEncodeError di Windows."""
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8")
        except Exception:
            pass


# Set console output encoding to UTF-8
_reconfigure_stream_encoding(sys.stdout)
_reconfigure_stream_encoding(sys.stderr)


# =========================================================================
# CONFIGURATION CLASS (Information Expert)
# Menyimpan seluruh konfigurasi penapisan secara terpusat untuk Backend SIPAS
# =========================================================================
class AggregatorConfig:
    DEFAULT_TARGET = str(Path(__file__).parent.resolve())
    DEFAULT_OUTPUT = f"{Path(__file__).parent.name}.txt"

    # 1. Folder Blacklist (Diabaikan secara mutlak)
    FORBIDDEN_DIRS = {
        "node_modules", ".git", "dist", "build", "out", "coverage",
        ".vscode", ".idea", "recovered", "temp", "tmp", "__pycache__",
        ".venv", "venv", "env", "ENV", ".pytest_cache", ".mypy_cache", ".ruff_cache",
        "postgres_data", "geoserver_data", "uploads", "geojson", "docs",
        "versions"  # Migrasi historis Alembic diabaikan secara default agar tidak membengkak
    }

    # 2. Berkas Blacklist (Diabaikan secara mutlak)
    FORBIDDEN_FILES = {
        "poetry.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
        ".DS_Store", "Thumbs.db", "desktop.ini",
        "system_config.json",  # Dikecualikan karena berisi string base64 gambar berukuran >300KB
        "pyrightconfig.json",
        "bum-be.py", "agregator.py"  # Skrip agregator sendiri
    }

    # 3. Whitelist Folder Tingkat Root yang Diizinkan untuk Ditelusuri
    ALLOWED_DIRS = {
        "src", "alembic", "docker", "templates", "scratch", "tests"
    }

    # 4. Ekstensi Berkas Teks yang Diizinkan
    INCLUDE_EXTENSIONS = {
        ".py", ".toml", ".ini", ".json", ".yaml", ".yml",
        ".sql", ".conf", ".sh", ".mako", ".md", ".txt",
        ".html", ".jinja", ".jinja2"
    }

    # 5. Berkas Konfigurasi Wajib di Tingkat Root
    ESSENTIAL_ROOT_FILES = {
        "pyproject.toml", "alembic.ini", "Dockerfile", "docker-compose.yml",
        "README.md", ".gitignore", ".env.example"
    }

    # 6. Batas Maksimum Ukuran Berkas Teks (1 MB)
    MAX_FILE_SIZE_BYTES = 1024 * 1024

    # Pre-compiled Regex untuk Sensor Keamanan (Mencegah Kebocoran Kredensial Rahasia)
    SENSITIVE_REGEX = re.compile(
        r"(\.env$|\.env\..*|key.*\.pem|.*\.key|id_rsa.*|credentials.*)",
        re.IGNORECASE
    )

    # Ekstensi biner yang pasti diabaikan
    BINARY_EXTENSIONS = {
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".pdf",
        ".dxf", ".dwg", ".shp", ".shx", ".dbf", ".cpg", ".prj",
        ".exe", ".dll", ".so", ".bin", ".zip", ".tar", ".gz",
        ".pyc", ".pyo", ".pyd", ".db", ".sqlite", ".sqlite3"
    }


# =========================================================================
# OPTIMIZER CLASS (Pure Fabrication)
# Pintu gerbang optimasi konten teks dan deteksi data biner
# =========================================================================
class LLMContextOptimizer:
    @staticmethod
    def strip_python_comments_and_docstrings(source: str) -> str:
        """Menghapus komentar (#) dan docstring (triple quotes) dari file Python secara aman menggunakan tokenize."""
        try:
            io_obj = io.StringIO(source)
            prev_toktype = tokenize.INDENT
            tokens = tokenize.generate_tokens(io_obj.readline)
            modified_tokens = []

            for tok in tokens:
                token_type = tok.type
                token_string = tok.string

                # 1. Hapus komentar (#)
                if token_type == tokenize.COMMENT:
                    continue

                # 2. Hapus docstring (string literal di posisi awal blok)
                if token_type == tokenize.STRING:
                    if token_string.startswith(('"""', "'''")):
                        if prev_toktype in (tokenize.INDENT, tokenize.NEWLINE, tokenize.NL, tokenize.ENCODING):
                            continue

                modified_tokens.append(tok)
                if token_type not in (tokenize.NL, tokenize.COMMENT):
                    prev_toktype = token_type

            return tokenize.untokenize(modified_tokens)
        except Exception:
            # Fallback baris per baris sederhana jika tokenize gagal
            lines = []
            for line in source.splitlines():
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                lines.append(line)
            return "\n".join(lines)

    @staticmethod
    def strip_html_comments(text: str) -> str:
        """Menghapus komentar HTML <!-- ... -->."""
        return re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

    @staticmethod
    def strip_js_ts_comments(text: str) -> str:
        """Menghapus komentar // dan /* ... */ secara aman tanpa merusak string literal."""
        pattern = re.compile(
            r'/\*.*?\*/|//.*?$|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"|`(?:\\.|[^\\`])*`',
            re.DOTALL | re.MULTILINE
        )

        def replacer(match):
            s = match.group(0)
            if s.startswith('/'):
                return ""
            return s

        return re.sub(pattern, replacer, text)

    @classmethod
    def compress_code(cls, content: str, suffix: str = "", strip_comments: bool = True) -> str:
        """Menghapus spasi trailing, baris kosong ganda, komentar, dan docstring."""
        if strip_comments:
            if suffix == ".py":
                content = cls.strip_python_comments_and_docstrings(content)
            elif suffix in (".html", ".jinja", ".jinja2"):
                content = cls.strip_html_comments(content)
            elif suffix in (".js", ".jsx", ".ts", ".tsx", ".css"):
                content = cls.strip_js_ts_comments(content)

        lines = content.splitlines()
        optimized_lines = []
        previous_empty = False

        for line in lines:
            stripped = line.rstrip()
            is_empty = len(stripped) == 0

            if is_empty and previous_empty:
                continue

            optimized_lines.append(stripped)
            previous_empty = is_empty

        return "\n".join(optimized_lines)

    @classmethod
    def is_binary(cls, file_path: Path) -> bool:
        """Deteksi berkas biner berdasarkan ekstensi atau membaca byte awal."""
        if file_path.suffix.lower() in AggregatorConfig.BINARY_EXTENSIONS:
            return True
        try:
            with open(file_path, 'rb') as f:
                return b'\x00' in f.read(512)
        except Exception:
            return True


# =========================================================================
# AGGREGATOR CONTROLLER (GRASP Controller)
# Orkestrator utama penelusuran dan pembangunan bundel berkas teks
# =========================================================================
class CodebaseAggregator:
    def __init__(self, target_dir: str, output_name: str, include_migrations: bool = False, strip_comments: bool = True):
        self.config = AggregatorConfig()
        self.optimizer = LLMContextOptimizer()
        self.strip_comments = strip_comments

        # Atur perilaku pemindaian migrasi database
        if include_migrations:
            self.config.FORBIDDEN_DIRS.discard("versions")
        else:
            self.config.FORBIDDEN_DIRS.add("versions")

        # Penyelarasan Portabilitas Jalur Direktori
        self.target_path = Path(target_dir).resolve()
        if not self.target_path.is_dir():
            self.target_path = Path(__file__).parent.resolve()
            print(f"[SYSTEM] Target direktori tidak ditemukan. Menggunakan fallback portabel di: {self.target_path}")

        self.output_file = self.target_path / output_name
        self.config.FORBIDDEN_FILES.add(output_name)  # Jangan biarkan skrip membaca file output-nya sendiri
        self.config.FORBIDDEN_FILES.add(Path(__file__).name)  # Jangan biarkan skrip menyalin dirinya sendiri
        self.gitignore_patterns = self._parse_gitignore()

    def _parse_gitignore(self) -> List[str]:
        """Membaca berkas .gitignore sebagai daftar pola untuk pencocokan."""
        patterns = []
        gitignore_path = self.target_path / ".gitignore"
        if gitignore_path.exists():
            try:
                for line in gitignore_path.read_text("utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line)
            except Exception as e:
                print(f"[WARN] Gagal mengurai .gitignore: {e}")
        return patterns

    def should_ignore(self, path: Path, is_dir: bool = False) -> bool:
        """Memeriksa apakah berkas atau folder harus diabaikan berdasarkan blacklist dan gitignore."""
        try:
            rel_path = path.relative_to(self.target_path)
        except ValueError:
            rel_path = path

        parts = rel_path.parts
        if not parts:
            return False

        # 1. Cek folder blacklist bawaan pada komponen path manapun
        for part in parts:
            if part in self.config.FORBIDDEN_DIRS:
                return True

        # 2. Cek berkas blacklist bawaan jika bukan direktori
        if not is_dir:
            if path.name in self.config.FORBIDDEN_FILES:
                return True
            if self.config.SENSITIVE_REGEX.match(path.name):
                return True

        # 3. Cek kecocokan dengan pola gitignore
        rel_path_str = rel_path.as_posix()
        for pattern in self.gitignore_patterns:
            clean_pattern = pattern.lstrip('/')
            is_pattern_dir = pattern.endswith('/')
            match_pattern = clean_pattern.rstrip('/')

            if is_pattern_dir and not is_dir:
                continue

            if '/' in match_pattern:
                if fnmatch.fnmatch(rel_path_str, match_pattern) or fnmatch.fnmatch(rel_path_str, f"{match_pattern}/*"):
                    return True
            else:
                if any(fnmatch.fnmatch(part, match_pattern) for part in parts):
                    return True

        return False

    def execute(self):
        print(f"🔍 Memulai penggabungan kode dari target: {self.target_path}")
        if self.strip_comments:
            print("✂️ Pembersihan komentar & docstring diaktifkan untuk penghematan token LLM.")
        else:
            print("📝 Komentar & docstring dipertahankan.")

        if "versions" in self.config.FORBIDDEN_DIRS:
            print("🚫 Folder Migrasi Database ('alembic/versions') diabaikan untuk menghemat ruang.")
        else:
            print("⚠️ Folder Migrasi Database ('alembic/versions') disertakan.")

        file_count = 0
        original_total_size = 0
        compressed_total_size = 0

        # Menyimpan statistik berkas untuk dianalisis
        processed_files_stats: List[Tuple[str, int]] = []

        try:
            with open(self.output_file, "w", encoding="utf-8") as out_file:
                out_file.write("=== STRUKTUR & ISI KODE BACKEND SIPAS (HIGH OPTIMIZED PARADIGM) ===\n\n")

                for root, dirs, files in os.walk(self.target_path):
                    root_path = Path(root)
                    relative_root = root_path.relative_to(self.target_path)
                    is_root_level = len(relative_root.parts) == 0

                    # 1. Pangkas folder terlarang dari antrean os.walk
                    dirs[:] = [d for d in dirs if not self.should_ignore(root_path / d, is_dir=True)]

                    # 2. OPTIMASI I/O TINGKAT ROOT: Hanya telusuri folder yang masuk dalam whitelist ALLOWED_DIRS
                    if is_root_level:
                        dirs[:] = [d for d in dirs if d in self.config.ALLOWED_DIRS]

                    for file_name in files:
                        file_path = root_path / file_name
                        relative_file_path = file_path.relative_to(self.target_path)
                        is_root_file = len(relative_file_path.parts) == 1

                        # Penapisan A: Sensor Berkas Sensitif, Blacklist & Gitignore
                        if self.should_ignore(file_path, is_dir=False):
                            continue

                        # Penapisan B: Saring Berkas di tingkat Root (Hanya ambil file esensial atau skrip dengan ekstensi diizinkan)
                        if is_root_file:
                            if file_name not in self.config.ESSENTIAL_ROOT_FILES and file_path.suffix not in self.config.INCLUDE_EXTENSIONS:
                                continue

                        # Penapisan C: Saring Ekstensi yang diizinkan untuk subfolder
                        if not is_root_file and file_path.suffix not in self.config.INCLUDE_EXTENSIONS:
                            continue

                        # Penapisan D: Binary Guard (Mencegah pembacaan gambar, font, SHP, CAD, PDF dll.)
                        if self.optimizer.is_binary(file_path):
                            continue

                        # Penapisan E: Size Guard
                        try:
                            file_size = file_path.stat().st_size
                            if file_size > self.config.MAX_FILE_SIZE_BYTES:
                                print(f"[SKIP] Berkas terlalu besar ({file_size / 1024:.1f} KB): {relative_file_path}")
                                continue

                            content = file_path.read_text("utf-8", errors="ignore")
                            compressed_content = self.optimizer.compress_code(
                                content,
                                suffix=file_path.suffix,
                                strip_comments=self.strip_comments
                            )

                            # Tulis langsung ke stream buffer
                            out_file.write(f"\n--- FILE: {relative_file_path} ---\n")
                            out_file.write(compressed_content)
                            out_file.write("\n")

                            file_count += 1
                            comp_size = len(compressed_content.encode('utf-8'))
                            original_total_size += file_size
                            compressed_total_size += comp_size

                            processed_files_stats.append((str(relative_file_path), comp_size))
                            print(f"-> Menyalin & mengompresi: {relative_file_path}")

                        except Exception as e:
                            print(f"-> Gagal memproses {relative_file_path}: {e}")

            print(f"\n✅ Selesai! {file_count} Berkas berhasil disatukan di:\n   {self.output_file}")
            print(f"📊 Ukuran Asli: {original_total_size / 1024:.2f} KB")
            print(f"🚀 Ukuran Kompresi (LLM Ready): {compressed_total_size / 1024:.2f} KB")

            if original_total_size > 0:
                saving_percent = ((original_total_size - compressed_total_size) / original_total_size) * 100
                print(f"📉 Penghematan Ruang Konteks: ~{saving_percent:.1f}%")

            # Tampilkan 5 Berkas Terbesar setelah Kompresi
            if processed_files_stats:
                print("\n📦 5 Berkas Terbesar yang Disalin (Setelah Kompresi):")
                sorted_files = sorted(processed_files_stats, key=lambda x: x[1], reverse=True)[:5]
                for idx, (f_path, f_size) in enumerate(sorted_files, 1):
                    print(f"   {idx}. {f_path} ({f_size / 1024:.2f} KB)")

        except Exception as e:
            print(f"Critical Error: Gagal menulis file output: {e}")


# =========================================================================
# MAIN EXECUTION ENTRY POINT
# =========================================================================
if __name__ == "__main__":
    config_default = AggregatorConfig()

    parser = argparse.ArgumentParser(description="Optimasi Bundel Kode Backend SIPAS (FastAPI / SQLAlchemy / GIS)")
    parser.add_argument("--dir", type=str, default=config_default.DEFAULT_TARGET, help="Direktori target yang akan dipindai")
    parser.add_argument("--out", type=str, default=config_default.DEFAULT_OUTPUT, help="Nama berkas keluaran (.txt)")
    parser.add_argument("--include-migrations", action="store_true", help="Sertakan folder migrasi database alembic (versions)")
    parser.add_argument("--keep-comments", action="store_true", help="Pertahankan komentar dan docstring di dalam kode Python")

    args = parser.parse_args()

    aggregator = CodebaseAggregator(
        target_dir=args.dir,
        output_name=args.out,
        include_migrations=args.include_migrations,
        strip_comments=not args.keep_comments
    )
    aggregator.execute()