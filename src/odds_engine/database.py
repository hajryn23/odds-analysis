from contextlib import closing
import json
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
METADATA_DEFAULTS = {
    "bookmaker": "Unknown",
    "odds_period": "unspecified",
    "source_provider": "manual_csv",
}
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
        connection.execute("""
            CREATE TABLE IF NOT EXISTS source_data_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                import_id INTEGER NOT NULL,
                row_number INTEGER NOT NULL,
                source_match_id TEXT,
                match_name TEXT,
                league TEXT,
                start_time TEXT,
                raw_payload TEXT NOT NULL,
                FOREIGN KEY(import_id) REFERENCES import_history(id)
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
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_source_records_import "
            "ON source_data_records(import_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_source_records_match_id "
            "ON source_data_records(source_match_id)"
        )


def _normalize_value(column, value):
    if pd.isna(value):
        return None
    if column == "date":
        return pd.Timestamp(value).isoformat()
    if column in NUMERIC_COLUMNS:
        return float(value)
    return str(value).strip()


def _json_safe(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def save_analysis(df, report, source_file, db_path, raw_source_df=None):
    """Persist analyzed rows and, when supplied, complete original source rows."""
    if df.empty:
        raise ValueError("Tidak ada baris valid untuk disimpan.")

    missing = [col for col in RESULT_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Kolom hasil analisis tidak lengkap: {missing}")
    if raw_source_df is not None and len(raw_source_df) != len(df):
        raise ValueError("Jumlah baris sumber tidak cocok dengan hasil analisis.")

    init_db(db_path)
    available_columns = [
        col for col in ALL_RESULT_COLUMNS
        if col in df.columns or col in METADATA_COLUMNS
    ]
    rows = []
    for record in df.to_dict(orient="records"):
        values = []
        for col in available_columns:
            value = record.get(col)
            if col in METADATA_DEFAULTS and (
                value is None or pd.isna(value) or str(value).strip() == ""
            ):
                value = METADATA_DEFAULTS[col]
            values.append(_normalize_value(col, value))
        rows.append(tuple(values))

    source_name = Path(source_file).name
    with closing(_connect(db_path)) as connection, connection:
        # Older local databases may have an additional NOT NULL
        # imported_rows column. Populate it when present so imports remain
        # compatible without rebuilding or deleting the user's existing table.
        history_columns = {
            row["name"]: row
            for row in connection.execute("PRAGMA table_info(import_history)")
        }
        history_values = {
            "source_file": source_name,
            "original_rows": int(report["original_rows"]),
            "rejected_rows": int(report["rejected_rows"]),
            "duplicate_rows": int(report["duplicate_rows"]),
            "valid_rows": int(report["valid_rows"]),
            "saved_rows": len(rows),
        }
        if "imported_rows" in history_columns:
            history_values["imported_rows"] = len(rows)

        history_names = list(history_values)
        history_sql = (
            "INSERT INTO import_history ("
            + ", ".join(f'"{name}"' for name in history_names)
            + ") VALUES ("
            + ", ".join(["?"] * len(history_names))
            + ")"
        )
        cursor = connection.execute(
            history_sql,
            [history_values[name] for name in history_names],
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

        if raw_source_df is not None:
            source_records = []
            for source_index, record in raw_source_df.iterrows():
                payload = {
                    str(key): _json_safe(value)
                    for key, value in record.to_dict().items()
                }
                source_records.append((
                    import_id,
                    int(source_index) + 2,
                    str(record.get("id")) if pd.notna(record.get("id")) else None,
                    str(record.get("match")) if pd.notna(record.get("match")) else None,
                    str(record.get("league")) if pd.notna(record.get("league")) else None,
                    str(record.get("start_time")) if pd.notna(record.get("start_time")) else None,
                    json.dumps(payload, ensure_ascii=False, allow_nan=False),
                ))
            connection.executemany(
                """
                INSERT INTO source_data_records
                (import_id, row_number, source_match_id, match_name, league,
                 start_time, raw_payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                source_records,
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


def load_source_records(db_path):
    """Load archived raw source payloads for read-only outcome analysis."""
    init_db(db_path)
    with closing(_connect(db_path)) as connection:
        rows = connection.execute(
            "SELECT import_id, row_number, raw_payload "
            "FROM source_data_records ORDER BY import_id, row_number, id"
        ).fetchall()
    return [dict(row) for row in rows]
