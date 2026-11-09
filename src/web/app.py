from pathlib import Path
import sys

from flask import Flask, render_template

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from odds_engine.database import init_db, load_analysis

app = Flask(__name__)
DB_PATH = ROOT / "data" / "odds_analysis.sqlite3"

COLUMN_LABELS = {
    "date": "Tanggal",
    "home_team": "Tim Tuan Rumah",
    "away_team": "Tim Tandang",
    "home_odds": "Odds Tuan Rumah",
    "draw_odds": "Odds Seri",
    "away_odds": "Odds Tandang",
    "home_odds_prob": "Prob. Implisit Tuan Rumah",
    "draw_odds_prob": "Prob. Implisit Seri",
    "away_odds_prob": "Prob. Implisit Tandang",
    "bookmaker_margin": "Margin Bandar",
    "home_fair_prob": "Prob. Wajar Tuan Rumah",
    "draw_fair_prob": "Prob. Wajar Seri",
    "away_fair_prob": "Prob. Wajar Tandang",
    "home_fair_odds": "Odds Wajar Tuan Rumah",
    "draw_fair_odds": "Odds Wajar Seri",
    "away_fair_odds": "Odds Wajar Tandang",
    "source_file": "Sumber CSV",
}

# Schema initialization only. This never scans or imports CSV files.
init_db(DB_PATH)


@app.route("/", methods=["GET"])
def index():
    df = load_analysis(DB_PATH)
    results = df.astype(object).where(df.notna(), None).to_dict(orient="records")
    columns = [col for col in df.columns if col != "source_file"]
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
        column_labels=COLUMN_LABELS,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
