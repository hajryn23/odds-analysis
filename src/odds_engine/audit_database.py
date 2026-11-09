"""Read-only integrity and consistency audit for the local odds database."""
import argparse
import json
from pathlib import Path
import sqlite3


def audit_database(db_path):
    """Inspect an existing SQLite database without creating or modifying it."""
    path = Path(db_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Database tidak ditemukan: {path}")

    uri = path.as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    checks = []

    def add(name, ok, detail):
        checks.append({
            "name": name,
            "status": "OK" if ok else "ERROR",
            "detail": str(detail),
        })

    try:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        required = {"import_history", "analysis_results", "source_data_records"}
        missing = sorted(required - tables)
        if missing:
            add("Struktur tabel", False, "Tabel hilang: " + ", ".join(missing))
            return {"checks": checks, "errors": 1}

        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        add("Integritas SQLite", integrity == "ok", integrity)

        counts = {
            table: connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]
            for table in sorted(required)
        }
        add("Jumlah data", True, counts)

        bad_odds = connection.execute("""
            SELECT COUNT(*) FROM analysis_results
            WHERE home_odds IS NULL OR draw_odds IS NULL OR away_odds IS NULL
               OR home_odds <= 1 OR draw_odds <= 1 OR away_odds <= 1
        """).fetchone()[0]
        add("Validitas odds 1X2", bad_odds == 0,
            f"{bad_odds} baris memiliki odds kosong atau <= 1")

        bad_probabilities = connection.execute("""
            SELECT COUNT(*) FROM analysis_results
            WHERE home_fair_prob IS NULL OR draw_fair_prob IS NULL
               OR away_fair_prob IS NULL
               OR ABS(home_fair_prob + draw_fair_prob + away_fair_prob - 1.0) > 0.000001
        """).fetchone()[0]
        add("Konsistensi probabilitas fair", bad_probabilities == 0,
            f"{bad_probabilities} baris memiliki total probabilitas di luar toleransi")

        bad_margin = connection.execute("""
            SELECT COUNT(*) FROM analysis_results
            WHERE bookmaker_margin IS NULL
               OR ABS(bookmaker_margin -
                   (1.0/home_odds + 1.0/draw_odds + 1.0/away_odds - 1.0)) > 0.000001
        """).fetchone()[0]
        add("Konsistensi margin bookmaker", bad_margin == 0,
            f"{bad_margin} baris memiliki margin tidak konsisten")

        imports = connection.execute("""
            SELECT id, source_file, original_rows, rejected_rows,
                   valid_rows, saved_rows
            FROM import_history ORDER BY id
        """).fetchall()
        import_errors = []
        for item in imports:
            analysis_count = connection.execute(
                "SELECT COUNT(*) FROM analysis_results WHERE import_id = ?",
                (item["id"],),
            ).fetchone()[0]
            raw_count = connection.execute(
                "SELECT COUNT(*) FROM source_data_records WHERE import_id = ?",
                (item["id"],),
            ).fetchone()[0]
            if analysis_count != item["saved_rows"]:
                import_errors.append(
                    f"Impor #{item['id']}: saved_rows={item['saved_rows']}, "
                    f"analysis={analysis_count}"
                )
            if raw_count and raw_count != analysis_count:
                import_errors.append(
                    f"Impor #{item['id']}: raw_source={raw_count}, "
                    f"analysis={analysis_count}"
                )
            if item["valid_rows"] != item["saved_rows"]:
                import_errors.append(
                    f"Impor #{item['id']}: valid_rows tidak sama dengan saved_rows"
                )
        add("Kecocokan setiap riwayat impor", not import_errors,
            "; ".join(import_errors) if import_errors else
            f"{len(imports)} riwayat diperiksa")

        orphan_analysis = connection.execute("""
            SELECT COUNT(*) FROM analysis_results a
            LEFT JOIN import_history h ON h.id = a.import_id
            WHERE a.import_id IS NOT NULL AND h.id IS NULL
        """).fetchone()[0]
        orphan_raw = connection.execute("""
            SELECT COUNT(*) FROM source_data_records s
            LEFT JOIN import_history h ON h.id = s.import_id
            WHERE h.id IS NULL
        """).fetchone()[0]
        orphan_ok = orphan_analysis == 0 and orphan_raw == 0
        add("Relasi data impor", orphan_ok,
            f"analysis tanpa riwayat={orphan_analysis}; sumber tanpa riwayat={orphan_raw}")

        malformed = 0
        payload_columns = set()
        raw_rows = connection.execute(
            "SELECT raw_payload FROM source_data_records"
        )
        for row in raw_rows:
            try:
                payload = json.loads(row["raw_payload"])
                if not isinstance(payload, dict):
                    malformed += 1
                else:
                    payload_columns.update(payload.keys())
            except (TypeError, json.JSONDecodeError):
                malformed += 1
        add("JSON sumber asli", malformed == 0,
            f"{counts['source_data_records']} rekaman; "
            f"{len(payload_columns)} nama kolom sumber; JSON rusak={malformed}")

        date_range = connection.execute("""
            SELECT MIN(date), MAX(date) FROM analysis_results
        """).fetchone()
        add("Rentang tanggal", True,
            f"{date_range[0] or '—'} sampai {date_range[1] or '—'}")

        errors = sum(check["status"] == "ERROR" for check in checks)
        return {
            "checks": checks,
            "errors": errors,
            "counts": counts,
            "date_range": tuple(date_range),
            "source_columns": len(payload_columns),
        }
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(
        description="Audit database odds SQLite dalam mode hanya-baca."
    )
    parser.add_argument(
        "--db",
        default="data/odds_analysis.sqlite3",
        help="Lokasi database (default: data/odds_analysis.sqlite3)",
    )
    args = parser.parse_args()

    try:
        result = audit_database(args.db)
    except Exception as exc:
        parser.exit(1, f"Audit gagal: {exc}\\n")

    print("=== AUDIT DATABASE ODDS (HANYA-BACA) ===")
    for check in result["checks"]:
        print(f"[{check['status']}] {check['name']}: {check['detail']}")
    print(f"\nKesalahan ditemukan: {result['errors']}")
    if result["errors"]:
        raise SystemExit(1)
    print("Status audit: LULUS")


if __name__ == "__main__":
    main()
