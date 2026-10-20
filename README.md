# WHO-ENGINE v0.2 (Windows 11)

Local experimental prototype, not a transfer or proof of identity/WHO.

## Security first
The API key from the original uploads was disclosed in a chat and hard-coded into a script. **Revoke that key in the xAI console, generate a new one and do not send it to ChatGPT.** This release contains no secret keys. `.env` is ignored by git.

## Installation
1. Install Python 3.11 or 3.12 and check **Add Python to PATH**. Windows 11 and macOS supported. Newer Python versions might work but were not tested against all dependencies.
2. Unzip this package to a directory you control.
3. Run `python start.py` in the project directory. On the first run it creates `.venv`, installs dependencies and copies `.env.example` to `.env`; afterwards it only starts the app.
4. Edit `.env` locally: `XAI_API_KEY=<new secret key>`; set an available `XAI_MODEL` according to the xAI Console. `.env` is not a virtual environment: `.venv` is.
5. In a browser open `http://127.0.0.1:8501` if it does not open automatically. Stop the app with Ctrl+C.
6. Optional connection test: `.venv\Scripts\python.exe tests\first_connection_test.py` and type `yes` to approve a paid request.

## Archive
In grok.com account settings, request an account data export; alternatively consult https://accounts.x.ai/data. Download the original ZIP and **preserve it unchanged**. Extract it locally. The interface imports normalized `TXT` with headers `## 00001`, `role:`, `datetime:`, `conversation_id:`, or some JSON export shapes. The xAI export JSON schema varies: if import fails, inspect structure before writing a converter. Do not rename a ZIP to JSON. For very large archives, convert or split them locally while preserving order and source metadata. The supplied parser is best-effort and does not claim support for every xAI export schema.

## Protocol
A: no historical archive, no described operators. B: selected archive. C: same archive + operator description. D: same archive + explicit G3 recipe. These are **external prompt interventions**, not modifications of the model's weights. For fair comparison, match model IDs and test stimuli. Importing a source archive into SQLite never sends it to xAI. Only fragments manually pasted into the experiment text area are sent after approval, up to 8000 characters. Each active run carries its own conversation history.

## Caveats
- No live API calls were made while building this package. SDK requests follow the documented `Client`, `chat.create`, `chat.append` API and read the answer with `chat.stream()`, but availability of model IDs, authentication, billing and Windows dependency installation must be verified locally.
- Do not use public file-sharing links for personal histories.
- The xAI API processes content sent in approved experiment prompts; it is not a purely offline system.
- Compare observations in journal before attributing a specific HOW operator.


## xAI export format (v0.3)
This version supports the verified `conversations[] → {conversation, responses[]} → response` structure with MongoDB `$date/$numberLong` timestamps and sender `human`, `assistant`, `ASSISTANT`. `source_metadata` stores response ID, parent response ID, model and path, besides the searchable text. Attachments and other metadata remain only in the original JSON; do not delete that original. This is a text-only research import, not a lossless archival migration.

Run with `python start.py` (or directly: `.venv/Scripts/python -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501`). Open http://127.0.0.1:8501. Import in `Архив локально`. In `Эксперименты`, create separate A/B/C/D runs; manually paste the exact same archival fragment for B/C/D and an identical question. Do not assume a stored archive is implicitly sent to an API request.


## Структура кода (v0.4)
Логика не изменилась; изменилась её организация.

```
start.py                  локальный запуск одной командой: python start.py
streamlit_app.py          точка входа Streamlit (главный файл для деплоя)
who_engine/
  domain.py               Arm, Role, TurnStatus, Run, Turn, Note — предметные типы
  prompts.py              PromptComposer: группа описана данными, не ветвлениями
  config.py               Settings + источники (.env → окружение → st.secrets)
  errors.py               иерархия ошибок
  providers/              ChatClient/ModelCatalog/AccountInspector (протоколы),
                          XaiProvider, NullProvider, build_provider
  archive/                ArchiveParser (протокол), TXT/JSON парсеры, ArchiveImporter
  storage/                узкие протоколы репозиториев + SqliteRepository
  services.py             ExperimentService, ArchiveService, ObservationService,
                          DiagnosticsService
  ui/                     Page (протокол), PageRouter, пять разделов, SessionStore,
                          корень композиции
tests/                    58 тестов, запуск: python -m unittest discover -s tests -t .
```

Принципы: один модуль — одна причина для изменения (SRP); новая группа,
формат архива или раздел интерфейса добавляются регистрацией, а не правкой
условий (OCP); сервисы зависят от протоколов, а не от SQLite и SDK (DIP);
зависимости собираются только в `who_engine/ui/app.py`.

## Деплой на Streamlit Community Cloud
Автоматического деплоя через библиотеку не существует: Streamlit Community
Cloud разворачивает приложение только из публичного репозитория GitHub через
веб-интерфейс. Локальная папка роли не играет — читается то, что лежит в
репозитории.

1. Закоммитьте и отправьте изменения: главный файл `streamlit_app.py` должен
   присутствовать в ветке на GitHub.
2. На https://share.streamlit.io → **New app** → **Deploy a public app from a
   GitHub repo**: репозиторий `allayunusoglu07/who-engine`, ветка `main`,
   **Main file path** = `streamlit_app.py`.
3. **Advanced settings → Secrets**: вставьте содержимое
   `.streamlit/secrets.toml.example`, подставив действующий ключ. Streamlit
   Cloud пробрасывает эти значения и в переменные окружения, поэтому
   `config.py` читает их без правок.
4. Python version: 3.11 или 3.12.

### Ограничения облачного размещения
- **Приложение публичное.** Любой, у кого есть ссылка, видит интерфейс и может
  отправлять запросы вашим ключом. Для личной переписки это неприемлемо:
  архив импортируйте только в локальной копии.
- **База не сохраняется.** SQLite лежит в `data/` на эфемерной файловой
  системе контейнера и исчезает при перезапуске или обновлении приложения.
  Журнал экспериментов выгружайте кнопкой «Скачать журнал JSON».
- Приложение в облаке — демонстрация интерфейса, а не место хранения
  исследовательских данных.


## Ключ и выбор модели (v0.4)
Ключ можно не держать в `.env`: поле **API ключ xAI** в боковой панели
принимает его на время сессии. Введённый там ключ хранится только в памяти
Streamlit — на диск не пишется, в git не попадает и исчезает при закрытии
вкладки. Приоритет: введённый в интерфейсе → `.env`/секреты → офлайн-режим.

Модель выбирается в боковой панели, а не фиксируется в `.env`. Полный
перечень доступных моделей загружается кнопкой в разделе **Проверка API**
прямо из xAI и подставляется в выбор; пункт «Другая модель…» оставляет
возможность ввести ID вручную. `XAI_MODEL` в `.env` остаётся значением по
умолчанию.

## Раздел «Проверка API»
Три отдельных действия, намеренно разделённых по стоимости:

1. **Проверить ключ** — бесплатно. Подтверждает, что ключ принят, не
   заблокирован и не отключён; показывает скрытое представление ключа и его права.
2. **Загрузить список моделей** — бесплатно. Перечень языковых моделей с
   версией, размером контекста и псевдонимами.
3. **Тестовый запрос** — платный. Одно сообщение выбранной модели, под
   отдельным подтверждением. Нужен, чтобы убедиться в доступе к самой модели,
   а не только к API.

Первые два вызова токенов не расходуют, поэтому проверять связь можно
свободно. Отдельный скрипт `tests/first_connection_test.py` остаётся для
запуска из консоли.

## Удаление эксперимента
В разделе «Эксперименты» под выбранным экспериментом есть свёрнутый блок
**«Удалить эксперимент»**. Он показывает, сколько реплик и наблюдений будет
удалено, требует отдельной отметки подтверждения и только тогда разрешает
удаление. Операция необратима и затрагивает лишь сам эксперимент: импортированный
архив в `source_messages` не трогается. Журнал стоит заранее выгрузить
кнопкой в разделе «Наблюдения и экспорт».

## Тема оформления
Тёмная тема задана в `.streamlit/config.toml` (`[theme] base = "dark"`).
Чтобы вернуть светлую, замените `base` на `"light"` и удалите переопределения
цветов ниже.


## Почему ответ забирается потоком (v0.4)
Унарный `chat.sample()` на рассуждающих моделях оказался нерабочим: модель
обдумывает ответ десятки секунд, соединение всё это время простаивает, и
промежуточное сетевое оборудование разрывает поток — gRPC возвращает
`UNAVAILABLE: Stream removed (End of TCP stream)`. Проверено: `grok-4.6`
стабильно падал через ~7 секунд, тогда как быстрая `grok-4.20-non-reasoning`
отвечала за 0.7 с и проходила.

Поэтому `complete()` читает ответ через `chat.stream()`: фрагменты идут
непрерывно, простоя нет, медленные модели доходят до конца. Запрос при этом
остаётся ровно один — автоповторов по-прежнему нет. В потоковом ответе не
заполняется поле `model`, поэтому записывается запрошенный идентификатор.

Там же исправлен разбор `usage`: объект protobuf не отдаёт поля через
`vars()`, и в журнал вместо счётчиков токенов попадали служебные атрибуты
модуля. Теперь поля перечисляются по дескриптору, и в журнале видны
`prompt_tokens`, `completion_tokens`, `reasoning_tokens` и `cost_in_usd_ticks`.
