# Football Odds Analysis

A personal historical football-odds analysis project. The current web dashboard reads analysis records from a local SQLite database.

## Features

- Read a complete, explicitly selected CSV file (not a sample).
- Validate date, team names, and decimal 1X2 odds.
- Calculate implied probabilities, bookmaker margin, proportional fair probabilities, and fair odds.
- Keep repeated fixture rows. Repeated date/home/away combinations are counted in the import report, not silently discarded; this allows different bookmakers or price snapshots to remain in the dataset.
- Save analysis results and import audit information in SQLite.
- Display stored analysis in a mobile-friendly Flask dashboard.

## Safety and data handling

- The web dashboard does not contain a file upload control or a download button.
- Starting the web server only initializes the SQLite schema. It does not scan folders or import CSV files.
- No CSV is imported automatically.
- The database remains empty until a user explicitly selects a CSV path in the Termux command and confirms the import by typing `IMPOR`.
- The import command reads the entire selected CSV. It does not use a sample or truncate the file.
- The original CSV is not modified or deleted.

## Termux setup

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If the virtual environment already exists, activate it and install any missing requirements.

## Run the dashboard

```bash
python src/web/app.py
```

Open this address in Chrome on the same Android device:

```
http://127.0.0.1:8000
```

The dashboard is read-only. If no import has been confirmed, it displays an empty state.

## Explicitly import one CSV

Use the actual path of the CSV you intentionally want to import:

```bash
python src/odds_engine/import_csv.py "/path/to/your/file.csv"
```

The command will show the number of source rows, rejected rows, repeated fixture keys, and valid rows. It then asks for the exact confirmation word `IMPOR`. Any other response cancels the import without writing records.

The database is stored at:

```
data/odds_analysis.sqlite3
```

## Run tests

```bash
pytest -q
```

Tests include the existing odds-engine checks and additional validation for non-finite odds and preservation of repeated fixture rows. The existing test fixture is used only by tests; it is not automatically imported into the application database.
