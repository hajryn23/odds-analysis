from pathlib import Path
import sys

from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from odds_engine.pipeline import run_pipeline

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

UPLOAD_DIR = ROOT / "data" / "raw" / "uploads"
OUTPUT_FILE = ROOT / "data" / "processed" / "web_analysis_results.csv"
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
}
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)


@app.route("/", methods=["GET", "POST"])
def index():
    results = None
    columns = []
    stats = None
    error = None

    if request.method == "POST":
        uploaded_file = request.files.get("file")

        if not uploaded_file or not uploaded_file.filename:
            error = "Pilih file CSV terlebih dahulu."

        elif not uploaded_file.filename.lower().endswith(".csv"):
            error = "Format file harus CSV."

        else:
            filename = secure_filename(uploaded_file.filename)

            if not filename:
                error = "Nama file tidak valid."
            else:
                input_file = UPLOAD_DIR / filename
                uploaded_file.save(input_file)

                try:
                    df = run_pipeline(input_file, OUTPUT_FILE)

                    columns = list(df.columns)
                    results = (
                        df.fillna("")
                        .astype(object)
                        .to_dict(orient="records")
                    )

                    stats = {
                        "total_matches": len(df),
                        "average_margin": (
                            df["bookmaker_margin"].mean() * 100
                        ),
                        "home_probability": (
                            df["home_fair_prob"].mean() * 100
                        ),
                        "draw_probability": (
                            df["draw_fair_prob"].mean() * 100
                        ),
                        "away_probability": (
                            df["away_fair_prob"].mean() * 100
                        ),
                        "home_fair_odds": (
                            df["home_fair_odds"].mean()
                        ),
                        "draw_fair_odds": (
                            df["draw_fair_odds"].mean()
                        ),
                        "away_fair_odds": (
                            df["away_fair_odds"].mean()
                        ),
                    }

                except Exception as exc:
                    error = f"Analisis gagal: {exc}"

    return render_template(
        "index.html",
        results=results,
        columns=columns,
        stats=stats,
        error=error,
        column_labels=COLUMN_LABELS,
    )


@app.route("/download")
def download():
    if not OUTPUT_FILE.exists():
        return "Belum ada hasil analisis.", 404

    return send_file(
        OUTPUT_FILE,
        as_attachment=True,
        download_name="odds_analysis_results.csv",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
