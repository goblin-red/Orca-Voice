"""Мини-сервер на 127.0.0.1 для окна (ui.html): пульт, журнал и настройки."""

import json
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import i18n
from i18n import t

HERE = Path(__file__).resolve().parent
MODELS = HERE / "models"

# файлы окна: адрес -> (файл, тип)
PAGES = {
    "/": ("ui.html", "text/html; charset=utf-8"),
    "/ui_texts.js": ("ui_texts.js", "application/javascript; charset=utf-8"),
    "/logo.svg": ("logo.svg", "image/svg+xml"),
}


def list_models(extra_dirs=()):
    """Все модели whisper.cpp (ggml-*.bin): папка models утилиты и папки из настройки model_dirs."""
    # свои модели — путём от папки утилиты, как в настройках по умолчанию
    found = [f"models/{p.name}" for p in sorted(MODELS.glob("ggml-*.bin"))]
    for folder in extra_dirs:
        folder = Path(folder).expanduser()
        if folder.is_dir():
            found += [str(p) for p in sorted(folder.glob("ggml-*.bin"))]
    return found


def list_voices():
    """Голоса macOS: [{name, lang}]."""
    out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    voices = []
    for line in out.splitlines():
        m = re.match(r"^(.+?)\s{2,}([a-z]{2}_[A-Z]{2})", line)
        if m:
            voices.append({"name": m[1].strip(), "lang": m[2]})
    return voices


class SettingsServer:
    def __init__(self, app, port, log):
        self.app = app
        self.port = port
        self.log = log
        self._voices = None

    def log_tail(self, lines=60):
        """Свежие строки журнала (в файле они сверху) без шума — фраз без команд."""
        path = HERE / "logs" / "orca-voice.log"
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                head = [next(f, "") for _ in range(400)]
        except FileNotFoundError:
            return []
        rows = [r.rstrip("\n") for r in head if r.strip() and not r.rstrip().endswith("-> —")]
        return rows[:lines]

    def url(self):
        return f"http://127.0.0.1:{self.port}/"

    def start(self):
        # порт может ещё держать только что убитая прошлая копия — пробуем до 10 с
        for attempt in range(40):
            try:
                server = ThreadingHTTPServer(("127.0.0.1", self.port), self._handler())
                break
            except OSError:
                if attempt == 39:
                    raise
                time.sleep(0.25)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.log.info(t("log.settings_url"), self.url())

    def _handler(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, body, content_type, code=200):
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _json(self, data, code=200):
                self._send(json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8", code)

            def _body(self):
                size = int(self.headers.get("Content-Length") or 0)
                return json.loads(self.rfile.read(size) or b"{}")

            def do_GET(self):
                if self.path in PAGES:
                    name, content_type = PAGES[self.path]
                    body = (HERE / name).read_text(encoding="utf-8")
                    if name == "ui.html":
                        # язык — сразу в странице: окно открывается на нужном языке без мигания
                        body = body.replace('<html lang="ru">', f'<html lang="{i18n.get_lang()}">', 1)
                    self._send(body.encode(), content_type)
                elif self.path == "/api/config":
                    if owner._voices is None:
                        owner._voices = list_voices()
                    self._json({
                        "config": owner.app.cfg,
                        "models": list_models(owner.app.cfg.get("model_dirs", [])),
                        "voices": owner._voices,
                        "status": owner.app.status,
                    })
                elif self.path == "/api/state":
                    self._json({**owner.app.snapshot(), "log": owner.log_tail()})
                else:
                    self._json({"error": t("err.not_found")}, 404)

            def do_POST(self):
                try:
                    data = self._body()
                    if self.path == "/api/config":
                        owner.app.apply_config(data)
                        self._json({"ok": True})
                    elif self.path == "/api/test-voice":
                        owner.app.speaker.test(data.get("voice"), data.get("rate"))
                        self._json({"ok": True})
                    elif self.path == "/api/action":
                        owner.app.action(data.get("name", ""))
                        self._json({"ok": True})
                    elif self.path == "/api/lang":
                        owner.app.set_language(data.get("lang", ""))
                        self._json({"ok": True})
                    else:
                        self._json({"error": t("err.not_found")}, 404)
                except Exception as e:
                    owner.log.warning(t("log.settings_error"), e)
                    self._json({"ok": False, "error": str(e)}, 400)

        return Handler
