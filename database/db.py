# database/db.py

import sqlite3
from pathlib import Path


DATABASE_DIR = Path("storage")
DATABASE_PATH = DATABASE_DIR / "database.sqlite3"


def get_connection():
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def init_database():
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS survey_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            current_question INTEGER DEFAULT 0,
            total_questions INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            question_index INTEGER NOT NULL,
            block_id TEXT,
            thinking_type TEXT,
            question_text TEXT,
            answer_text TEXT,
            analysis_text TEXT,
            score INTEGER DEFAULT 0,
            presence TEXT DEFAULT 'НЕТ',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            amount INTEGER DEFAULT 0,
            currency TEXT DEFAULT 'RUB',
            status TEXT DEFAULT 'pending',
            provider TEXT DEFAULT 'test',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            report_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Мягкая миграция: добавляем новые поля для двухуровневого анализа.
    # Если поля уже существуют — ошибка игнорируется.
    try:
        cursor.execute(
            """
            ALTER TABLE answers
            ADD COLUMN full_analysis_text TEXT
            """
        )
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute(
            """
            ALTER TABLE answers
            ADD COLUMN advice_text TEXT
            """
        )
    except sqlite3.OperationalError:
        pass

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS value_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            summary_text TEXT,
            key_values_text TEXT,
            probable_values_text TEXT,
            desires_text TEXT,
            importance_text TEXT,
            contradictions_text TEXT,
            responsibility_text TEXT,
            responsibility_shift_text TEXT,
            value_formula_text TEXT,
            recommendations_text TEXT,
            presentation_summary_text TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Мягкие миграции для версии v2:
    # ценности, желания, важности, противоречия, ответственность.
    # Если колонка уже существует — ошибка игнорируется.

    try:
        cursor.execute(
            """
            ALTER TABLE answers
            ADD COLUMN values_analysis_text TEXT
            """
        )
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute(
            """
            ALTER TABLE answers
            ADD COLUMN detected_values_text TEXT
            """
        )
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute(
            """
            ALTER TABLE answers
            ADD COLUMN detected_desires_text TEXT
            """
        )
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute(
            """
            ALTER TABLE answers
            ADD COLUMN detected_importance_text TEXT
            """
        )
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute(
            """
            ALTER TABLE answers
            ADD COLUMN contradictions_text TEXT
            """
        )
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute(
            """
            ALTER TABLE answers
            ADD COLUMN responsibility_text TEXT
            """
        )
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute(
            """
            ALTER TABLE answers
            ADD COLUMN responsibility_shift_text TEXT
            """
        )
    except sqlite3.OperationalError:
        pass



    connection.commit()
    connection.close()