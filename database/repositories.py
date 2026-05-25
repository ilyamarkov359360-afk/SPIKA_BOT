# database/repositories.py

from database.db import get_connection

def dict_factory(cursor, row):
    result = {}

    for index, column in enumerate(cursor.description):
        result[column[0]] = row[index]

    return result

def save_user(
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
):
    """
    Создаёт или обновляет пользователя.
    """

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
        VALUES (?, ?, ?, ?)
        ON CONFLICT(telegram_id)
        DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            telegram_id,
            username,
            first_name,
            last_name,
        ),
    )

    connection.commit()
    connection.close()


def create_or_reset_session(
    telegram_id: int,
    total_questions: int,
):
    """
    Создаёт новую сессию опроса.
    Старую активную сессию помечает как cancelled.
    Старые ответы пользователя удаляет, чтобы новый опрос был чистым.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE survey_sessions
        SET status = 'cancelled',
            updated_at = CURRENT_TIMESTAMP
        WHERE telegram_id = ?
        AND status = 'active'
        """,
        (telegram_id,),
    )

    cursor.execute(
        """
        DELETE FROM answers
        WHERE telegram_id = ?
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
        VALUES (?, 0, ?, 'active')
        """,
        (
            telegram_id,
            total_questions,
        ),
    )

    connection.commit()
    connection.close()


def update_session_progress(
    telegram_id: int,
    current_question: int,
    status: str = "active",
):
    """
    Обновляет прогресс текущего опроса.
    """

    connection = get_connection()
    cursor = connection.cursor()

    if status == "finished":
        cursor.execute(
            """
            UPDATE survey_sessions
            SET current_question = ?,
                status = ?,
                finished_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE telegram_id = ?
            AND status = 'active'
            """,
            (
                current_question,
                status,
                telegram_id,
            ),
        )
    else:
        cursor.execute(
            """
            UPDATE survey_sessions
            SET current_question = ?,
                status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE telegram_id = ?
            AND status = 'active'
            """,
            (
                current_question,
                status,
                telegram_id,
            ),
        )

    connection.commit()
    connection.close()


def get_active_session(telegram_id: int):
    """
    Возвращает активную сессию пользователя.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM survey_sessions
        WHERE telegram_id = ?
        AND status = 'active'
        ORDER BY id DESC
        LIMIT 1
        """,
        (telegram_id,),
    )

    row = cursor.fetchone()
    connection.close()

    return dict(row) if row else None


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
    """
    Сохраняет ответ пользователя и результат анализа.

    analysis_text = краткий анализ
    full_analysis_text = расширенный анализ
    advice_text = совет

    values_analysis_text = ценностная диагностика
    detected_values_text = выявленные ценности
    detected_desires_text = выявленные желания
    detected_importance_text = выявленные важности
    contradictions_text = возможные противоречия
    responsibility_text = ответственность
    responsibility_shift_text = перекладывание ответственности
    """

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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    connection.close()

def get_user_answers(telegram_id: int) -> list[dict]:
    """
    Возвращает все ответы пользователя.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM answers
        WHERE telegram_id = ?
        ORDER BY question_index ASC
        """,
        (telegram_id,),
    )

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


def mark_payment_paid(
    telegram_id: int,
    amount: int = 0,
    provider: str = "test",
):
    """
    Сохраняет успешную оплату.
    Пока provider='test'.
    Потом сюда можно подключить ЮKassa / CloudPayments / Telegram Payments.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO payments (
            telegram_id,
            amount,
            status,
            provider
        )
        VALUES (?, ?, 'paid', ?)
        """,
        (
            telegram_id,
            amount,
            provider,
        ),
    )

    connection.commit()
    connection.close()


def has_paid_access(telegram_id: int) -> bool:
    """
    Проверяет, есть ли у пользователя оплаченный доступ.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id
        FROM payments
        WHERE telegram_id = ?
        AND status = 'paid'
        ORDER BY id DESC
        LIMIT 1
        """,
        (telegram_id,),
    )

    row = cursor.fetchone()
    connection.close()

    return row is not None


def save_report(
    telegram_id: int,
    report_type: str,
    file_path: str,
):
    """
    Сохраняет информацию о созданном отчёте.
    report_type: pdf / ppt
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO reports (
            telegram_id,
            report_type,
            file_path
        )
        VALUES (?, ?, ?)
        """,
        (
            telegram_id,
            report_type,
            file_path,
        ),
    )

    connection.commit()
    connection.close()


def get_user_reports(telegram_id: int) -> list[dict]:
    """
    Возвращает отчёты пользователя.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM reports
        WHERE telegram_id = ?
        ORDER BY created_at DESC
        """,
        (telegram_id,),
    )

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]

def get_latest_answers_as_runtime_data(telegram_id: int) -> tuple[dict, list[dict]]:
    """
    Возвращает данные ответов в формате, который использует bot.py:
    user_results и user_answers.
    """

    rows = get_user_answers(telegram_id)

    results = {}
    answers = []

    for row in rows:
        thinking_type = row.get("thinking_type")
        score = row.get("score", 0)
        presence = row.get("presence", "НЕТ")

        results[thinking_type] = {
            "score": score,
            "presence": presence,
        }

        answers.append(
            {
                "block_id": row.get("block_id"),
                "type": thinking_type,
                "question": row.get("question_text"),
                "answer": row.get("answer_text"),
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


def get_latest_finished_session(telegram_id: int):
    """
    Возвращает последнюю завершённую сессию пользователя.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM survey_sessions
        WHERE telegram_id = ?
        AND status = 'finished'
        ORDER BY id DESC
        LIMIT 1
        """,
        (telegram_id,),
    )

    row = cursor.fetchone()
    connection.close()

    return dict(row) if row else None

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
    presentation_summary_text: str = "",
):
    """
    Сохраняет итоговую ценностную характеристику пользователя
    после завершения прохождения маршрута.
    """

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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    connection.close()

    def get_latest_value_profile(telegram_id: int) -> dict | None:
        """
        Возвращает последнюю итоговую ценностную характеристику пользователя.
        """

        connection = get_connection()
        connection.row_factory = dict_factory
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM value_profiles
            WHERE telegram_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (telegram_id,),
        )

    profile = cursor.fetchone()

    connection.close()

    return profile

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
    """
    Сохраняет итоговую ценностную характеристику пользователя.
    """

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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    connection.close()


def get_latest_value_profile(telegram_id: int) -> dict | None:
    """
    Возвращает последнюю итоговую ценностную характеристику пользователя.
    """

    connection = get_connection()
    connection.row_factory = dict_factory
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM value_profiles
        WHERE telegram_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (telegram_id,),
    )

    profile = cursor.fetchone()

    connection.close()

    return profile