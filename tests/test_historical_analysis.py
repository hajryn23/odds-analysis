import pandas as pd
import pytest

from src.odds_engine.historical_analysis import analyze_historical_odds


def _frame():
    return pd.DataFrame([
        {
            "home_odds": 1.40, "draw_odds": 4.5, "away_odds": 8.0,
            "home_fair_prob": 0.70, "draw_fair_prob": 0.20,
            "away_fair_prob": 0.10, "bookmaker_margin": 0.05,
        },
        {
            "home_odds": 2.10, "draw_odds": 3.2, "away_odds": 3.4,
            "home_fair_prob": 0.45, "draw_fair_prob": 0.30,
            "away_fair_prob": 0.25, "bookmaker_margin": 0.02,
        },
        {
            "home_odds": 3.0, "draw_odds": 2.8, "away_odds": 2.5,
            "home_fair_prob": 0.30, "draw_fair_prob": 0.32,
            "away_fair_prob": 0.38, "bookmaker_margin": 0.09,
        },
    ])


def test_favorite_price_bands_and_favorite_side_counts():
    result = analyze_historical_odds(_frame())
    assert [row["band"] for row in result["favorite_bands"]] == [
        "1.01–1.49", "2.00–2.49"
    ]
    assert result["favorite_bands"][0]["count"] == 1
    assert result["favorite_bands"][0]["home_count"] == 1
    assert result["favorite_bands"][1]["away_count"] == 1
    assert result["favorite_bands"][0]["avg_favorite_fair_prob"] == pytest.approx(70)


def test_margin_bands_are_exhaustive_for_valid_rows():
    result = analyze_historical_odds(_frame())
    assert sum(row["count"] for row in result["margin_bands"]) == 3
    assert sum(row["share"] for row in result["margin_bands"]) == pytest.approx(100)


def test_empty_frame_returns_empty_segments():
    result = analyze_historical_odds(_frame().iloc[0:0])
    assert result == {"favorite_bands": [], "margin_bands": []}


def test_missing_required_column_is_reported():
    with pytest.raises(ValueError, match="Kolom analisis tidak lengkap"):
        analyze_historical_odds(pd.DataFrame({"home_odds": [2.0]}))
