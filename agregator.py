#!/usr/bin/env python3
# agregator.py
import os
import sys
import re
import argparse
import fnmatch
from pathlib import Path
from typing import Any, Set, List


def _reconfigure_stream_encoding(stream: Any) -> None:
    """Apply UTF-8 encoding to console streams when the runtime supports it."""
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8")
        except Exception:
            pass


# Set console output encoding to UTF-8 to prevent UnicodeEncodeError on Windows
_reconfigure_stream_encoding(sys.stdout)
_reconfigure_stream_encoding(sys.stderr)

# =========================================================================
# CONFIGURATION CLASS (Information Expert)
# Menyimpan seluruh konfigurasi penapisan secara terpusat untuk Backend
# =========================================================================
class AggregatorConfig:
    DEFAULT_TARGET = str(Path(__file__).parent.resolve())
    DEFAULT_OUTPUT = f"{Path(__file__).parent.name}.txt"

    # 1. Folder Blacklist (Diabaikan secara mutlak)
    FORBIDDEN_DIRS = {
        "node_modules", ".git", "dist", "build", "out", "coverage",
        ".vscode", ".idea", "recovered", "temp", "tmp", "__pycache__",
        ".venv", "venv", ".pytest_cache", ".mypy_cache", ".ruff_cache",
        "postgres_data", "geoserver_data"
    }

    # 2. Berkas Blacklist (Diabaikan secara mutlak)
    FORBIDDEN_FILES = {
        "poetry.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        ".DS_Store", "Thumbs.db"
    }

    # 3. Whitelist Folder Tingkat Root (Hanya turun ke folder di bawah ini jika di root)
    ALLOWED_DIRS = {
        "src", "alembic", "docker", "tests"
    }

    # 4. Ekstensi Berkas Teks yang Diizinkan untuk Backend
    INCLUDE_EXTENSIONS = {
        ".py", ".toml", ".ini", ".json", ".yaml", ".yml", 
        ".sql", ".conf", ".sh", ".mako", ".md", ".txt"
    }

    # 5. Berkas Konfigurasi Wajib di Tingkat Root
    ESSENTIAL_ROOT_FILES = {
        "pyproject.toml", "alembic.ini", "pyrightconfig.json", 
        "README.md", ".gitignore", ".env.example"
    }

    # 6. Batas Maksimum Ukuran Berkas (1 MB)
    MAX_FILE_SIZE_BYTES = 1024 * 1024  

    # Pre-compiled Regex untuk Sensor Keamanan (Mencegah Kebocoran Kredensial)
    SENSITIVE_REGEX = re.compile(
        r"(\.env|key.*\.pem|.*\.key|id_rsa.*|credentials.*)", 
        re.IGNORECASE
    )


# =========================================================================
# OPTIMIZER CLASS (Pure Fabrication)
# Pintu gerbang optimasi konten teks dan deteksi data biner
# =========================================================================
class LLMContextOptimizer:
    @staticmethod
    def compress_code(content: str) -> str:
        """Menghapus spasi trailing dan baris kosong ganda secara efisien untuk menghemat token LLM."""
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

    @staticmethod
    def is_binary(file_path: Path) -> bool:
        """Deteksi biner murah dengan membaca 512 byte pertama."""
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
    def __init__(self, target_dir: str, output_name: str):
        self.config = AggregatorConfig()
        self.optimizer = LLMContextOptimizer()
        
        # Penyelarasan Portabilitas Jalur Direktori
        self.target_path = Path(target_dir).resolve()
        if not self.target_path.is_dir():
            self.target_path = Path(__file__).parent.resolve()
            print(f"[SYSTEM] Target direktori tidak ditemukan. Menggunakan fallback portabel di: {self.target_path}")

        self.output_file = self.target_path / output_name
        self.config.FORBIDDEN_FILES.add(output_name) # Jangan biarkan skrip membaca file output-nya sendiri
        self.config.FORBIDDEN_FILES.add(Path(__file__).name) # Jangan biarkan skrip menyalin dirinya sendiri
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
        # Ubah path menggunakan slash '/' untuk konsistensi di Windows
        rel_path_str = rel_path.as_posix()
        
        for pattern in self.gitignore_patterns:
            # Hapus leading slash untuk pencocokan relatif
            clean_pattern = pattern.lstrip('/')
            is_pattern_dir = pattern.endswith('/')
            match_pattern = clean_pattern.rstrip('/')
            
            # Jika pola khusus direktori tapi path saat ini bukan direktori, skip
            if is_pattern_dir and not is_dir:
                continue
                
            # Pencocokan pola:
            # a. Jika pola mengandung '/', cocokkan terhadap rel_path_str lengkap
            # b. Jika tidak, cocokkan terhadap tiap komponen path (parts) atau nama file/direktori langsung
            if '/' in match_pattern:
                if fnmatch.fnmatch(rel_path_str, match_pattern) or fnmatch.fnmatch(rel_path_str, f"{match_pattern}/*"):
                    return True
            else:
                # Cocokkan nama file/direktori langsung atau salah satu bagiannya
                if any(fnmatch.fnmatch(part, match_pattern) for part in parts):
                    return True
                    
        return False

    def execute(self):
        print(f"🔍 Memulai penggabungan kode dari target: {self.target_path}")
        
        file_count = 0
        original_total_size = 0
        compressed_total_size = 0

        try:
            # Membuka file output dengan mode stream buffer langsung
            with open(self.output_file, "w", encoding="utf-8") as out_file:
                out_file.write("=== STRUKTUR & ISI KODE BACKEND (COMPRESSED PARADIGM) ===\n\n")

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

                        # Penapisan B: Saring Berkas non-esensial di tingkat Root
                        if is_root_file and file_name not in self.config.ESSENTIAL_ROOT_FILES:
                            continue

                        # Penapisan C: Saring Ekstensi yang diizinkan (Kecuali berkas konfigurasi penting root)
                        if not is_root_file and file_path.suffix not in self.config.INCLUDE_EXTENSIONS:
                            continue

                        # Penapisan D: Cheap Binary Guard (Cegah membaca berkas gambar, font, pdf, dll.)
                        if self.optimizer.is_binary(file_path):
                            continue

                        # Penapisan E: Size Guard
                        try:
                            file_size = file_path.stat().st_size
                            if file_size > self.config.MAX_FILE_SIZE_BYTES:
                                print(f"[SKIP] Berkas terlalu besar ({file_size / 1024:.1f} KB): {relative_file_path}")
                                continue

                            content = file_path.read_text("utf-8", errors="ignore")
                            compressed_content = self.optimizer.compress_code(content)

                            # Tulis langsung ke stream buffer tanpa menahan seluruh isi memori di RAM
                            out_file.write(f"\n--- FILE: {relative_file_path} ---\n")
                            out_file.write(compressed_content)
                            out_file.write("\n")

                            file_count += 1
                            original_total_size += file_size
                            compressed_total_size += len(compressed_content.encode('utf-8'))
                            print(f"-> Menyalin & mengompresi: {relative_file_path}")

                        except Exception as e:
                            print(f"-> Gagal memproses {relative_file_path}: {e}")

            print(f"\n✅ Selesai! {file_count} Berkas berhasil disatukan di:\n   {self.output_file}")
            print(f"📊 Ukuran Asli: {original_total_size / 1024:.2f} KB")
            print(f"🚀 Ukuran Kompresi (LLM Ready): {compressed_total_size / 1024:.2f} KB")
            
            # SINKRONISASI EVALUASI: Perbaikan Typo NameError secara presisi
            if original_total_size > 0:
                saving_percent = ((original_total_size - compressed_total_size) / original_total_size) * 100
                print(f"📉 Penghematan Ruang Konteks: ~{saving_percent:.1f}%")

        except Exception as e:
            print(f"Critical Error: Gagal menulis file output: {e}")


# =========================================================================
# MAIN EXECUTION ENTRY POINT
# =========================================================================
if __name__ == "__main__":
    config_default = AggregatorConfig()

    parser = argparse.ArgumentParser(description="Optimasi Bundel Kode Backend - GFW Paradigm")
    parser.add_argument("--dir", type=str, default=config_default.DEFAULT_TARGET, help="Direktori target yang akan dipindai")
    parser.add_argument("--out", type=str, default=config_default.DEFAULT_OUTPUT, help="Nama berkas keluaran (.txt)")
    
    args = parser.parse_args()

    aggregator = CodebaseAggregator(target_dir=args.dir, output_name=args.out)
    aggregator.execute()
