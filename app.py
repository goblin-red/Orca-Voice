"""Goblin Voice — окно-пульт голосового управления вкладками Orca.

Два режима распознавания (тумблер в окне, при переключении — короткий звук):
  штатный — Whisper на компьютере;
  OpenAI  — OpenAI live в облаке.
Тумблер «Голосовой ввод текста»: включён — речь печатается во вкладку (в обоих режимах),
выключен — работают только команды.
Команды в обоих режимах: «дамбл-бамбл» — пробел, «рекс» — Enter, «заткнись» — прервать голос,
«переключи терминал» — следующая вкладка с агентом в активном проекте.
(«тузик-арбузик» для смены режима временно выключен.)
Всё уходит во вкладку Orca, которая сейчас в фокусе. Ответы агентов читаются голосом.
Закрыли окно — утилита завершается целиком.
Язык окна, статусов, журнала и фраз голоса — русский или английский (переключатель EN / RU в шапке; главный — английский).
"""

import copy
import json
import logging
import os
import queue
import re
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

import webview

import i18n
import orca_cli
from i18n import t
from listener import Listener
from live import LiveSession
from matcher import Matcher
from settings_server import SettingsServer
from speaker import AnswerWatcher, Speaker
from whisper_srv import WhisperServer

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "config.json"
DEFAULT_CONFIG = HERE / "config.default.json"
LOG_FILE = HERE / "logs" / "orca-voice.log"
PID_FILE = HERE / "logs" / "app.pid"

SOUNDS = {
    "space": "/System/Library/Sounds/Tink.aiff",
    "enter": "/System/Library/Sounds/Pop.aiff",
    "text": "/System/Library/Sounds/Purr.aiff",       # фраза напечатана
    "switch": "/System/Library/Sounds/Morse.aiff",    # вкладка переключена
    "mode_on": "/System/Library/Sounds/Glass.aiff",
    "mode_off": "/System/Library/Sounds/Bottle.aiff",
    "error": "/System/Library/Sounds/Basso.aiff",
}
WHISPER_KEYS = ("model", "language", "prompt", "whisper_port")   # их смена перезапускает Whisper


class NewestFirstHandler(logging.Handler):
    """Журнал в файл, свежие записи сверху. Файл обрезается до max_lines строк."""

    STAMP = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")

    def __init__(self, path, max_lines=3000):
        super().__init__()
        self.path = Path(path)
        self.max_lines = max_lines
        self._flip_old_file()

    def _read(self):
        try:
            return self.path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []

    def _write(self, lines):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text("\n".join(lines[:self.max_lines]) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)     # целиком, чтобы просмотрщик не увидел пустой файл

    def _flip_old_file(self):
        """Старый журнал (свежие внизу) один раз переворачиваем, многострочные записи не разрываем."""
        lines = self._read()
        stamps = [line[:23] for line in lines if self.STAMP.match(line)]
        if len(stamps) < 2 or stamps[0] >= stamps[-1]:
            return
        records = []
        for line in lines:
            if self.STAMP.match(line) or not records:
                records.append([line])
            else:
                records[-1].append(line)
        self._write([line for rec in reversed(records) for line in rec])

    def emit(self, record):
        try:
            self._write(self.format(record).splitlines() + self._read())
        except Exception:
            self.handleError(record)


def setup_log():
    LOG_FILE.parent.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[NewestFirstHandler(LOG_FILE), logging.StreamHandler()],
    )
    for noisy in ("aioice", "aiortc", "websockets", "pywebview"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return logging.getLogger("orca-voice")


# ---------- прошлые запуски

def _pid_cwd(pid):
    """Рабочая папка процесса (через lsof)."""
    out = subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
                         capture_output=True, text=True).stdout
    return next((line[1:] for line in out.splitlines() if line.startswith("n")), "")


def _our_processes():
    """pid прошлых запусков: строго процесс Python, у которого скрипт — наш app.py."""
    me = os.getpid()
    out = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True).stdout
    found = set()
    for line in out.splitlines():
        pid_text, _, command = line.strip().partition(" ")
        parts = command.split()
        if len(parts) < 2 or not Path(parts[0]).name.lower().startswith("python"):
            continue    # не Python (например, оболочка, где просто упомянут путь)
        pid = int(pid_text)
        script = parts[1]
        if pid != me and (script == str(HERE / "app.py")
                          or (script == "app.py" and _pid_cwd(pid) == str(HERE))):
            found.add(pid)
    return found


def kill_previous(log):
    """Убивает прошлые запуски Goblin Voice (их whisper-server гасится при старте нового)."""
    victims = _our_processes()
    for pid in victims:
        try:
            os.kill(pid, signal.SIGTERM)
            log.info(t("log.killed_previous"), pid)
        except ProcessLookupError:
            pass

    # кто не ушёл за секунду — добиваем (проверяем заново, что это всё ещё наш процесс)
    if victims:
        time.sleep(1.0)
        for pid in victims & _our_processes():
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        # ждём, пока процессы реально исчезнут (до 5 с)
        deadline = time.time() + 5
        while victims & _our_processes() and time.time() < deadline:
            time.sleep(0.2)

    PID_FILE.write_text(str(os.getpid()))


# ---------- ядро

class OrcaVoice:
    def __init__(self, cfg, log):
        self.cfg = cfg
        self.log = log

        # общее состояние (его читает и AnswerWatcher)
        self.state = {"speak_answers": cfg["speak_answers"], "last_target": None, "live": False}
        self.status = t("st.whisper_start")
        self.heard = "—"
        self.ready = False
        self.error = None

        # части приложения
        self.whisper = WhisperServer(cfg, log)
        self.whisper_lock = threading.Lock()
        self.matcher = Matcher(cfg)
        self.speaker = Speaker(cfg["voice"], cfg["rate"], log)
        self.watcher = AnswerWatcher(cfg, self.speaker, log, self.state)
        self.settings = SettingsServer(self, cfg.get("settings_port", 8792), log)
        self.listener = None
        self.phrases = queue.Queue()

        # live-режим
        self.live = None
        self.live_started = 0.0
        self.live_lock = threading.Lock()
        self.ignore_until = 0.0     # короткая глухота после выхода из live

    # ---------- запуск / выход

    def start(self):
        self.settings.start()   # окно грузится с этого сервера — поднимаем сразу
        threading.Thread(target=self.boot, daemon=True).start()
        threading.Thread(target=self.worker, daemon=True).start()
        threading.Thread(target=self.ticker, daemon=True).start()

    def boot(self):
        try:
            self.whisper.start()
            self.listener = Listener(self.cfg["vad"], self.on_phrase, self.log)
            # пока говорит голос (и ещё speech_tail_s после) — не печатаем, а при mute — не слушаем вовсе
            self.listener.hold = lambda: self.speaker.busy_or_recent(self.cfg.get("speech_tail_s", 1.0))
            self.listener.dictation = bool(self.cfg.get("voice_typing"))
            self.listener.mute_on_speech = bool(self.cfg.get("mute_while_speaking", True))
            self.listener.start()
            self.watcher.start()
            self.ready = True
            self.status = t("st.standard")
        except Exception as e:
            self.error = str(e)
            self.status = t("st.error", e)
            self.log.exception(t("log.boot_failed"))

    def shutdown(self):
        self.log.info(t("log.exit"))
        self.stop_live("exit")
        if self.listener:
            self.listener.stop()
        self.watcher.stop()
        self.speaker.stop()
        self.whisper.stop()
        try:
            PID_FILE.unlink()
        except FileNotFoundError:
            pass

    def ticker(self):
        """Раз в секунду: автовыключение режима OpenAI."""
        while True:
            limit = self.cfg.get("live_max_minutes", 10) * 60
            if self.state["live"] and time.time() - self.live_started > limit:
                self.stop_live("timeout")
            time.sleep(1)

    # ---------- распознавание фраз (по очереди)

    def on_phrase(self, wav, long=False, spoken=False):
        self.phrases.put((wav, long, spoken))

    def worker(self):
        """Штатный режим: Whisper слушает команды.

        В режиме OpenAI сюда попадает только звук, пока говорит наш голос (ради «заткнись»).
        """
        while True:
            wav, long, spoken = self.phrases.get()
            try:
                with self.whisper_lock:
                    text = self.whisper.transcribe(wav)
            except Exception as e:
                self.log.warning("whisper: %s", e)
                continue
            if not text:
                continue

            # голосовой ввод: печатаем (если не звучал наш голос и это не режим OpenAI)
            if self.cfg.get("voice_typing") and not long and not spoken and not self.state["live"]:
                if self.is_junk(text):
                    self.log.info(t("log.junk"), text)
                    continue
                self.heard = text
                self.log.info(t("log.heard_typing"), text)
                self.handle_speech(text)
                continue

            commands = self.matcher.commands(text, long)
            if commands and time.time() < self.ignore_until:
                self.log.info(t("log.skipped_after_mode"), text)
                continue
            if not long:
                self.heard = text
            self.log.info(t("log.heard_long" if long else "log.heard"), text, commands or "—")
            if commands:
                self.fire(commands)

    def is_junk(self, text):
        """Фразы, которые Whisper «слышит» в шуме: «Субтитры…», «Спасибо за просмотр», капс."""
        letters = [c for c in text if c.isalpha()]
        if len(letters) >= 3 and all(c.isupper() for c in letters):
            return True
        norm = " ".join(re.sub(r"[^\w\s]+", " ", text.lower().replace("ё", "е")).split())
        if len(norm.split()) > 8:
            return False
        return any(norm.startswith(item) for item in self.cfg.get("dictation_ignore", []) if item)

    def handle_speech(self, text):
        """Фраза для ввода: текст печатаем во вкладку в фокусе, команды выполняем по порядку."""
        term = None
        for kind, value in self.matcher.segments(text):
            if kind == "stop":
                self.speaker.stop()
                self.log.info(t("log.voice_stopped"))
                continue
            if kind == "toggle":        # временно выключено
                continue
            if kind == "switch":
                term = self._switch_tab() or term   # дальше печатаем уже в новую вкладку
                continue
            term = term or self._focused()
            if not term:
                return
            if kind == "text":
                try:
                    orca_cli.send_text(term["handle"], value + " ")
                    self.state["last_target"] = term
                    self.play("text", 0.5)     # тихий сигнал: фраза в терминале
                    self.log.info(t("log.typed"), value)
                except Exception as e:
                    self.log.warning("orca: %s", e)
            else:   # space / enter
                self._send_key(term, kind)

    # ---------- команды

    def fire_async(self, commands):
        threading.Thread(target=self.fire, args=(commands,), daemon=True).start()

    def play(self, sound, volume=1.0):
        if self.cfg.get("sounds", True) and sound in SOUNDS:
            subprocess.Popen(["afplay", "-v", str(volume), SOUNDS[sound]])

    def fire(self, commands):
        """Выполняет команды по порядку во вкладке в фокусе."""
        self.speaker.stop()   # любая команда перебивает голос
        term = None
        for cmd in commands:
            if cmd == "stop":
                self.status = t("st.voice_stopped")
                self.log.info(t("log.voice_stopped"))
            elif cmd == "toggle":
                self.toggle_mode()
                return            # после смены режима остальное не выполняем
            elif cmd == "switch":
                term = self._switch_tab() or term   # следующие клавиши — уже в новую вкладку
            elif cmd in ("space", "enter"):
                term = term or self._focused()
                if not term:
                    return
                self._send_key(term, cmd)

    def _focused(self):
        """Вкладка Orca в фокусе или None (с сообщением в статусе)."""
        try:
            term = orca_cli.focused_terminal()
        except Exception as e:
            self.log.warning("orca: %s", e)
            term = None
        if not term:
            self.status = t("st.no_focus")
            self.log.warning(self.status)
        return term

    def _switch_tab(self):
        """Переходит на следующую вкладку с агентом в активном проекте. Возвращает её или None."""
        try:
            term = orca_cli.next_agent_terminal()
            if not term:
                self.status = t("st.no_other_tab")
                self.log.info(self.status)
                return None
            orca_cli.switch_terminal(term["handle"])
        except Exception as e:
            self.status = t("st.orca_error", e)[:80]
            self.log.warning("orca: %s", e)
            return None

        self.play("switch")
        self.status = t("st.switched", term["worktree"], term["title"][:30])
        self.log.info(t("log.switched"), term["title"], term["handle"])
        return term

    def _send_key(self, term, cmd):
        try:
            if cmd == "space":
                orca_cli.send_space(term["handle"])
            else:
                orca_cli.send_enter(term["handle"])
        except Exception as e:
            self.status = t("st.orca_error", e)[:80]
            self.log.warning("orca: %s", e)
            return
        self.play(cmd)
        self.state["last_target"] = term
        label = t("st.key_space" if cmd == "space" else "st.key_enter")
        self.status = f"{label} → {term['worktree']} / {term['title'][:30]}"
        self.log.info(t("log.sent"), cmd, term["title"], term["handle"])

    # ---------- режимы: штатный <-> OpenAI

    def toggle_mode(self):
        if self.state["live"]:
            self.stop_live("toggle")
        else:
            self.start_live()

    def start_live(self):
        with self.live_lock:
            if self.state["live"] or not self.listener:
                return
            self.state["live"] = True
            self.live_started = time.time()

            # колбэки знают свою сессию: старая сессия не тронет новую
            session = LiveSession(
                lambda text: self.on_live_text(text, session),
                lambda st, detail: self.on_live_state(st, detail, session),
                self.log,
            )
            self.live = session
            self.listener.tap = session.feed        # звук микрофона — в OpenAI (кроме моментов, когда говорит голос)
            session.start()

            self.play("mode_on")
            self.status = t("st.live_connecting")
            self.log.info(t("log.live_on"))

    def on_live_text(self, text, session):
        """Фраза от OpenAI: при голосовом вводе печатаем, иначе ищем только команды."""
        if session is not self.live:
            return
        self.heard = text.strip()
        if self.cfg.get("voice_typing"):
            self.log.info(t("log.live_typing"), text)
            self.handle_speech(text)
        else:
            commands = self.matcher.commands(text)
            self.log.info("OpenAI: %r -> %s", text, commands or "—")
            if commands:
                self.fire(commands)

    def on_live_state(self, state, detail, session):
        if session is not self.live:
            return
        if state == "live":
            self.status = t("st.live_talk")
        elif state == "error":
            self.status = t("st.live_error", detail)[:80]
            self.stop_live("error", keep_status=True, sound="error")
        elif state == "closed":
            self.stop_live("closed", keep_status=True, sound="error")

    def stop_live(self, reason, keep_status=False, sound="mode_off"):
        with self.live_lock:
            if not self.state["live"]:
                return
            self.state["live"] = False
            if self.listener:
                self.listener.tap = None
                self.listener.reset()
            if self.live:
                self.live.stop()
                self.live = None

            # выбрасываем то, что успело накопиться, и чуть-чуть не слушаем команды
            while not self.phrases.empty():
                try:
                    self.phrases.get_nowait()
                except queue.Empty:
                    break
            self.ignore_until = time.time() + 1.5

            if reason != "exit":
                self.play(sound)
            if not keep_status:
                self.status = t("st.standard")
            self.log.info(t("log.live_off"), t("why." + reason))

    # ---------- пульт (кнопки в окне)

    def snapshot(self):
        """Состояние для окна."""
        if self.error:
            mode = "error"
        elif not self.ready:
            mode = "starting"
        elif self.listener and self.listener.paused:
            mode = "paused"
        elif self.state["live"]:
            mode = "live"
        elif self.speaker.busy():
            mode = "speaking"
        else:
            mode = "listening"

        target = self.state.get("last_target")
        return {
            "mode": mode,
            "status": self.status,
            "heard": self.heard,
            "listening": bool(self.listener and not self.listener.paused),
            "speak_answers": self.state["speak_answers"],
            "voice_typing": bool(self.cfg.get("voice_typing")),
            "live": self.state["live"],
            "level": round(self.listener.level, 4) if self.listener else 0,
            "target": f"{target['worktree']} / {target['title']}" if target else "",
        }

    def action(self, name):
        if name == "listen":
            if self.listener:
                self.listener.paused = not self.listener.paused
        elif name == "speak":
            self.state["speak_answers"] = not self.state["speak_answers"]
            self.save_setting("speak_answers", self.state["speak_answers"])
            if not self.state["speak_answers"]:
                self.speaker.stop()
        elif name == "live":
            threading.Thread(target=self.toggle_mode, daemon=True).start()
        elif name == "typing":
            value = not self.cfg.get("voice_typing")
            self.save_setting("voice_typing", value)
            if self.listener:
                self.listener.dictation = value
            self.log.info(t("log.typing_on" if value else "log.typing_off"))
        elif name == "hush":
            self.speaker.stop()
        elif name in ("space", "enter", "switch"):
            self.fire_async([name])
        elif name == "log":
            subprocess.Popen(["open", str(LOG_FILE)])
        else:
            raise ValueError(t("err.unknown_action", name))

    # ---------- настройки

    def apply_config(self, new):
        """Сохраняет настройки из окна и применяет их без перезапуска."""
        merged = copy.deepcopy(self.cfg)
        # язык окна меняется отдельно (set_language) — старая форма не должна вернуть прежний
        merged.update({k: v for k, v in new.items() if k not in ("vad", "ui_language")})
        merged["vad"] = {**self.cfg["vad"], **(new.get("vad") or {})}

        for name in ("space", "enter", "toggle", "switch", "stop"):
            command = merged["commands"].get(name)
            if not isinstance(command, dict) or not isinstance(command.get("words"), list):
                raise ValueError(t("err.bad_command", name))
            command["words"] = [str(w).strip() for w in command["words"] if str(w).strip()]

        matcher = Matcher(merged)   # заодно проверка, что всё разбирается
        restart_whisper = any(merged.get(k) != self.cfg.get(k) for k in WHISPER_KEYS)

        CONFIG_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        self.cfg = merged
        self.matcher = matcher
        self.speaker.voice = merged["voice"]
        self.speaker.rate = merged["rate"]
        self.watcher.cfg = merged
        self.state["speak_answers"] = merged["speak_answers"]
        if self.listener:
            self.listener.cfg = merged["vad"]
            self.listener.dictation = bool(merged.get("voice_typing"))
            self.listener.mute_on_speech = bool(merged.get("mute_while_speaking", True))
        self.log.info(t("log.settings_saved"))

        if restart_whisper:
            threading.Thread(target=self._restart_whisper, daemon=True).start()

    def _restart_whisper(self):
        self.status = t("st.whisper_restarting")
        try:
            with self.whisper_lock:
                self.whisper.restart(self.cfg)
            self.status = t("st.whisper_restarted")
        except Exception as e:
            self.status = f"Whisper: {e}"[:80]
            self.log.exception(t("log.whisper_restart"))

    def save_setting(self, key, value):
        self.cfg[key] = value
        CONFIG_FILE.write_text(json.dumps(self.cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def set_language(self, lang):
        """Язык окна, статусов, журнала и фраз голоса: ru / en. Применяется сразу."""
        if lang not in i18n.LANGS:
            raise ValueError(t("err.bad_language", lang))
        i18n.set_lang(lang)
        self.save_setting("ui_language", lang)

        # статус на пульте переводим сразу, не дожидаясь нового события
        if self.ready and not self.error:
            self.status = t("st.live_talk" if self.state["live"] else "st.standard")
        self.log.info(t("log.language"), lang)


def load_config():
    """Настройки из config.json; при первом запуске — копия config.default.json.

    Чего нет в старом config.json (новые настройки и команды) — берём из настроек по умолчанию.
    """
    defaults = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    if not CONFIG_FILE.exists():
        shutil.copy(DEFAULT_CONFIG, CONFIG_FILE)
    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

    for key, value in defaults.items():
        cfg.setdefault(key, value)
    for section in ("commands", "vad"):
        for key, value in defaults[section].items():
            cfg[section].setdefault(key, value)
    return cfg


def set_app_name(name):
    """Имя в меню macOS вместо «Python»."""
    try:
        from Foundation import NSBundle
        info = NSBundle.mainBundle().infoDictionary()
        info["CFBundleName"] = name
        info["CFBundleDisplayName"] = name
    except Exception:
        pass


def main():
    log = setup_log()
    cfg = load_config()
    i18n.set_lang(cfg["ui_language"])   # язык — до первых записей в журнал
    kill_previous(log)

    core = OrcaVoice(cfg, log)
    core.start()

    # закрыли окно или прислали SIGTERM — гасим всё
    def on_term(*_):
        core.shutdown()
        os._exit(0)
    signal.signal(signal.SIGTERM, on_term)

    set_app_name("Goblin Voice")
    window = webview.create_window("Goblin Voice", core.settings.url(),
                                   width=860, height=920, min_size=(560, 600))
    window.events.closed += on_term   # крестик — выходим целиком
    webview.start()          # ждёт, пока окно открыто

    core.shutdown()
    os._exit(0)              # добиваем фоновые потоки


if __name__ == "__main__":
    main()
