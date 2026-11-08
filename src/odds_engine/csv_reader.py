from pathlib import Path
import pandas as pd


def read_odds_csv(file_path):
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")

    if path.stat().st_size == 0:
        raise ValueError("File CSV kosong.")

    try:
        df = pd.read_csv(
            path,
            sep=None,
            engine="python",
            encoding="utf-8-sig"
        )
    except UnicodeDecodeError:
        df = pd.read_csv(
            path,
            sep=None,
            engine="python",
            encoding="latin-1"
        )

    if df.empty:
        raise ValueError("Tidak ada data di dalam CSV.")

    df.columns = [
        str(col).strip().lower().replace(" ", "_")
        for col in df.columns
    ]

    if df.columns.duplicated().any():
        raise ValueError("Terdapat nama kolom duplikat.")

    return df


def inspect_csv(file_path):
    df = read_odds_csv(file_path)

    return {
        "rows": len(df),
        "columns": list(df.columns),
        "missing_values": df.isnull().sum().to_dict(),
        "data_types": df.dtypes.astype(str).to_dict()
    }
