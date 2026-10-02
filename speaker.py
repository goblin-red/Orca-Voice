"""Озвучка ответов ИИ: следим за агентами в Orca и читаем ответ голосом macOS (say)."""

import datetime
import json
import re
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

import orca_cli
from i18n import t


def clean_for_speech(text, limit):
    """Markdown -> обычный текст, который приятно слушать."""
    text = re.sub(r"```.*?```", t("say.code"), text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)     # [текст](ссылка) -> текст
    text = re.sub(r"https?://\S+", t("say.link"), text)
    text = re.sub(r"`([^`]*)`", r"\1", text)                  # `код` -> код
    text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.M)      # маркеры списков
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.M)         # заголовки
    text = re.sub(r"[*_>|#~]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + t("say.cut")
    return text


class Speaker:
    """Один голос за раз: новая фраза прерывает старую."""

    def __init__(self, voice, rate, log):
        self.voice = voice
        self.rate = rate
        self.log = log
        self._proc = None
        self._lock = threading.Lock()
        self._last_busy = 0.0

    def say(self, text):
        with self._lock:
            self._kill()
            self._proc = subprocess.Popen(
                ["say", "-v", self.voice, "-r", str(self.rate), "--", text],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

    def stop(self):
        with self._lock:
            self._kill()

    def test(self, voice=None, rate=None):
        """Пробная фраза выбранным голосом (из окна настроек)."""
        with self._lock:
            self._kill()
            self._proc = subprocess.Popen(
                ["say", "-v", voice or self.voice, "-r", str(rate or self.rate), "--",
                 t("say.test")],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

    def busy(self):
        return self._proc is not None and self._proc.poll() is None

    def busy_or_recent(self, tail=0.5):
        """Говорит сейчас или замолчал меньше tail секунд назад (эхо в комнате)."""
        if self.busy():
            self._last_busy = time.time()
            return True
        return time.time() - self._last_busy < tail

    def _kill(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self._proc = None




class CodexLogs:
    """Журналы сессий Codex (~/.codex/sessions): событие task_complete = ход закончен.

    Нужен, потому что Orca не всегда видит статус Codex.
    """

    ROOT = Path.home() / ".codex" / "sessions"
    DAYS = 14

    def __init__(self):
        self._files = {}   # путь -> {"offset": сколько байт уже прочитано, "cwd": папка сессии}

    def _recent_files(self):
        today = datetime.date.today()
        for back in range(self.DAYS):
            day = today - datetime.timedelta(days=back)
            folder = self.ROOT / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}"
            if folder.is_dir():
                yield from folder.glob("*.jsonl")

    @staticmethod
    def _session_cwd(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.loads(f.readline()).get("payload", {}).get("cwd", "")
        except Exception:
            return ""

    def poll(self, first):
        """Новые завершённые ходы: [{agent, cwd, state, message}]."""
        events = []
        for path in self._recent_files():
            size = path.stat().st_size
            info = self._files.get(path)
            if info is None:
                # старые файлы при запуске не читаем, новые — с начала
                info = {"offset": size if first else 0, "cwd": self._session_cwd(path)}
                self._files[path] = info
            if size <= info["offset"]:
                continue

            with open(path, "rb") as f:
                f.seek(info["offset"])
                chunk = f.read()
            end = chunk.rfind(b"\n") + 1          # только целые строки
            info["offset"] += end

            for line in chunk[:end].splitlines():
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                payload = item.get("payload") or {}
                if item.get("type") == "event_msg" and payload.get("type") == "task_complete":
                    events.append({
                        "agent": "codex",
                        "paneKey": None,
                        "cwd": info["cwd"],
                        "state": "done",
                        "message": payload.get("last_agent_message") or "",
                    })
        return events


class AnswerWatcher(threading.Thread):
    """Раз в N секунд проверяет, какой агент закончил ход, и читает его ответ.

    Claude и OpenCode — через `orca worktree ps`, Codex — через его журналы.
    Читаем только агента во вкладке в фокусе или во вкладке, куда последний раз слали клавишу.
    """

    def __init__(self, cfg, speaker, log, state):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.speaker = speaker
        self.log = log
        self.state = state                 # общее состояние (speak_answers, last_target)
        self._prev = {}                    # paneKey -> прошлое состояние агента в Orca
        self._spoken = deque(maxlen=30)    # уже прочитанные ответы (без повторов)
        self._codex = CodexLogs()
        self._last_error = None            # последняя ошибка опроса (чтобы не повторять её в журнале)
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        first = True
        while not self._stop.is_set():
            try:
                self._tick(first)
                first = False
                self._last_error = None
            except Exception as e:
                # одну и ту же ошибку (например, Orca закрыт) пишем один раз, а не при каждом опросе
                if str(e) != self._last_error:
                    self._last_error = str(e)
                    self.log.warning("watcher: %s", e)
            self._stop.wait(self.cfg.get("poll_seconds", 2.0))

    # ---------- источники событий

    def _orca_events(self, first):
        """Агенты Orca, у которых только что сменилось состояние на done / blocked / waiting."""
        events = []
        for wt in orca_cli.worktrees():
            for agent in wt.get("agents", []):
                key = agent.get("paneKey")
                prev = self._prev.get(key)
                self._prev[key] = agent
                if first or not prev:
                    continue

                state = agent.get("state")
                changed = (state != prev.get("state")
                           or agent.get("stateStartedAt") != prev.get("stateStartedAt"))
                if changed and state in ("done", "blocked", "waiting"):
                    events.append({
                        "agent": agent.get("agentType"),
                        "paneKey": key,
                        "cwd": wt.get("path"),
                        "state": state,
                        "message": agent.get("lastAssistantMessage") or "",
                        "interrupted": agent.get("interrupted"),
                    })
        return events

    # ---------- чей это агент

    @staticmethod
    def _matches(event, term):
        if not term:
            return False
        if event.get("paneKey"):
            return event["paneKey"] == term.get("paneKey")
        # Codex: совпадает тип агента и папка проекта
        cwd, root = event.get("cwd") or "", term.get("cwd") or ""
        return term.get("agent") == event["agent"] and bool(root) and cwd.startswith(root)

    def _tick(self, first):
        events = self._orca_events(first) + self._codex.poll(first)
        if not events or not self.state["speak_answers"]:
            return

        try:
            focused = orca_cli.focused_terminal()
        except Exception:
            focused = None
        last = self.state.get("last_target")

        for ev in events:
            if not (self._matches(ev, focused) or self._matches(ev, last)):
                continue

            message = ev["message"].strip()
            if ev["state"] == "done":
                if message and message not in self._spoken:
                    self._spoken.append(message)
                    self.log.info(t("log.reading"), ev["agent"], len(message))
                    self.speaker.say(clean_for_speech(message, self.cfg.get("max_speech_chars", 2500)))
            elif not ev.get("interrupted") and self.cfg.get("announce_waiting", True):
                self.log.info(t("log.agent_waiting"), ev["agent"], ev["state"])
                self.speaker.say(t("say.waiting"))
