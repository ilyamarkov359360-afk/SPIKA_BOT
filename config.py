import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN не найден в .env")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY не найден в .env")

APP_ENV = os.getenv("APP_ENV", "production").strip().lower()
PAYMENTS_ENABLED = os.getenv("PAYMENTS_ENABLED", "false").strip().lower() == "true"
SHOW_TEST_BUTTONS = os.getenv("SHOW_TEST_BUTTONS", "false").strip().lower() == "true"
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").strip().lower() == "true"
MONITORING_SITE_ENABLED = os.getenv("MONITORING_SITE_ENABLED", "true").strip().lower() == "true"