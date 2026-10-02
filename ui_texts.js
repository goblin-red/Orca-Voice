// Тексты окна на двух языках: ключ -> [русский, английский].
// В ui.html элемент с data-i18n="ключ" получает текст на текущем языке.
// Статусы, журнал и фразы голоса переводятся в i18n.py.

const KW = (cmd) => `<span class="kw" data-cmd="${cmd}"></span>`;   // ключевое слово команды из настроек

const TEXTS = {
  // ---------- вкладки
  "tab.dash": ["Пульт", "Dashboard"],
  "tab.settings": ["Настройки", "Settings"],
  "tab.guide": ["Инструкция", "Guide"],

  // ---------- пульт
  "dash.tab": ["Вкладка", "Tab"],
  "dash.heard": ["Услышано", "Heard"],
  "dash.mic": ["Микрофон", "Microphone"],
  "dash.controls": ["Управление", "Controls"],
  "dash.controls.hint": ["Кнопки дублируют голосовые команды.", "The buttons mirror the voice commands."],
  "dash.commands": ["Голосовые команды", "Voice commands"],
  "dash.commands.hint": ["Меняются во вкладке «Настройки».", "Edit them on the Settings tab."],
  "dash.log": ["Журнал", "Log"],
  "dash.log.hint": [
    `Свежие события сверху. Полный журнал: <a href="#" data-act="log">открыть файл</a>.`,
    `Newest events on top. Full log: <a href="#" data-act="log">open the file</a>.`,
  ],

  "btn.mic": ["Микрофон", "Microphone"],
  "btn.speak": ["Озвучка ответов", "Read answers aloud"],
  "btn.mode": ["Режим", "Mode"],
  "btn.typing": ["Голосовой ввод", "Voice typing"],
  "btn.hush": ["Замолчать", "Hush"],
  "btn.hush.sub": ["остановить чтение", "stop reading"],
  "btn.space": ["Проверить ввод пробела", "Test Space"],
  "btn.enter": ["Проверить ввод Enter", "Test Enter"],
  "btn.focused": ["во вкладку в фокусе", "to the focused tab"],
  "btn.switch": ["Следующий терминал", "Next terminal"],
  "btn.switch.sub": ["вкладка с агентом, по кругу", "next agent tab, in a loop"],
  "btn.cancel": ["Отменить", "Cancel"],
  "btn.save": ["Сохранить", "Save"],

  // ---------- состояние (меняется на ходу)
  "mode.starting": ["Запуск…", "Starting…"],
  "mode.listening": ["Штатный режим", "Standard mode"],
  "mode.live": ["Режим OpenAI", "OpenAI mode"],
  "mode.speaking": ["Читаю ответ", "Reading an answer"],
  "mode.paused": ["Микрофон на паузе", "Microphone paused"],
  "mode.error": ["Ошибка", "Error"],
  "mode.offline": ["Нет связи с утилитой", "No connection to the app"],
  "mode.typing": [" · ввод текста", " · typing"],
  "mode.commands": [" · только команды", " · commands only"],

  "sub.listening": ["слушает", "listening"],
  "sub.paused": ["на паузе", "paused"],
  "sub.on": ["включена", "on"],
  "sub.off": ["выключена", "off"],
  "sub.live": ["OpenAI — нажмите для штатного", "OpenAI — click for standard"],
  "sub.standard": ["штатный — нажмите для OpenAI", "standard — click for OpenAI"],
  "sub.typing": ["речь печатается", "speech is typed"],
  "sub.commands": ["только команды", "commands only"],

  // ---------- команды
  "cmd.space.title": ["Пробел", "Space"],
  "cmd.space.desc": ["пробел во вкладку в фокусе (в обоих режимах)", "Space to the focused tab (in both modes)"],
  "cmd.enter.title": ["Enter", "Enter"],
  "cmd.enter.desc": ["Enter во вкладку в фокусе (в обоих режимах)", "Enter to the focused tab (in both modes)"],
  "cmd.switch.title": ["Следующий терминал", "Next terminal"],
  "cmd.switch.desc": [
    "следующая вкладка с агентом в активном проекте, по кругу",
    "the next agent tab in the active project, in a loop",
  ],
  "cmd.stop.title": ["Замолчать", "Hush"],
  "cmd.stop.desc": ["прерывает голос (в обоих режимах)", "interrupts the voice (in both modes)"],
  "legend.off": [" (выключено)", " (off)"],
  "chips.add": ["добавить вариант…", "add a variant…"],
  "chips.remove": ["Удалить", "Remove"],

  // ---------- сообщения внизу окна
  "msg.dirty": ["Есть несохранённые изменения", "You have unsaved changes"],
  "msg.saved": ["Сохранено и применено", "Saved and applied"],
  "msg.error": ["Ошибка: ", "Error: "],
  "msg.load_failed": ["Не удалось загрузить настройки: ", "Could not load the settings: "],

  // ---------- инструкция
  "g.start.h": ["Запуск и выход", "Starting and quitting"],
  "g.start.1": [
    `Двойной клик по <b>Orca Voice.app</b> в папке <code>orca-voice</code> (или <code>./start.sh</code>).`,
    `Double-click <b>Orca Voice.app</b> in the <code>orca-voice</code> folder (or run <code>./start.sh</code>).`,
  ],
  "g.start.2": [
    "Если утилита уже была запущена — старая копия закрывается сама.",
    "If the app is already running, the old copy closes by itself.",
  ],
  "g.start.3": [
    "Крестик окна — полный выход: микрофон, Whisper и голос выключаются.",
    "Closing the window quits everything: the microphone, Whisper and the voice are turned off.",
  ],

  "g.modes.h": ["Два режима распознавания", "Two recognition modes"],
  "g.modes.1": [
    "<b>Штатный</b> — Whisper прямо на компьютере. С него утилита стартует.",
    "<b>Standard</b> — Whisper running on your computer. The app starts in this mode.",
  ],
  "g.modes.2": [
    "<b>OpenAI</b> — облачное распознавание OpenAI live (через вашу подписку ChatGPT).",
    "<b>OpenAI</b> — cloud recognition by OpenAI live (through your ChatGPT subscription).",
  ],
  "g.modes.p": [
    "Переключается тумблером «Режим OpenAI» в «Настройках» или кнопкой «Режим» на пульте. При переключении звучит короткий сигнал.",
    "Switch with the “OpenAI mode” toggle in Settings or the “Mode” button on the Dashboard. A short sound plays on every switch.",
  ],

  "g.typing.h": ["Голосовой ввод текста", "Voice typing"],
  "g.typing.1": [
    "<b>Включён</b> — всё, что вы говорите, печатается во вкладку в фокусе (без Enter). Работает в обоих режимах.",
    "<b>On</b> — everything you say is typed into the focused tab (without Enter). Works in both modes.",
  ],
  "g.typing.2": [
    "<b>Выключен</b> — текст не печатается, работают только команды.",
    "<b>Off</b> — nothing is typed, only the commands work.",
  ],
  "g.typing.p": [
    "Тумблер — в «Настройках» или кнопка «Голосовой ввод» на пульте.",
    "The toggle is in Settings; there is also a “Voice typing” button on the Dashboard.",
  ],

  "g.cmds.h": ["Четыре команды — одинаковые в обоих режимах", "Four commands — the same in both modes"],
  "g.cmds.1": [
    `${KW("space")} — пробел. В Claude с включённым /voice: начать или закончить запись.`,
    `${KW("space")} — Space. In Claude with /voice enabled: start or stop recording.`,
  ],
  "g.cmds.2": [
    `${KW("enter")} — Enter: отправить сообщение агенту.`,
    `${KW("enter")} — Enter: send the message to the agent.`,
  ],
  "g.cmds.3": [
    `${KW("switch")} — перейти на следующую вкладку с агентом в активном проекте (по кругу). Обычные терминалы без агента пропускаются.`,
    `${KW("switch")} — go to the next agent tab in the active project (in a loop). Plain terminals without an agent are skipped.`,
  ],
  "g.cmds.4": [
    `${KW("stop")} — прервать голос, если он читает ответ.`,
    `${KW("stop")} — interrupt the voice while it is reading an answer.`,
  ],
  "g.cmds.p": [
    "Всё уходит во вкладку Orca, которая сейчас открыта (в фокусе) — в Claude, Codex или OpenCode. Кнопка «Микрофон» на пульте — главный выключатель: на паузе не работает ничего.",
    "Everything goes to the Orca tab that is currently open (focused) — Claude, Codex or OpenCode. The “Microphone” button on the Dashboard is the master switch: when paused, nothing works.",
  ],

  "g.how.h": ["Как говорить", "How to speak"],
  "g.how.1": [
    `Без голосового ввода говорите команду <b>отдельной короткой фразой</b>, с паузой до и после. Внутри длинной речи команды не срабатывают (кроме ${KW("stop")}).`,
    `Without voice typing, say a command as a <b>separate short phrase</b>, with a pause before and after. Commands inside long speech are ignored (except ${KW("stop")}).`,
  ],
  "g.how.2": [
    `С голосовым вводом команду можно сказать прямо в конце фразы: «сделай аудит проекта, ${KW("enter")}» — текст напечатается и сразу уйдёт агенту.`,
    `With voice typing, you can say a command right at the end of a phrase: “audit the project, ${KW("enter")}” — the text is typed and sent to the agent at once.`,
  ],

  "g.speak.h": ["Озвучка ответов", "Reading answers aloud"],
  "g.speak.1": [
    "Когда агент закончил ответ, голос читает его текст — в обоих режимах. Читается агент во вкладке в фокусе или тот, кому вы последним отправили команду.",
    "When an agent finishes its answer, the voice reads it aloud — in both modes. It reads the agent in the focused tab or the one you last sent a command to.",
  ],
  "g.speak.2": ["Код не читается, длинные ответы обрезаются.", "Code is not read, long answers are cut off."],
  "g.speak.3": [
    "Пока голос говорит, речь не печатается — ответ ИИ не попадёт во вкладку.",
    "While the voice is speaking, nothing is typed — the AI's answer will not end up in the tab.",
  ],
  "g.speak.4": [
    `Тумблер «Выключать микрофон, пока говорит голос» (в «Настройках → Озвучка ответов»): включён — микрофон полностью глохнет; выключен — слышно только ${KW("stop")}.`,
    `The “Mute the microphone while the voice is speaking” toggle (Settings → Reading answers aloud): on — the microphone is fully muted; off — only ${KW("stop")} is heard.`,
  ],
  "g.speak.5": [
    "Если агент ждёт разрешения или ответа — прозвучит «Агент ждёт вашего ответа».",
    "If an agent is waiting for permission or a reply, you will hear “The agent is waiting for your reply”.",
  ],

  "g.dot.h": ["Индикатор на пульте", "Dashboard indicator"],
  "g.dot.listening": ["штатный режим", "standard mode"],
  "g.dot.live": ["режим OpenAI", "OpenAI mode"],
  "g.dot.speaking": ["читаю ответ", "reading an answer"],
  "g.dot.paused": ["микрофон на паузе", "microphone paused"],

  "g.fix.h": ["Если слово не срабатывает", "If a word does not work"],
  "g.fix.1": [
    "Скажите его и посмотрите на пульте строку «Услышано» — так его расслышал Whisper.",
    "Say it and look at the “Heard” line on the Dashboard — that is how Whisper heard it.",
  ],
  "g.fix.2": [
    "Добавьте этот вариант в «Настройки → Голосовые команды» и нажмите «Сохранить». Перезапуск не нужен.",
    "Add that variant in Settings → Voice commands and click “Save”. No restart is needed.",
  ],
  "g.fix.3": [
    "Срабатывает от шума — поднимите «Минимальную громкость речи» в разделе «Микрофон».",
    "If it triggers on noise, raise “Minimum speech volume” in the Microphone section.",
  ],

  "g.lang.h": ["Язык", "Language"],
  "g.lang.p": [
    "Кнопки RU / EN в шапке окна переключают язык окна, статусов, журнала и служебных фраз голоса. Язык распознавания речи задаётся отдельно: «Настройки → Распознавание (Whisper) → Язык». Чтобы ответы читались правильно, выберите голос нужного языка в «Озвучке ответов».",
    "The RU / EN buttons in the window header switch the language of the window, statuses, log and the voice's service phrases. The speech recognition language is set separately: Settings → Recognition (Whisper) → Language. To have answers read properly, pick a voice for the right language under “Reading answers aloud”.",
  ],

  "g.inside.h": ["Что внутри", "What's inside"],
  "g.inside.p": [
    "Штатный режим — Whisper на компьютере. Режим OpenAI — облачное распознавание через вашу подписку ChatGPT (вход в Codex). Клавиши и текст уходят во вкладку через Orca CLI, ответы читает голос macOS.",
    "Standard mode — Whisper on your computer. OpenAI mode — cloud recognition through your ChatGPT subscription (Codex sign-in). Keys and text go to the tab through the Orca CLI; answers are read by the macOS voice.",
  ],

  // ---------- настройки
  "s.mode.h": ["Режим", "Mode"],
  "s.mode.hint": [
    "Эти два тумблера применяются сразу, без «Сохранить».",
    "These two toggles apply immediately, without “Save”.",
  ],
  "s.mode.live": [
    "Режим OpenAI<small>Выключен — штатный режим (Whisper на компьютере). При переключении — короткий звук.</small>",
    "OpenAI mode<small>Off — standard mode (Whisper on your computer). A short sound plays on every switch.</small>",
  ],
  "s.mode.typing": [
    "Голосовой ввод текста<small>Включён — речь печатается во вкладку в фокусе (в обоих режимах). Выключен — только команды.</small>",
    "Voice typing<small>On — speech is typed into the focused tab (in both modes). Off — commands only.</small>",
  ],

  "s.typing.h": ["Голосовой ввод", "Voice typing"],
  "s.typing.hint": [
    "Whisper иногда «слышит» в шуме готовые фразы. Такие фразы не печатаются.",
    "Whisper sometimes “hears” stock phrases in noise. Such phrases are not typed.",
  ],
  "s.typing.ignore": ["Не печатать фразы, которые начинаются с", "Do not type phrases that start with"],
  "s.typing.max": [
    "Максимальная длина фразы при вводе (с)<small>Длиннее — режется на части.</small>",
    "Maximum phrase length when typing (s)<small>Longer phrases are split into parts.</small>",
  ],

  "s.cmds.h": ["Голосовые команды", "Voice commands"],
  "s.cmds.hint": [
    "Варианты — как Whisper может услышать слово. Добавляйте через Enter или запятую. Сравнение нечёткое: гласные и одна-две буквы могут отличаться.",
    "Variants are the ways Whisper may hear the word. Add them with Enter or a comma. Matching is fuzzy: vowels and one or two letters may differ.",
  ],
  "s.cmds.max": [
    "Максимум слов во фразе-команде<small>Если фраза длиннее — это обычная речь, команды в ней игнорируются (кроме «замолчать»).</small>",
    "Maximum words in a command phrase<small>A longer phrase is ordinary speech; commands in it are ignored (except “hush”).</small>",
  ],

  "s.speak.h": ["Озвучка ответов", "Reading answers aloud"],
  "s.speak.hint": [
    "Когда агент во вкладке в фокусе закончил ответ, его текст читается вслух.",
    "When the agent in the focused tab finishes its answer, the text is read aloud.",
  ],
  "s.speak.on": ["Озвучивать ответы ИИ", "Read AI answers aloud"],
  "s.speak.mute": [
    "Выключать микрофон, пока говорит голос<small>Включено — обрывки голоса не попадут в ввод, но команда «замолчать» не сработает. Выключено — пока говорит голос, слушается только она.</small>",
    "Mute the microphone while the voice is speaking<small>On — fragments of the voice will not get into the input, but the “hush” command will not work. Off — while the voice is speaking, only that command is heard.</small>",
  ],
  "s.speak.waiting": [
    "Сообщать «Агент ждёт вашего ответа»<small>Когда агент просит разрешение или задаёт вопрос.</small>",
    "Announce “The agent is waiting for your reply”<small>When an agent asks for permission or asks a question.</small>",
  ],
  "s.speak.voice": ["Голос", "Voice"],
  "s.speak.rate": ["Скорость речи (слов в минуту)", "Speech rate (words per minute)"],
  "s.speak.max": [
    "Максимум символов для чтения<small>Длинный ответ обрезается.</small>",
    "Maximum characters to read<small>A long answer is cut off.</small>",
  ],
  "s.speak.check": ["Проверка", "Test"],
  "s.speak.test": ["Проверить голос", "Test the voice"],

  "s.live.h": ["Режим OpenAI", "OpenAI mode"],
  "s.live.hint": [
    "Включается тумблером вверху или кнопкой «Режим» на пульте. Доступ — через ваш вход Codex (подписка ChatGPT): на этом компьютере нужен <code>codex login</code>. Режим экспериментальный и может перестать работать.",
    "Turned on with the toggle at the top or the “Mode” button on the Dashboard. Access goes through your own Codex sign-in (ChatGPT subscription): run <code>codex login</code> on this computer. The mode is experimental and may stop working.",
  ],
  "s.live.max": [
    "Возврат в штатный режим через (минут)<small>Защита, если забыли выключить.</small>",
    "Return to standard mode after (minutes)<small>A safeguard in case you forget to turn it off.</small>",
  ],

  "s.whisper.h": ["Распознавание (Whisper)", "Recognition (Whisper)"],
  "s.whisper.hint": [
    "Смена модели, языка или подсказки перезапускает Whisper (пара секунд).",
    "Changing the model, language or prompt restarts Whisper (a couple of seconds).",
  ],
  "s.whisper.model": ["Модель", "Model"],
  "s.whisper.lang": ["Язык", "Language"],
  "s.whisper.auto": ["Автоопределение", "Auto-detect"],
  "s.whisper.prompt": [
    "Подсказка словаря<small>Осторожно: с подсказкой Whisper начинает «слышать» эти слова в шуме. Лучше оставить пустой.</small>",
    "Vocabulary prompt<small>Careful: with a prompt Whisper starts “hearing” these words in noise. Better leave it empty.</small>",
  ],
  "s.whisper.empty": ["пусто", "empty"],

  "s.mic.h": ["Микрофон", "Microphone"],
  "s.mic.hint": ["Детектор речи. Меняется на ходу.", "Speech detector. Changes apply on the fly."],
  "s.mic.level": [
    "Минимальная громкость речи<small>Больше — меньше реагирует на тихие звуки.</small>",
    "Minimum speech volume<small>Higher — less sensitive to quiet sounds.</small>",
  ],
  "s.mic.ratio": ["Во сколько раз громче фона", "How many times louder than the background"],
  "s.mic.silence": ["Пауза конца фразы (мс)", "End-of-phrase pause (ms)"],
  "s.mic.min": ["Минимальная длина фразы (мс)", "Minimum phrase length (ms)"],
  "s.mic.max": [
    "Максимальная длина команды (с)<small>Длиннее — считается обычной речью.</small>",
    "Maximum command length (s)<small>Anything longer counts as ordinary speech.</small>",
  ],

  "s.misc.h": ["Прочее", "Other"],
  "s.misc.sounds": [
    "Звуковые сигналы<small>Щелчок на пробел и Enter, тихий сигнал на напечатанную фразу, звук смены режима и вкладки.</small>",
    "Sound signals<small>A click for Space and Enter, a quiet sound for a typed phrase, a sound for mode and tab switches.</small>",
  ],
  "s.misc.poll": ["Проверять статусы агентов раз в (с)", "Check agent statuses every (s)"],
  "s.misc.keys": ["Проверка клавиш во вкладку в фокусе", "Test keys in the focused tab"],
  "s.misc.space": ["Тест: пробел", "Test: Space"],
  "s.misc.enter": ["Тест: Enter", "Test: Enter"],
  "s.misc.advanced": ["Для опытных", "Advanced"],
  "s.misc.wport": ["Порт Whisper", "Whisper port"],
  "s.misc.sport": [
    "Порт окна <small>Применится после перезапуска утилиты.</small>",
    "Window port <small>Takes effect after restarting the app.</small>",
  ],
};
