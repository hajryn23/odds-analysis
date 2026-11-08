import pandas as pd

ODDS_COLUMNS = [
    "home_odds",
    "draw_odds",
    "away_odds"
]


def analyze_1x2(df):
    result = df.copy()

    for col in ODDS_COLUMNS:
        result[col] = pd.to_numeric(
            result[col], errors="raise"
        )

    if result[ODDS_COLUMNS].isna().any().any():
        raise ValueError("Odds mengandung nilai kosong.")

    if (result[ODDS_COLUMNS] <= 1).any().any():
        raise ValueError("Semua odds harus lebih besar dari 1.")

    # Implied probability
    for col in ODDS_COLUMNS:
        result[f"{col}_prob"] = 1 / result[col]

    prob_columns = [
        f"{col}_prob" for col in ODDS_COLUMNS
    ]

    # Total implied probability
    result["bookmaker_margin"] = (
        result[prob_columns].sum(axis=1) - 1
    )

    # Fair probability tanpa margin (metode proportional)
    result["home_fair_prob"] = (
        result["home_odds_prob"]
        / result[prob_columns].sum(axis=1)
    )

    result["draw_fair_prob"] = (
        result["draw_odds_prob"]
        / result[prob_columns].sum(axis=1)
    )

    result["away_fair_prob"] = (
        result["away_odds_prob"]
        / result[prob_columns].sum(axis=1)
    )

    # Fair odds
    for outcome in ["home", "draw", "away"]:
        result[f"{outcome}_fair_odds"] = (
            1 / result[f"{outcome}_fair_prob"]
        )

    return result
