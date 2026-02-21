# study-with-ai

Desktop MVP scaffold for the Praktikum learning assistant.

## Project Structure

```text
src/praktikum_app/
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

## Quality Checks

```bash
python -m ruff check .
python -m pyright
python -m pytest
```

## Pre-commit

```bash
python -m pre_commit install
python -m pre_commit run --all-files
```
