"""Отслеживание позиций товара в выдаче Яндекс Маркета (ПК Chrome + iPhone Safari).

Каждый запуск: для каждого запроса и платформы открывает выдачу в чистом
профиле браузера (как инкогнито), регион Москва, прокручивает до 100 карточек
и дописывает результат в Google Таблицу.
"""
import json
import os
import random
import sys
import time
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

import gspread
from playwright.sync_api import sync_playwright

# ---------- Настройки ----------
QUERIES = ["Вакууматор для продуктов", "Вакуумный упаковщик"]
PRODUCT_ID = "6267248670"          # ID карточки на Маркете (из ссылки /card/.../6267248670)
DEPTH = 100                        # сколько позиций просматривать
REGION_ID = 213                    # Москва
MOSCOW_CENTER = {"latitude": 55.7558, "longitude": 37.6173}
SHEET_ID = os.environ["SHEET_ID"]
SHEET_NAME = "История"
HEADER = [
    "Дата/время (МСК)", "Запрос", "Платформа",
    "Позиция в выдаче", "Реклама в выдаче",
    "Позиция в Premium-карусели",
    "Статус",
]
DASH = "—"

DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)

# JS: карточки в порядке на странице. Premium — рекламная карусель над выдачей.
COLLECT_JS = """
() => [...document.querySelectorAll('[data-zone-name="productSnippet"]')].map(s => {
  const a = s.querySelector('a[href*="/card/"], a[href*="/product"]');
  const href = a ? a.getAttribute('href') : '';
  return {
    href,
    id: href.split('?')[0].split('/').filter(Boolean).pop() || '',
    ad: href.includes('sponsored=1') || !!s.querySelector('[data-auto="sponsored-tag"]'),
    premium: !!s.closest('[data-auto="Premium"]'),
  };
})
"""

# JS: закрыть всплывающее окно входа, прокрутить, нажать «Показать ещё», если есть.
SCROLL_JS = """
(dy) => {
  document.querySelectorAll('[aria-label="Закрыть"]').forEach(b => {
    if (b.getClientRects().length) b.click();
  });
  window.scrollBy(0, dy);
  const more = document.querySelector('[data-auto="infifinityButton"] button, [data-auto="infifinityButton"]');
  if (more && more.getBoundingClientRect().top < window.innerHeight * 2) more.click();
}
"""


def platforms(p):
    iphone = {k: v for k, v in p.devices["iPhone 15 Pro"].items() if k != "default_browser_type"}
    return {
        "ПК (Chrome)": dict(
            browser="chromium",
            context=dict(viewport={"width": 1920, "height": 1080}, user_agent=DESKTOP_UA),
        ),
        # iPhone эмулируется в Chromium (экран, user-agent Safari, тач) — вдвое меньше памяти, чем WebKit
        "iOS (Safari)": dict(browser="chromium", context=dict(**iphone)),
    }


def check(page, query):
    url = f"https://market.yandex.ru/search?text={quote(query)}&lr={REGION_ID}"
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    if "showcaptcha" in page.url or page.locator("form#checkbox-captcha-form, .CheckboxCaptcha").count():
        return None, None, None, 0, "капча"
    try:
        page.wait_for_selector('[data-zone-name="productSnippet"]', timeout=30_000)
    except Exception:
        if "showcaptcha" in page.url:
            return None, None, None, 0, "капча"
        return None, None, None, 0, "выдача не загрузилась"

    grid, premium, seen = [], [], set()
    stale = 0
    deadline = time.time() + 120  # не дольше 2 минут на одну проверку
    while len(grid) < DEPTH and stale < 12 and time.time() < deadline:
        if "showcaptcha" in page.url:
            return None, None, None, len(grid), "капча"
        before = len(grid)
        for c in page.evaluate(COLLECT_JS):
            if c["href"] in seen:
                continue
            seen.add(c["href"])
            (premium if c["premium"] else grid).append(c)
        if any(c["id"] == PRODUCT_ID for c in grid):
            break  # товар найден — дальше листать не нужно
        # если подгрузка застряла — докручиваем до самого низа и ждём дольше
        page.evaluate(SCROLL_JS, 10**6 if stale >= 3 else random.randint(900, 1400))
        page.wait_for_timeout(random.randint(900, 1500) + stale * 500)
        stale = stale + 1 if len(grid) == before else 0

    grid = grid[:DEPTH]
    pos = next((i + 1 for i, c in enumerate(grid) if c["id"] == PRODUCT_ID), None)
    is_ad = grid[pos - 1]["ad"] if pos else None
    prem = next((i + 1 for i, c in enumerate(premium) if c["id"] == PRODUCT_ID), None)
    # «ok», если товар найден или честно просмотрены все DEPTH карточек
    status = "ok" if pos or len(grid) >= DEPTH else f"подгрузилось только {len(grid)} из {DEPTH}"
    return pos, is_ad, prem, len(grid), status


def open_sheet():
    creds = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    sh = gspread.service_account_from_dict(creds).open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(SHEET_NAME, rows=1000, cols=len(HEADER))
    if ws.row_values(1) != HEADER:
        ws.update(range_name="A1", values=[HEADER])
        ws.freeze(rows=1)
    return ws


def main():
    ws = open_sheet()
    now = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y-%m-%d %H:%M")
    rows = []
    with sync_playwright() as p:
        for name, cfg in platforms(p).items():
            browser = getattr(p, cfg["browser"]).launch()
            for query in random.sample(QUERIES, len(QUERIES)):
                # Новый контекст = чистый профиль без cookies (как инкогнито)
                for attempt in range(2):  # при капче/ошибке — одна повторная попытка
                    ctx = browser.new_context(
                        **cfg["context"], locale="ru-RU", timezone_id="Europe/Moscow",
                        geolocation=MOSCOW_CENTER, permissions=["geolocation"],
                    )
                    page = ctx.new_page()
                    try:
                        pos, is_ad, prem, total, status = check(page, query)
                    except Exception as e:  # noqa: BLE001
                        pos, is_ad, prem, total, status = None, None, None, 0, f"ошибка: {e}"[:200]
                    ctx.close()
                    if status == "ok":
                        break
                    time.sleep(random.uniform(20, 40))
                rows.append([
                    now, query, name,
                    pos or DASH,
                    DASH if is_ad is None else ("да" if is_ad else "нет"),
                    prem or DASH,
                    status,
                ])
                print(rows[-1], flush=True)
                time.sleep(random.uniform(5, 15))
            browser.close()
    ws.append_rows(rows, value_input_option="USER_ENTERED")


if __name__ == "__main__":
    sys.exit(main())
