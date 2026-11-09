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
METADATA_COLUMNS = ["bookmaker", "odds_period", "source_provider"]
TEXT_COLUMNS = {"date", "home_team", "away_team", *METADATA_COLUMNS}
NUMERIC_COLUMNS = [col for col in RESULT_COLUMNS if col not in {"date", "home_team", "away_team"}]
ALL_RESULT_COLUMNS = RESULT_COLUMNS + METADATA_COLUMNS


def _connect(db_path):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _column_type(column):
    return "TEXT" if column in TEXT_COLUMNS else "REAL"


def init_db(db_path):
    """Create the current schema and add missing columns without deleting rows."""
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

        definitions = [
            f'"{col}" {_column_type(col)}'
            for col in ALL_RESULT_COLUMNS
        ]
        connection.execute(
            "CREATE TABLE IF NOT EXISTS analysis_results ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "source_file TEXT NOT NULL DEFAULT '', "
            "import_id INTEGER, "
            + ", ".join(definitions)
            + ", FOREIGN KEY(import_id) REFERENCES import_history(id))"
        )

        existing = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(analysis_results)")
        }
        # Add every current result/metadata field missing from older schemas.
        # Nullable ALTERs preserve all existing rows and remain idempotent.
        required_columns = {
            "source_file": "TEXT NOT NULL DEFAULT ''",
            "import_id": "INTEGER",
            **{col: _column_type(col) for col in ALL_RESULT_COLUMNS},
        }
        for column, sql_type in required_columns.items():
            if column not in existing:
                connection.execute(
                    f'ALTER TABLE analysis_results ADD COLUMN "{column}" {sql_type}'
                )

        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_analysis_date ON analysis_results(date)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_analysis_import ON analysis_results(import_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_analysis_bookmaker ON analysis_results(bookmaker)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_analysis_provider ON analysis_results(source_provider)"
        )


def _normalize_value(column, value):
    if pd.isna(value):
        return None
    if column == "date":
        return pd.Timestamp(value).isoformat()
    if column in NUMERIC_COLUMNS:
        return float(value)
    return str(value).strip()


def save_analysis(df, report, source_file, db_path):
    """Persist all analyzed rows, including optional bookmaker/provider metadata."""
    if df.empty:
        raise ValueError("Tidak ada baris valid untuk disimpan.")

    missing = [col for col in RESULT_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Kolom hasil analisis tidak lengkap: {missing}")

    init_db(db_path)
    available_columns = [
        col for col in ALL_RESULT_COLUMNS
        if col in df.columns or col in METADATA_COLUMNS
    ]
    rows = []
    for record in df.to_dict(orient="records"):
        rows.append(tuple(
            _normalize_value(col, record.get(col))
            for col in available_columns
        ))

    source_name = Path(source_file).name
    with closing(_connect(db_path)) as connection, connection:
        cursor = connection.execute(
            """
            INSERT INTO import_history
            (source_file, original_rows, rejected_rows, duplicate_rows, valid_rows, saved_rows)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                source_name,
                int(report["original_rows"]),
                int(report["rejected_rows"]),
                int(report["duplicate_rows"]),
                int(report["valid_rows"]),
                len(rows),
            ),
        )
        import_id = cursor.lastrowid
        columns = available_columns + ["source_file", "import_id"]
        placeholders = ", ".join(["?"] * len(columns))
        quoted_columns = ", ".join(f'"{col}"' for col in columns)
        sql = (
            f"INSERT INTO analysis_results ({quoted_columns}) "
            f"VALUES ({placeholders})"
        )
        connection.executemany(
            sql,
            [row + (source_name, import_id) for row in rows],
        )
    return import_id


def load_analysis(db_path):
    init_db(db_path)
    columns = ALL_RESULT_COLUMNS + ["source_file"]
    with closing(_connect(db_path)) as connection:
        rows = connection.execute(
            "SELECT " + ", ".join(f'"{col}"' for col in columns)
            + " FROM analysis_results ORDER BY date DESC, id DESC"
        ).fetchall()
    return pd.DataFrame([dict(row) for row in rows], columns=columns)


def load_import_history(db_path, limit=10):
    """Return recent explicit imports for dashboard traceability."""
    init_db(db_path)
    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, source_file, imported_at, original_rows, rejected_rows,
                   duplicate_rows, valid_rows, saved_rows
            FROM import_history
            ORDER BY imported_at DESC, id DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
    return [dict(row) for row in rows]
