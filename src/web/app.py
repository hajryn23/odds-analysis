from pathlib import Path
import sys

from flask import Flask, render_template

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from odds_engine.database import init_db, load_analysis, load_import_history

app = Flask(__name__)
DB_PATH = ROOT / "data" / "odds_analysis.sqlite3"

COLUMN_LABELS = {
    "date": "Tanggal",
    "home_team": "Tim Tuan Rumah",
    "away_team": "Tim Tandang",
    "home_odds": "Odds Home",
    "draw_odds": "Odds Draw",
    "away_odds": "Odds Away",
    "home_odds_prob": "Prob. Implisit Home",
    "draw_odds_prob": "Prob. Implisit Draw",
    "away_odds_prob": "Prob. Implisit Away",
    "bookmaker_margin": "Margin Bandar",
    "home_fair_prob": "Prob. Wajar Home",
    "draw_fair_prob": "Prob. Wajar Draw",
    "away_fair_prob": "Prob. Wajar Away",
    "home_fair_odds": "Fair Odds Home",
    "draw_fair_odds": "Fair Odds Draw",
    "away_fair_odds": "Fair Odds Away",
    "source_file": "Sumber Data",
}

PERCENT_COLUMNS = {
    "home_odds_prob", "draw_odds_prob", "away_odds_prob",
    "bookmaker_margin",
    "home_fair_prob", "draw_fair_prob", "away_fair_prob",
}
ODDS_COLUMNS = {
    "home_odds", "draw_odds", "away_odds",
    "home_fair_odds", "draw_fair_odds", "away_fair_odds",
}

# Schema initialization only. This never scans or imports CSV files.
init_db(DB_PATH)


@app.route("/", methods=["GET"])
def index():
    df = load_analysis(DB_PATH)
    results = df.astype(object).where(df.notna(), None).to_dict(orient="records")
    columns = list(df.columns)
    import_history = load_import_history(DB_PATH)

    stats = None
    if not df.empty:
        stats = {
            "total_matches": len(df),
            "average_margin": float(df["bookmaker_margin"].mean() * 100),
            "home_probability": float(df["home_fair_prob"].mean() * 100),
            "draw_probability": float(df["draw_fair_prob"].mean() * 100),
            "away_probability": float(df["away_fair_prob"].mean() * 100),
            "home_fair_odds": float(df["home_fair_odds"].mean()),
            "draw_fair_odds": float(df["draw_fair_odds"].mean()),
            "away_fair_odds": float(df["away_fair_odds"].mean()),
        }

    return render_template(
        "index.html",
        results=results,
        columns=columns,
        stats=stats,
        import_history=import_history,
        column_labels=COLUMN_LABELS,
        percent_columns=PERCENT_COLUMNS,
        odds_columns=ODDS_COLUMNS,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
