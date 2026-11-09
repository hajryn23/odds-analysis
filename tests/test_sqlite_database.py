import pandas as pd

from src.odds_engine.database import init_db, load_analysis, save_analysis
from src.odds_engine.odds_analyzer import analyze_1x2


def test_sqlite_save_and_load_records_and_import_history(tmp_path):
    db_path = tmp_path / "odds.sqlite3"
    source = pd.DataFrame([{
        "date": pd.Timestamp("2026-02-01"),
        "home_team": "Home FC",
        "away_team": "Away FC",
        "home_odds": 2.1,
        "draw_odds": 3.2,
        "away_odds": 4.0,
    }])
    analyzed = analyze_1x2(source)
    report = {
        "original_rows": 1,
        "rejected_rows": 0,
        "duplicate_rows": 0,
        "valid_rows": 1,
    }

    init_db(db_path)
    import_id = save_analysis(analyzed, report, "chosen_history.csv", db_path)
    loaded = load_analysis(db_path)

    assert import_id == 1
    assert len(loaded) == 1
    assert loaded.iloc[0]["home_team"] == "Home FC"
    assert loaded.iloc[0]["source_file"] == "chosen_history.csv"
    assert loaded.iloc[0]["bookmaker_margin"] > 0

    import sqlite3
    with sqlite3.connect(db_path) as connection:
        history = connection.execute(
            "SELECT source_file, saved_rows FROM import_history"
        ).fetchone()
    assert history == ("chosen_history.csv", 1)
