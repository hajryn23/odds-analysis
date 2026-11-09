import json
import sqlite3

import pandas as pd

from src.odds_engine.source_adapters import adapt_odds_source
from src.odds_engine.data_cleaner import clean_odds_data
from src.odds_engine.odds_analyzer import analyze_1x2
from src.odds_engine.database import save_analysis


def _sgodds_frame():
    return pd.DataFrame([
        {
            "id": 1537,
            "match": "Barcelona vs Girona",
            "start_time": "2025-10-18 22:15:00",
            "league": "Spanish League",
            "result": "HT:1-1, FT:2-1",
            "ft1x2_01": 2.1,
            "ft1x2_02": 3.2,
            "ft1x2_03": 4.0,
            "ah_01_hcap": -0.25,
            "ah_01": 1.9,
        },
        {
            "id": 1537,  # Source IDs are reused; both fixtures must survive.
            "match": "Sociedad vs Atletico Madrid",
            "start_time": "2026-01-05 04:00:00",
            "league": "Spanish League",
            "result": "HT:0-0, FT:1-1",
            "ft1x2_01": 2.3,
            "ft1x2_02": 3.0,
            "ft1x2_03": 3.1,
            "ah_01_hcap": None,
            "ah_01": None,
        },
    ])


def test_sgodds_adapter_maps_1x2_and_keeps_reused_source_ids():
    source = _sgodds_frame()
    mapped, raw = adapt_odds_source(source)

    clean, report = clean_odds_data(mapped)

    assert len(clean) == 2
    assert report["rejected_rows"] == 0
    assert clean["home_team"].tolist() == ["Barcelona", "Sociedad"]
    assert clean["away_team"].tolist() == ["Girona", "Atletico Madrid"]
    assert clean["_source_row"].tolist() == [0, 1]
    assert raw["id"].tolist() == [1537, 1537]


def test_sgodds_import_persists_all_raw_columns_and_reused_ids(tmp_path):
    source = _sgodds_frame()
    mapped, raw = adapt_odds_source(source)
    clean, report = clean_odds_data(mapped)
    source_rows = raw.iloc[clean["_source_row"].astype(int).tolist()].copy()
    analyzed = analyze_1x2(clean.drop(columns=["_source_row"]))

    db_path = tmp_path / "sgodds.sqlite3"
    import_id = save_analysis(
        analyzed, report, "sgodds-spanish-league.csv", db_path,
        raw_source_df=source_rows,
    )

    with sqlite3.connect(db_path) as connection:
        analysis_count = connection.execute(
            "SELECT COUNT(*) FROM analysis_results WHERE import_id = ?",
            (import_id,),
        ).fetchone()[0]
        raw_rows = connection.execute(
            """
            SELECT source_match_id, raw_payload
            FROM source_data_records
            WHERE import_id = ?
            ORDER BY row_number
            """,
            (import_id,),
        ).fetchall()

    assert analysis_count == 2
    assert len(raw_rows) == 2
    assert [row[0] for row in raw_rows] == ["1537", "1537"]

    first_payload = json.loads(raw_rows[0][1])
    second_payload = json.loads(raw_rows[1][1])
    assert len(first_payload) == 10
    assert first_payload["ah_01_hcap"] == -0.25
    assert second_payload["ah_01_hcap"] is None
    assert second_payload["result"] == "HT:0-0, FT:1-1"
