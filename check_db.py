import sqlite3

conn = sqlite3.connect("storage/database.sqlite3")
cursor = conn.cursor()

print("TABLES:")
for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
    print(row)

print("\nANSWERS COLUMNS:")
for column in cursor.execute("PRAGMA table_info(answers)").fetchall():
    print(column)

print("\nVALUE_PROFILES COLUMNS:")
for column in cursor.execute("PRAGMA table_info(value_profiles)").fetchall():
    print(column)

conn.close()

import sqlite3
from pathlib import Path


DB_PATH = Path("storage/database.sqlite3")


def main():
    if not DB_PATH.exists():
        print("❌ База не найдена:", DB_PATH)
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("✅ База найдена:", DB_PATH)

    print("\n📌 Таблицы:")
    tables = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()

    for table in tables:
        print("-", table[0])

    print("\n📊 Количество записей:")

    for table in ["users", "survey_sessions", "answers", "payments", "reports"]:
        try:
            count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}: {count}")
        except Exception as error:
            print(f"{table}: ошибка — {error}")

    print("\n🧾 Последние ответы:")
    try:
        rows = cursor.execute(
            """
            SELECT question_index, thinking_type, score, presence
            FROM answers
            ORDER BY id DESC
            LIMIT 10
            """
        ).fetchall()

        for row in rows:
            print(row)
    except Exception as error:
        print("answers: ошибка —", error)

    print("\n💳 Платежи:")
    try:
        rows = cursor.execute(
            """
            SELECT telegram_id, status, provider, created_at
            FROM payments
            ORDER BY id DESC
            LIMIT 10
            """
        ).fetchall()

        for row in rows:
            print(row)
    except Exception as error:
        print("payments: ошибка —", error)

    print("\n📄 Отчёты:")
    try:
        rows = cursor.execute(
            """
            SELECT telegram_id, report_type, file_path, created_at
            FROM reports
            ORDER BY id DESC
            LIMIT 10
            """
        ).fetchall()

        for row in rows:
            print(row)
    except Exception as error:
        print("reports: ошибка —", error)

    conn.close()


if __name__ == "__main__":
    main()

import sqlite3

conn = sqlite3.connect("storage/database.sqlite3")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

profile = cursor.execute(
    """
    SELECT
        summary_text,
        key_values_text,
        probable_values_text,
        desires_text,
        importance_text,
        contradictions_text,
        responsibility_text,
        responsibility_shift_text,
        value_formula_text,
        recommendations_text,
        presentation_summary_text
    FROM value_profiles
    ORDER BY id DESC
    LIMIT 1
    """
).fetchone()

if profile:
    print(dict(profile))
else:
    print("Профиль ценностей пока не найден.")

conn.close()