# Позиции товара на Яндекс Маркете → Google Таблица

Раз в час GitHub открывает выдачу Маркета в чистом браузере (как инкогнито), регион — Москва:

- **ПК (Chrome)** — десктопная версия, окно 1920×1080;
- **iOS (Safari)** — мобильная версия, эмуляция iPhone 15 Pro.

Запросы: «Вакууматор для продуктов», «Вакуумный упаковщик». Товар: карточка `6267248670`.
Листает до 100 карточек и останавливается, как только нашёл товар.

Результат дописывается на лист **«История»** таблицы:

| Колонка | Что значит |
|---|---|
| Позиция в выдаче | Фактический номер карточки по счёту в основной выдаче, включая рекламные. «—» — нет в первых 100 |
| Реклама в выдаче | «да», если ваша карточка в этой позиции показана как реклама |
| Позиция в Premium-карусели | Номер в рекламной карусели над выдачей (если вы там есть) |
| Статус | `ok`, `капча`, `подгрузилось только N из 100` или текст ошибки |

---

## Настройка (один раз, ~20 минут)

### 1. Сервисный аккаунт Google (робот, который пишет в таблицу)

1. Откройте https://console.cloud.google.com/ → вверху **Select project → New project** → любое имя → Create.
2. В поиске наверху: **Google Sheets API** → **Enable**.
3. Меню ☰ → **IAM & Admin → Service Accounts → Create service account** → имя `ym-tracker` → Done.
4. Нажмите на созданный аккаунт → вкладка **Keys → Add key → Create new key → JSON**. Скачается файл `.json` — это ключ, никому его не показывайте.
5. Скопируйте e-mail аккаунта (вида `ym-tracker@....iam.gserviceaccount.com`).
6. Откройте вашу таблицу → **Настройки доступа** → добавьте этот e-mail как **Редактор**.

### 2. Репозиторий на GitHub

1. https://github.com/new → имя `ym-position-tracker` → **Public** (у публичных репозиториев GitHub Actions бесплатны без лимита; ключи хранятся в секретах и не видны) → Create.
2. **Add file → Upload files** → перетащите файлы `tracker.py`, `requirements.txt`, `.gitignore`, `README.md` и папку `.github` (в ней `workflows/track.yml`) → Commit.
   > Папку `.github` на Mac не видно в Finder: нажмите `Cmd+Shift+.`, чтобы показать скрытые файлы.
3. **Settings → Secrets and variables → Actions → New repository secret**, два секрета:
   - `SHEET_ID` = `1gHqMbOJPJsHfG-pynwW09spX0mLYpoXMyW0fQW60jFw`
   - `GOOGLE_CREDENTIALS` = всё содержимое скачанного `.json` (откройте в TextEdit, скопируйте целиком).

### 3. Первый запуск

**Actions → «Позиции Яндекс Маркет» → Run workflow**. Через 2–3 минуты в таблице появится лист «История» с 4 строками.
Дальше запуск идёт сам каждый час.

---

## Если с GitHub не получается — перенос на VPS

Серверы GitHub находятся за границей, и Маркет может отвечать им капчей или показывать иную выдачу.
Если в колонке «Статус» часто «капча», переносим тот же скрипт на российский VPS (Ubuntu):

```bash
sudo apt update && sudo apt install -y python3-venv git
git clone https://github.com/<ваш-логин>/ym-position-tracker.git && cd ym-position-tracker
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
sudo .venv/bin/python -m playwright install-deps chromium webkit && .venv/bin/python -m playwright install chromium webkit
# положите ключ в credentials.json рядом со скриптом, затем:
crontab -e
# и добавьте строку:
17 * * * * cd ~/ym-position-tracker && SHEET_ID=1gHqMbOJPJsHfG-pynwW09spX0mLYpoXMyW0fQW60jFw GOOGLE_CREDENTIALS="$(cat credentials.json)" .venv/bin/python tracker.py >> run.log 2>&1
```

## Особенности GitHub Actions

- Запуск по расписанию может опаздывать на 5–30 минут — у GitHub это нормально.
- Если в публичном репозитории 60 дней не было коммитов, GitHub выключает расписание и пишет письмо. Включается одной кнопкой **Enable workflow** во вкладке Actions.

## Изменить настройки

В начале `tracker.py`: `QUERIES` (запросы), `PRODUCT_ID`, `DEPTH` (глубина). Частота — строка `cron` в `.github/workflows/track.yml`.
Проверить парсер у себя на Mac без записи в таблицу: `python test_local.py`.
