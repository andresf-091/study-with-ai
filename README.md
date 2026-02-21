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

## Pre-commit

```bash
python -m pre_commit install
python -m pre_commit run --all-files
```
