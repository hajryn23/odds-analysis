import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
    "date", "home_team", "away_team",
    "home_odds", "draw_odds", "away_odds",
]
ODDS_COLUMNS = ["home_odds", "draw_odds", "away_odds"]


def clean_odds_data(df):
    df = df.copy()
    original_rows = len(df)

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Kolom wajib tidak ditemukan: {missing_columns}")

    for col in ["home_team", "away_team"]:
        df[col] = df[col].astype("string").str.strip()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ODDS_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    invalid_date = df["date"].isna()
    invalid_teams = (
        df["home_team"].isna()
        | df["away_team"].isna()
        | df["home_team"].eq("")
        | df["away_team"].eq("")
    )
    odds_values = df[ODDS_COLUMNS].to_numpy(dtype=float)
    invalid_odds = (
        (~np.isfinite(odds_values)).any(axis=1)
        | (df[ODDS_COLUMNS] <= 1).any(axis=1)
    )

    invalid = invalid_date | invalid_teams | invalid_odds
    rejected_rows = int(invalid.sum())
    df = df.loc[~invalid].copy()

    # Identical fixtures can contain different bookmakers or price snapshots.
    # Count repeated fixture keys, but retain every valid row.
    duplicate_rows = int(
        df.duplicated(subset=["date", "home_team", "away_team"], keep="first").sum()
    )
    df = df.sort_values("date").reset_index(drop=True)

    report = {
        "original_rows": original_rows,
        "rejected_rows": rejected_rows,
        "duplicate_rows": duplicate_rows,
        "valid_rows": len(df),
    }
    return df, report
