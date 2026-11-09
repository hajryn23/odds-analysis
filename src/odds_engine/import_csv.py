import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from odds_engine.csv_reader import read_odds_csv
from odds_engine.data_cleaner import clean_odds_data
from odds_engine.odds_analyzer import analyze_1x2
from odds_engine.database import init_db, save_analysis

DB_PATH = ROOT / "data" / "odds_analysis.sqlite3"


def import_file(file_path):
    path = Path(file_path).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File CSV tidak ditemukan: {path}")
    if path.suffix.lower() != ".csv":
        raise ValueError("File yang dipilih harus berekstensi .csv")

    print(f"File yang dipilih: {path}")
    print("Membaca seluruh isi CSV; tidak menggunakan sampel...")
    raw = read_odds_csv(path)
    clean, report = clean_odds_data(raw)

    print("\n=== LAPORAN PEMBERSIHAN ===")
    print(f"Baris awal       : {report['original_rows']}")
    print(f"Baris ditolak    : {report['rejected_rows']}")
    print(f"Pertandingan berulang (dipertahankan): {report['duplicate_rows']}")
    print(f"Baris valid      : {report['valid_rows']}")

    if clean.empty:
        raise ValueError("Tidak ada baris valid. Database tidak diubah.")

    analyzed = analyze_1x2(clean)
    print(f"\nBaris siap disimpan: {len(analyzed)}")
    confirmation = input(
        "Ketik IMPOR untuk menyimpan hasil ke database SQLite: "
    ).strip()
    if confirmation != "IMPOR":
        print("Impor dibatalkan. Database tidak diubah.")
        return None

    init_db(DB_PATH)
    import_id = save_analysis(analyzed, report, path, DB_PATH)
    print(f"Impor berhasil. ID impor: {import_id}")
    print(f"Database: {DB_PATH}")
    return import_id


def main():
    parser = argparse.ArgumentParser(
        description="Impor satu file CSV odds secara manual ke database SQLite."
    )
    parser.add_argument(
        "csv_file",
        help="Path lengkap atau relatif ke satu file CSV yang dipilih",
    )
    args = parser.parse_args()
    try:
        import_file(args.csv_file)
    except Exception as exc:
        print(f"Gagal mengimpor: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
