import os
import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from database.repositories import get_latest_value_profile


REPORTS_DIR = Path("storage/reports")
FONTS_DIR = Path("assets/fonts")


BLOCK_ORDER = [
    "base",
    "present",
    "past",
    "future",
    "people",
    "project",
    "unusual",
]


BLOCK_TITLES = {
    "base": "БАЗА",
    "present": "НАСТОЯЩЕЕ ВРЕМЯ",
    "past": "ПРОШЛОЕ ВРЕМЯ",
    "future": "БУДУЩЕЕ ВРЕМЯ",
    "people": "ЛЮДИ И ОТНОШЕНИЯ",
    "project": "ПРОЕКТЫ, ДОСТИЖЕНИЯ, БИЗНЕС",
    "unusual": "НЕОБЫЧНЫЕ ВИДЫ МЫШЛЕНИЯ",
}


def _find_regular_font() -> str:
    """
    Ищет обычный Unicode-шрифт для PDF.

    Важно:
    - Railway работает на Linux.
    - Windows Arial там отсутствует.
    - Поэтому нужен системный DejaVu из пакета fonts-dejavu-core.
    """

    candidates = [
        # Локальные шрифты внутри проекта
        FONTS_DIR / "DejaVuSans.ttf",
        FONTS_DIR / "DejaVuSansCondensed.ttf",
        FONTS_DIR / "Arial.ttf",

        # Railway / Linux / Debian / Ubuntu
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),

        # Windows для локальной проверки
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\Arial.ttf"),
        Path(r"C:\Windows\Fonts\calibri.ttf"),
        Path(r"C:\Windows\Fonts\Calibri.ttf"),
    ]

    for path in candidates:
        if path.exists():
            print(f"PDF REGULAR FONT FOUND: {path}")
            return str(path)

    raise FileNotFoundError(
        "Не найден Unicode-шрифт для PDF. "
        "На Railway добавьте nixpacks.toml с fonts-dejavu-core "
        "или положите DejaVuSans.ttf в assets/fonts/."
    )


def _find_bold_font() -> str:
    """
    Ищет жирный Unicode-шрифт для PDF.
    Если жирный не найден, возвращает обычный шрифт.
    """

    candidates = [
        # Локальные шрифты внутри проекта
        FONTS_DIR / "DejaVuSans-Bold.ttf",
        FONTS_DIR / "DejaVuSansCondensed-Bold.ttf",
        FONTS_DIR / "Arial-Bold.ttf",

        # Railway / Linux / Debian / Ubuntu
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),

        # Windows для локальной проверки
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
        Path(r"C:\Windows\Fonts\Arialbd.ttf"),
        Path(r"C:\Windows\Fonts\calibrib.ttf"),
        Path(r"C:\Windows\Fonts\Calibrib.ttf"),
    ]

    for path in candidates:
        if path.exists():
            print(f"PDF BOLD FONT FOUND: {path}")
            return str(path)

    print("PDF BOLD FONT NOT FOUND. USING REGULAR FONT.")
    return _find_regular_font()


def _presence_label(value: str) -> str:
    """
    Единый формат отображения результата.
    В отчёте не используем слово НЕТ.
    """

    if value == "ЕСТЬ":
        return "ЕСТЬ"

    return "Есть что проращивать"


def _safe_text(value) -> str:
    if value is None:
        return ""

    text = str(value)

    replacements = {
        "✅": "+",
        "⬜": "-",
        "📄": "",
        "📊": "",
        "📽": "",
        "🧠": "",
        "🔵": "",
        "🟢": "",
        "⚫": "",
        "🌸": "",
        "🤍": "",
        "🟡": "",
        "🟣": "",
        "🚗": "",
        "🏁": "",
        "💳": "",
        "🤖": "",
        "❓": "",
        "➡️": "",
        "⬅️": "",
        "🎤": "",
        "⏳": "",
        "🔥": "",
        "🎯": "",
        "🧭": "",
        "🗺": "",
        "🔒": "",
        "▶️": "",
        "🔁": "",
        "🚦": "",
        "📞": "",
        "🧑‍🏫": "",
        "📩": "",
        "👤": "",
        "🔁": "",
        "—": "-",
        "–": "-",
        "\u00a0": " ",
        "\u200b": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _break_long_words(text: str, chunk_size: int = 42) -> str:
    def split_word(word: str) -> str:
        if len(word) <= chunk_size:
            return word

        return " ".join(
            word[i:i + chunk_size]
            for i in range(0, len(word), chunk_size)
        )

    result_lines = []

    for line in text.splitlines():
        words = line.split(" ")
        result_lines.append(" ".join(split_word(word) for word in words))

    return "\n".join(result_lines)


class MindPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("MindFont", "", 9)
        self.cell(0, 10, f"Страница {self.page_no()}", align="C")


def _write_text(
    pdf: MindPDF,
    text: str,
    size: int = 10,
    bold: bool = False,
    line_height: int = 7,
    align: str = "L",
):
    text = _safe_text(text)
    text = _break_long_words(text)

    style = "B" if bold else ""
    pdf.set_font("MindFont", style, size)
    pdf.set_x(pdf.l_margin)

    width = pdf.w - pdf.l_margin - pdf.r_margin

    if width <= 30:
        width = 170

    try:
        pdf.multi_cell(
            width,
            line_height,
            text,
            align=align,
        )
    except Exception:
        fallback = _break_long_words(text[:1800], 25)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(
            width,
            line_height,
            fallback,
            align=align,
        )


def _section_title(pdf: MindPDF, title: str):
    pdf.ln(5)
    _write_text(
        pdf,
        title,
        size=14,
        bold=True,
        line_height=8,
    )
    pdf.ln(2)


def _small_divider(pdf: MindPDF):
    pdf.ln(2)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)


def _calculate_summary(results: dict) -> dict:
    total = len(results)

    found = sum(
        1
        for value in results.values()
        if value.get("presence") == "ЕСТЬ"
    )

    missing = total - found

    average_score = 0

    if total:
        average_score = round(
            sum(value.get("score", 0) for value in results.values()) / total,
            1,
        )

    return {
        "total": total,
        "found": found,
        "missing": missing,
        "average_score": average_score,
    }


def _build_missing_list(results: dict) -> list[str]:
    return [
        type_name
        for type_name, data in results.items()
        if data.get("presence") != "ЕСТЬ"
    ]


def _build_found_list(results: dict) -> list[str]:
    return [
        type_name
        for type_name, data in results.items()
        if data.get("presence") == "ЕСТЬ"
    ]


def _diagnostic_summary_text(summary: dict) -> str:
    if summary["total"] == 0:
        return (
            "Диагностика пока не сформирована. Пользователь ещё не прошёл "
            "достаточное количество вопросов."
        )

    if summary["found"] >= max(1, summary["total"] * 0.7):
        return (
            "Ответы показывают широкий спектр проявленных типов мышления. "
            "Пользователь хорошо раскрывает логику, мотивацию, опыт, решения "
            "и способы действия. Основная задача дальше - не просто сохранять "
            "сильные стороны, а применять их системно в реальных проектах."
        )

    if summary["found"] >= max(1, summary["total"] * 0.4):
        return (
            "У пользователя есть выраженная база мышления и несколько сильных зон. "
            "Часть типов проявлена уверенно, но некоторые направления требуют "
            "более подробных ответов, примеров, выводов и связи с реальным опытом."
        )

    return (
        "Пока раскрыта только часть типов мышления. Это не означает слабый "
        "потенциал. Скорее, ответы требуют большей конкретики: ситуаций, "
        "решений, причин, последствий и личных выводов."
    )


def _slogan(summary: dict) -> str:
    if summary["total"] == 0:
        return (
            "Маршрут ещё не сформирован. Чтобы увидеть карту мышления, "
            "нужно пройти вопросы диагностики."
        )

    if summary["found"] >= max(1, summary["total"] * 0.7):
        return (
            "Ты уже уверенно двигаешься по Городу Мышления. "
            "Теперь задача - превратить сильные стороны в систему действий."
        )

    if summary["found"] >= max(1, summary["total"] * 0.4):
        return (
            "Маршрут уже построен. Усиливай сильные стороны и постепенно "
            "осваивай новые районы своего мышления."
        )

    return (
        "Каждый ответ - это шаг. Чем точнее ты описываешь опыт, "
        "тем яснее становится карта твоего мышления."
    )


def _write_value_profile(pdf: MindPDF, value_profile: dict | None):
    _section_title(pdf, "6. Карта ценностей пользователя")

    if not value_profile:
        _write_text(
            pdf,
            "Итоговая ценностная характеристика пока не сформирована.",
            size=10,
            line_height=7,
        )
        return

    sections = [
        ("Итоговая ценностная характеристика", value_profile.get("summary_text", "")),
        ("Ведущие ценности", value_profile.get("key_values_text", "")),
        ("Вероятные ценности", value_profile.get("probable_values_text", "")),
        ("Желания и цели", value_profile.get("desires_text", "")),
        ("Важности", value_profile.get("importance_text", "")),
        ("Противоречия", value_profile.get("contradictions_text", "")),
        ("Ответственность", value_profile.get("responsibility_text", "")),
        ("Перекладывание ответственности", value_profile.get("responsibility_shift_text", "")),
        ("Ценностная формула", value_profile.get("value_formula_text", "")),
    ]

    for title, content in sections:
        if not content:
            continue

        _write_text(
            pdf,
            title,
            size=11,
            bold=True,
            line_height=7,
        )

        _write_text(
            pdf,
            content,
            size=10,
            line_height=7,
        )

        pdf.ln(3)


def _write_answers_analysis(pdf: MindPDF, answers: list[dict]):
    _section_title(pdf, "5. Анализ ответов пользователя")

    if not answers:
        _write_text(pdf, "Ответов пока нет.", size=10)
        return

    for index, item in enumerate(answers, start=1):
        thinking_type = item.get("type", "")
        question = item.get("question", "")
        answer = item.get("answer", "")

        short_analysis = item.get("analysis", "") or "Краткий анализ не сформирован."
        full_analysis = item.get("full_analysis", "") or "Расширенный анализ не сформирован."
        advice = item.get("advice", "") or "Совет не сформирован."

        values_analysis = item.get("values_analysis", "") or "Ценностная диагностика не сформирована."
        detected_values = item.get("detected_values", "") or "явно не выявлены"
        detected_desires = item.get("detected_desires", "") or "явно не выявлены"
        detected_importance = item.get("detected_importance", "") or "явно не выявлены"
        contradictions = item.get("contradictions", "") or "данных недостаточно"
        responsibility = item.get("responsibility", "") or "данных недостаточно"
        responsibility_shift = item.get("responsibility_shift", "") or "явно не выявлено"

        score = item.get("score", 0)
        presence = _presence_label(item.get("presence", "ЕСТЬ ЧТО ПРОРАЩИВАТЬ"))

        if index > 1:
            _small_divider(pdf)

        _write_text(
            pdf,
            f"Ответ {index}. {thinking_type}",
            size=11,
            bold=True,
            line_height=7,
        )

        _write_text(
            pdf,
            f"Вопрос: {question}",
            size=10,
            line_height=7,
        )

        _write_text(
            pdf,
            f"Ответ пользователя: {answer}",
            size=10,
            line_height=7,
        )

        _write_text(
            pdf,
            f"Оценка: {score}/10",
            size=10,
            line_height=7,
        )

        _write_text(
            pdf,
            f"Наличие типа мышления: {presence}",
            size=10,
            line_height=7,
        )

        pdf.ln(2)

        _write_text(pdf, "Краткий анализ:", size=10, bold=True, line_height=7)
        _write_text(pdf, short_analysis, size=10, line_height=7)

        pdf.ln(2)

        _write_text(pdf, "Расширенный анализ:", size=10, bold=True, line_height=7)
        _write_text(pdf, full_analysis, size=10, line_height=7)

        pdf.ln(2)

        _write_text(pdf, "Ориентир дальше:", size=10, bold=True, line_height=7)
        _write_text(pdf, advice, size=10, line_height=7)

        pdf.ln(2)

        _write_text(pdf, "Ценностная диагностика:", size=10, bold=True, line_height=7)
        _write_text(pdf, values_analysis, size=10, line_height=7)

        pdf.ln(2)

        _write_text(pdf, "Выявленные ценности:", size=10, bold=True, line_height=7)
        _write_text(pdf, detected_values, size=10, line_height=7)

        pdf.ln(2)

        _write_text(pdf, "Выявленные желания:", size=10, bold=True, line_height=7)
        _write_text(pdf, detected_desires, size=10, line_height=7)

        pdf.ln(2)

        _write_text(pdf, "Выявленные важности:", size=10, bold=True, line_height=7)
        _write_text(pdf, detected_importance, size=10, line_height=7)

        pdf.ln(2)

        _write_text(pdf, "Возможные противоречия:", size=10, bold=True, line_height=7)
        _write_text(pdf, contradictions, size=10, line_height=7)

        pdf.ln(2)

        _write_text(pdf, "Ответственность:", size=10, bold=True, line_height=7)
        _write_text(pdf, responsibility, size=10, line_height=7)

        pdf.ln(2)

        _write_text(pdf, "Перекладывание ответственности:", size=10, bold=True, line_height=7)
        _write_text(pdf, responsibility_shift, size=10, line_height=7)

        pdf.ln(5)


def build_pdf_report(user_id: int, results: dict, answers: list[dict]) -> str:
    value_profile = get_latest_value_profile(user_id)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    file_path = REPORTS_DIR / f"report_{user_id}.pdf"

    regular_font = _find_regular_font()
    bold_font = _find_bold_font()

    pdf = MindPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.add_font("MindFont", "", regular_font, uni=True)
    pdf.add_font("MindFont", "B", bold_font, uni=True)

    summary = _calculate_summary(results)
    found_types = _build_found_list(results)
    missing_types = _build_missing_list(results)

    # PAGE 1 - TITLE
    pdf.add_page()

    _write_text(
        pdf,
        "Путешествие по Городу Мышления",
        size=20,
        bold=True,
        line_height=11,
        align="C",
    )

    pdf.ln(4)

    _write_text(
        pdf,
        "Итоговый отчёт по диагностике типов мышления и ценностей",
        size=13,
        bold=True,
        line_height=8,
        align="C",
    )

    pdf.ln(8)

    _write_text(
        pdf,
        (
            "Этот отчёт создан после прохождения опроса. "
            "Он показывает, какие типы мышления проявились в ответах, "
            "какие направления требуют развития, какие ценности и важности "
            "видны в ответах пользователя, а также где проявлена ответственность "
            "или возможное перекладывание ответственности."
        ),
        size=10,
        line_height=7,
    )

    pdf.ln(4)

    _write_text(
        pdf,
        (
            "Представьте маршрут по городу: сначала вы смотрите на карту, "
            "затем двигаетесь по улицам настоящего, заезжаете в районы прошлого, "
            "выезжаете на дорогу будущего, встречаете людей, заходите в рабочее "
            "пространство и возвращаетесь на улицу уже с новым пониманием себя."
        ),
        size=10,
        line_height=7,
    )

    pdf.ln(6)

    _write_text(
        pdf,
        f"Дата создания отчёта: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        size=10,
    )

    _small_divider(pdf)

    _write_text(pdf, "Назначение отчёта", size=13, bold=True, line_height=8)

    _write_text(
        pdf,
        (
            "Файл нужен для того, чтобы пользователь увидел не только итоговые "
            "баллы, но и логику диагностики: почему тип мышления считается "
            "проявленным или не проявленным, какие ответы были сильными, "
            "какие зоны требуют развития, какие ценностные сигналы повторяются "
            "и какие шаги можно предпринять дальше."
        ),
        size=10,
        line_height=7,
    )

    # PAGE 2 - SUMMARY
    pdf.add_page()

    _section_title(pdf, "1. Сводка результата")

    _write_text(pdf, f"Всего проверено типов мышления: {summary['total']}", size=11)
    _write_text(pdf, f"Найдено типов мышления: {summary['found']}", size=11)
    _write_text(pdf, f"Зоны развития: {summary['missing']}", size=11)
    _write_text(pdf, f"Средний балл: {summary['average_score']}/10", size=11)

    pdf.ln(5)

    _write_text(pdf, "Общая диагностика", size=13, bold=True)

    _write_text(
        pdf,
        _diagnostic_summary_text(summary),
        size=10,
        line_height=7,
    )

    # PAGE 3 - TABLE
    pdf.add_page()

    _section_title(pdf, "2. Таблица наличия типов мышления")

    if not results:
        _write_text(pdf, "Результатов пока нет.", size=10)
    else:
        for type_name, data in results.items():
            presence = _presence_label(data.get("presence", "ЕСТЬ ЧТО ПРОРАЩИВАТЬ"))
            score = data.get("score", 0)
            marker = "+" if data.get("presence") == "ЕСТЬ" else "*"

            _write_text(
                pdf,
                f"{marker} {type_name} - {score}/10 - {presence}",
                size=9,
                line_height=6,
            )

    # PAGE 4 - STRENGTHS
    pdf.add_page()

    _section_title(pdf, "3. Сильные стороны")

    if found_types:
        _write_text(
            pdf,
            (
                "Ниже перечислены типы мышления, которые проявились в ответах. "
                "Они могут считаться сильными зонами пользователя."
            ),
            size=10,
            line_height=7,
        )

        pdf.ln(3)

        for type_name in found_types:
            score = results[type_name].get("score", 0)
            _write_text(
                pdf,
                f"+ {type_name} - {score}/10",
                size=10,
                line_height=7,
            )
    else:
        _write_text(
            pdf,
            (
                "Сильные стороны пока не выявлены из-за недостатка данных "
                "или низких оценок ответов."
            ),
            size=10,
        )

    # PAGE 5 - DEVELOPMENT ZONES
    pdf.add_page()

    _section_title(pdf, "4. Зоны развития")

    if missing_types:
        _write_text(
            pdf,
            (
                "Ниже перечислены типы мышления, которые пока не проявились "
                "достаточно уверенно. Их можно развивать через практику, "
                "рефлексию, обучение и более точное описание опыта."
            ),
            size=10,
            line_height=7,
        )

        pdf.ln(3)

        for type_name in missing_types:
            score = results[type_name].get("score", 0)
            _write_text(
                pdf,
                f"- {type_name} - {score}/10",
                size=10,
                line_height=7,
            )
    else:
        _write_text(
            pdf,
            (
                "Все проверенные типы мышления проявлены. Дальше важно "
                "работать не над наличием, а над качеством, глубиной и "
                "практическим применением мышления."
            ),
            size=10,
            line_height=7,
        )

    # PAGE 6 - FULL ANSWERS
    pdf.add_page()
    _write_answers_analysis(pdf, answers)

    # PAGE 7 - VALUES PROFILE
    pdf.add_page()
    _write_value_profile(pdf, value_profile)

    # PAGE 8 - RECOMMENDATIONS
    pdf.add_page()

    _section_title(pdf, "7. Рекомендации")

    _write_text(
        pdf,
        (
            "1. Отвечать на вопросы через реальные ситуации, а не только через "
            "общие рассуждения.\n"
            "2. В каждом ответе показывать: ситуацию, действие, решение, вывод.\n"
            "3. Для зон развития выбирать один тип мышления в неделю и тренировать "
            "его через практические задачи.\n"
            "4. Использовать результаты отчёта как карту: сильные стороны - это "
            "опора, зоны развития - это маршрут следующего движения.\n"
            "5. Отдельно возвращаться к ценностной карте: смотреть, какие ценности "
            "повторяются, какие желания являются инструментами и где требуется больше ответственности."
        ),
        size=10,
        line_height=7,
    )

    pdf.ln(5)

    _write_text(pdf, "Лозунг", size=13, bold=True)

    _write_text(pdf, _slogan(summary), size=10, line_height=7)

    # PAGE 9 - PROJECT DEVELOPMENT
    pdf.add_page()

    _section_title(pdf, "8. Блок для дальнейшего развития проекта")

    _write_text(
        pdf,
        (
            "Здесь будут ссылки на курсы по обучению.\n"
            "Здесь будут ссылки для оплаты обучения.\n"
            "Здесь будет информация по оплате опроса.\n"
            "Здесь будет контактная информация для связи с экспертом.\n"
            "Здесь будет информация для записи на консультацию."
        ),
        size=10,
        line_height=7,
    )

    pdf.ln(5)

    _write_text(
        pdf,
        (
            "Финальная сцена маршрута: пользователь выходит из помещения "
            "с результатами диагностики, возвращается на улицу и видит город "
            "иначе. Теперь мышление воспринимается не как абстрактная способность, "
            "а как инструмент, который сопровождает его в движении, работе, "
            "общении, планировании и принятии решений."
        ),
        size=10,
        line_height=7,
    )

    pdf.output(str(file_path))

    if not file_path.exists():
        raise FileNotFoundError(f"PDF-файл не был создан: {file_path}")

    return str(file_path)