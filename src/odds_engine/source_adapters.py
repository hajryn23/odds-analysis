"""Adapters for supported historical odds CSV layouts.

The SGOdds export uses source-specific column names and a reusable source ID.
We keep its complete source rows separately while mapping its 1X2 prices into
the existing analysis pipeline.
"""
import re

import pandas as pd


SGODDS_REQUIRED_COLUMNS = {
    "id", "match", "start_time", "league", "result",
    "ft1x2_01", "ft1x2_02", "ft1x2_03",
}


def adapt_odds_source(df):
    """Return (analysis_frame, raw_source_frame_or_None).

    Standard CSVs already using date/home_team/away_team/home_odds/draw_odds/
    away_odds pass through unchanged. SGOdds exports are mapped explicitly.
    The source ID is metadata only and is never treated as a unique key.
    """
    standard_columns = {
        "date", "home_team", "away_team",
        "home_odds", "draw_odds", "away_odds",
    }
    if standard_columns.issubset(df.columns):
        return df.copy(), None

    missing = sorted(SGODDS_REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise ValueError(
            "Format CSV tidak dikenali. Kolom SGOdds yang tidak ditemukan: "
            + ", ".join(missing)
        )

    teams = df["match"].astype("string").str.extract(
        r"^\s*(.*?)\s+vs\.?\s+(.*?)\s*$",
        flags=re.IGNORECASE,
    )
    mapped = pd.DataFrame(index=df.index)
    mapped["date"] = pd.to_datetime(df["start_time"], errors="coerce")
    mapped["home_team"] = teams[0].str.strip()
    mapped["away_team"] = teams[1].str.strip()
    mapped["home_odds"] = pd.to_numeric(df["ft1x2_01"], errors="coerce")
    mapped["draw_odds"] = pd.to_numeric(df["ft1x2_02"], errors="coerce")
    mapped["away_odds"] = pd.to_numeric(df["ft1x2_03"], errors="coerce")
    mapped["_source_row"] = range(len(df))

    return mapped, df.copy()
