import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

from config import (
    EMAIL_ENABLED,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_FROM,
)


def is_email_configured() -> bool:
    """
    Проверяет, настроена ли email-отправка.
    Если EMAIL_ENABLED=false — сервис считается выключенным.
    """

    if not EMAIL_ENABLED:
        return False

    required_values = [
        SMTP_HOST,
        SMTP_PORT,
        SMTP_USER,
        SMTP_PASSWORD,
        SMTP_FROM,
    ]

    return all(bool(value) for value in required_values)


def _guess_mime_type(file_path: str) -> tuple[str, str]:
    """
    Определяет MIME-тип файла для вложения.
    """

    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return "application", "pdf"

    if suffix == ".pptx":
        return (
            "application",
            "vnd.openxmlformats-officedocument.presentationml.presentation",
        )

    if suffix == ".ppt":
        return "application", "vnd.ms-powerpoint"

    return "application", "octet-stream"


def _attach_file(message: EmailMessage, file_path: str):
    """
    Прикрепляет файл к письму.
    """

    if not file_path:
        return

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    maintype, subtype = _guess_mime_type(file_path)

    with open(path, "rb") as file:
        file_data = file.read()

    message.add_attachment(
        file_data,
        maintype=maintype,
        subtype=subtype,
        filename=path.name,
    )


def build_reports_email_body() -> str:
    """
    Текст письма пользователю.
    """

    return (
        "Здравствуйте!\n\n"
        "Вы прошли диагностику SPIKA Thinking Diagnostic.\n\n"
        "Во вложении находятся ваши материалы:\n"
        "- PDF-отчёт\n"
        "- PowerPoint-презентация\n\n"
        "Рекомендуемый следующий шаг:\n"
        "разобрать результаты с экспертом и выбрать 1–2 типа мышления для развития.\n\n"
        "С уважением,\n"
        "Команда SPIKA"
    )


def send_reports_to_email(
    email_to: str,
    pdf_path: str | None = None,
    ppt_path: str | None = None,
) -> bool:
    """
    Отправляет PDF/PPT отчёты пользователю на email.

    Возвращает:
    True  — письмо отправлено
    False — email-сервис не настроен
    """

    email_to = (email_to or "").strip()

    if not email_to:
        raise ValueError("Email получателя не указан")

    if not is_email_configured():
        return False

    if not pdf_path and not ppt_path:
        raise ValueError("Не переданы файлы для отправки")

    message = EmailMessage()

    message["Subject"] = "Ваши отчёты SPIKA Thinking Diagnostic"
    message["From"] = formataddr(("SPIKA Thinking Diagnostic", SMTP_FROM))
    message["To"] = email_to

    message.set_content(build_reports_email_body())

    if pdf_path:
        _attach_file(message, pdf_path)

    if ppt_path:
        _attach_file(message, ppt_path)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(message)

    return True