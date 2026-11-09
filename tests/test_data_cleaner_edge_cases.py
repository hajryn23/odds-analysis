import pandas as pd

from src.odds_engine.data_cleaner import clean_odds_data


def _row(home_odds, draw_odds=3.2, away_odds=4.1):
    return {
        "date": "2026-01-01",
        "home_team": "Team A",
        "away_team": "Team B",
        "home_odds": home_odds,
        "draw_odds": draw_odds,
        "away_odds": away_odds,
    }


def test_cleaner_rejects_non_finite_odds_rowwise():
    df = pd.DataFrame([
        _row(float("inf")),
        _row(2.1, float("nan")),
        _row(2.2, 3.3, 4.4),
    ])
    clean, report = clean_odds_data(df)
    assert len(clean) == 1
    assert report["rejected_rows"] == 2


def test_cleaner_counts_but_preserves_repeated_fixture_rows():
    df = pd.DataFrame([
        _row(2.1, 3.2, 4.1),
        _row(2.0, 3.3, 4.2),
    ])
    clean, report = clean_odds_data(df)
    assert len(clean) == 2
    assert report["duplicate_rows"] == 1
    assert report["valid_rows"] == 2
    assert clean["home_odds"].tolist() == [2.1, 2.0]
