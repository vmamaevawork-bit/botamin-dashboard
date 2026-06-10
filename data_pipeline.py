"""
Обработка выгрузки звонков Botamin -> признаки для дашборда аналитика.

Логика разметки шагов опирается на то, что скрипт бота шаблонный:
определяем максимальный шаг воронки, до которого ДОШЁЛ разговор,
по маркерам в репликах бота. Причину обрыва на шаге 1 и тип реакции
клиента размечаем эвристиками по тексту клиента. Всё детерминировано
и воспроизводимо (без обращения к LLM); при наличии файла llm_labels.csv
его метки подмешиваются опционально.
"""
import re
import pandas as pd


SUBCATEGORY_ALIASES = {
    "Непонимание / связь": "Связь / не понял бота",
    "Не интересно / не актуально": "Не интересно / отказ",
    "Клиент отказался, разговор завершил бот": "Не интересно / отказ",
    "Клиент замолчал, бот завершил": "Не интересно / отказ",
    "Не профиль / не наш бизнес": "Не интересно / отказ",
    "Не интересно": "Не интересно / отказ",
}


def canonicalize_subcategory(label):
    """Приводит исторические варианты подкатегорий к одному имени."""
    if label is None:
        return None
    return SUBCATEGORY_ALIASES.get(label, label)

# ---- Маркеры шагов в репликах БОТА (скрипт шаблонный) -----------------------
STEP_MARKERS = {
    1: [r"добрый день", r"Звоню насч[её]т", r"Тридцать секунд"],
    2: [r"запускаем ИИ-продавца", r"Это Лариса", r"бата[мМ]ин",
        r"это к вам вопрос или к коммерческ", r"первую линию продаж"],
    3: [r"удобно созвониться", r"созвониться с нашим экспертом", r"с нашим экспертом",
        r"по видеосвязи", r"во сколько вам", r"зафиксируем", r"назначим"],
    4: [r"база в месяц на прозвон", r"сколько тысяч", r"обычно база",
        r"тысяч контактов", r"какая у вас обычно база"],
}
STEP_NAMES = {
    0: "0 · Нет приветствия",
    1: "1 · Приветствие + согласие",
    2: "2 · Оффер",
    3: "3 · Встреча",
    4: "4 · Квалификация",
}

# ---- Эвристики реакции клиента ---------------------------------------------
OBJECTION_RULES = [
    ("Согласие слушать", r"\b(слушаю|да,? слушаю|говорите|давайте|конечно|рассказывайте|внимательн)"),
    ("Нет времени / некогда", r"(некогда|нет времени|не до|занят|за рул[её]м|на встрече|перезвон|позже|потом|неудобно сейчас)"),
    ("Не интересно / отказ", r"(не интересно|неинтересно|не нужно|не надо|нет,? спасибо|отказ|не хочу|не буду|спам)"),
    ("Уже есть / используем", r"(уже есть|уже используем|у нас есть|есть свой|сами справля|не первый раз звон)"),
    ("Непонимание / переспрос", r"(\bчто\?|что это|кто это|не пон|повтор|ещ[её] раз|не слыш|алло)"),
    ("Кто говорит / робот?", r"(это робот|вы робот|автоответ|с кем говорю|это бот)"),
    ("Грубость / негатив", r"(отстаньте|надоели|достали|не звоните|идите|блокир)"),
]


def dur_to_sec(s):
    s = (s or "").strip()
    if not s or ":" not in s:
        return None
    try:
        m, sec = s.split(":")
        return int(m) * 60 + int(sec)
    except Exception:
        return None


def parse_turns(text):
    """Список (speaker, utterance) из истории диалога."""
    if not text:
        return []
    parts = re.split(r"(?im)(?:^|\n)\s*(bot|user)\s*:\s*", text)
    turns = []
    # parts: ['', 'bot', 'text', 'user', 'text', ...]
    for i in range(1, len(parts) - 1, 2):
        spk = parts[i].lower()
        utt = parts[i + 1].strip()
        turns.append((spk, utt))
    return turns


def is_real_user_text(u):
    """Клиент реально что-то сказал, а не молчал (user: ...)."""
    u = (u or "").strip()
    if not u:
        return False
    stripped = u.strip(".… ")
    return len(stripped) > 0


def reached_step(text):
    """Максимальный шаг, до которого дошёл разговор (по репликам бота)."""
    if not text or not text.strip():
        return 0
    bot_text = "\n".join(u for spk, u in parse_turns(text) if spk == "bot")
    if not bot_text:
        bot_text = text
    step = 0
    for s in [1, 2, 3, 4]:
        if any(re.search(p, bot_text, re.I) for p in STEP_MARKERS[s]):
            step = s
    # шаг не может «перепрыгнуть»: если есть s, считаем что прошли и предыдущие
    return step


def extract_industry(text):
    """Отрасль из оффера: 'есть кейс по {Отрасль}, хотела показать'."""
    if not text:
        return None
    m = re.search(r"кейс по\s+(.*?)\s*,\s*хотела показать", text)
    if m:
        return m.group(1).strip() or "<ПУСТО>"
    if re.search(r"кейс по\s*,", text):
        return "<ПУСТО>"
    return None


def step1_outcome(text, reason, reached):
    """Что произошло на «обрыве» шага 1 — ключ к главной утечке."""
    if not text or not text.strip():
        return "Нет диалога (мгновенный сброс/АО)"
    turns = parse_turns(text)
    user_turns = [u for spk, u in turns if spk == "user"]
    real = [u for u in user_turns if is_real_user_text(u)]
    if reached >= 2:
        return "Дошёл до оффера+"
    if not user_turns:
        return "Сброс на приветствии (клиент не ответил)"
    if not real:
        return "Молчание (user: ...)"
    return "Ответил, но сорвался на шаге 1"


def classify_objection(text):
    """Тип первой содержательной реакции клиента (rule-based)."""
    turns = parse_turns(text)
    user_real = [u for spk, u in turns if spk == "user" and is_real_user_text(u)]
    if not user_real:
        return None
    joined = " ".join(user_real).lower()
    for name, pat in OBJECTION_RULES:
        if re.search(pat, joined, re.I):
            return canonicalize_subcategory(name)
    return canonicalize_subcategory("Другое / нейтрально")


def _user_joined(text):
    return " ".join(u for s, u in parse_turns(text) if s == "user" and is_real_user_text(u)).lower()


# ---- Детектор автоответчиков / машин (по репликам клиента) -----------------
# В данных нет классической голосовой почты — «машины» это операторские
# сервисы и виртуальные секретари. Слово «абонент» в реплике клиента —
# почти стопроцентный признак автоматики (живой человек так о себе не говорит).
MACHINE_RULES = [
    ("Виртуальный секретарь",
     r"общаетесь с секретар|на связи секретар|передам ему|передать.{0,15}сообщени|"
     r"продиктуйте сообщени|записал[а]? ваше сообщени|написала абонент|"
     r"мы перезвоним абонент|если что,? (вам|с вами) (перезвон|свяж)|"
     r"справитс[яь].{0,20}секретар|дождитесь ответа.{0,20}секретар|"
     r"чем могу помочь|благодарим вас за звонок в офис"),
    ("Абонент недоступен/занят",
     r"вне зоны|отключ[её]н|не в сети|недоступен|в данный момент абонент|"
     r"к сожалению абонент|абонент.{0,30}(разговаривает|занят|по другой линии|"
     r"не бер[её]т|не отвеч|не ответил|не закончил|не смож|не смог|сейчас не)"),
    ("Антиспам / отклонение",
     r"отказал.{0,15}получать.{0,15}(массов|вызов)|звонок будет отклон|будет отклон[её]н"),
    ("Голосовая почта",
     r"оставьте.{0,15}сообщени|после (звукового )?сигнал|голосов.{0,3} почт|автоответчик"),
    ("IVR-меню (нажмите N)",
     r"нажмите \d|нажмите кнопк|наберите.{0,20}в тоновом режиме|"
     r"наберите цифру|кнопк[еаи].{0,5}\d|внутренний номер"),
    ("Маркер «абонент»", r"\bабонент"),
]


NOBOOK_RULES = [
    ("Нет времени / перезвонить позже", r"некогда|нет времени|занят|за рул|перезвон|позже|потом|неудобно"),
    ("Не интересно / не актуально", r"не интересн|неинтересн|не нужно|не надо|не актуальн|не хочу|спам"),
    ("Уже есть решение", r"уже есть|используем|свой|сами справ|не первый раз"),
    ("Цена / невыгодно", r"невыгодн|дорог|\bцена\b|сколько стоит|бесплатн"),
    ("Непонимание / связь", r"\bчто\b|не слыш|повтор|алло|подвис|пропада"),
    ("Надо подумать", r"подума|не готов|не знаю|сложно сказать"),
]


def nobook_reason(text, reason, gave_contact_flag):
    """Причина, почему услышавший оффер не назначил встречу."""
    if gave_contact_flag:
        return canonicalize_subcategory("Не ЛПР / переадресация")
    t = _user_joined(text)
    if reason == "bot_hangup":
        # Не считаем это «нашей ошибкой» по умолчанию: сначала отсеиваем
        # явный отказ клиента и другие читаемые сценарии.
        for name, pat in NOBOOK_RULES:
            if re.search(pat, t):
                if name == "Непонимание / связь":
                    return canonicalize_subcategory(name)
                return canonicalize_subcategory("Клиент отказался, разговор завершил бот")
        if bot_silent(text):
            return canonicalize_subcategory("Молчание бота / dead air")
        if detect_bot_loop(text):
            return canonicalize_subcategory("Зацикливание / ошибка логики")
        if re.search(r"\bкоммерческ|\bдиректор|кто.*отвечает|не я|другому", t):
            return canonicalize_subcategory("Не ЛПР / переадресация")
        if re.search(r"\.\.\.|…", text):
            return canonicalize_subcategory("Клиент замолчал, бот завершил")
        return canonicalize_subcategory("Бот сам завершил без явной причины")
    for name, pat in NOBOOK_RULES:
        if re.search(pat, t):
            return canonicalize_subcategory(name)
    if reason == "client_hangup":
        return canonicalize_subcategory("Клиент сам положил трубку (отказ)")
    return canonicalize_subcategory("Другое / нейтрально")


def preconsent_bot_reason(text):
    """Почему бот завершил разговор до оффера (step < 2)."""
    t = _user_joined(text)
    if bot_silent(text):
        return canonicalize_subcategory("Молчание бота / dead air")
    if detect_bot_loop(text):
        return canonicalize_subcategory("Зацикливание / ошибка логики")
    if re.search(r"(не звоните|нет,? спасибо|не надо|не нужно|не интересно|неинтересно|"
                 r"\bнет\b|отстаньте|уберите номер|не туда)", t):
        return canonicalize_subcategory("Клиент отказался, разговор завершил бот")
    if re.search(r"(не слыш|не пон|что\?|алло|повтор|связ|шум)", t):
        return canonicalize_subcategory("Связь / не понял бота")
    # Молчание клиента после опенера часто закрывается вежливой репликой бота.
    if any(s == "user" and (not u.strip() or set(u.strip()) <= set(".… ")) for s, u in parse_turns(text)):
        return canonicalize_subcategory("Клиент молчит, бот завершил")
    if re.search(r"\b(да|слушаю|говорите|давайте|конечно)\b", t):
        return canonicalize_subcategory("Бот завершил после согласия клиента")
    return canonicalize_subcategory("Бот вежливо завершил после реакции клиента")


_SCHEDULE_PAT = (
    r"(сегодня|завтра|в понедельник|во вторник|в среду|в четверг|в пятницу|в субботу|"
    r"в воскресенье|на следующей неделе|утром|вечером|после обеда|к обеду|"
    r"в первой половине дня|во второй половине дня|ближе к обеду|"
    r"\b\d{1,2}:\d{2}\b|\bв\s*\d{1,2}\b|\bчас[ао]?\b|"
    r"\b\d{1,2}[- ]?(го|ого)? числа\b|пятого июня|первого числа|"
    r"звоните завтра|перезвоните завтра|давайте .*завтра)"
)


def meeting_booked(text, reached):
    """Похоже ли, что встречу/созвон действительно зафиксировали."""
    if reached < 3:
        return False
    if reached >= 4:
        return True
    turns = parse_turns(text)
    in_meeting = False
    for spk, utt in turns:
        low = (utt or "").lower()
        if spk == "bot" and re.search(
                r"(удобно созвониться|в какое время|во сколько|на какой день|"
                r"созвониться с нашим экспертом|по видеосвязи|назначим|зафиксируем)", low, re.I):
            in_meeting = True
            continue
        if in_meeting and spk == "user" and is_real_user_text(utt):
            if re.search(r"(неудобно|не могу|не смогу|неинтересно|не надо|не нужно|подумаю)", low, re.I):
                continue
            if re.search(_SCHEDULE_PAT, low, re.I):
                return True
    return False


def script_offscript(text):
    """Бот произнёс приветствие не по скрипту (есть «Тридцать секунд», но нет оффера про ИИ)."""
    for s, u in parse_turns(text):
        if s == "bot" and re.search(r"тридцать секунд", u, re.I):
            return not bool(re.search(r"искусственн", u, re.I))
    return False


def bot_silent(text):
    """Бот выдал пустую реплику (молчание/dead air): 'bot: ...' без слов."""
    for s, u in parse_turns(text):
        if s == "bot" and (not u.strip() or set(u.strip()) <= set(".… ")):
            return True
    return False


_AO_IVR = (r"вас приветствует|разговор может быть запис|оставьте сообщение|автоответчик|"
           r"после сигнала|вызываемый абонент|записывается")


def ao_missed(text):
    """Бот не распознал автоответчик: в репликах клиента фразы IVR/АО."""
    txt = " ".join(u for s, u in parse_turns(text) if s == "user").lower()
    return bool(re.search(_AO_IVR, txt))


def bot_error_type(row):
    """Доминирующий тип ошибки бота в звонке (или None)."""
    if row["script_offscript"]:
        return "Не по скрипту"
    if row["industry_bug"]:
        return "Баг: пустая отрасль в оффере"
    if row["bot_silent"]:
        return "Молчание бота (пустая реплика)"
    if row["ao_missed"] and row["reached_step"] >= 2:
        return "Не распознал автоответчик"
    if row["bot_loop"]:
        return "Зацикливание / повтор"
    return None


OFFER_REFUSE_RULES = [
    ("Грубость / агрессия", r"на ?хуй|нахуй|заеба|пош(ёл|ла) ты|идите вы|долбан|отстань|достал"),
    ("Не профиль / не наш бизнес",
     r"не работаем|не занимаемся|не наш|нет продаж|нет клиентск|не по адресу|не участву|"
     r"не та сфера|компания (закрыв|почти закрыв)|ничего не прода|не туда|не моя сфера|нет базы"),
    ("Уже есть решение", r"уже есть|уже использ|сами справ|такой робот стоит|свой робот|уже.*робот"),
    ("Скепсис к ИИ / «это робот?»",
     r"это робот|вы робот|с роботом|искусственн.*(не|ещё не|нелья)|разговаривать с искусственн|"
     r"робот.*(не может|как)|не вышел на"),
    ("Кто звонит / откуда номер",
     r"кто вы|вы кто|откуда.*(телефон|номер)|где.*телефон взял|с кем.*разговар|куда.*звон|по какому"),
    ("Неудобно / поздно / перезвонить",
     r"поздно звон|командировк|\bзанят|завтра|перезвон|позже|неудобно|рабочее время|сейчас не мог"),
    ("Не интересно", r"не интересн|неинтересн|не нужно|не интересует|не надо|не заинтерес"),
]


def _after_offer_user(text):
    seen, out = False, []
    for s, u in parse_turns(text):
        if s == "bot" and re.search(r"запускаем ИИ-продавца|это к вам вопрос или к коммерч|"
                                    r"первую линию продаж", u, re.I):
            seen = True
            continue
        if seen and s == "user" and is_real_user_text(u):
            out.append(u.strip())
    return out


def offer_refuse_reason(text):
    """Почему клиент отказался идти дальше после оффера."""
    after = _after_offer_user(text)
    joined = " ".join(after).lower()
    if not joined.strip():
        return canonicalize_subcategory("Молча бросил трубку")
    for name, pat in OFFER_REFUSE_RULES:
        if re.search(pat, joined):
            return canonicalize_subcategory(name)
    return canonicalize_subcategory("Другое / нейтрально")


def qual_answered(text):
    """Этап 4: клиент дал реальный ответ на квалификационный вопрос бота."""
    asked = False
    for spk, utt in parse_turns(text):
        if spk == "bot" and re.search(
                r"база в месяц|сколько тысяч|обычно база|тысяч контакт", utt, re.I):
            asked = True
            continue
        if asked and spk == "user":
            u = utt.strip(".… ")
            if u and not re.search(r"^(что|не слыш|алло|повтор|а\?)", u, re.I):
                return True
    return False


def detect_machine(text, reason=None):
    """Тип автоответчика/машины или None (живой/неопределимо)."""
    if reason == "answering_machine":
        return "Флаг телефонии"
    ut = " ".join(u for spk, u in parse_turns(text) if spk == "user").lower()
    if not ut:
        return None
    for name, pat in MACHINE_RULES:
        if re.search(pat, ut):
            return name
    return None


def detect_bot_loop(text):
    """Бот зацикливается / списывает на 'связь' живого собеседника."""
    turns = parse_turns(text)
    bot = [u for spk, u in turns if spk == "bot"]
    user_real = any(is_real_user_text(u) for spk, u in turns if spk == "user")
    # повтор почти идентичных подряд реплик бота
    rep = any(_similar(bot[i], bot[i + 1]) for i in range(len(bot) - 1))
    # списал на связь, хотя клиент говорил
    conn_excuse = bool(re.search(r"(связь.*подвис|пропада.*связь|не слыш|вы меня слышите)", text, re.I))
    return bool(rep or (conn_excuse and user_real and len(turns) >= 4))


def _similar(a, b):
    a2 = re.sub(r"[^а-яё ]", "", (a or "").lower())
    b2 = re.sub(r"[^а-яё ]", "", (b or "").lower())
    if not a2 or not b2:
        return False
    sa, sb = set(a2.split()), set(b2.split())
    if not sa or not sb:
        return False
    return len(sa & sb) / max(len(sa | sb), 1) > 0.7


TECH_REASONS = {"no_answer", "queue_timeout", "bad_number", "answering_machine",
                "network_error", "no_user_speech", "elevenlabs_hangup", "hangup"}

# причины «никто не взял трубку» (соединения не было)
NOPICKUP_REASONS = {"no_answer", "queue_timeout", "bad_number", "network_error"}

# взаимоисключающие ветки воронки (после «взяли трубку»)
BRANCHES = [
    "Не взяли трубку",
    "АО / автоматика",
    "Короткий отказ",
    "Отвал до оффера (1 этап)",
    "Оффер → отказ (informed)",
    "Встреча (успех)",
    "Квалификация (успех)",
]


# порог: приветствие занимает ~12с; за 19с клиент успевает услышать 1-е предложение
STAGE1_MIN_SEC = 19


def funnel_branch(row):
    """Единственная ветка воронки для звонка (после набора)."""
    if row["reason"] in NOPICKUP_REASONS:
        return "Не взяли трубку"
    if row["is_ao"]:
        return "АО / автоматика"
    if row["reached_step"] >= 4:
        return "Квалификация (успех)"
    if row["reached_step"] >= 3:
        return "Встреча (успех)"
    if row["reached_step"] >= 2:
        return "Оффер → отказ (informed)"
    # живой человек, до оффера не дошёл — делим по длительности:
    if (row["dur_sec"] or 0) < STAGE1_MIN_SEC:
        return "Короткий отказ"     # не успел услышать 1-е предложение
    return "Отвал до оффера (1 этап)"              # прослушал предложение, потом сбросил


def load_and_process(path):
    df = pd.read_csv(path)
    df = df.rename(columns={
        "телефон": "phone",
        "дата и время": "dt_raw",
        "длительность мин:сек": "dur_raw",
        "статус": "status",
        "запись аудио": "audio",
        "причина завершения": "reason",
        "история диалога юзер-бот": "dialog",
    })
    df["dialog"] = df["dialog"].fillna("")
    df["reason"] = df["reason"].fillna("<пусто>")

    df["dt"] = pd.to_datetime(df["dt_raw"], errors="coerce")
    df["date"] = df["dt"].dt.date
    df["hour"] = df["dt"].dt.hour
    df["weekday"] = df["dt"].dt.dayofweek  # 0=Mon
    df["weekday_name"] = df["dt"].dt.day_name()

    df["dur_sec"] = df["dur_raw"].apply(dur_to_sec)

    df["has_dialog"] = df["dialog"].str.strip().str.len() > 0
    df["n_turns"] = df["dialog"].apply(lambda t: len(parse_turns(t)))
    df["n_user_real"] = df["dialog"].apply(
        lambda t: sum(1 for spk, u in parse_turns(t) if spk == "user" and is_real_user_text(u)))
    df["engaged"] = df["n_user_real"] > 0

    df["reached_step"] = df["dialog"].apply(reached_step)
    df["reached_step_name"] = df["reached_step"].map(STEP_NAMES)
    df["qual_answered"] = df["dialog"].apply(qual_answered) & (df["reached_step"] >= 4)
    df["step1_outcome"] = df.apply(
        lambda r: step1_outcome(r["dialog"], r["reason"], r["reached_step"]), axis=1)
    df["objection"] = df["dialog"].apply(classify_objection)
    df["negative"] = df["objection"].isin(["Грубость / негатив", "Не интересно / отказ"])
    df["industry"] = df["dialog"].apply(extract_industry)
    df["industry_bug"] = df["industry"] == "<ПУСТО>"
    df["script_offscript"] = df["dialog"].apply(script_offscript)
    df["bot_loop"] = df["dialog"].apply(detect_bot_loop)
    df["bot_silent"] = df["dialog"].apply(bot_silent)
    df["ao_missed"] = df["dialog"].apply(ao_missed)
    df["bot_error_type"] = df.apply(bot_error_type, axis=1)
    df["has_bot_error"] = df["bot_error_type"].notna()

    # автоответчики / машины
    df["machine_type"] = df.apply(lambda r: detect_machine(r["dialog"], r["reason"]), axis=1)
    df["is_machine"] = df["machine_type"].notna()                      # подтв. по тексту
    # Быстрое AMD-правило: если за 1-4 сек клиент не дал ни одной реальной реплики,
    # считаем это автоответчиком/автоматикой, даже если в логе остались `user: ...`.
    df["amd_suspect"] = ((df["reason"] == "bot_hangup")
                         & df["dur_sec"].between(1, 4, inclusive="both")
                         & (df["n_user_real"] == 0))
    # вероятная «молчаливая автоматика»: до оффера не дошли, бот завершил звонок,
    # а клиент не дал ни одной реальной реплики. Сюда попадают и случаи с `user: ...`,
    # которые по аудио звучат как IVR / автоответчик / секретарь.
    df["silent_ao_suspect"] = ((df["reason"] == "bot_hangup")
                               & (df["reached_step"] < 2)
                               & (df["dur_sec"].fillna(0) > 4)
                               & (df["n_user_real"] == 0)
                               & ~df["is_machine"])
    # структурный бот-бот: долго (>=45с), но клиент почти молчит (<=1 реплики), оффер не дошёл
    # ловит «робот-робот» 2-10 мин, которые по тексту не видны
    df["bot_bot_struct"] = ((df["dur_sec"].fillna(0) >= 45) & (df["n_user_real"] <= 1)
                            & (df["reached_step"] < 2) & ~df["is_machine"] & ~df["amd_suspect"]
                            & ~df["silent_ao_suspect"])
    # сводный признак «не живой человек»
    df["is_ao"] = df["is_machine"] | df["amd_suspect"] | df["silent_ao_suspect"] | df["bot_bot_struct"]
    # «разговор бот-бот» = был обмен репликами с автоматикой (без чистого АО-сброса)
    df["is_botbot"] = df["is_machine"] | df["bot_bot_struct"]

    # бот сбросил живого, который хотел продолжить: последнее слово за клиентом,
    # он вовлечён, не отказывался и не прощался, а бот завершил звонок
    _closing = (r"спасибо|до свидан|всего (доброго|хорошего)|хорошего дня|"
                r"\bпока\b|не интересно|не нужно|не надо|не буду")

    def _dropped(row):
        if (row["reason"] != "bot_hangup" or not row["engaged"] or row["negative"]
                or row["is_ao"] or row["reached_step"] >= 3):
            return False
        turns = parse_turns(row["dialog"])
        if not turns:
            return False
        spk, utt = turns[-1]
        if spk != "user" or not is_real_user_text(utt):
            return False
        return not re.search(_closing, utt, re.I)

    df["bot_dropped_willing"] = df.apply(_dropped, axis=1)

    # клиент выразил согласие слушать (ответ на приветствие)
    _consent_re = (r"\b(да|ладно|говорите|говори|давайте|давай|слушаю|слушаю вас|"
                   r"конечно|рассказывайте|продолжайте|хорошо|можно|интересно|внимательно)\b")
    df["said_consent"] = df["dialog"].apply(
        lambda t: any(spk == "user" and is_real_user_text(u) and re.search(_consent_re, u, re.I)
                      for spk, u in parse_turns(t)))
    # клиент явно отказался (чтобы не путать с согласием)
    _refuse_re = (r"(\bнет\b|не звоните|не надо|не нужно|не интересн|неинтересн|уберите|"
                  r"не хочу|отстаньте|долбан|идите|не работаем|не занимаемся|у нас нет|"
                  r"у вас нет|не подходит|\bне буду\b)")
    df["refused"] = df["dialog"].apply(
        lambda t: any(spk == "user" and is_real_user_text(u) and re.search(_refuse_re, u, re.I)
                      for spk, u in parse_turns(t)))
    # клиент дал контакт другого лица / переадресовал
    _newc_re = (r"(обратит|свяжит|это к |к коммерческ|к директор|позвоните|наберите|"
                r"его номер|другому|другой человек|не я занима|не ко мне|нужен другой|"
                r"запишите (его |её )?(номер|телефон))")
    df["gave_contact"] = df["dialog"].apply(
        lambda t: any(spk == "user" and is_real_user_text(u) and re.search(_newc_re, u, re.I)
                      for spk, u in parse_turns(t)))

    # качество базы: клиент не работает в этой компании / ошиблись номером
    _nowork_re = (r"(я (тут|здесь)?\s*(больше\s*)?не работаю|не работаю (тут|здесь|там|больше)|"
                  r"уволил|не моя компания|не та компания|ошиблись номером|не туда попал|"
                  r"вы ошиблись|я не из|бывший сотрудник|давно не работаю|это не моя компан)")
    df["wrong_company"] = df["dialog"].apply(
        lambda t: any(spk == "user" and is_real_user_text(u) and re.search(_nowork_re, u, re.I)
                      for spk, u in parse_turns(t)))

    # качество базы: оффер не профиль — у компании нет продаж / не та сфера
    _notprof_re = (r"(нет отдела продаж|у нас нет продаж|не работаем с продаж|не занимаемся продаж|"
                   r"мы не прода|ничего не прода|у нас нет прода|не наш профиль|не наша сфера|"
                   r"не та сфера|не наш бизнес|нет.*клиентск.*баз|нет базы|грузоперевозк|"
                   r"на прозвон.*не работ|не работаем в этой систем|не наша тема|другая тема|не та тема)")
    df["not_profile"] = df["dialog"].apply(
        lambda t: bool(re.search(_notprof_re, " ".join(
            u for s, u in parse_turns(t) if s == "user" and is_real_user_text(u)).lower())))

    # причина неназначения встречи (только для услышавших оффер, но без встречи)
    nb = df.apply(lambda r: nobook_reason(r["dialog"], r["reason"], r["gave_contact"]), axis=1)
    df["nobook_reason"] = nb.where(df["reached_step"] == 2, other=None)
    # причина бот-обрыва до оффера
    prebot = df["dialog"].apply(preconsent_bot_reason)
    df["preconsent_bot_reason"] = prebot.where(
        (df["reached_step"] < 2) & (df["reason"] == "bot_hangup") & ~df["is_ao"],
        other=None,
    )
    # причина отказа именно на этапе оффера (для отказавшихся клиентов)
    df["offer_refuse_reason"] = df["dialog"].apply(offer_refuse_reason)
    for col in ["objection", "nobook_reason", "preconsent_bot_reason", "offer_refuse_reason"]:
        df[col] = df[col].map(canonicalize_subcategory)
    # встреча действительно зафиксирована
    df["meeting_booked"] = df.apply(lambda r: meeting_booked(r["dialog"], r["reached_step"]), axis=1)

    df["is_tech_fail"] = df["reason"].isin(TECH_REASONS)
    df["client_hangup"] = df["reason"] == "client_hangup"
    df["bot_hangup"] = df["reason"] == "bot_hangup"
    df["no_pickup"] = df["reason"].isin(NOPICKUP_REASONS)
    df["branch"] = df.apply(funnel_branch, axis=1)

    # повторные звонки на номер
    df = df.sort_values("dt")
    df["call_index"] = df.groupby("phone").cumcount() + 1
    counts = df.groupby("phone")["phone"].transform("size")
    df["is_repeat_phone"] = counts > 1
    df["is_first_call"] = df["call_index"] == 1

    # опциональные LLM-метки
    try:
        lab = pd.read_csv("llm_labels.csv")
        df = df.merge(lab, on=["phone", "dt_raw"], how="left", suffixes=("", "_llm"))
    except Exception:
        pass

    return df.reset_index(drop=True)


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else "/Users/viktoriamamaeva/Downloads/Calls Week Anon.csv"
    d = load_and_process(p)
    print("rows:", len(d))
    print("\nreached_step:\n", d["reached_step_name"].value_counts().sort_index())
    print("\nstep1_outcome:\n", d["step1_outcome"].value_counts())
    print("\nobjection (engaged):\n", d[d.engaged]["objection"].value_counts())
    print("\nindustry_bug:", int(d["industry_bug"].sum()))
    print("bot_loop:", int(d["bot_loop"].sum()))
    print("repeat phones rows:", int(d["is_repeat_phone"].sum()))
