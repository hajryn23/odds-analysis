import sqlite3

import pandas as pd

from src.odds_engine.audit_database import audit_database
from src.odds_engine.database import save_analysis
from src.odds_engine.odds_analyzer import analyze_1x2


def _report():
    return {
        "original_rows": 1,
        "rejected_rows": 0,
        "duplicate_rows": 0,
        "valid_rows": 1,
    }


def _save_valid_import(path):
    source = pd.DataFrame([{
        "date": pd.Timestamp("2026-02-01"),
        "home_team": "Home FC",
        "away_team": "Away FC",
        "home_odds": 2.0,
        "draw_odds": 4.0,
        "away_odds": 4.0,
    }])
    raw = pd.DataFrame([{
        "id": 77,
        "match": "Home FC vs Away FC",
        "start_time": "2026-02-01",
        "league": "Test League",
        "ft1x2_01": 2.0,
        "ft1x2_02": 4.0,
        "ft1x2_03": 4.0,
    }])
    return save_analysis(
        analyze_1x2(source), _report(), "test.csv", path, raw_source_df=raw
    )


def test_read_only_audit_passes_for_consistent_import(tmp_path):
    db_path = tmp_path / "audit.sqlite3"
    _save_valid_import(db_path)

    before = db_path.read_bytes()
    result = audit_database(db_path)
    after = db_path.read_bytes()

    assert result["errors"] == 0
    assert result["counts"] == {
        "analysis_results": 1,
        "import_history": 1,
        "source_data_records": 1,
    }
    assert result["source_columns"] == 7
    assert before == after


def test_read_only_audit_detects_invalid_odds(tmp_path):
    db_path = tmp_path / "invalid.sqlite3"
    _save_valid_import(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE analysis_results SET home_odds = 1.0"
        )

    result = audit_database(db_path)

    assert result["errors"] >= 1
    odds_check = next(
        item for item in result["checks"]
        if item["name"] == "Validitas odds 1X2"
    )
    assert odds_check["status"] == "ERROR"
