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

- Откройте главное окно и нажмите `Импортировать курс...`.
- Используйте вкладку `Текстовый файл` для `.txt` / `.md` или вкладку `Вставка`.
- Нажмите `Предпросмотр` для нормализации и проверки текста.
- Нажмите `Продолжить`, чтобы сохранить импорт в локальную SQLite БД.

Temporary storage note:
- The app keeps a transient in-memory cache for current UI state.
- Source of truth for imported text is the local SQLite database.

## PDF Import Flow (PR#4)

- В диалоге `Импорт курса` откройте вкладку `PDF`.
- Выберите локальный `.pdf` файл и нажмите `Предпросмотр`.
- Извлечение текста использует primary (`pypdf`) и fallback (`pdfminer.six`) при низком качестве.
- Нажмите `Продолжить`, чтобы сохранить нормализованный текст в SQLite.
- Если PDF похож на скан/low-text, появится подсказка про OCR.

## Current Courses UI (Out-of-plan task)

- Главный экран показывает блок `Загруженные курсы` со всеми курсами из БД.
- Для каждого курса отображаются: `course_id`, тип источника, имя файла (или fallback),
  дата импорта, длина текста и короткий хеш.
- В правой панели доступны действия:
  `Обновить из БД`, `Импортировать курс...`, `Удалить выбранный курс`.
- Удаление требует подтверждения в диалоге `Подтверждение удаления`.
- После удаления список и выбор обновляются сразу; удалённый курс не возвращается после рестарта.

Покрытые UI-состояния:
- `loaded`: список курсов загружен и доступен для выбора.
- `empty`: показан empty-state с подсказкой импортировать курс.
- `error`: при ошибке БД показано сообщение пользователю + diagnostics в логах.
- `no-selection`: удаление заблокировано до выбора курса.

## Database and Migrations (PR#5)

Path resolution:

1. If `PRAKTIKUM_DB_PATH` is set, app uses that value as DB file path.
2. Otherwise app uses default from code:
   `Path.home() / ".study-with-ai" / "study_with_ai.db"`.

Default path examples:

- Linux: `/home/<user>/.study-with-ai/study_with_ai.db`
- macOS: `/Users/<user>/.study-with-ai/study_with_ai.db`
- Windows: `C:\Users\<user>\.study-with-ai\study_with_ai.db`

Naming note:

- Default directory is `.study-with-ai` (hyphen).
- Default file name is `study_with_ai.db` (underscore).
- Both come from `src/praktikum_app/infrastructure/db/config.py`.

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

Environment variable recommendations:

- Prefer absolute path to a `.db` file.
- Relative values are resolved against the current working directory.
- Value should point to a file path, not a directory.
- Set `PRAKTIKUM_DB_PATH` before running migrations and before starting the app.

Verify import persistence:

- Run migrations (`alembic upgrade head`).
- Start app and complete `Импортировать курс... -> Предпросмотр -> Продолжить`.
- Убедитесь, что курс появился в списке `Загруженные курсы`.
- Перезапустите приложение: список курсов восстановится из БД.
- Выберите курс и удалите его через `Удалить выбранный курс` + подтверждение.
- In-memory store is retained only as transient UI cache.

## Localization

- Все user-facing строки интерфейса переведены на русский:
  окно приложения, диалог импорта, вкладки, кнопки, подсказки, статусные сообщения,
  confirm/error dialogs, меню system tray.

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
