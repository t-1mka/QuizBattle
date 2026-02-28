# -*- coding: utf-8 -*-
"""AI-клиент BrainStorm — GigaChat с валидацией вопросов"""
import os, re, json, random, logging

logger = logging.getLogger(__name__)

DIFFICULTY_LABELS = {
    "easy":   "ЛЁГКИЙ — простые факты, известные каждому школьнику",
    "medium": "СРЕДНИЙ — для эрудированного взрослого, требует кругозора",
    "hard":   "СЛОЖНЫЙ — экспертный уровень, глубокие специализированные знания",
}

# ── Промпт ───────────────────────────────────────────────────

def build_prompt(topic: str, count: int, difficulty: str, num_options: int) -> str:
    diff_label = DIFFICULTY_LABELS.get(difficulty, DIFFICULTY_LABELS["medium"])
    example = json.dumps({
        "questions": [
            {"question": "Какой химический символ у железа?",
             "options": ["Fe", "Au", "Ag", "Cu"], "correct": 0}
        ]
    }, ensure_ascii=False, indent=2)

    return (
        f'Создай РОВНО {count} вопросов для викторины по теме "{topic}".\n'
        f'Сложность: {diff_label}.\n\n'
        f'ПРАВИЛА (строго):\n'
        f'1. У каждого вопроса РОВНО {num_options} вариантов ответа.\n'
        f'2. "correct" — индекс правильного варианта от 0 до {num_options-1}. '
        f'   Нумерация С НУЛЯ: первый = 0, второй = 1, третий = 2, четвёртый = 3.\n'
        f'3. Вопросы должны быть КОРРЕКТНЫМИ — правильный ответ действительно верен.\n'
        f'4. Ответь ТОЛЬКО валидным JSON, без пояснений и markdown.\n\n'
        f'Формат:\n{example}\n\n'
        f'Создай {count} вопросов по теме "{topic}":'
    )

# ── Парсинг ответа ───────────────────────────────────────────

def _parse_response(raw: str, num_options: int) -> list:
    text = raw.strip().lstrip('\ufeff')

    # Убираем markdown-блок если есть
    cb = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if cb:
        text = cb.group(1).strip()

    # Вырезаем { ... }
    s, e = text.find('{'), text.rfind('}')
    if s != -1 and e != -1:
        text = text[s:e+1]

    # Убираем trailing commas
    text = re.sub(r',\s*([}\]])', r'\1', text)

    try:
        data = json.loads(text)
        # Поддерживаем разные ключи которые может вернуть GigaChat
        qs = data.get("questions") or next(
            (v for v in data.values()
             if isinstance(v, list) and v
             and isinstance(v[0], dict) and "question" in v[0]), None
        )
        if qs:
            logger.info("✅ JSON распарсен (%d вопросов)", len(qs))
            return qs
    except json.JSONDecodeError as exc:
        logger.warning("⚠️ json.loads: %s", exc)

    # Fallback: regex-извлечение по шаблонам
    logger.info("🔧 Regex-извлечение...")
    qs = []
    for qm, om, cm in zip(
        re.finditer(r'"question"\s*:\s*"((?:[^"\\]|\\.)*)"', raw),
        re.finditer(r'"options"\s*:\s*\[([\s\S]*?)\]', raw),
        re.finditer(r'"correct"\s*:\s*(\d+)', raw),
    ):
        q_text  = qm.group(1).replace('\\"', '"')
        options = [o.replace('\\"', '"') for o in re.findall(r'"((?:[^"\\]|\\.)*)"', om.group(1))]
        correct = int(cm.group(1))
        if q_text and len(options) >= 2:
            qs.append({"question": q_text, "options": options, "correct": correct})

    if qs:
        logger.info("✅ Regex: %d вопросов", len(qs))
        return qs

    raise ValueError(f"Не удалось разобрать ответ GigaChat: {raw[:100]!r}")

# ── Валидация и фильтрация вопросов ─────────────────────────

# Паттерны мусорных/проблемных вопросов
_BAD_PATTERNS = [
    r'^\s*вопрос\s*\d*\s*[:\?]?\s*$',   # просто "Вопрос 1:"
    r'^\s*\.{3,}\s*$',                    # "..."
    r'^\s*$',                              # пустая строка
]

def _is_bad_question(q: dict, num_options: int) -> bool:
    text = q.get("question", "")
    # Слишком короткий вопрос (менее 10 символов)
    if len(text.strip()) < 10:
        return True
    # Вопрос по мусорному паттерну
    for p in _BAD_PATTERNS:
        if re.match(p, text, re.IGNORECASE):
            return True
    # Одинаковые варианты ответов
    opts = q.get("options", [])
    if len(set(str(o).strip().lower() for o in opts)) < len(opts):
        return True
    # Пустые варианты
    if any(not str(o).strip() for o in opts):
        return True
    return False

def _fix_and_validate(q: dict, num_options: int) -> dict | None:
    """Возвращает исправленный вопрос или None если вопрос безнадёжно плохой."""
    q = q.copy()

    # Проверяем текст вопроса
    if not isinstance(q.get("question"), str) or not q["question"].strip():
        return None

    # Исправляем варианты ответов
    opts = q.get("options", [])
    if not isinstance(opts, list):
        return None
    opts = [str(o).strip() for o in opts if str(o).strip()]
    opts = opts[:num_options]
    if len(opts) < 2:
        return None
    while len(opts) < num_options:
        opts.append(f"Вариант {chr(65 + len(opts))}")
    q["options"] = opts

    # Исправляем индекс правильного ответа
    c = q.get("correct", 0)
    try:
        c = int(c)
    except (ValueError, TypeError):
        c = 0

    # GigaChat часто даёт нумерацию с 1 (1,2,3,4) вместо 0-based
    corrects_in_batch = None  # будет проверено в _fix_indexing на уровне батча
    if c < 0 or c >= num_options:
        logger.warning("⚠️ correct=%d вне диапазона для '%s...' — сбрасываю в 0", c, q["question"][:40])
        c = 0
    q["correct"] = c

    # Финальная проверка на мусор
    if _is_bad_question(q, num_options):
        logger.warning("⚠️ Плохой вопрос отфильтрован: '%s'", q["question"][:60])
        return None

    return q

def _fix_indexing(questions: list, num_options: int) -> list:
    """Автодетект 1-based нумерации (GigaChat часто даёт 1,2,3,4 вместо 0,1,2,3)."""
    corrects = [q["correct"] for q in questions if isinstance(q.get("correct"), int)]
    if not corrects:
        return questions
    if min(corrects) >= 1 and max(corrects) <= num_options:
        logger.info("🔧 1-based нумерация → конвертирую в 0-based")
        for q in questions:
            if isinstance(q.get("correct"), int):
                q["correct"] -= 1
    return questions

# ── GigaChat ─────────────────────────────────────────────────

def _call_gigachat(topic: str, count: int, difficulty: str, num_options: int) -> list:
    creds = os.getenv("GIGACHAT_CREDENTIALS", "")
    scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    model = os.getenv("GIGACHAT_MODEL", "GigaChat")
    if not creds:
        raise RuntimeError("GIGACHAT_CREDENTIALS не задан в .env")

    from gigachat import GigaChat
    from gigachat.models import Chat, Messages, MessagesRole

    prompt = build_prompt(topic, count, difficulty, num_options)
    logger.info("📤 GigaChat | %s | тема=%s | кол-во=%d", model, topic, count)

    with GigaChat(credentials=creds, scope=scope, model=model, verify_ssl_certs=False) as gc:
        resp = gc.chat(Chat(messages=[Messages(role=MessagesRole.USER, content=prompt)]))

    text = resp.choices[0].message.content
    logger.info("📥 Ответ: %d символов", len(text))
    return _parse_response(text, num_options)

# ── Fallback банк ────────────────────────────────────────────

_FALLBACK = [
    {"question": "Сколько планет в Солнечной системе?",        "options": ["6","7","8","9"],                                "correct": 2},
    {"question": "Химический символ золота?",                   "options": ["Ag","Fe","Au","Cu"],                            "correct": 2},
    {"question": "Год Октябрьской революции в России?",         "options": ["1905","1914","1917","1922"],                    "correct": 2},
    {"question": "Столица Австралии?",                          "options": ["Сидней","Мельбурн","Канберра","Брисбен"],       "correct": 2},
    {"question": "Кто написал «Войну и мир»?",                  "options": ["Достоевский","Толстой","Тургенев","Чехов"],     "correct": 1},
    {"question": "Основной газ атмосферы Земли?",               "options": ["Кислород","Углекислый газ","Аргон","Азот"],     "correct": 3},
    {"question": "Самый лёгкий металл?",                        "options": ["Алюминий","Литий","Магний","Натрий"],           "correct": 1},
    {"question": "Год первого полёта человека в космос?",       "options": ["1957","1959","1961","1965"],                    "correct": 2},
    {"question": "Самая длинная река в мире?",                  "options": ["Амазонка","Нил","Янцзы","Миссисипи"],           "correct": 1},
    {"question": "Сколько костей у взрослого человека?",        "options": ["186","206","226","246"],                        "correct": 1},
    {"question": "Столица Японии?",                             "options": ["Осака","Токио","Киото","Хиросима"],             "correct": 1},
    {"question": "Кто написал «Мастер и Маргарита»?",           "options": ["Достоевский","Булгаков","Пастернак","Есенин"],  "correct": 1},
    {"question": "Скорость света в вакууме (км/с)?",            "options": ["100 000","200 000","300 000","400 000"],        "correct": 2},
    {"question": "Сколько сторон у правильного шестиугольника?","options": ["4","5","6","7"],                                "correct": 2},
    {"question": "В каком году Гагарин полетел в космос?",      "options": ["1957","1959","1961","1963"],                    "correct": 2},
]

# ── Публичный API ────────────────────────────────────────────

def generate_questions(topic: str, count: int, difficulty: str, num_options: int) -> list:
    if os.getenv("GIGACHAT_CREDENTIALS"):
        try:
            raw_qs = _call_gigachat(topic, count, difficulty, num_options)
            raw_qs = _fix_indexing(raw_qs, num_options)
            qs = [_fix_and_validate(q, num_options) for q in raw_qs]
            qs = [q for q in qs if q is not None]
            if qs:
                logger.info("✅ Итого после фильтрации: %d вопросов (было %d)", len(qs), len(raw_qs))
                return qs
            logger.warning("⚠️ Все вопросы отфильтрованы — fallback")
        except Exception as e:
            logger.warning("⚠️ GigaChat ошибка: %s — fallback", e)

    logger.warning("⚠️ Используется встроенный банк вопросов")
    pool = _FALLBACK * (count // len(_FALLBACK) + 1)
    qs = random.sample(pool, min(count, len(pool)))
    return [_fix_and_validate(q, num_options) or q for q in qs]

def active_backend() -> str:
    return "GigaChat (Сбербанк) ✅" if os.getenv("GIGACHAT_CREDENTIALS") else "Fallback (встроенный банк)"
