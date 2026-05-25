import time
from contextlib import contextmanager

from database.db import get_connection


def log_monitoring_event(
    event_type: str,
    telegram_id: int | None = None,
    details: str = "",
    duration_seconds: float | None = None,
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO monitoring_events (
            event_type,
            telegram_id,
            details,
            duration_seconds
        )
        VALUES (%s, %s, %s, %s)
        """,
        (
            event_type,
            telegram_id,
            details,
            duration_seconds,
        ),
    )

    connection.commit()
    cursor.close()
    connection.close()


@contextmanager
def measure_event(
    event_type: str,
    telegram_id: int | None = None,
    details: str = "",
):
    start_time = time.perf_counter()

    try:
        yield
    finally:
        duration = time.perf_counter() - start_time
        log_monitoring_event(
            event_type=event_type,
            telegram_id=telegram_id,
            details=details,
            duration_seconds=duration,
        )


def get_event_count(event_type: str) -> int:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM monitoring_events
        WHERE event_type = %s
        """,
        (event_type,),
    )

    value = cursor.fetchone()[0]
    cursor.close()
    connection.close()

    return int(value or 0)


def get_avg_duration(event_type: str) -> float:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT AVG(duration_seconds)
        FROM monitoring_events
        WHERE event_type = %s
          AND duration_seconds IS NOT NULL
        """,
        (event_type,),
    )

    value = cursor.fetchone()[0]
    cursor.close()
    connection.close()

    return float(value or 0)


def get_max_duration(event_type: str) -> float:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT MAX(duration_seconds)
        FROM monitoring_events
        WHERE event_type = %s
          AND duration_seconds IS NOT NULL
        """,
        (event_type,),
    )

    value = cursor.fetchone()[0]
    cursor.close()
    connection.close()

    return float(value or 0)


def get_p95_duration(event_type: str) -> float:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT percentile_cont(0.95)
        WITHIN GROUP (ORDER BY duration_seconds)
        FROM monitoring_events
        WHERE event_type = %s
          AND duration_seconds IS NOT NULL
        """,
        (event_type,),
    )

    value = cursor.fetchone()[0]
    cursor.close()
    connection.close()

    return float(value or 0)


def _get_count(sql: str, params: tuple = ()) -> int:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(sql, params)
    value = cursor.fetchone()[0]

    cursor.close()
    connection.close()

    return int(value or 0)


def get_monitoring_stats() -> dict:
    return {
        "users_total": _get_count("SELECT COUNT(DISTINCT telegram_id) FROM users"),
        "answers_total": _get_count("SELECT COUNT(*) FROM answers"),

        "surveys_started_total": get_event_count("session_started"),
        "surveys_finished_total": _get_count(
            "SELECT COUNT(*) FROM survey_sessions WHERE status = %s",
            ("finished",),
        ),
        "active_sessions_total": _get_count(
            "SELECT COUNT(*) FROM survey_sessions WHERE status = %s",
            ("active",),
        ),

        "answers_processed_total": get_event_count("answer_processed"),
        "openai_errors_total": get_event_count("openai_error"),

        "pdf_reports_total": _get_count(
            "SELECT COUNT(*) FROM reports WHERE report_type = %s",
            ("pdf",),
        ),
        "pdf_generated_total": get_event_count("pdf_generated"),
        "pdf_errors_total": get_event_count("pdf_error"),

        "ppt_reports_total": _get_count(
            "SELECT COUNT(*) FROM reports WHERE report_type = %s",
            ("ppt",),
        ),
        "ppt_generated_total": get_event_count("ppt_generated"),
        "ppt_errors_total": get_event_count("ppt_error"),

        "payments_confirmed_total": _get_count(
            "SELECT COUNT(*) FROM payments WHERE status = %s",
            ("confirmed",),
        ),

        "value_profiles_total": _get_count("SELECT COUNT(*) FROM value_profiles"),
        "value_profile_generated_total": get_event_count("value_profile_generated"),

        "answer_analysis_seconds_avg": get_avg_duration("answer_analysis"),
        "answer_analysis_seconds_max": get_max_duration("answer_analysis"),
        "answer_analysis_seconds_p95": get_p95_duration("answer_analysis"),

        "pdf_generation_seconds_avg": get_avg_duration("pdf_generation"),
        "pdf_generation_seconds_max": get_max_duration("pdf_generation"),
        "pdf_generation_seconds_p95": get_p95_duration("pdf_generation"),

        "ppt_generation_seconds_avg": get_avg_duration("ppt_generation"),
        "ppt_generation_seconds_max": get_max_duration("ppt_generation"),
        "ppt_generation_seconds_p95": get_p95_duration("ppt_generation"),

        "final_profile_generation_seconds_avg": get_avg_duration("final_profile_generation"),
        "final_profile_generation_seconds_max": get_max_duration("final_profile_generation"),
        "final_profile_generation_seconds_p95": get_p95_duration("final_profile_generation"),
    }