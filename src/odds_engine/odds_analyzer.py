import numpy as np
import pandas as pd

ODDS_COLUMNS = ["home_odds", "draw_odds", "away_odds"]


def analyze_1x2(df):
    result = df.copy()
    for col in ODDS_COLUMNS:
        result[col] = pd.to_numeric(result[col], errors="raise")

    odds_values = result[ODDS_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(odds_values).all():
        raise ValueError("Odds harus berupa angka terbatas dan tidak boleh kosong.")
    if (result[ODDS_COLUMNS] <= 1).any().any():
        raise ValueError("Semua odds harus lebih besar dari 1.")

    for col in ODDS_COLUMNS:
        result[f"{col}_prob"] = 1 / result[col]

    prob_columns = [f"{col}_prob" for col in ODDS_COLUMNS]
    implied_total = result[prob_columns].sum(axis=1)
    result["bookmaker_margin"] = implied_total - 1

    for outcome in ["home", "draw", "away"]:
        result[f"{outcome}_fair_prob"] = (
            result[f"{outcome}_odds_prob"] / implied_total
        )
        result[f"{outcome}_fair_odds"] = 1 / result[f"{outcome}_fair_prob"]

    return result
