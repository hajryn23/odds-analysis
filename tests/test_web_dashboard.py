import pandas as pd

from src.odds_engine.database import save_analysis
from src.odds_engine.odds_analyzer import analyze_1x2
from src.web import app as web_module


def _save_one_match(db_path):
    source = pd.DataFrame([{
        "date": pd.Timestamp("2026-02-01"),
        "home_team": "Home FC",
        "away_team": "Away FC",
        "home_odds": 2.0,
        "draw_odds": 4.0,
        "away_odds": 4.0,
    }])
    report = {
        "original_rows": 1,
        "rejected_rows": 0,
        "duplicate_rows": 0,
        "valid_rows": 1,
    }
    save_analysis(analyze_1x2(source), report, "history-test.csv", db_path)


def test_dashboard_empty_state_has_no_upload_or_download(tmp_path, monkeypatch):
    db_path = tmp_path / "empty.sqlite3"
    monkeypatch.setattr(web_module, "DB_PATH", db_path)

    response = web_module.app.test_client().get("/")

    assert response.status_code == 200
    assert "Belum Ada Data Analisis" in response.get_data(as_text=True)
    assert 'type="file"' not in response.get_data(as_text=True)
    assert "download" not in response.get_data(as_text=True).lower()


def test_dashboard_formats_probabilities_and_shows_import_history(tmp_path, monkeypatch):
    db_path = tmp_path / "populated.sqlite3"
    _save_one_match(db_path)
    monkeypatch.setattr(web_module, "DB_PATH", db_path)

    response = web_module.app.test_client().get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Home FC" in html
    assert "50.00%" in html
    assert "25.00%" in html
    assert "history-test.csv" in html
    assert "2.000" in html


def test_dashboard_displays_bookmaker_and_odds_provenance(tmp_path, monkeypatch):
    db_path = tmp_path / "metadata-dashboard.sqlite3"
    source = pd.DataFrame([{
        "date": pd.Timestamp("2026-02-01"),
        "home_team": "Metadata Home",
        "away_team": "Metadata Away",
        "home_odds": 2.0,
        "draw_odds": 4.0,
        "away_odds": 4.0,
        "bookmaker": "Pinnacle",
        "odds_period": "closing",
        "source_provider": "football-data",
    }])
    report = {
        "original_rows": 1,
        "rejected_rows": 0,
        "duplicate_rows": 0,
        "valid_rows": 1,
    }
    save_analysis(analyze_1x2(source), report, "football-data.csv", db_path)
    monkeypatch.setattr(web_module, "DB_PATH", db_path)

    response = web_module.app.test_client().get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Pinnacle" in html
    assert "closing" in html
    assert "football-data" in html
    assert "Bookmaker" in html
    assert "Periode Odds" in html
    assert "Penyedia Data" in html
