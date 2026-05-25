# services/payment_service.py

from database.repositories import (
    has_paid_access,
    mark_payment_paid,
)


def is_paid(user_id: int) -> bool:
    return has_paid_access(user_id)


def mark_paid(user_id: int) -> None:
    mark_payment_paid(
        telegram_id=user_id,
        amount=0,
        provider="test",
    )


def payment_text() -> str:
    return (
        "💳 <b>Тестовая оплата</b>\n\n"
        "Сейчас включён тестовый режим.\n"
        "Нажмите «✅ Я оплатил», чтобы открыть PDF и PowerPoint.\n\n"
        "Позже сюда добавим оплату через СПБ, банк или ЮKassa."
    )