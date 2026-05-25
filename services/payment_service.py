from database.repositories import (
    has_paid_access,
    mark_paid_access,
)


def is_paid(telegram_id: int) -> bool:
    """
    Проверяет, открыт ли пользователю платный доступ.
    """

    return has_paid_access(telegram_id)


def mark_paid(telegram_id: int):
    """
    Отмечает пользователя как оплатившего.

    Сейчас используется тестовая оплата через кнопку «Я оплатил».
    Для реальной платёжной системы сюда позже можно добавить:
    - provider
    - amount
    - payment_id
    - проверку webhook
    """

    mark_paid_access(
        telegram_id=telegram_id,
        amount=0,
        provider="test",
    )


def payment_text() -> str:
    """
    Текст блока оплаты.
    """

    return (
        "💳 <b>Оплата доступа к отчётам</b>\n\n"
        "После оплаты открывается доступ к:\n"
        "— PDF-отчёту;\n"
        "— PowerPoint-презентации;\n"
        "— полной карте результата;\n"
        "— итоговой ценностной характеристике.\n\n"
        "Сейчас включён тестовый режим оплаты.\n\n"
        "Нажмите кнопку «✅ Я оплатил», чтобы открыть доступ."
    )