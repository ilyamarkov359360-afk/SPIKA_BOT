import os

import psycopg
from dotenv import load_dotenv


load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def get_connection():
    """
    Production connection.
    Railway передаёт DATABASE_URL через Variables.
    """

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL не найден. Добавьте DATABASE_URL в Railway Variables."
        )

    return psycopg.connect(DATABASE_URL)


def _add_column_if_not_exists(
    cursor,
    table_name: str,
    column_name: str,
    column_definition: str,
):
    """
    Безопасно добавляет колонку в существующую таблицу,
    если такой колонки ещё нет.

    table_name, column_name и column_definition задаются только внутри кода,
    пользовательский ввод сюда не попадает.
    """

    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )

    exists = cursor.fetchone()

    if not exists:
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


def init_database():
    """
    Создаёт production-таблицы PostgreSQL.
    SQLite больше не используется.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            _add_column_if_not_exists(cursor, "users", "phone", "TEXT")
            _add_column_if_not_exists(cursor, "users", "email", "TEXT")
            _add_column_if_not_exists(
                cursor,
                "users",
                "registration_completed",
                "BOOLEAN DEFAULT FALSE",
            )
            _add_column_if_not_exists(
                cursor,
                "users",
                "last_activity_at",
                "TIMESTAMP",
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS survey_sessions (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT NOT NULL,
                    current_question INTEGER DEFAULT 0,
                    total_questions INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            _add_column_if_not_exists(
                cursor,
                "survey_sessions",
                "finished_at",
                "TIMESTAMP",
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS answers (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT NOT NULL,
                    question_index INTEGER NOT NULL,
                    block_id TEXT,
                    thinking_type TEXT,
                    question_text TEXT,
                    answer_text TEXT,
                    analysis_text TEXT,
                    score INTEGER DEFAULT 0,
                    presence TEXT DEFAULT 'ЕСТЬ ЧТО ПРОРАЩИВАТЬ',
                    full_analysis_text TEXT,
                    advice_text TEXT,

                    values_analysis_text TEXT,
                    detected_values_text TEXT,
                    detected_desires_text TEXT,
                    detected_importance_text TEXT,
                    contradictions_text TEXT,
                    responsibility_text TEXT,
                    responsibility_shift_text TEXT,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT NOT NULL,
                    report_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            _add_column_if_not_exists(cursor, "reports", "pdf_path", "TEXT")
            _add_column_if_not_exists(cursor, "reports", "ppt_path", "TEXT")
            _add_column_if_not_exists(
                cursor,
                "reports",
                "email_sent",
                "BOOLEAN DEFAULT FALSE",
            )
            _add_column_if_not_exists(cursor, "reports", "sent_at", "TIMESTAMP")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS payments (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    amount INTEGER DEFAULT 0,
                    provider TEXT DEFAULT 'test',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS value_profiles (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT NOT NULL,
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS monitoring_events (
                    id BIGSERIAL PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    telegram_id BIGINT,
                    details TEXT,
                    duration_seconds DOUBLE PRECISION,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Базовые индексы для Telegram-бота
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_users_telegram_id
                ON users (telegram_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sessions_telegram_id_status
                ON survey_sessions (telegram_id, status)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_answers_telegram_id
                ON answers (telegram_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_reports_telegram_id
                ON reports (telegram_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_value_profiles_telegram_id
                ON value_profiles (telegram_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_monitoring_events_type
                ON monitoring_events (event_type)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_monitoring_events_telegram_id
                ON monitoring_events (telegram_id)
                """
            )

            # Индексы для production-версии и поиска Заказчиком
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_users_email
                ON users (email)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_users_phone
                ON users (phone)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_users_username
                ON users (username)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_users_registration_completed
                ON users (registration_completed)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_users_last_activity_at
                ON users (last_activity_at)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sessions_status
                ON survey_sessions (status)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sessions_finished_at
                ON survey_sessions (finished_at)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sessions_updated_at
                ON survey_sessions (updated_at)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_reports_email_sent
                ON reports (email_sent)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_reports_created_at
                ON reports (created_at)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_reports_report_type
                ON reports (report_type)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_answers_question_index
                ON answers (question_index)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_answers_thinking_type
                ON answers (thinking_type)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_answers_presence
                ON answers (presence)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_monitoring_events_created_at
                ON monitoring_events (created_at)
                """
            )

            connection.commit()


if __name__ == "__main__":
    init_database()
    print("DATABASE INITIALIZED")