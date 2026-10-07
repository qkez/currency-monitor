import argparse
import csv
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import requests

API_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
DB_PATH = Path.home() / ".currency-monitor 07.10.db"


# ---------- База данных ----------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            value REAL NOT NULL,
            nominal INTEGER NOT NULL,
            fetched_at TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_date_code
        ON rates (date, code)
    """)
    conn.commit()
    return conn


def save_rates(conn, date_str: str, rates: list[dict]):
    cursor = conn.cursor()
    fetched_at = datetime.now().isoformat()
    saved = 0
    for r in rates:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO rates (date, code, name, value, nominal, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (date_str, r["code"], r["name"], r["value"], r["nominal"], fetched_at))
            saved += cursor.rowcount
        except sqlite3.Error as e:
            print(f"⚠ Ошибка с {r['code']}: {e}")
    conn.commit()
    return saved


# ---------- API ----------

def fetch_rates() -> tuple[str, list[dict]]:
    """Возвращает (дата с API, список валют)."""
    headers = {"User-Agent": "CurrencyMonitor/1.0"}
    try:
        response = requests.get(API_URL, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Не смог получить данные: {e}")
        raise

    data = response.json()
    date_str = data["Date"][:10]  # '2026-10-03T11:30:00+03:00' → '2026-10-03'

    rates = []
    for code, info in data["Valute"].items():
        rates.append({
            "code": code,
            "name": info["Name"],
            "value": float(info["Value"]),
            "nominal": int(info["Nominal"]),
        })
    return date_str, rates


# ---------- Команды ----------

def cmd_fetch(conn):
    date_str, rates = fetch_rates()
    saved = save_rates(conn, date_str, rates)
    print(f"✅ Получено {len(rates)} валют за {date_str}")
    print(f"💾 Новых записей: {saved}")


def cmd_current(conn):
    date_str, rates = fetch_rates()
    print(f"\n📅 Курсы ЦБ РФ на {date_str}\n")
    print(f"{'Код':<5} {'Название':<35} {'Курс':>10}")
    print("-" * 55)
    # Показываем только основные
    main = {"USD", "EUR", "CNY", "GBP", "JPY", "KZT", "BYN", "TRY"}
    for r in sorted(rates, key=lambda x: x["code"]):
        if r["code"] in main:
            per_unit = r["value"] / r["nominal"]
            print(f"{r['code']:<5} {r['name']:<35} {per_unit:>9.2f}₽")


def cmd_history(conn, code: str, days: int):
    code = code.upper()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    cursor = conn.cursor()
    cursor.execute("""
        SELECT date, value, nominal FROM rates
        WHERE code = ? AND date >= ?
        ORDER BY date
    """, (code, since))
    rows = cursor.fetchall()

    if not rows:
        print(f"Нет данных по {code} за {days} дней. Сначала запусти `fetch`.")
        return

    print(f"\n📈 История {code} за {days} дней\n")
    print(f"{'Дата':<12} {'Курс':>10} {'Изм.':>10}")
    print("-" * 35)

    prev = None
    for date, value, nominal in rows:
        per_unit = value / nominal
        if prev is None:
            diff = ""
        else:
            d = per_unit - prev
            sign = "+" if d >= 0 else ""
            diff = f"{sign}{d:.2f}"
        print(f"{date:<12} {per_unit:>9.2f}₽ {diff:>10}")
        prev = per_unit


def cmd_export(conn, output: str):
    output = Path(output).expanduser().resolve()
    cursor = conn.cursor()
    cursor.execute("SELECT date, code, name, value, nominal FROM rates ORDER BY date, code")
    rows = cursor.fetchall()

    if not rows:
        print("Нечего экспортировать.")
        return

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "code", "name", "value", "nominal"])
        writer.writerows(rows)

    print(f"✅ Экспортировано {len(rows)} записей в {output}")


def cmd_stats(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), COUNT(DISTINCT date), COUNT(DISTINCT code) FROM rates")
    total, days, codes = cursor.fetchone()
    print(f"\n📊 Статистика базы\n")
    print(f"Всего записей:    {total}")
    print(f"Уникальных дат:   {days}")
    print(f"Валют отслежено:  {codes}")
    print(f"База:             {DB_PATH}")

    if days > 0:
        cursor.execute("SELECT MIN(date), MAX(date) FROM rates")
        first, last = cursor.fetchone()
        print(f"Период:           {first} → {last}")


# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(
        description="Мониторинг курсов валют ЦБ РФ. Данные в SQLite: ~/.currency-monitor 07.10.db"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("fetch", help="Скачать и сохранить курсы на сегодня")
    sub.add_parser("current", help="Показать текущие курсы (без сохранения)")

    p_hist = sub.add_parser("history", help="История курса валюты")
    p_hist.add_argument("code", help="Код валюты (USD, EUR, CNY, ...)")
    p_hist.add_argument("--days", type=int, default=30, help="Сколько дней назад (по умолчанию 30)")

    p_exp = sub.add_parser("export", help="Экспорт всей базы в CSV")
    p_exp.add_argument("output", help="Путь к CSV")

    sub.add_parser("stats", help="Статистика базы")

    args = parser.parse_args()

    conn = init_db()

    try:
        if args.command == "fetch":
            cmd_fetch(conn)
        elif args.command == "current":
            cmd_current(conn)
        elif args.command == "history":
            cmd_history(conn, args.code, args.days)
        elif args.command == "export":
            cmd_export(conn, args.output)
        elif args.command == "stats":
            cmd_stats(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()