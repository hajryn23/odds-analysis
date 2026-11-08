import pandas as pd
import pytest

from src.odds_engine.csv_reader import read_odds_csv
from src.odds_engine.data_cleaner import clean_odds_data
from src.odds_engine.odds_analyzer import analyze_1x2


def test_csv_reader():
    df = read_odds_csv("data/raw/sample_odds.csv")
    assert len(df) == 3
    assert "home_odds" in df.columns


def test_data_cleaner():
    df = read_odds_csv("data/raw/sample_odds.csv")
    clean, report = clean_odds_data(df)

    assert len(clean) == 3
    assert report["rejected_rows"] == 0


def test_invalid_odds_rejected():
    df = pd.DataFrame({
        "date": ["2026-01-01"],
        "home_team": ["Team A"],
        "away_team": ["Team B"],
        "home_odds": [0],
        "draw_odds": [3.4],
        "away_odds": [4.2]
    })

    clean, report = clean_odds_data(df)

    assert len(clean) == 0
    assert report["rejected_rows"] == 1


def test_fair_probability_total():
    df = read_odds_csv("data/raw/sample_odds.csv")
    clean, _ = clean_odds_data(df)
    result = analyze_1x2(clean)

    total = (
        result["home_fair_prob"]
        + result["draw_fair_prob"]
        + result["away_fair_prob"]
    )

    assert all(abs(value - 1) < 1e-10 for value in total)


def test_bookmaker_margin():
    df = pd.DataFrame({
        "home_odds": [2.0],
        "draw_odds": [3.0],
        "away_odds": [4.0]
    })

    result = analyze_1x2(df)

    assert result["bookmaker_margin"].iloc[0] == pytest.approx(
        1/12
    )


def test_fair_odds():
    df = pd.DataFrame({
        "home_odds": [2.0],
        "draw_odds": [3.0],
        "away_odds": [4.0]
    })

    result = analyze_1x2(df)

    for outcome in ["home", "draw", "away"]:
        assert (
            result[f"{outcome}_fair_odds"].iloc[0]
            * result[f"{outcome}_fair_prob"].iloc[0]
        ) == pytest.approx(1.0)
