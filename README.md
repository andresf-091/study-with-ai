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

## LLM Infrastructure (PR#6)

What is added:

- Unified LLM contracts (`LLMTaskType`, `LLMRequest`, `LLMResponse`, provider protocol).
- Provider clients:
  - Anthropic Messages API (`AnthropicClient`)
  - OpenRouter chat completions (`OpenRouterClient`)
- `LLMRouter` with strict policy mapping and no silent provider fallback.
- Bounded retry/backoff for retryable failures (timeouts, HTTP 429, HTTP 5xx).
- Audit persistence for each call into `llm_calls`.
- Prompt governance module with purpose/schema/version for `course_parse`.
- API key storage via OS keyring only.

Routing policy (fixed by product policy):

- `COURSE_PARSE` -> Anthropic (`claude-3-5-sonnet-latest`)
- `PRACTICE_GRADE` -> Anthropic (`claude-3-5-sonnet-latest`)
- `PRACTICE_GEN` -> OpenRouter (`openai/gpt-4o-mini`)
- `CURATOR_MSG` -> OpenRouter (`openai/gpt-4o-mini`)

If config violates this policy, router initialization fails explicitly.

API keys setup:

- Open app and click `Ключи LLM...` in the right action panel.
- Save/delete provider keys in the `Ключи LLM` dialog.
- Keys are stored in system keyring (`keyring` backend), not in DB/files.

Retry/backoff defaults:

- max attempts: `3`
- base delay: `0.25s`
- max delay: `2.0s`
- backoff multiplier: `2.0`

LLM audit payload storage:

- The app writes `llm_calls` for every call status, including `schema_invalid`.
- Raw provider output and validation diagnostics are saved into DB fields
  (`output_text`, `validation_errors`) by default.
- To disable payload persistence, set:
  `PRAKTIKUM_LLM_AUDIT_STORE_OUTPUT=0`.

Schema validation behavior:

- Router validates model output using request schema (`pydantic` model).
- If output is malformed or schema-mismatched, router raises validation error and
  provides a repair-ready prompt payload; no silent partial parsing.

## Course Decomposition Flow (PR#7)

- Выберите курс в блоке `Загруженные курсы`.
- Нажмите `План курса...` в правой панели действий.
- В окне `План курса` нажмите `Сформировать план`:
  - используется task `COURSE_PARSE` через LLM-router;
  - ответ валидируется строго по схеме `CoursePlan v1`;
  - при невалидном JSON запускается bounded repair loop (до 2 repair-попыток).
- Отредактируйте поля курса, таблицу модулей и таблицу дедлайнов (при необходимости).
- Нажмите `Сохранить план` для транзакционного сохранения в SQLite (`modules`, `deadlines`).
- Повторное сохранение идемпотентно: существующий план курса заменяется без дубликатов.

Ограничения PR#7:

- Поддерживается только `CoursePlan v1` (курс/модули/дедлайны).
- Генерация и проверка практики, напоминания и расширенные учебные сценарии ещё не реализованы.
- OCR-движок для сканов PDF не встроен (только подсказка пользователю).

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

## Current Limitations (PR#7)

- OCR engine is not embedded (hint only for scan-like PDFs).
- End-user flow beyond decomposition (practice generation/grading, reminders) is not implemented yet.
- No OCR engine integration.

## Pre-commit

```bash
python -m pre_commit install
python -m pre_commit run --all-files
```
