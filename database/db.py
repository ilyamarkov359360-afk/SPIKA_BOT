import os

import psycopg
from dotenv import load_dotenv


load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL", "")


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


def init_database():
    """
    Создаёт production-таблицы PostgreSQL.
    SQLite больше не используется.
    """

    connection = get_connection()
    cursor = connection.cursor()

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
            presence TEXT DEFAULT 'НЕТ',
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

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users (telegram_id)"
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sessions_telegram_id_status
        ON survey_sessions (telegram_id, status)
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_answers_telegram_id ON answers (telegram_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_reports_telegram_id ON reports (telegram_id)"
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

    connection.commit()
    cursor.close()
    connection.close()