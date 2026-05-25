import asyncio
import os
import re

from database.db import init_database
from database.repositories import (
    save_user,
    create_or_reset_session,
    update_session_progress,
    save_answer,
    save_report,
    get_active_session,
    get_latest_finished_session,
    get_latest_answers_as_runtime_data,
    save_value_profile,
    get_latest_value_profile,
)

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    FSInputFile,
)
from aiogram.filters import CommandStart, Command

from config import TELEGRAM_TOKEN
from data.questions import QUESTIONS
from data.blocks import BLOCKS
from services.openai_service import (
    analyze_answer,
    ask_consultant,
    transcribe_audio,
    build_final_values_profile,
)
from services.payment_service import is_paid, mark_paid, payment_text
from services.pdf_service import build_pdf_report
from services.ppt_service import build_ppt_report


bot = Bot(
    token=TELEGRAM_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()


user_state = {}
user_results = {}
user_answers = {}
user_mode = {}

def load_user_runtime_data_if_needed(user_id: int) -> bool:
    """
    Подгружает результаты и ответы пользователя из SQLite,
    если после перезапуска бота данные отсутствуют в памяти.
    """

    if user_results.get(user_id) and user_answers.get(user_id):
        return True

    results, answers = get_latest_answers_as_runtime_data(user_id)

    if not results and not answers:
        return False

    user_results[user_id] = results
    user_answers[user_id] = answers
    user_state[user_id] = len(answers)

    return True

def extract_section(text: str, start_marker: str, end_markers: list[str]) -> str:
    if not text:
        return ""

    start_index = text.find(start_marker)

    if start_index == -1:
        return ""

    start_index += len(start_marker)
    end_index = len(text)

    for marker in end_markers:
        marker_index = text.find(marker, start_index)
        if marker_index != -1:
            end_index = min(end_index, marker_index)

    return text[start_index:end_index].strip()

def parse_final_values_profile(text: str) -> dict:
    summary_text = extract_section(
        text,
        "Итоговая ценностная характеристика:",
        [
            "Ведущие ценности:",
            "Вероятные ценности:",
            "Желания и цели:",
            "Важности:",
            "Противоречия:",
            "Ответственность:",
            "Перекладывание ответственности:",
            "Ценностная формула:",
            "Краткий вывод для презентации:",
        ],
    )

    key_values_text = extract_section(
        text,
        "Ведущие ценности:",
        [
            "Вероятные ценности:",
            "Желания и цели:",
            "Важности:",
            "Противоречия:",
            "Ответственность:",
            "Перекладывание ответственности:",
            "Ценностная формула:",
            "Краткий вывод для презентации:",
        ],
    )

    probable_values_text = extract_section(
        text,
        "Вероятные ценности:",
        [
            "Желания и цели:",
            "Важности:",
            "Противоречия:",
            "Ответственность:",
            "Перекладывание ответственности:",
            "Ценностная формула:",
            "Краткий вывод для презентации:",
        ],
    )

    desires_text = extract_section(
        text,
        "Желания и цели:",
        [
            "Важности:",
            "Противоречия:",
            "Ответственность:",
            "Перекладывание ответственности:",
            "Ценностная формула:",
            "Краткий вывод для презентации:",
        ],
    )

    importance_text = extract_section(
        text,
        "Важности:",
        [
            "Противоречия:",
            "Ответственность:",
            "Перекладывание ответственности:",
            "Ценностная формула:",
            "Краткий вывод для презентации:",
        ],
    )

    contradictions_text = extract_section(
        text,
        "Противоречия:",
        [
            "Ответственность:",
            "Перекладывание ответственности:",
            "Ценностная формула:",
            "Краткий вывод для презентации:",
        ],
    )

    responsibility_text = extract_section(
        text,
        "Ответственность:",
        [
            "Перекладывание ответственности:",
            "Ценностная формула:",
            "Краткий вывод для презентации:",
        ],
    )

    responsibility_shift_text = extract_section(
        text,
        "Перекладывание ответственности:",
        [
            "Ценностная формула:",
            "Краткий вывод для презентации:",
        ],
    )

    value_formula_text = extract_section(
        text,
        "Ценностная формула:",
        [
            "Краткий вывод для презентации:",
        ],
    )

    presentation_summary_text = extract_section(
        text,
        "Краткий вывод для презентации:",
        [],
    )

    return {
        "summary_text": summary_text or "Итоговая ценностная характеристика не сформирована.",
        "key_values_text": key_values_text or "явно не выделены",
        "probable_values_text": probable_values_text or "явно не выделены",
        "desires_text": desires_text or "явно не выявлены",
        "importance_text": importance_text or "явно не выявлены",
        "contradictions_text": contradictions_text or "данных недостаточно",
        "responsibility_text": responsibility_text or "данных недостаточно",
        "responsibility_shift_text": responsibility_shift_text or "явно не выявлено",
        "value_formula_text": value_formula_text or "Ценностная формула не сформирована.",
        "presentation_summary_text": presentation_summary_text or "Краткий вывод не сформирован.",
        "raw_profile_text": text,
    }

def generate_and_save_value_profile(user_id: int) -> dict:
    answers = user_answers.get(user_id, [])

    if not answers:
        loaded = load_user_runtime_data_if_needed(user_id)
        if loaded:
            answers = user_answers.get(user_id, [])

    raw_profile = build_final_values_profile(answers)
    parsed_profile = parse_final_values_profile(raw_profile)

    save_value_profile(
        telegram_id=user_id,
        summary_text=parsed_profile["summary_text"],
        key_values_text=parsed_profile["key_values_text"],
        probable_values_text=parsed_profile["probable_values_text"],
        desires_text=parsed_profile["desires_text"],
        importance_text=parsed_profile["importance_text"],
        contradictions_text=parsed_profile["contradictions_text"],
        responsibility_text=parsed_profile["responsibility_text"],
        responsibility_shift_text=parsed_profile["responsibility_shift_text"],
        value_formula_text=parsed_profile["value_formula_text"],
        presentation_summary_text=parsed_profile["presentation_summary_text"],
    )

    return parsed_profile

def parse_analysis(text: str) -> dict:
    score = 0
    presence = "НЕТ"

    score_match = re.search(r"Оценка:\s*([0-9]+)", text)
    result_match = re.search(r"Результат:\s*(ЕСТЬ|НЕТ)", text, re.IGNORECASE)

    if score_match:
        score = max(0, min(10, int(score_match.group(1))))

    if result_match:
        presence = result_match.group(1).upper()

    presence = "ЕСТЬ" if score >= 8 else "НЕТ"

    short_analysis = extract_section(
        text,
        "Краткий анализ:",
        ["Расширенный анализ:", "Ценностная диагностика:", "Совет:"],
    )

    full_analysis = extract_section(
        text,
        "Расширенный анализ:",
        ["Ценностная диагностика:", "Выявленные ценности:", "Совет:"],
    )

    values_analysis = extract_section(
        text,
        "Ценностная диагностика:",
        [
            "Выявленные ценности:",
            "Выявленные желания:",
            "Выявленные важности:",
            "Возможные противоречия:",
            "Ответственность:",
            "Перекладывание ответственности:",
            "Совет:",
        ],
    )

    detected_values = extract_section(
        text,
        "Выявленные ценности:",
        [
            "Выявленные желания:",
            "Выявленные важности:",
            "Возможные противоречия:",
            "Ответственность:",
            "Перекладывание ответственности:",
            "Совет:",
        ],
    )

    detected_desires = extract_section(
        text,
        "Выявленные желания:",
        [
            "Выявленные важности:",
            "Возможные противоречия:",
            "Ответственность:",
            "Перекладывание ответственности:",
            "Совет:",
        ],
    )

    detected_importance = extract_section(
        text,
        "Выявленные важности:",
        [
            "Возможные противоречия:",
            "Ответственность:",
            "Перекладывание ответственности:",
            "Совет:",
        ],
    )

    contradictions = extract_section(
        text,
        "Возможные противоречия:",
        [
            "Ответственность:",
            "Перекладывание ответственности:",
            "Совет:",
        ],
    )

    responsibility = extract_section(
        text,
        "Ответственность:",
        [
            "Перекладывание ответственности:",
            "Совет:",
        ],
    )

    responsibility_shift = extract_section(
        text,
        "Перекладывание ответственности:",
        [
            "Совет:",
        ],
    )

    advice = extract_section(
        text,
        "Совет:",
        [],
    )

    if not short_analysis:
        short_analysis = "Краткий анализ не сформирован."

    if not full_analysis:
        full_analysis = "Расширенный анализ не сформирован."

    if not values_analysis:
        values_analysis = "Ценностная диагностика не сформирована."

    if not detected_values:
        detected_values = "явно не выявлены"

    if not detected_desires:
        detected_desires = "явно не выявлены"

    if not detected_importance:
        detected_importance = "явно не выявлены"

    if not contradictions:
        contradictions = "явных противоречий не видно или данных недостаточно"

    if not responsibility:
        responsibility = "данных недостаточно"

    if not responsibility_shift:
        responsibility_shift = "явно не выявлено"

    if not advice:
        advice = "Совет не сформирован."

    return {
        "score": score,
        "presence": presence,
        "short_analysis": short_analysis,
        "full_analysis": full_analysis,
        "values_analysis": values_analysis,
        "detected_values": detected_values,
        "detected_desires": detected_desires,
        "detected_importance": detected_importance,
        "contradictions": contradictions,
        "responsibility": responsibility,
        "responsibility_shift": responsibility_shift,
        "advice": advice,
        "raw_analysis": text,
    }

def build_telegram_analysis_text(parsed: dict) -> str:
    return (
        "🧭 <b>Краткий разбор</b>\n\n"
        f"<b>Оценка:</b> {parsed.get('score', 0)}/10\n"
        f"<b>Результат:</b> {parsed.get('presence', 'НЕТ')}\n\n"
        f"<b>Что видно по ответу:</b>\n"
        f"{parsed.get('short_analysis', 'Краткий анализ не сформирован.')}\n\n"
        f"<b>Ориентир дальше:</b>\n"
        f"{parsed.get('advice', 'Совет не сформирован.')}"
    )

def build_value_profile_ready_text(profile: dict) -> str:
    return (
        "🧭 <b>Ценностная карта собрана.</b>\n\n"
        "Система объединила сигналы из ответов и подготовила итоговую ценностную характеристику.\n\n"
        f"<b>Ценностная формула:</b>\n"
        f"{profile.get('value_formula_text', 'Ценностная формула не сформирована.')}\n\n"
        "Полный разбор ценностей, желаний, важностей, ответственности и возможных противоречий "
        "будет доступен в PDF и PowerPoint."
    )

def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🚗 Начать маршрут"),
            ],
            [
                KeyboardButton(text="❓ Подсказки маршрута"),
                KeyboardButton(text="🧭 Помощник маршрута"),
            ],
        ],
        resize_keyboard=True,
    )


def result_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🗺 Карта результата"),
            ],
            [
                KeyboardButton(text="📄 PDF-отчёт"),
                KeyboardButton(text="📽 Презентация PPT"),
            ],
            [
                KeyboardButton(text="💳 Оплатить"),
            ],
            [
                KeyboardButton(text="🚗 Начать маршрут"),
            ],
        ],
        resize_keyboard=True,
    )

def resume_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="▶️ Продолжить маршрут",
                    callback_data="resume_survey",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔁 Начать маршрут заново",
                    callback_data="restart_survey",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗺 Карта результата",
                    callback_data="short_result",
                )
            ],
        ]
    )

def payment_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Я оплатил",
                    callback_data="payment_confirmed",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад к карте результата",
                    callback_data="short_result",
                )
            ],
        ]
    )


def continue_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➡️ Следующий вопрос"),
            ],
            [
                KeyboardButton(text="❓ Подсказки маршрута"),
                KeyboardButton(text="🧭 Помощник маршрута"),
            ],
        ],
        resize_keyboard=True,
    )


async def send_block_description(message: Message, block_id: str):
    block = BLOCKS[block_id]

    await message.answer(
        f"{block['label']}\n\n"
        f"<b>{block['title']}</b>\n\n"
        f"<i>{block.get('scene', '')}</i>\n\n"
        f"{block['description']}\n\n"
        f"🧭 <b>Ориентир маршрута:</b>\n"
        f"{block.get('route_hint', '')}"
    )


async def send_question(message: Message, user_id: int):
    idx = user_state.get(user_id, 0)

    if idx >= len(QUESTIONS):
        await send_final_message(message, user_id)
        return

    user_mode[user_id] = "survey"

    question = QUESTIONS[idx]
    block_id = question["block_id"]

    if idx == 0 or QUESTIONS[idx - 1]["block_id"] != block_id:
        await send_block_description(message, block_id)

    await message.answer(
        f"{question.get('block', BLOCKS[block_id]['label'])}\n\n"
        f"<b>Вопрос {idx + 1}/{len(QUESTIONS)}</b>\n\n"
        f"{question['q']}\n\n"
        f"<i>Совет: {question['hint']}</i>"
    )


async def send_final_message(message: Message, user_id: int):
    await message.answer(
        "🏁 <b>Опрос завершён.</b>\n\n"
        "Ты прошёл маршрут по Городу Мышления. "
        "Теперь можно посмотреть короткий результат или получить расширенный PDF/PPT.",
        reply_markup=result_keyboard(),
    )


def build_short_result_text(user_id: int) -> str:
    results = user_results.get(user_id, {})

    if not results:
        return (
            "🗺 <b>Карта результата</b>\n\n"
            "Результатов пока нет. Пройдите маршрут или используйте /test."
        )

    total_checked = len(results)
    found_count = sum(
        1 for value in results.values()
        if value.get("presence") == "ЕСТЬ"
    )
    missing_count = total_checked - found_count

    text = (
        "🗺 <b>КАРТА РЕЗУЛЬТАТА</b>\n\n"
        f"Всего проверено типов мышления: <b>{total_checked}</b>\n"
        f"Найдено типов мышления: <b>{found_count}</b>\n"
        f"Зоны развития: <b>{missing_count}</b>\n\n"
    )

    for block_id, block_data in BLOCKS.items():
        block_lines = []

        for question in QUESTIONS:
            if question["block_id"] != block_id:
                continue

            type_name = question["type"]
            data = results.get(type_name)

            if not data:
                continue

            presence = data.get("presence", "НЕТ")
            score = data.get("score", 0)
            marker = "✅" if presence == "ЕСТЬ" else "⬜"

            block_lines.append(f"{marker} {type_name} — {score}/10")

        if block_lines:
            text += (
                f"{block_data['label']}\n"
                f"<b>{block_data['title']}</b>\n"
            )
            text += "\n".join(block_lines)
            text += "\n\n"

    text += (
        "🚗 <b>Итог маршрута:</b>\n"
        "Это краткая карта результата. Полный разбор доступен в PDF и PowerPoint."
    )

    return text


@dp.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id

    save_user(
        telegram_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )

    active_session = get_active_session(user_id)
    finished_session = get_latest_finished_session(user_id)

    greeting_text = (
    "<b>🚗 Добро пожаловать в Город Мышления.</b>\n\n"
    "Это не обычный тест, а маршрут по разным районам твоего мышления.\n\n"
    "Сначала ты посмотришь на карту целей и мотивации, затем проедешь по улицам настоящего, "
    "остановишься у зданий прошлого опыта, выедешь на дорогу будущего, встретишь людей, "
    "зайдёшь в рабочее пространство проектов и попадёшь в необычный район нестандартных решений.\n\n"
    "На каждом этапе ты отвечаешь на вопросы, а AI даёт краткий анализ и совет. "
    "В конце маршрута ты получишь PDF и PowerPoint-отчёт с полной диагностикой.\n\n"
    "Нажми «🚗 Начать маршрут», чтобы выехать на первую улицу."
)

    await message.answer(
        greeting_text,
        reply_markup=main_keyboard(),
    )

    if active_session:
        current_question = active_session.get("current_question", 0)
        total_questions = active_session.get("total_questions", len(QUESTIONS))

        await message.answer(
            "🚗 <b>У тебя есть незавершённый маршрут.</b>\n\n"
            f"Пройдено вопросов: <b>{current_question}</b> из <b>{total_questions}</b>.\n"
            f"Следующий вопрос: <b>{current_question + 1}</b> из <b>{total_questions}</b>.\n\n"
            "Можно продолжить с места остановки или начать заново.",
            reply_markup=resume_keyboard(),
        )
        return

    if finished_session:
        await message.answer(
            "🏁 <b>У тебя уже есть завершённый результат.</b>\n\n"
            "Можно посмотреть короткий результат, получить PDF/PPT или начать опрос заново.",
            reply_markup=result_keyboard(),
        )
        return

    await message.answer(
    "Нажми «🚗 Начать маршрут», чтобы начать движение по Городу Мышления.",
    )

@dp.callback_query(F.data == "resume_survey")
async def resume_survey(call: CallbackQuery):
    user_id = call.from_user.id

    active_session = get_active_session(user_id)

    if not active_session:
        await call.message.answer(
            "Активный опрос не найден. Можно начать новый маршрут.",
            reply_markup=main_keyboard(),
        )
        await call.answer()
        return

    current_question = active_session.get("current_question", 0)

    if current_question >= len(QUESTIONS):
        user_state[user_id] = len(QUESTIONS)

        results, answers = get_latest_answers_as_runtime_data(user_id)
        user_results[user_id] = results
        user_answers[user_id] = answers

        await send_final_message(call.message, user_id)
        await call.answer()
        return

    results, answers = get_latest_answers_as_runtime_data(user_id)

    user_state[user_id] = current_question
    user_results[user_id] = results
    user_answers[user_id] = answers
    user_mode[user_id] = "survey"

    await call.message.answer(
        "▶️ Продолжаем маршрут с места остановки."
    )

    await send_question(call.message, user_id)
    await call.answer()

@dp.callback_query(F.data == "restart_survey")
async def restart_survey(call: CallbackQuery):
    user_id = call.from_user.id

    save_user(
        telegram_id=user_id,
        username=call.from_user.username,
        first_name=call.from_user.first_name,
        last_name=call.from_user.last_name,
    )

    create_or_reset_session(
        telegram_id=user_id,
        total_questions=len(QUESTIONS),
    )

    user_state[user_id] = 0
    user_results[user_id] = {}
    user_answers[user_id] = []
    user_mode[user_id] = "survey"

    await call.message.answer(
        "🔁 Начинаем маршрут заново. Поехали!"
    )

    await send_question(call.message, user_id)
    await call.answer()

@dp.message(Command("test"))
async def test(message: Message):
    user_id = message.from_user.id

    save_user(
        telegram_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )

    create_or_reset_session(
        telegram_id=user_id,
        total_questions=len(QUESTIONS),
    )

    user_state[user_id] = len(QUESTIONS)
    user_results[user_id] = {}
    user_answers[user_id] = []

    missing_types = {
        "Мышление масштаба",
        "Инвестиционно-доходное мышление",
        "Парадоксальное мышление",
        "Командное мышление",
        "Гениальное мышление",
        "Квантовое мышление",
    }

    for index, q in enumerate(QUESTIONS, start=1):
        presence = "НЕТ" if q["type"] in missing_types else "ЕСТЬ"
        score = 4 if presence == "НЕТ" else 9

        answer_text = (
            f"Тестовый ответ пользователя на вопрос {index}. "
            f"Пользователь описывает свой опыт, логику, примеры, выводы и связь "
            f"с типом мышления «{q['type']}». Ответ нужен для проверки PDF, "
            f"PowerPoint, SQLite и итоговой диагностики."
        )

        short_analysis = (
            f"Ответ тестовый. Тип мышления «{q['type']}» "
            f"{'проявлен уверенно' if presence == 'ЕСТЬ' else 'пока проявлен недостаточно'}. "
            f"Оценка выставлена для проверки логики отчётов и короткого результата."
        )

        full_analysis = (
            f"Это расширенный тестовый анализ по типу мышления «{q['type']}». "
            f"В рамках проверки считается, что пользователь дал ответ на вопрос: «{q['q']}». "
            f"Если результат отмечен как ЕСТЬ, значит в ответе условно присутствуют признаки типа мышления: "
            f"логика, связь с опытом, способность объяснять свои действия и делать выводы. "
            f"Если результат отмечен как НЕТ, значит ответ рассматривается как зона развития: "
            f"ему не хватает конкретики, личного примера, причинно-следственной связи или практического вывода. "
            f"Этот блок нужен для проверки того, как расширенный анализ отображается в PDF и PowerPoint. "
            f"В реальном прохождении здесь будет индивидуальная диагностика ответа пользователя."
        )

        advice = (
            f"Чтобы усилить тип мышления «{q['type']}», пользователю стоит отвечать подробнее: "
            f"описывать ситуацию, своё действие, причину выбора, результат и личный вывод."
        )

        values_analysis = (
            f"Тестовая ценностная диагностика по вопросу {index}. "
            f"В ответе условно проявляются ценностные сигналы, связанные с типом мышления "
            f"«{q['type']}». Этот блок нужен для проверки сохранения ценностей, желаний, "
            f"важностей, противоречий, ответственности и перекладывания ответственности."
        )

        detected_values = (
            "развитие, ответственность, польза"
            if presence == "ЕСТЬ"
            else "явно не выявлены"
        )

        detected_desires = (
            "улучшить результат, повысить качество жизни, двигаться к цели"
            if presence == "ЕСТЬ"
            else "явно не выявлены"
        )

        detected_importance = (
            "обучение, конкретные действия, личный вывод"
            if presence == "ЕСТЬ"
            else "явно не выявлены"
        )

        contradictions = (
            "явных противоречий не видно"
            if presence == "ЕСТЬ"
            else "данных недостаточно для вывода о противоречиях"
        )

        responsibility = (
            "Позиция ответственности условно проявлена: пользователь описывает действия, выводы и развитие."
            if presence == "ЕСТЬ"
            else "Позиция ответственности выражена слабо: в ответе недостаточно действий и личной позиции."
        )

        responsibility_shift = (
            "явно не выявлено"
            if presence == "ЕСТЬ"
            else "возможна слабая опора на собственные действия, но данных недостаточно"
        )

        user_results[user_id][q["type"]] = {
            "score": score,
            "presence": presence,
        }

        user_answers[user_id].append(
            {
                "block_id": q["block_id"],
                "type": q["type"],
                "question": q["q"],
                "answer": answer_text,
                "analysis": short_analysis,
                "full_analysis": full_analysis,
                "values_analysis": values_analysis,
                "detected_values": detected_values,
                "detected_desires": detected_desires,
                "detected_importance": detected_importance,
                "contradictions": contradictions,
                "responsibility": responsibility,
                "responsibility_shift": responsibility_shift,
                "advice": advice,
                "score": score,
                "presence": presence,
            }
        )

        save_answer(
            telegram_id=user_id,
            question_index=index,
            block_id=q["block_id"],
            thinking_type=q["type"],
            question_text=q["q"],
            answer_text=answer_text,
            analysis_text=short_analysis,
            score=score,
            presence=presence,
            full_analysis_text=full_analysis,
            advice_text=advice,
            values_analysis_text=values_analysis,
            detected_values_text=detected_values,
            detected_desires_text=detected_desires,
            detected_importance_text=detected_importance,
            contradictions_text=contradictions,
            responsibility_text=responsibility,
            responsibility_shift_text=responsibility_shift,
        )

    update_session_progress(
        telegram_id=user_id,
        current_question=len(QUESTIONS),
        status="finished",
    )

    value_profile = generate_and_save_value_profile(user_id)

    await message.answer(
        "✅ Тестовые данные созданы для 43 вопросов.\n\n"
        "Теперь /test использует формат v2:\n"
        "— краткий анализ;\n"
        "— расширенный анализ;\n"
        "— ценностная диагностика;\n"
        "— выявленные ценности;\n"
        "— желания;\n"
        "— важности;\n"
        "— противоречия;\n"
        "— ответственность;\n"
        "— перекладывание ответственности;\n"
        "— итоговая ценностная характеристика.\n\n"
        f"🧭 Ценностная формула:\n{value_profile.get('value_formula_text', 'не сформирована')}\n\n"
        "Можно проверить карту результата, PDF и PowerPoint.",
        reply_markup=result_keyboard(),
    )


@dp.message(F.text.in_({"❓ FAQ", "❓ Подсказки маршрута"}))
async def faq_message(message: Message):
    await message.answer(
        "<b>❓ Подсказки маршрута</b>\n\n"
        "1. Отвечай подробно, но живым языком: ситуация, действие, вывод.\n"
        "2. Оценка 8+ означает, что тип мышления проявлен.\n"
        "3. После каждого ответа ты увидишь краткий анализ и совет.\n"
        "4. Полный разбор будет в PDF и PowerPoint после оплаты.\n"
        "5. Если не понимаешь вопрос — открой «🧭 Помощник маршрута».\n"
        "6. Голосовые ответы можно отправлять как обычный ответ.\n\n"
        "🧭 Главный ориентир: не пытайся отвечать идеально. "
        "Показывай реальный опыт, мысли, решения и направление движения."
    )


@dp.callback_query(F.data == "faq")
async def faq_callback(call: CallbackQuery):
    await call.message.answer(
        "<b>❓ Подсказки маршрута</b>\n\n"
        "Отвечай честно, подробно и с примерами. "
        "Подсказки не сбрасывают текущий вопрос и не прерывают маршрут."
    )
    await call.answer()


@dp.message(F.text == "💳 Оплатить")
async def pay_message(message: Message):
    await message.answer(payment_text(), reply_markup=payment_keyboard())


@dp.callback_query(F.data == "pay")
async def pay_callback(call: CallbackQuery):
    await call.message.answer(payment_text(), reply_markup=payment_keyboard())
    await call.answer()


@dp.callback_query(F.data == "payment_confirmed")
async def payment_confirmed(call: CallbackQuery):
    user_id = call.from_user.id

    if is_paid(user_id):
        await call.message.answer(
            "✅ Доступ уже открыт.\n\n"
            "Можно получить PDF и PowerPoint отчёты.",
            reply_markup=result_keyboard(),
        )
        await call.answer()
        return

    mark_paid(user_id)

    await call.message.answer(
        "✅ Тестовая оплата подтверждена.\n\n"
        "PDF и PowerPoint отчёты открыты.",
        reply_markup=result_keyboard(),
    )

    await call.answer()


@dp.callback_query(F.data == "short_result")
async def short_result(call: CallbackQuery):
    user_id = call.from_user.id

    loaded = load_user_runtime_data_if_needed(user_id)

    if not loaded:
        await call.message.answer(
            "📊 Результатов пока нет.\n\n"
            "Пройдите опрос или используйте команду /test."
        )
        await call.answer()
        return

    await call.message.answer(
        build_short_result_text(user_id),
        reply_markup=result_keyboard(),
    )

    await call.answer()


@dp.message(F.text == "📄 PDF")
async def pdf_message(message: Message):
    await send_pdf(message)


@dp.callback_query(F.data == "get_pdf")
async def pdf_callback(call: CallbackQuery):
    await send_pdf(call.message, call.from_user.id)
    await call.answer()


async def send_pdf(message: Message, user_id: int | None = None):
    if user_id is None:
        user_id = message.from_user.id

    if not is_paid(user_id):
        await message.answer(
            "🔒 PDF доступен после оплаты.",
            reply_markup=payment_keyboard(),
        )
        return

    loaded = load_user_runtime_data_if_needed(user_id)

    if not loaded:
        await message.answer(
            "📄 Не удалось сформировать PDF: результатов пока нет.\n\n"
            "Пройдите опрос или используйте /test."
        )
        return

    path = build_pdf_report(
        user_id,
        user_results.get(user_id, {}),
        user_answers.get(user_id, []),
    )

    save_report(
        telegram_id=user_id,
        report_type="pdf",
        file_path=path,
    )

    await message.answer_document(
        FSInputFile(path),
        caption="📄 Ваш PDF-отчёт готов.",
    )

@dp.message(F.text == "📽 PowerPoint")
async def ppt_message(message: Message):
    await send_ppt(message)


@dp.callback_query(F.data == "get_ppt")
async def ppt_callback(call: CallbackQuery):
    await send_ppt(call.message, call.from_user.id)
    await call.answer()


async def send_ppt(message: Message, user_id: int | None = None):
    if user_id is None:
        user_id = message.from_user.id

    if not is_paid(user_id):
        await message.answer(
            "🔒 PowerPoint доступен после оплаты.",
            reply_markup=payment_keyboard(),
        )
        return

    loaded = load_user_runtime_data_if_needed(user_id)

    if not loaded:
        await message.answer(
            "📽 Не удалось сформировать PowerPoint: результатов пока нет.\n\n"
            "Пройдите опрос или используйте /test."
        )
        return

    path = build_ppt_report(
        user_id,
        user_results.get(user_id, {}),
        user_answers.get(user_id, []),
    )

    save_report(
        telegram_id=user_id,
        report_type="ppt",
        file_path=path,
    )

    await message.answer_document(
        FSInputFile(path),
        caption="📽 Ваш PowerPoint-отчёт готов.",
    )

@dp.callback_query(F.data == "consultant")
async def consultant_callback(call: CallbackQuery):
    user_mode[call.from_user.id] = "consultant"
    await call.message.answer(
        "🧭 <b>Помощник маршрута рядом.</b>\n\n"
        "Задай вопрос по текущему заданию или формату ответа."
    )
    await call.answer()


@dp.message(F.text.in_({"🤖 AI-Консультант", "🧭 Помощник маршрута"}))
async def consultant_message_start(message: Message):
    user_mode[message.from_user.id] = "consultant"
    await message.answer(
        "🧭 <b>Помощник маршрута рядом.</b>\n\n"
        "Задай вопрос по текущему заданию, формату ответа или смыслу вопроса. "
        "Я помогу сориентироваться, но не буду проходить маршрут вместо тебя."
    )


@dp.message(F.voice)
async def handle_voice(message: Message):
    user_id = message.from_user.id
    os.makedirs("storage/temp", exist_ok=True)

    file = await bot.get_file(message.voice.file_id)
    path = f"storage/temp/{message.voice.file_unique_id}.ogg"
    await bot.download_file(file.file_path, path)

    try:
        text = transcribe_audio(path)
    finally:
        if os.path.exists(path):
            os.remove(path)

    await message.answer(f"🎤 Распознано:\n{text}")

    if user_mode.get(user_id) == "consultant":
        idx = user_state.get(user_id, 0)
        current_question = QUESTIONS[idx] if idx < len(QUESTIONS) else None

        answer = ask_consultant(text, current_question)

        await message.answer(f"🧭 {answer}")
        user_mode[user_id] = "survey"
        return

    await process_survey_answer(message, text)


@dp.callback_query(F.data == "next_question")
async def next_question(call: CallbackQuery):
    await send_question(call.message, call.from_user.id)
    await call.answer()

async def begin_survey_flow(message: Message):
    user_id = message.from_user.id

    save_user(
        telegram_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )

    active_session = get_active_session(user_id)

    if active_session:
        current_question = active_session.get("current_question", 0)
        total_questions = active_session.get("total_questions", len(QUESTIONS))

        await message.answer(
            "🚗 <b>У тебя уже есть незавершённый маршрут.</b>\n\n"
            f"Пройдено вопросов: <b>{current_question}</b> из <b>{total_questions}</b>.\n"
            f"Следующий вопрос: <b>{current_question + 1}</b> из <b>{total_questions}</b>.\n\n"
            "Можно продолжить с места остановки или начать заново.",
            reply_markup=resume_keyboard(),
        )
        return

    create_or_reset_session(
        telegram_id=user_id,
        total_questions=len(QUESTIONS),
    )

    user_state[user_id] = 0
    user_results[user_id] = {}
    user_answers[user_id] = []
    user_mode[user_id] = "survey"

    await message.answer(
        "🚗 <b>Маршрут начинается.</b>\n\n"
        "Ты выезжаешь на первую улицу Города Мышления. "
        "Сейчас мы откроем карту твоей мотивации, целей и внутренней опоры."
    )
    await send_question(message, user_id)

@dp.message(F.text.in_({"🧠 Начать опрос", "🚗 Начать маршрут"}))
async def start_survey_button(message: Message):
    await begin_survey_flow(message)


@dp.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    if text in {"🧠 Начать опрос", "🚗 Начать маршрут"}:
        await begin_survey_flow(message)
        return

    if text in {"➡️ Следующий вопрос", "▶️ Следующий вопрос", "Следующий вопрос"}:
        await send_question(message, user_id)
        return

    if text in {"❓ FAQ", "❓ Подсказки маршрута"}:
        await faq_message(message)
        return

    if text in {"🤖 AI-Консультант", "🤖 Помощник маршрута", "🧭 Помощник маршрута"}:
        await consultant_message_start(message)
        return

    if text == "💳 Оплатить":
        await pay_message(message)
        return

    if text in {"📄 PDF", "📄 PDF-отчёт"}:
        await send_pdf(message)
        return

    if text in {"📽 PowerPoint", "📽 Презентация PPT"}:
        await send_ppt(message)
        return

    if text in {"📊 Короткий результат", "🗺 Карта результата"}:
        loaded = load_user_runtime_data_if_needed(user_id)

        if not loaded:
            await message.answer(
                "🗺 Результатов пока нет.\n\n"
                "Пройдите маршрут или используйте команду /test."
            )
            return

        await message.answer(
            build_short_result_text(user_id),
            reply_markup=result_keyboard(),
        )
        return

    if user_mode.get(user_id) == "consultant":
        idx = user_state.get(user_id, 0)
        current_question = QUESTIONS[idx] if idx < len(QUESTIONS) else None
        answer = ask_consultant(text, current_question)

        await message.answer(
            f"🧭 {answer}\n\n"
            "Возвращаемся к маршруту опроса."
        )

        user_mode[user_id] = "survey"
        return

    if user_mode.get(user_id) == "waiting_next":
        await message.answer(
            "🚦 Мы уже разобрали предыдущий ответ.\n\n"
            "Чтобы продолжить маршрут, нажмите «➡️ Следующий вопрос».",
            reply_markup=continue_keyboard(),
        )
        return

    await process_survey_answer(message, text)


async def process_survey_answer(message: Message, text: str):
    user_id = message.from_user.id

    if user_id not in user_state:
        await message.answer("Нажмите «🚗 Начать маршрут» или /start.")
        return

    idx = user_state[user_id]

    if idx >= len(QUESTIONS):
        await send_final_message(message, user_id)
        return

    question = QUESTIONS[idx]

    await message.answer("⏳ Анализирую ответ...")

    try:
        analysis = analyze_answer(question, text)
    except Exception:
        analysis = (
             "Оценка: 0\n"
            "Результат: НЕТ\n\n"
            "Краткий анализ:\n"
            "AI-анализ временно недоступен. Ответ не был оценён автоматически.\n\n"
            "Расширенный анализ:\n"
            "Система не смогла получить расширенный анализ ответа. "
            "Код бота продолжает работать, но нужно проверить OpenAI API, регион подключения или интернет.\n\n"
            "Ценностная диагностика:\n"
            "Ценностная диагностика временно недоступна, потому что AI-анализ не был выполнен.\n\n"
            "Выявленные ценности:\n"
            "явно не выявлены\n\n"
            "Выявленные желания:\n"
            "явно не выявлены\n\n"
            "Выявленные важности:\n"
            "явно не выявлены\n\n"
            "Возможные противоречия:\n"
            "данных недостаточно\n\n"
            "Ответственность:\n"
            "данных недостаточно\n\n"
            "Перекладывание ответственности:\n"
            "явно не выявлено\n\n"
            "Совет:\n"
            "Проверьте OPENAI_API_KEY, VPN/регион подключения и перезапустите бота."
        )

    parsed = parse_analysis(analysis)
    
    short_analysis = parsed.get("short_analysis", "")
    full_analysis = parsed.get("full_analysis", "")
    values_analysis = parsed.get("values_analysis", "")
    detected_values = parsed.get("detected_values", "")
    detected_desires = parsed.get("detected_desires", "")
    detected_importance = parsed.get("detected_importance", "")
    contradictions = parsed.get("contradictions", "")
    responsibility = parsed.get("responsibility", "")
    responsibility_shift = parsed.get("responsibility_shift", "")
    advice = parsed.get("advice", "")
    
    user_results[user_id][question["type"]] = {
        "score": parsed["score"],
        "presence": parsed["presence"],
    }

    answer_data = {
        "block_id": question["block_id"],
        "type": question["type"],
        "question": question["q"],
        "answer": text,
        "analysis": short_analysis,
        "full_analysis": full_analysis,
        "values_analysis": values_analysis,
        "detected_values": detected_values,
        "detected_desires": detected_desires,
        "detected_importance": detected_importance,
        "contradictions": contradictions,
        "responsibility": responsibility,
        "responsibility_shift": responsibility_shift,
        "advice": advice,
        "raw_analysis": analysis,
        "score": parsed["score"],
        "presence": parsed["presence"],
    }

    user_answers[user_id].append(answer_data)

    save_answer(
        telegram_id=user_id,
        question_index=idx + 1,
        block_id=question["block_id"],
        thinking_type=question["type"],
        question_text=question["q"],
        answer_text=text,
        analysis_text=short_analysis,
        score=parsed["score"],
        presence=parsed["presence"],
        full_analysis_text=full_analysis,
        advice_text=advice,
        values_analysis_text=values_analysis,
        detected_values_text=detected_values,
        detected_desires_text=detected_desires,
        detected_importance_text=detected_importance,
        contradictions_text=contradictions,
        responsibility_text=responsibility,
        responsibility_shift_text=responsibility_shift,
    )

    user_state[user_id] += 1

    new_index = user_state[user_id]

    if new_index >= len(QUESTIONS):
        update_session_progress(
        telegram_id=user_id,
        current_question=new_index,
        status="finished",
        )

        await message.answer(
        build_telegram_analysis_text(parsed)
        )

        await message.answer("🧭 Собираю итоговую ценностную карту по всем ответам...")

        value_profile = generate_and_save_value_profile(user_id)

        await message.answer(
        build_value_profile_ready_text(value_profile)
        )

        await send_final_message(message, user_id)
        return

    update_session_progress(
        telegram_id=user_id,
        current_question=new_index,
        status="active",
    )

    user_mode[user_id] = "waiting_next"

    await message.answer(
        build_telegram_analysis_text(parsed),
        reply_markup=continue_keyboard(),
    )


async def main():
    init_database()

    print("DATABASE INITIALIZED")
    print("BOT NEW STARTED")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())