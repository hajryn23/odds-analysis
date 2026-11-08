import pandas as pd

REQUIRED_COLUMNS = [
    "date",
    "home_team",
    "away_team",
    "home_odds",
    "draw_odds",
    "away_odds"
]

ODDS_COLUMNS = [
    "home_odds",
    "draw_odds",
    "away_odds"
]


def clean_odds_data(df):
    df = df.copy()
    original_rows = len(df)

    missing_columns = [
        col for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Kolom wajib tidak ditemukan: {missing_columns}"
        )

    # Bersihkan nama tim
    for col in ["home_team", "away_team"]:
        df[col] = df[col].astype("string").str.strip()

    # Konversi tanggal
    df["date"] = pd.to_datetime(
        df["date"], errors="coerce"
    )

    # Konversi odds
    for col in ODDS_COLUMNS:
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        )

    # Tandai data yang tidak valid
    invalid_date = df["date"].isna()

    invalid_teams = (
        df["home_team"].isna()
        | df["away_team"].isna()
        | df["home_team"].eq("")
        | df["away_team"].eq("")
    )

    invalid_odds = (
        df[ODDS_COLUMNS].isna().any(axis=1)
        | (df[ODDS_COLUMNS] <= 1).any(axis=1)
    )

    invalid = invalid_date | invalid_teams | invalid_odds

    rejected_rows = int(invalid.sum())

    df = df.loc[~invalid].copy()

    # Hapus duplikasi pertandingan
    before_duplicates = len(df)

    df = df.drop_duplicates(
        subset=["date", "home_team", "away_team"],
        keep="last"
    )

    duplicate_rows = before_duplicates - len(df)

    df = df.sort_values("date").reset_index(drop=True)

    report = {
        "original_rows": original_rows,
        "rejected_rows": rejected_rows,
        "duplicate_rows": duplicate_rows,
        "valid_rows": len(df)
    }

    return df, report
