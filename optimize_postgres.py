import os
from sqlalchemy import text
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Load environment variables
load_dotenv()

db_url = os.getenv("DATABASE_URL", "postgresql://postgres:naufal@localhost:5432/sipas_db")

def main():
    print("=" * 80)
    print("SIPAS POSTGRESQL SPATIAL PERFORMANCE OPTIMIZER")
    print("=" * 80)
    
    print(f"Connecting to database: {db_url.split('@')[-1]}...")
    engine = create_engine(db_url)
    
    # Kueri konfigurasi yang akan dieksekusi
    # 1. random_page_cost = 1.1 (Sangat direkomendasikan untuk SSD agar query planner memilih GIST index)
    # 2. work_mem = '64MB' (Memperbesar RAM untuk sorting dan operasi overlay spasial seperti ST_Intersection)
    optimizations = [
        ("random_page_cost", "1.1"),
        ("work_mem", "64MB"),
        ("temp_buffers", "32MB")
    ]
    
    try:
        with engine.connect() as conn:
            # Mulai transaksi autocommit untuk ALTER SYSTEM
            conn.connection.connection.autocommit = True
            
            # Periksa nilai awal
            print("\n[1/3] Memeriksa konfigurasi awal:")
            for param, _ in optimizations:
                val = conn.execute(text(f"SHOW {param}")).scalar()
                print(f"  - {param}: {val}")
                
            print("\n[2/3] Menerapkan optimasi sistem...")
            for param, val in optimizations:
                conn.execute(text(f"ALTER SYSTEM SET {param} = '{val}'"))
                print(f"  [OK] ALTER SYSTEM SET {param} = '{val}' berhasil.")
                
            print("\n[3/3] Memuat ulang konfigurasi PostgreSQL...")
            conn.execute(text("SELECT pg_reload_conf()"))
            print("  [OK] Konfigurasi berhasil dimuat ulang (pg_reload_conf).")
            
            # Verifikasi konfigurasi setelah reload
            print("\nVerifikasi nilai saat ini setelah reload:")
            for param, _ in optimizations:
                val = conn.execute(text(f"SHOW {param}")).scalar()
                print(f"  - {param}: {val}")
                
        print("\n" + "=" * 80)
        print("OPTIMASI SUKSES: Mesin spasial PostgreSQL Anda telah dikonfigurasi secara optimal!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n[FAIL] Gagal mengonfigurasi PostgreSQL: {str(e)}")
        print("Catatan: Pastikan user database Anda memiliki hak akses superuser (postgres).")

if __name__ == "__main__":
    main()
