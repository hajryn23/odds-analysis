from contextlib import closing
from pathlib import Path
import sqlite3

import pandas as pd

RESULT_COLUMNS = [
    "date", "home_team", "away_team",
    "home_odds", "draw_odds", "away_odds",
    "home_odds_prob", "draw_odds_prob", "away_odds_prob",
    "bookmaker_margin",
    "home_fair_prob", "draw_fair_prob", "away_fair_prob",
    "home_fair_odds", "draw_fair_odds", "away_fair_odds",
]

NUMERIC_COLUMNS = [col for col in RESULT_COLUMNS if col not in {"date", "home_team", "away_team"}]


def _connect(db_path):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path):
    with closing(_connect(db_path)) as connection, connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS import_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                original_rows INTEGER NOT NULL,
                rejected_rows INTEGER NOT NULL,
                duplicate_rows INTEGER NOT NULL,
                valid_rows INTEGER NOT NULL,
                saved_rows INTEGER NOT NULL
            )
        """)
        definitions = []
        for col in RESULT_COLUMNS:
            sql_type = "TEXT" if col in {"date", "home_team", "away_team"} else "REAL"
            definitions.append(f'"{col}" {sql_type}')
        connection.execute(
            "CREATE TABLE IF NOT EXISTS analysis_results ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "source_file TEXT NOT NULL, "
            "import_id INTEGER, "
            + ", ".join(definitions)
            + ", FOREIGN KEY(import_id) REFERENCES import_history(id))"
        )

        # Migrate older SQLite databases without deleting existing records.
        existing = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(analysis_results)")
        }
        if "source_file" not in existing:
            connection.execute(
                "ALTER TABLE analysis_results ADD COLUMN source_file TEXT NOT NULL DEFAULT ''"
            )
        if "import_id" not in existing:
            connection.execute(
                "ALTER TABLE analysis_results ADD COLUMN import_id INTEGER"
            )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_analysis_date ON analysis_results(date)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_analysis_import ON analysis_results(import_id)"
        )


def save_analysis(df, report, source_file, db_path):
    if df.empty:
        raise ValueError("Tidak ada baris valid untuk disimpan.")

    missing = [col for col in RESULT_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Kolom hasil analisis tidak lengkap: {missing}")

    init_db(db_path)
    rows = []
    for record in df[RESULT_COLUMNS].to_dict(orient="records"):
        values = []
        for col in RESULT_COLUMNS:
            value = record[col]
            if pd.isna(value):
                values.append(None)
            elif col == "date":
                values.append(pd.Timestamp(value).isoformat())
            elif col in NUMERIC_COLUMNS:
                values.append(float(value))
            else:
                values.append(str(value))
        rows.append(tuple(values))

    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO import_history
            (source_file, original_rows, rejected_rows, duplicate_rows, valid_rows, saved_rows)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                Path(source_file).name,
                int(report["original_rows"]),
                int(report["rejected_rows"]),
                int(report["duplicate_rows"]),
                int(report["valid_rows"]),
                len(rows),
            ),
        )
        import_id = cursor.lastrowid
        columns = RESULT_COLUMNS + ["source_file", "import_id"]
        placeholders = ", ".join(["?"] * len(columns))
        sql = (
            f"INSERT INTO analysis_results ({', '.join(columns)}) "
            f"VALUES ({placeholders})"
        )
        source_name = Path(source_file).name
        connection.executemany(
            sql,
            [row + (source_name, import_id) for row in rows],
        )
    return import_id


def load_analysis(db_path):
    init_db(db_path)
    columns = RESULT_COLUMNS + ["source_file"]
    with _connect(db_path) as connection:
        rows = connection.execute(
            "SELECT " + ", ".join(f'"{col}"' for col in columns)
            + " FROM analysis_results ORDER BY date DESC, id DESC"
        ).fetchall()
    return pd.DataFrame([dict(row) for row in rows], columns=columns)
