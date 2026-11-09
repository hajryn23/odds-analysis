"""Descriptive segmentation for historical 1X2 odds snapshots."""
import pandas as pd


ODDS_BANDS = [
    ("1.01–1.49", 1.0, 1.5),
    ("1.50–1.99", 1.5, 2.0),
    ("2.00–2.49", 2.0, 2.5),
    ("2.50–3.49", 2.5, 3.5),
    ("3.50+", 3.5, float("inf")),
]


def analyze_historical_odds(df):
    """Summarize favorite-price bands and bookmaker-margin bands.

    This is descriptive market analysis only. It does not use match outcomes
    and must not be interpreted as a model of realized winning frequency.
    """
    required = {
        "home_odds", "draw_odds", "away_odds",
        "home_fair_prob", "draw_fair_prob", "away_fair_prob",
        "bookmaker_margin",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError("Kolom analisis tidak lengkap: " + ", ".join(missing))

    if df.empty:
        return {"favorite_bands": [], "margin_bands": []}

    odds = df[["home_odds", "draw_odds", "away_odds"]].apply(
        pd.to_numeric, errors="coerce"
    )
    fair = df[[
        "home_fair_prob", "draw_fair_prob", "away_fair_prob"
    ]].apply(pd.to_numeric, errors="coerce")
    margin = pd.to_numeric(df["bookmaker_margin"], errors="coerce")

    valid = (
        odds.notna().all(axis=1)
        & fair.notna().all(axis=1)
        & margin.notna()
        & (odds > 1).all(axis=1)
    )
    odds, fair, margin = odds.loc[valid], fair.loc[valid], margin.loc[valid]
    if odds.empty:
        return {"favorite_bands": [], "margin_bands": []}

    favorite_index = odds.to_numpy().argmin(axis=1)
    favorite_prices = odds.to_numpy().min(axis=1)
    fair_values = fair.to_numpy()
    favorite_probabilities = fair_values[
        range(len(fair_values)), favorite_index
    ]
    favorite_sides = ["Home", "Draw", "Away"]

    favorite_rows = []
    for label, lower, upper in ODDS_BANDS:
        selected = (favorite_prices >= lower) & (favorite_prices < upper)
        count = int(selected.sum())
        if count:
            side_counts = {
                side: int((favorite_index[selected] == index).sum())
                for index, side in enumerate(favorite_sides)
            }
            favorite_rows.append({
                "band": label,
                "count": count,
                "share": count / len(favorite_prices) * 100,
                "avg_favorite_fair_prob": float(
                    favorite_probabilities[selected].mean() * 100
                ),
                "avg_margin": float(margin.to_numpy()[selected].mean() * 100),
                "home_count": side_counts["Home"],
                "draw_count": side_counts["Draw"],
                "away_count": side_counts["Away"],
            })

    margin_values = margin.to_numpy() * 100
    margin_definitions = [
        ("Negatif", float("-inf"), 0.0),
        ("0–3%", 0.0, 3.0),
        ("3–5%", 3.0, 5.0),
        ("5–8%", 5.0, 8.0),
        (">8%", 8.0, float("inf")),
    ]
    margin_rows = []
    for label, lower, upper in margin_definitions:
        selected = (margin_values >= lower) & (margin_values < upper)
        count = int(selected.sum())
        if count:
            margin_rows.append({
                "band": label,
                "count": count,
                "share": count / len(margin_values) * 100,
                "avg_margin": float(margin_values[selected].mean()),
            })

    return {
        "favorite_bands": favorite_rows,
        "margin_bands": margin_rows,
    }
