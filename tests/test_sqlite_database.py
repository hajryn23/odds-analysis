import sqlite3

import pandas as pd

from src.odds_engine.database import init_db, load_analysis, save_analysis
from src.odds_engine.odds_analyzer import analyze_1x2


def _source_frame():
    return pd.DataFrame([{
        "date": pd.Timestamp("2026-02-01"),
        "home_team": "Home FC",
        "away_team": "Away FC",
        "home_odds": 2.1,
        "draw_odds": 3.2,
        "away_odds": 4.0,
    }])


def _report():
    return {
        "original_rows": 1,
        "rejected_rows": 0,
        "duplicate_rows": 0,
        "valid_rows": 1,
    }


def test_sqlite_save_and_load_records_and_import_history(tmp_path):
    db_path = tmp_path / "odds.sqlite3"
    analyzed = analyze_1x2(_source_frame())

    init_db(db_path)
    import_id = save_analysis(analyzed, _report(), "chosen_history.csv", db_path)
    loaded = load_analysis(db_path)

    assert import_id == 1
    assert len(loaded) == 1
    assert loaded.iloc[0]["home_team"] == "Home FC"
    assert loaded.iloc[0]["source_file"] == "chosen_history.csv"
    assert loaded.iloc[0]["bookmaker_margin"] > 0

    with sqlite3.connect(db_path) as connection:
        history = connection.execute(
            "SELECT source_file, saved_rows FROM import_history"
        ).fetchone()
    assert history == ("chosen_history.csv", 1)


def test_metadata_columns_are_migrated_and_persisted(tmp_path):
    db_path = tmp_path / "metadata.sqlite3"
    analyzed = analyze_1x2(_source_frame())
    analyzed["bookmaker"] = "Pinnacle"
    analyzed["odds_period"] = "closing"
    analyzed["source_provider"] = "football-data"

    save_analysis(analyzed, _report(), "historical.csv", db_path)
    loaded = load_analysis(db_path)

    assert loaded.loc[0, "bookmaker"] == "Pinnacle"
    assert loaded.loc[0, "odds_period"] == "closing"
    assert loaded.loc[0, "source_provider"] == "football-data"


def test_init_db_adds_missing_columns_without_losing_legacy_rows(tmp_path):
    db_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.execute("""
            CREATE TABLE analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                home_team TEXT,
                away_team TEXT,
                home_odds REAL,
                draw_odds REAL,
                away_odds REAL
            )
        """)
        connection.execute(
            """
            INSERT INTO analysis_results
            (date, home_team, away_team, home_odds, draw_odds, away_odds)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("2025-12-01", "Legacy Home", "Legacy Away", 2.0, 3.0, 4.0),
        )

    init_db(db_path)
    init_db(db_path)  # Migration must be safe to run repeatedly.
    loaded = load_analysis(db_path)

    assert len(loaded) == 1
    assert loaded.loc[0, "home_team"] == "Legacy Home"
    assert loaded.loc[0, "away_team"] == "Legacy Away"
    assert loaded.loc[0, "bookmaker"] is None
    assert loaded.loc[0, "odds_period"] is None
    assert loaded.loc[0, "source_provider"] is None

    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(analysis_results)")
        }
    assert {"bookmaker", "odds_period", "source_provider"} <= columns


def test_save_analysis_supports_legacy_required_imported_rows_column(tmp_path):
    db_path = tmp_path / "legacy_import_history.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.execute("""
            CREATE TABLE import_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                original_rows INTEGER NOT NULL,
                rejected_rows INTEGER NOT NULL,
                duplicate_rows INTEGER NOT NULL,
                imported_rows INTEGER NOT NULL,
                valid_rows INTEGER NOT NULL DEFAULT 0,
                saved_rows INTEGER NOT NULL DEFAULT 0
            )
        """)

    analyzed = analyze_1x2(_source_frame())
    import_id = save_analysis(
        analyzed, _report(), "legacy_history.csv", db_path
    )

    with sqlite3.connect(db_path) as connection:
        history = connection.execute(
            """
            SELECT source_file, original_rows, imported_rows,
                   valid_rows, saved_rows
            FROM import_history WHERE id = ?
            """,
            (import_id,),
        ).fetchone()
        analysis_count = connection.execute(
            "SELECT COUNT(*) FROM analysis_results WHERE import_id = ?",
            (import_id,),
        ).fetchone()[0]

    assert history == ("legacy_history.csv", 1, 1, 1, 1)
    assert analysis_count == 1


def test_save_analysis_supplies_legacy_metadata_defaults(tmp_path):
    db_path = tmp_path / "legacy_metadata.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.execute("""
            CREATE TABLE analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                home_odds REAL NOT NULL,
                draw_odds REAL NOT NULL,
                away_odds REAL NOT NULL,
                home_odds_prob REAL NOT NULL,
                draw_odds_prob REAL NOT NULL,
                away_odds_prob REAL NOT NULL,
                bookmaker_margin REAL NOT NULL,
                home_fair_prob REAL NOT NULL,
                draw_fair_prob REAL NOT NULL,
                away_fair_prob REAL NOT NULL,
                home_fair_odds REAL NOT NULL,
                draw_fair_odds REAL NOT NULL,
                away_fair_odds REAL NOT NULL,
                analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                source_file TEXT NOT NULL DEFAULT '',
                import_id INTEGER,
                bookmaker TEXT NOT NULL DEFAULT 'Unknown',
                odds_period TEXT NOT NULL DEFAULT 'unspecified',
                source_provider TEXT NOT NULL DEFAULT 'manual_csv'
            )
        """)

    analyzed = analyze_1x2(_source_frame())
    import_id = save_analysis(
        analyzed, _report(), "legacy_metadata.csv", db_path
    )

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT bookmaker, odds_period, source_provider
            FROM analysis_results WHERE import_id = ?
            """,
            (import_id,),
        ).fetchone()

    assert row == ("Unknown", "unspecified", "manual_csv")
