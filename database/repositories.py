from psycopg.rows import dict_row

from database.db import get_connection


# ============================================================
# USERS
# ============================================================

def save_user(
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
):
    """
    Создаёт пользователя или обновляет его Telegram-данные.

    Важно:
    - phone/email/registration_completed не трогаем при повторном /start,
      чтобы не стереть уже сохранённые контакты.
    - last_activity_at обновляем.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (
                    telegram_id,
                    username,
                    first_name,
                    last_name,
                    last_activity_at
                )
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (telegram_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    last_activity_at = CURRENT_TIMESTAMP
                """,
                (
                    telegram_id,
                    username,
                    first_name,
                    last_name,
                ),
            )
            connection.commit()


def get_user_by_telegram_id(telegram_id: int) -> dict | None:
    """
    Получить пользователя по Telegram ID.
    Используется для регистрации, профиля, отчётов и monitoring-сайта.
    """

    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    telegram_id,
                    username,
                    first_name,
                    last_name,
                    phone,
                    email,
                    registration_completed,
                    created_at,
                    last_activity_at
                FROM users
                WHERE telegram_id = %s
                LIMIT 1
                """,
                (telegram_id,),
            )
            return cursor.fetchone()


def update_user_activity(telegram_id: int):
    """
    Обновляет время последней активности пользователя.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET last_activity_at = CURRENT_TIMESTAMP
                WHERE telegram_id = %s
                """,
                (telegram_id,),
            )
            connection.commit()


def update_user_phone(telegram_id: int, phone: str):
    """
    Сохраняет телефон пользователя.
    """

    phone = (phone or "").strip()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET phone = %s,
                    last_activity_at = CURRENT_TIMESTAMP
                WHERE telegram_id = %s
                """,
                (phone, telegram_id),
            )
            connection.commit()


def update_user_email(telegram_id: int, email: str):
    """
    Сохраняет email пользователя.
    """

    email = (email or "").strip().lower()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET email = %s,
                    last_activity_at = CURRENT_TIMESTAMP
                WHERE telegram_id = %s
                """,
                (email, telegram_id),
            )
            connection.commit()


def update_user_contacts(
    telegram_id: int,
    phone: str | None = None,
    email: str | None = None,
):
    """
    Обновляет телефон и/или email пользователя одной функцией.
    Если phone или email не переданы, старое значение сохраняется.
    Если после обновления есть и телефон, и email — регистрация считается завершённой.
    """

    phone_clean = phone.strip() if phone else None
    email_clean = email.strip().lower() if email else None

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET phone = COALESCE(%s, phone),
                    email = COALESCE(%s, email),
                    registration_completed = CASE
                        WHEN COALESCE(%s, phone) IS NOT NULL
                         AND COALESCE(%s, email) IS NOT NULL
                        THEN TRUE
                        ELSE registration_completed
                    END,
                    last_activity_at = CURRENT_TIMESTAMP
                WHERE telegram_id = %s
                """,
                (
                    phone_clean,
                    email_clean,
                    phone_clean,
                    email_clean,
                    telegram_id,
                ),
            )
            connection.commit()


def mark_registration_completed(telegram_id: int):
    """
    Отмечает регистрацию пользователя как завершённую.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET registration_completed = TRUE,
                    last_activity_at = CURRENT_TIMESTAMP
                WHERE telegram_id = %s
                """,
                (telegram_id,),
            )
            connection.commit()


def is_registration_completed(telegram_id: int) -> bool:
    """
    Проверяет, завершена ли регистрация пользователя.
    """

    user = get_user_by_telegram_id(telegram_id)

    if not user:
        return False

    return bool(user.get("registration_completed"))


def get_user_profile_text(telegram_id: int) -> str:
    """
    Возвращает текст профиля пользователя для Telegram.
    """

    user = get_user_by_telegram_id(telegram_id)

    if not user:
        return (
            "👤 Профиль не найден.\n\n"
            "Нажмите /start, чтобы начать работу с ботом."
        )

    username = user.get("username") or "не указан"
    first_name = user.get("first_name") or "не указано"
    last_name = user.get("last_name") or "не указано"
    phone = user.get("phone") or "не указан"
    email = user.get("email") or "не указан"

    registration_completed = (
        "завершена"
        if user.get("registration_completed")
        else "не завершена"
    )

    username_text = f"@{username}" if username != "не указан" else username

    return (
        "👤 Профиль пользователя\n\n"
        f"Telegram ID: {user.get('telegram_id')}\n"
        f"Username: {username_text}\n"
        f"Имя: {first_name}\n"
        f"Фамилия: {last_name}\n"
        f"Телефон: {phone}\n"
        f"Email: {email}\n"
        f"Регистрация: {registration_completed}"
    )


def get_users_for_dashboard(limit: int = 100) -> list[dict]:
    """
    Возвращает список пользователей для monitoring-сайта Заказчика.
    """

    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    telegram_id,
                    username,
                    first_name,
                    last_name,
                    phone,
                    email,
                    registration_completed,
                    created_at,
                    last_activity_at
                FROM users
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return cursor.fetchall()


def find_user_by_email(email: str) -> dict | None:
    """
    Поиск пользователя по email.
    """

    email = (email or "").strip().lower()

    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE LOWER(email) = LOWER(%s)
                LIMIT 1
                """,
                (email,),
            )
            return cursor.fetchone()


def find_user_by_phone(phone: str) -> dict | None:
    """
    Поиск пользователя по телефону.
    """

    phone = (phone or "").strip()

    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE phone = %s
                LIMIT 1
                """,
                (phone,),
            )
            return cursor.fetchone()


def search_users_for_dashboard(query: str, limit: int = 50) -> list[dict]:
    """
    Поиск пользователей для dashboard.
    Ищет по email, телефону, username, имени, фамилии и telegram_id.
    """

    query = (query or "").strip()

    if not query:
        return get_users_for_dashboard(limit=limit)

    search_value = f"%{query.lower()}%"

    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    telegram_id,
                    username,
                    first_name,
                    last_name,
                    phone,
                    email,
                    registration_completed,
                    created_at,
                    last_activity_at
                FROM users
                WHERE LOWER(COALESCE(email, '')) LIKE %s
                   OR LOWER(COALESCE(phone, '')) LIKE %s
                   OR LOWER(COALESCE(username, '')) LIKE %s
                   OR LOWER(COALESCE(first_name, '')) LIKE %s
                   OR LOWER(COALESCE(last_name, '')) LIKE %s
                   OR CAST(telegram_id AS TEXT) LIKE %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (
                    search_value,
                    search_value,
                    search_value,
                    search_value,
                    search_value,
                    search_value,
                    limit,
                ),
            )
            return cursor.fetchall()


# ============================================================
# SURVEY SESSIONS
# ============================================================

def create_or_reset_session(
    telegram_id: int,
    total_questions: int,
):
    """
    Отменяет старую активную сессию и создаёт новую.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
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


def update_session_progress(
    telegram_id: int,
    current_question: int,
    status: str = "active",
):
    """
    Обновляет прогресс текущей сессии.
    Если status='finished', дополнительно заполняет finished_at.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE survey_sessions
                SET current_question = %s,
                    status = %s,
                    updated_at = CURRENT_TIMESTAMP,
                    finished_at = CASE
                        WHEN %s = 'finished' THEN CURRENT_TIMESTAMP
                        ELSE finished_at
                    END
                WHERE telegram_id = %s
                  AND status IN ('active', 'finished')
                """,
                (
                    current_question,
                    status,
                    status,
                    telegram_id,
                ),
            )

            connection.commit()


def get_active_session(telegram_id: int) -> dict | None:
    """
    Возвращает активную сессию пользователя.
    """

    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
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
            return cursor.fetchone()


def get_latest_finished_session(telegram_id: int) -> dict | None:
    """
    Возвращает последнюю завершённую сессию пользователя.
    """

    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
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
            return cursor.fetchone()


def mark_session_finished_by_telegram_id(telegram_id: int):
    """
    Завершает активную сессию пользователя.
    Используется после прохождения всех 43 вопросов.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE survey_sessions
                SET status = 'finished',
                    finished_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = %s
                  AND status = 'active'
                """,
                (telegram_id,),
            )
            connection.commit()


def mark_session_finished(session_id: int):
    """
    Завершает конкретную сессию по ID.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE survey_sessions
                SET status = 'finished',
                    finished_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (session_id,),
            )
            connection.commit()


# ============================================================
# ANSWERS
# ============================================================

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
    Сохраняет ответ пользователя и анализ по вопросу.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
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


def get_latest_answers_as_runtime_data(telegram_id: int) -> tuple[dict, list[dict]]:
    """
    Возвращает данные последнего набора ответов в формате,
    который используют PDF/PPT и итоговая карта.
    """

    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
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

    results = {}
    answers = []

    for row in rows:
        thinking_type = row.get("thinking_type") or ""
        score = row.get("score") or 0
        presence = row.get("presence") or "ЕСТЬ ЧТО ПРОРАЩИВАТЬ"

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


# ============================================================
# REPORTS
# ============================================================

def save_report(
    telegram_id: int,
    report_type: str,
    file_path: str,
):
    """
    Сохраняет запись об отчёте.
    Совместимо со старым кодом.

    report_type:
    - pdf
    - ppt
    - values
    """

    pdf_path = file_path if report_type.lower() == "pdf" else None
    ppt_path = file_path if report_type.lower() in ("ppt", "pptx") else None

    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                INSERT INTO reports (
                    telegram_id,
                    report_type,
                    file_path,
                    pdf_path,
                    ppt_path
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    telegram_id,
                    report_type,
                    file_path,
                    pdf_path,
                    ppt_path,
                ),
            )

            row = cursor.fetchone()
            connection.commit()

            if row:
                return row.get("id")

            return None


def update_report_files(
    report_id: int,
    pdf_path: str | None = None,
    ppt_path: str | None = None,
):
    """
    Сохраняет пути к PDF/PPT файлам отчёта по report_id.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE reports
                SET pdf_path = COALESCE(%s, pdf_path),
                    ppt_path = COALESCE(%s, ppt_path)
                WHERE id = %s
                """,
                (pdf_path, ppt_path, report_id),
            )
            connection.commit()


def update_latest_report_files(
    telegram_id: int,
    pdf_path: str | None = None,
    ppt_path: str | None = None,
):
    """
    Сохраняет пути к PDF/PPT в последний отчёт пользователя.
    Удобно, если в bot.py нет report_id.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE reports
                SET pdf_path = COALESCE(%s, pdf_path),
                    ppt_path = COALESCE(%s, ppt_path)
                WHERE id = (
                    SELECT id
                    FROM reports
                    WHERE telegram_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                """,
                (pdf_path, ppt_path, telegram_id),
            )
            connection.commit()


def mark_report_email_sent(report_id: int):
    """
    Отмечает, что отчёт отправлен на email.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE reports
                SET email_sent = TRUE,
                    sent_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (report_id,),
            )
            connection.commit()


def mark_latest_report_email_sent(telegram_id: int):
    """
    Отмечает, что последний отчёт пользователя отправлен на email.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE reports
                SET email_sent = TRUE,
                    sent_at = CURRENT_TIMESTAMP
                WHERE id = (
                    SELECT id
                    FROM reports
                    WHERE telegram_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                """,
                (telegram_id,),
            )
            connection.commit()


def get_latest_report_for_user(telegram_id: int) -> dict | None:
    """
    Возвращает последний отчёт пользователя.
    """

    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM reports
                WHERE telegram_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (telegram_id,),
            )
            return cursor.fetchone()


def get_latest_report_by_type(
    telegram_id: int,
    report_type: str,
) -> dict | None:
    """
    Возвращает последний отчёт пользователя конкретного типа.
    """

    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM reports
                WHERE telegram_id = %s
                  AND report_type = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (telegram_id, report_type),
            )
            return cursor.fetchone()


def get_reports_for_dashboard(limit: int = 100) -> list[dict]:
    """
    Возвращает отчёты для monitoring-сайта Заказчика.
    """

    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    r.id,
                    r.telegram_id,
                    u.username,
                    u.first_name,
                    u.last_name,
                    u.phone,
                    u.email,
                    r.report_type,
                    r.file_path,
                    r.pdf_path,
                    r.ppt_path,
                    r.email_sent,
                    r.sent_at,
                    r.created_at
                FROM reports r
                LEFT JOIN users u ON u.telegram_id = r.telegram_id
                ORDER BY r.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return cursor.fetchall()


# ============================================================
# PAYMENTS
# Пока оставляем для совместимости.
# В production-меню оплату потом просто скроем через настройки.
# ============================================================

def save_payment(
    telegram_id: int,
    status: str = "confirmed",
    amount: int = 0,
    provider: str = "test",
):
    """
    Сохраняет платеж.
    Пока оставлено для совместимости со старым payment_service.py.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
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


def has_confirmed_payment(telegram_id: int) -> bool:
    """
    Проверяет наличие подтверждённой оплаты.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
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

    return count > 0


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


def mark_payment_paid(
    telegram_id: int,
    amount: int = 0,
    provider: str = "test",
):
    """
    Alias для старого payment_service.py.
    Старый код ожидает функцию mark_payment_paid.
    """

    mark_paid_access(
        telegram_id=telegram_id,
        amount=amount,
        provider=provider,
    )


# ============================================================
# VALUE PROFILES
# ============================================================

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
    Сохраняет итоговый ценностный профиль пользователя.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
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


def get_latest_value_profile(telegram_id: int) -> dict | None:
    """
    Возвращает последний ценностный профиль пользователя.
    """

    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
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

            return cursor.fetchone()


# ============================================================
# STATS FOR MONITORING
# ============================================================

def get_users_total() -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]

    return int(count or 0)


def get_answers_total() -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM answers")
            count = cursor.fetchone()[0]

    return int(count or 0)


def get_finished_surveys_total() -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM survey_sessions
                WHERE status = 'finished'
                """
            )
            count = cursor.fetchone()[0]

    return int(count or 0)


def get_active_sessions_total() -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM survey_sessions
                WHERE status = 'active'
                """
            )
            count = cursor.fetchone()[0]

    return int(count or 0)


def get_reports_total(report_type: str) -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM reports
                WHERE report_type = %s
                """,
                (report_type,),
            )
            count = cursor.fetchone()[0]

    return int(count or 0)


def get_value_profiles_total() -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM value_profiles")
            count = cursor.fetchone()[0]

    return int(count or 0)


def get_registered_users_total() -> int:
    """
    Количество пользователей с завершённой регистрацией.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM users
                WHERE registration_completed = TRUE
                """
            )
            count = cursor.fetchone()[0]

    return int(count or 0)


def get_email_sent_reports_total() -> int:
    """
    Количество отчётов, отправленных на email.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM reports
                WHERE email_sent = TRUE
                """
            )
            count = cursor.fetchone()[0]

    return int(count or 0)