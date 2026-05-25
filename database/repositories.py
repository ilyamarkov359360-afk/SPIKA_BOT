from psycopg.rows import dict_row

from database.db import get_connection


def save_user(
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO users (
            telegram_id,
            username,
            first_name,
            last_name
        )
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (telegram_id)
        DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name
        """,
        (
            telegram_id,
            username,
            first_name,
            last_name,
        ),
    )

    connection.commit()
    cursor.close()
    connection.close()


def create_or_reset_session(
    telegram_id: int,
    total_questions: int,
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE survey_sessions
        SET status = 'cancelled',
            updated_at = CURRENT_TIMESTAMP
        WHERE telegram_id = %s
          AND status = 'active'
        """,
        (telegram_id,),
    )

    cursor.execute(
        """
        INSERT INTO survey_sessions (
            telegram_id,
            current_question,
            total_questions,
            status
        )
        VALUES (%s, %s, %s, %s)
        """,
        (
            telegram_id,
            0,
            total_questions,
            "active",
        ),
    )

    connection.commit()
    cursor.close()
    connection.close()


def update_session_progress(
    telegram_id: int,
    current_question: int,
    status: str = "active",
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE survey_sessions
        SET current_question = %s,
            status = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE telegram_id = %s
          AND status IN ('active', 'finished')
        """,
        (
            current_question,
            status,
            telegram_id,
        ),
    )

    connection.commit()
    cursor.close()
    connection.close()


def get_active_session(telegram_id: int) -> dict | None:
    connection = get_connection()
    cursor = connection.cursor(row_factory=dict_row)

    cursor.execute(
        """
        SELECT *
        FROM survey_sessions
        WHERE telegram_id = %s
          AND status = 'active'
        ORDER BY id DESC
        LIMIT 1
        """,
        (telegram_id,),
    )

    session = cursor.fetchone()

    cursor.close()
    connection.close()

    return session


def get_latest_finished_session(telegram_id: int) -> dict | None:
    connection = get_connection()
    cursor = connection.cursor(row_factory=dict_row)

    cursor.execute(
        """
        SELECT *
        FROM survey_sessions
        WHERE telegram_id = %s
          AND status = 'finished'
        ORDER BY id DESC
        LIMIT 1
        """,
        (telegram_id,),
    )

    session = cursor.fetchone()

    cursor.close()
    connection.close()

    return session


def save_answer(
    telegram_id: int,
    question_index: int,
    block_id: str,
    thinking_type: str,
    question_text: str,
    answer_text: str,
    analysis_text: str,
    score: int,
    presence: str,
    full_analysis_text: str = "",
    advice_text: str = "",
    values_analysis_text: str = "",
    detected_values_text: str = "",
    detected_desires_text: str = "",
    detected_importance_text: str = "",
    contradictions_text: str = "",
    responsibility_text: str = "",
    responsibility_shift_text: str = "",
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO answers (
            telegram_id,
            question_index,
            block_id,
            thinking_type,
            question_text,
            answer_text,
            analysis_text,
            score,
            presence,
            full_analysis_text,
            advice_text,
            values_analysis_text,
            detected_values_text,
            detected_desires_text,
            detected_importance_text,
            contradictions_text,
            responsibility_text,
            responsibility_shift_text
        )
        VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s
        )
        """,
        (
            telegram_id,
            question_index,
            block_id,
            thinking_type,
            question_text,
            answer_text,
            analysis_text,
            score,
            presence,
            full_analysis_text,
            advice_text,
            values_analysis_text,
            detected_values_text,
            detected_desires_text,
            detected_importance_text,
            contradictions_text,
            responsibility_text,
            responsibility_shift_text,
        ),
    )

    connection.commit()
    cursor.close()
    connection.close()


def save_report(
    telegram_id: int,
    report_type: str,
    file_path: str,
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO reports (
            telegram_id,
            report_type,
            file_path
        )
        VALUES (%s, %s, %s)
        """,
        (
            telegram_id,
            report_type,
            file_path,
        ),
    )

    connection.commit()
    cursor.close()
    connection.close()


def save_payment(
    telegram_id: int,
    status: str = "confirmed",
    amount: int = 0,
    provider: str = "test",
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO payments (
            telegram_id,
            status,
            amount,
            provider
        )
        VALUES (%s, %s, %s, %s)
        """,
        (
            telegram_id,
            status,
            amount,
            provider,
        ),
    )

    connection.commit()
    cursor.close()
    connection.close()


def has_confirmed_payment(telegram_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM payments
        WHERE telegram_id = %s
          AND status = 'confirmed'
        """,
        (telegram_id,),
    )

    count = cursor.fetchone()[0]

    cursor.close()
    connection.close()

    return count > 0


def get_latest_answers_as_runtime_data(telegram_id: int) -> tuple[dict, list[dict]]:
    connection = get_connection()
    cursor = connection.cursor(row_factory=dict_row)

    cursor.execute(
        """
        SELECT *
        FROM answers
        WHERE telegram_id = %s
        ORDER BY question_index ASC, id ASC
        """,
        (telegram_id,),
    )

    rows = cursor.fetchall()

    cursor.close()
    connection.close()

    results = {}
    answers = []

    for row in rows:
        thinking_type = row.get("thinking_type") or ""
        score = row.get("score") or 0
        presence = row.get("presence") or "НЕТ"

        if thinking_type:
            results[thinking_type] = {
                "score": score,
                "presence": presence,
            }

        answers.append(
            {
                "block_id": row.get("block_id") or "",
                "type": thinking_type,
                "question": row.get("question_text") or "",
                "answer": row.get("answer_text") or "",
                "analysis": row.get("analysis_text") or "",
                "full_analysis": row.get("full_analysis_text") or "",
                "advice": row.get("advice_text") or "",
                "values_analysis": row.get("values_analysis_text") or "",
                "detected_values": row.get("detected_values_text") or "",
                "detected_desires": row.get("detected_desires_text") or "",
                "detected_importance": row.get("detected_importance_text") or "",
                "contradictions": row.get("contradictions_text") or "",
                "responsibility": row.get("responsibility_text") or "",
                "responsibility_shift": row.get("responsibility_shift_text") or "",
                "score": score,
                "presence": presence,
            }
        )

    return results, answers


def save_value_profile(
    telegram_id: int,
    summary_text: str = "",
    key_values_text: str = "",
    probable_values_text: str = "",
    desires_text: str = "",
    importance_text: str = "",
    contradictions_text: str = "",
    responsibility_text: str = "",
    responsibility_shift_text: str = "",
    value_formula_text: str = "",
    recommendations_text: str = "",
    presentation_summary_text: str = "",
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO value_profiles (
            telegram_id,
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
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            telegram_id,
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
            presentation_summary_text,
        ),
    )

    connection.commit()
    cursor.close()
    connection.close()


def get_latest_value_profile(telegram_id: int) -> dict | None:
    connection = get_connection()
    cursor = connection.cursor(row_factory=dict_row)

    cursor.execute(
        """
        SELECT *
        FROM value_profiles
        WHERE telegram_id = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (telegram_id,),
    )

    profile = cursor.fetchone()

    cursor.close()
    connection.close()

    return profile


def get_users_total() -> int:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM users
        """
    )

    count = cursor.fetchone()[0]

    cursor.close()
    connection.close()

    return int(count or 0)


def get_answers_total() -> int:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM answers
        """
    )

    count = cursor.fetchone()[0]

    cursor.close()
    connection.close()

    return int(count or 0)


def get_finished_surveys_total() -> int:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM survey_sessions
        WHERE status = 'finished'
        """
    )

    count = cursor.fetchone()[0]

    cursor.close()
    connection.close()

    return int(count or 0)


def get_active_sessions_total() -> int:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM survey_sessions
        WHERE status = 'active'
        """
    )

    count = cursor.fetchone()[0]

    cursor.close()
    connection.close()

    return int(count or 0)


def get_reports_total(report_type: str) -> int:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM reports
        WHERE report_type = %s
        """,
        (report_type,),
    )

    count = cursor.fetchone()[0]

    cursor.close()
    connection.close()

    return int(count or 0)


def get_value_profiles_total() -> int:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM value_profiles
        """
    )

    count = cursor.fetchone()[0]

    cursor.close()
    connection.close()

    return int(count or 0)

def has_paid_access(telegram_id: int) -> bool:
    """
    Проверяет, есть ли у пользователя оплаченный доступ.
    Совместимость со старым payment_service.py.
    """

    return has_confirmed_payment(telegram_id)


def mark_paid_access(
    telegram_id: int,
    amount: int = 0,
    provider: str = "test",
):
    """
    Отмечает пользователя как оплатившего.
    Совместимость со старым payment_service.py.
    """

    save_payment(
        telegram_id=telegram_id,
        status="confirmed",
        amount=amount,
        provider=provider,
    )