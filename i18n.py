"""Тексты утилиты на двух языках: статусы, журнал и фразы голоса (тексты окна — в ui_texts.js)."""

LANGS = ("ru", "en")
_lang = "en"     # главный язык — английский

# ключ -> (русский, английский)
TEXTS = {
    # ---------- статусы на пульте
    "st.whisper_start": ("Запускаю Whisper…", "Starting Whisper…"),
    "st.standard": ("Штатный режим", "Standard mode"),
    "st.error": ("Ошибка: %s", "Error: %s"),
    "st.voice_stopped": ("Голос остановлен", "Voice stopped"),
    "st.no_focus": ("В Orca нет вкладки в фокусе", "No focused tab in Orca"),
    "st.orca_error": ("Ошибка Orca: %s", "Orca error: %s"),
    "st.key_space": ("␣ пробел", "␣ Space"),
    "st.key_enter": ("⏎ Enter", "⏎ Enter"),
    "st.no_other_tab": ("Нет другой вкладки с агентом", "No other agent tab"),
    "st.switched": ("⇄ вкладка → %s / %s", "⇄ tab → %s / %s"),
    "st.live_connecting": ("Режим OpenAI: подключаюсь…", "OpenAI mode: connecting…"),
    "st.live_talk": ("Режим OpenAI: говорите", "OpenAI mode: speak"),
    "st.live_error": ("OpenAI: ошибка %s", "OpenAI: error %s"),
    "st.whisper_restarting": ("Перезапускаю Whisper…", "Restarting Whisper…"),
    "st.whisper_restarted": ("Whisper перезапущен", "Whisper restarted"),

    # ---------- журнал
    "log.killed_previous": ("остановлен прошлый запуск (pid %s)", "stopped the previous run (pid %s)"),
    "log.boot_failed": ("запуск не удался", "startup failed"),
    "log.exit": ("выход", "exit"),
    "log.junk": ("мусор Whisper пропущен: %r", "Whisper noise skipped: %r"),
    "log.heard_typing": ("услышано (ввод): %r", "heard (typing): %r"),
    "log.heard": ("услышано: %r -> %s", "heard: %r -> %s"),
    "log.heard_long": ("услышано (длинная речь): %r -> %s", "heard (long speech): %r -> %s"),
    "log.skipped_after_mode": ("пропущено сразу после смены режима: %r", "skipped right after the mode change: %r"),
    "log.voice_stopped": ("голос остановлен командой", "voice stopped by command"),
    "log.typed": ("напечатано %r", "typed %r"),
    "log.sent": ("отправлено %s в %s (%s)", "sent %s to %s (%s)"),
    "log.switched": ("переключено на %s (%s)", "switched to %s (%s)"),
    "log.live_on": ("режим OpenAI: включён", "OpenAI mode: on"),
    "log.live_off": ("режим OpenAI: выключен (%s)", "OpenAI mode: off (%s)"),
    "log.live_typing": ("OpenAI (ввод): %r", "OpenAI (typing): %r"),
    "log.typing_on": ("голосовой ввод текста: включён", "voice typing: on"),
    "log.typing_off": ("голосовой ввод текста: выключен", "voice typing: off"),
    "log.settings_saved": ("настройки сохранены", "settings saved"),
    "log.whisper_restart": ("перезапуск whisper", "whisper restart"),
    "log.language": ("язык окна: %s", "interface language: %s"),
    "log.mic_open": ("микрофон открыт", "microphone opened"),
    "log.live_crash": ("live: сбой", "live: crashed"),
    "log.live_call": ("live: звонок %s", "live: call %s"),
    "log.reading": ("читаю ответ %s (%d симв.)", "reading the %s answer (%d chars)"),
    "log.agent_waiting": ("агент %s ждёт ответа (%s)", "agent %s is waiting for a reply (%s)"),
    "log.whisper_starting": ("whisper-server: старт %s", "whisper-server: starting %s"),
    "log.whisper_ready": ("whisper-server готов на порту %s", "whisper-server is ready on port %s"),
    "log.settings_url": ("окно: %s", "window: %s"),
    "log.settings_error": ("настройки: %s", "settings: %s"),

    # ---------- почему выключился режим OpenAI
    "why.exit": ("выход", "exit"),
    "why.toggle": ("переключение", "switched"),
    "why.timeout": ("время вышло", "time is up"),
    "why.error": ("ошибка", "error"),
    "why.closed": ("соединение закрыто", "connection closed"),

    # ---------- ошибки
    "err.unknown_action": ("неизвестное действие %s", "unknown action %s"),
    "err.bad_command": ("неверная команда %s", "invalid command %s"),
    "err.bad_language": ("неизвестный язык %s", "unknown language %s"),
    "err.not_found": ("нет такого адреса", "no such address"),
    "err.no_codex_login": ("Нет входа в Codex через ChatGPT (codex login)", "Not signed in to Codex with ChatGPT (codex login)"),
    "err.live": ("ошибка GPT-Live", "GPT-Live error"),
    "err.live_no_call": ("GPT-Live не вернул звонок", "GPT-Live did not return a call"),
    "err.no_whisper": ("не найден whisper-server (brew install whisper-cpp)", "whisper-server not found (brew install whisper-cpp)"),
    "err.no_model": ("не найдена модель Whisper: %s", "Whisper model not found: %s"),
    "err.whisper_crashed": ("whisper-server упал при старте (код %s)", "whisper-server crashed on start (code %s)"),
    "err.whisper_timeout": ("whisper-server не поднялся за 60 с", "whisper-server did not start within 60 s"),
    "err.orca_not_json": ("не JSON", "not JSON"),

    # ---------- фразы голоса
    "say.code": (" блок кода пропущен. ", " code block skipped. "),
    "say.link": (" ссылка ", " link "),
    "say.cut": (". Обрезка.", ". Cut off."),
    "say.waiting": ("Агент ждёт вашего ответа.", "The agent is waiting for your reply."),
    "say.test": ("Привет! Так я буду читать ответы агентов.", "Hi! This is how I will read the agents' answers."),
}


def set_lang(lang):
    global _lang
    _lang = lang if lang in LANGS else "en"


def get_lang():
    return _lang


def t(key, *args):
    """Текст на текущем языке; args подставляются через %."""
    text = TEXTS[key][LANGS.index(_lang)]
    return text % args if args else text
