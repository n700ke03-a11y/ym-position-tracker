"""Локальная проверка парсера без записи в таблицу: python test_local.py"""
import os, time
os.environ.setdefault("SHEET_ID", "test")
import tracker
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    for name, cfg in tracker.platforms(p).items():
        b = getattr(p, cfg["browser"]).launch()
        for q in tracker.QUERIES:
            ctx = b.new_context(**cfg["context"], locale="ru-RU", timezone_id="Europe/Moscow",
                                geolocation=tracker.MOSCOW_CENTER, permissions=["geolocation"])
            pg = ctx.new_page(); t = time.time()
            try:
                print(name, q, tracker.check(pg, q), f"{time.time()-t:.0f}s", flush=True)
            except Exception as e:
                print(name, q, "ERR", str(e)[:300], flush=True)
            ctx.close(); time.sleep(8)
        b.close()
