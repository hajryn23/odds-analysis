from pathlib import Path
from .csv_reader import read_odds_csv
from .data_cleaner import clean_odds_data
from .odds_analyzer import analyze_1x2


def run_pipeline(input_file, output_file=None):
    print("1. Membaca data CSV...")
    df = read_odds_csv(input_file)

    print("2. Membersihkan data...")
    clean, report = clean_odds_data(df)

    if clean.empty:
        raise ValueError("Tidak ada pertandingan valid.")

    print("3. Menganalisis odds 1X2...")
    result = analyze_1x2(clean)

    if output_file is None:
        output_file = "data/processed/analysis_results.csv"

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result.to_csv(output_path, index=False)

    print("\n=== HASIL PIPELINE ===")
    print("Data awal:", report["original_rows"])
    print("Data ditolak:", report["rejected_rows"])
    print("Duplikasi:", report["duplicate_rows"])
    print("Data valid:", report["valid_rows"])
    print("Hasil disimpan:", output_path)

    return result


if __name__ == "__main__":
    run_pipeline("data/raw/sample_odds.csv")
