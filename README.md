# study-with-ai

Desktop MVP scaffold for the Praktikum learning assistant.

## Project Structure

```text
src/praktikum_app/
  assets/
    theme/app.qss
    fonts/
  domain/
  application/
  infrastructure/
  presentation/qt/
tests/
```

## Local Setup

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

## Run Application

```bash
python -m praktikum_app
```

or:

```bash
praktikum-app
```

## Text Import Flow (PR#3)

- Open the main window and click `Import course...`.
- Use `Text file` tab for local `.txt` / `.md` sources or `Paste` tab for direct text.
- Click `Preview` to run normalization and inspect the result.
- Click `Continue` to save the normalized text into local SQLite storage.

Temporary storage note:
- The app keeps a transient in-memory cache for current UI state.
- Source of truth for imported text is the local SQLite database.

## PDF Import Flow (PR#4)

- Open the `Import course...` dialog and use the `PDF` tab.
- Select a local `.pdf` file and click `Preview`.
- Text extraction runs with primary strategy (`pypdf`) and fallback (`pdfminer.six`) when quality is low.
- Click `Continue` to save normalized extracted text into local SQLite storage.
- If the PDF appears scan-like or low-text, the dialog shows a short OCR hint.

## Database and Migrations (PR#5)

- Default local DB path: `~/.study-with-ai/study_with_ai.db`
- Optional override via environment variable: `PRAKTIKUM_DB_PATH`

Apply migrations:

```bash
# Linux/macOS
alembic upgrade head

# Windows PowerShell
.\.venv\Scripts\alembic.exe upgrade head
```

Optional custom DB path:

```bash
# Linux/macOS
PRAKTIKUM_DB_PATH=/tmp/study_with_ai.db alembic upgrade head

# Windows PowerShell
$env:PRAKTIKUM_DB_PATH = "$PWD\\study_with_ai.db"
.\.venv\Scripts\alembic.exe upgrade head
```

Verify import persistence:

- Run migrations (`alembic upgrade head`).
- Start app and complete `Import course... -> Preview -> Continue`.
- Import is persisted to SQLite; in-memory store is retained only as transient UI cache.

## Theme and Typography

- QSS theme file: `src/praktikum_app/assets/theme/app.qss`
- Optional local fonts directory: `src/praktikum_app/assets/fonts/`
- Font loading uses `QFontDatabase`; if no local fonts exist, the app falls back
  to system serif fonts.

## Quality Checks

```bash
python -m ruff check .
python -m pyright
python -m pytest
```

For headless CI-like environments:

```bash
# Linux/macOS
QT_QPA_PLATFORM=offscreen python -m pytest

# Windows PowerShell
$env:QT_QPA_PLATFORM='offscreen'; python -m pytest
```

## System Tray Notes

- Tray integration (`QSystemTrayIcon`) works on desktop sessions with available
  system tray support.
- In CI/headless (`QT_QPA_PLATFORM=offscreen`) tray can be unavailable; the app
  gracefully falls back to status-bar messages instead of failing.

## Current Limitations (PR#5)

- OCR engine is not embedded (hint only for scan-like PDFs).
- No LLM parsing/decomposition yet.
- No course decomposition/practice/reminders persistence flows yet.
- `llm_calls`, `modules`, and `deadlines` schema exists but is not actively used yet.

## Pre-commit

```bash
python -m pre_commit install
python -m pre_commit run --all-files
```
