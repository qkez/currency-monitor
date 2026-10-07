# Currency Monitor

CLI-утилита для мониторинга курсов валют ЦБ РФ. Скачивает данные с открытого API, сохраняет в SQLite, показывает историю и статистику.

## Что умеет

- Скачивать актуальные курсы валют с API ЦБ РФ (cbr-xml-daily.ru)
- Сохранять курсы в локальную SQLite-базу (~/.currency_monitor.db)
- Показывать текущие курсы без сохранения
- Показывать историю по конкретной валюте с динамикой изменения
- Экспортировать всю базу в CSV
- Статистика базы: количество записей, дат, валют

## Стек

- Python 3.10+
- `requests` — HTTP-запросы
- `sqlite3` — база данных (встроен в Python)
- `argparse`, `csv`, `datetime`, `pathlib`

## Установка

```bash
git clone https://github.com/qkez/currency-monitor.git
cd currency-monitor
pip install -r requirements.txt