"""OpenAI live (gpt-live-1-codex) через подписку ChatGPT — по схеме jauvex.

Звук микрофона уходит по WebRTC, распознанный текст приходит по WebSocket (sideband).
Доступ — вход Codex (~/.codex/auth.json), API-ключ не нужен.
"""

import asyncio
import fractions
import json
import re
import threading
import time
import urllib.request
import uuid
from pathlib import Path

import numpy as np
import websockets
from aiortc import MediaStreamTrack, RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole
from av import AudioFrame

from i18n import t

MODEL = "gpt-live-1-codex"
CALL_URL = "https://chatgpt.com/backend-api/codex/realtime/calls?intent=quicksilver&architecture=avas"
SIDEBAND_URL = "wss://api.openai.com/v1/live/"
PROMPT = (
    "You are a transparent voice relay between the user and a desktop coding agent. "
    "Listen silently while the user speaks. As soon as the user pauses and the phrase is complete, "
    "immediately delegate it once, verbatim, without waiting for more speech. "
    "Never repeat or answer the user aloud. The app sends the final transcript directly to its "
    "selected coding agent. When the app gives you an agent reply, speak only that reply, "
    "in full and verbatim. Do not add commentary."
)

RATE = 16000
CHUNK = 320   # 20 мс при 16 кГц
FLUSH_S = 0.9 # пауза в кусочках текста, после которой фраза считается законченной


# ---------- доступ

def credentials():
    """Токен и аккаунт из входа Codex через ChatGPT."""
    path = Path.home() / ".codex" / "auth.json"
    tokens = json.loads(path.read_text(encoding="utf-8")).get("tokens") or {}
    if not tokens.get("access_token") or not tokens.get("account_id"):
        raise RuntimeError(t("err.no_codex_login"))
    return tokens["access_token"], tokens["account_id"]


def make_headers(token, account):
    return {
        "Authorization": f"Bearer {token}",
        "ChatGPT-Account-ID": account,
        "OpenAI-Alpha": "quicksilver=v2",
        "session-id": str(uuid.uuid4()),
        "thread-id": str(uuid.uuid4()),
        "x-session-id": str(uuid.uuid4()),
        "originator": "orca-voice",
        "User-Agent": "orca-voice/1.0",
    }


# ---------- микрофон -> WebRTC

class MicTrack(MediaStreamTrack):
    """Аудиодорожка WebRTC из кадров, которые приходят из Listener (float32, 16 кГц)."""

    kind = "audio"

    def __init__(self, loop):
        super().__init__()
        self.loop = loop
        self.queue = asyncio.Queue()
        self.buffer = np.zeros(0, dtype=np.float32)
        self.pts = 0

    def feed(self, samples):
        """Вызывается из потока микрофона."""
        self.loop.call_soon_threadsafe(self.queue.put_nowait, samples)

    async def recv(self):
        while len(self.buffer) < CHUNK:
            self.buffer = np.concatenate([self.buffer, await self.queue.get()])
        chunk, self.buffer = self.buffer[:CHUNK], self.buffer[CHUNK:]

        pcm = (np.clip(chunk, -1, 1) * 32767).astype(np.int16).reshape(1, -1)
        frame = AudioFrame.from_ndarray(pcm, format="s16", layout="mono")
        frame.sample_rate = RATE
        frame.pts = self.pts
        frame.time_base = fractions.Fraction(1, RATE)
        self.pts += CHUNK
        return frame


# ---------- разбор событий (как parseLiveMessage / LiveTranscriptBuffer в jauvex)

def parse_event(raw):
    try:
        event = json.loads(raw)
    except ValueError:
        return None
    kind = event.get("type")

    if kind == "input_transcript.added" and isinstance((event.get("item") or {}).get("text"), str):
        return ("fragment", event["item"]["text"])
    if kind == "session.input_transcript.delta" and isinstance(event.get("delta"), str):
        return ("fragment", event["delta"])
    if kind == "turn.done":
        turn = event.get("turn") or {}
        if turn.get("role") == "user" and (turn.get("transcript") or "").strip():
            return ("transcript", turn["transcript"])
    if kind == "delegation.created" and (event.get("item") or {}).get("id"):
        return ("delegation", event["item"]["id"])
    if kind == "error":
        return ("error", (event.get("error") or {}).get("message") or t("err.live"))
    return None


def _norm(text):
    return re.sub(r"[^\w]+", "", text.lower())


class TranscriptBuffer:
    """Кусочки текста -> фразы; итоговый текст хода не дублирует уже отданные фразы.

    OpenAI делегирует только первую фразу сессии, дальше присылает лишь кусочки текста —
    поэтому фразу закрываем сами, по паузе в кусочках (FLUSH_S).
    """

    def __init__(self):
        self.partial = ""
        self.early = []
        self.last = 0.0      # когда пришёл последний кусочек

    def add(self, fragment):
        self.partial += fragment
        self.last = time.monotonic()

    def flush(self):
        text, self.partial = self.partial, ""
        if not text.strip():
            return None
        self.early = (self.early + [text])[-50:]
        return text

    def due(self):
        """Пора закрывать фразу: есть текст и кусочки давно не приходили."""
        return bool(self.partial.strip()) and time.monotonic() - self.last > FLUSH_S

    def on_delegation(self):
        return self.flush()

    def on_final(self, text):
        final = _norm(text)
        for count in range(len(self.early), 0, -1):
            for start in range(len(self.early) - count + 1):
                if _norm("".join(self.early[start:start + count])) == final:
                    del self.early[start:start + count]
                    return None
        self.partial = ""
        return text


# ---------- сессия

class LiveSession:
    """Одна live-сессия в своём потоке с asyncio.

    on_text(text)   — распознанная фраза
    on_state(state, detail) — "connecting" / "live" / "closed" / "error"
    """

    def __init__(self, on_text, on_state, log):
        self.on_text = on_text
        self.on_state = on_state
        self.log = log
        self.loop = None
        self.track = None
        self._stop = None
        self._cancel = False     # stop() мог прийти раньше, чем поднялся asyncio
        self._thread = None

    # ---- управление из других потоков

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def feed(self, samples):
        if self.track:
            self.track.feed(samples)

    def stop(self):
        self._cancel = True
        if self.loop and self._stop:
            self.loop.call_soon_threadsafe(self._stop.set)

    # ---- внутренности

    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._main())
        except Exception as e:
            self.log.exception(t("log.live_crash"))
            self.on_state("error", str(e))
        finally:
            self.track = None
            self.loop.close()
            self.on_state("closed", "")

    @staticmethod
    def _post_call(sdp, headers):
        """Отдаём SDP-предложение, получаем SDP-ответ и id звонка."""
        body = json.dumps({
            "sdp": sdp,
            "session": {
                "model": MODEL,
                "instructions": PROMPT,
                "audio": {"output": {"voice": "cove"}},
                "delegation": {"type": "client", "ack_filler": False},
            },
        }).encode()
        req = urllib.request.Request(CALL_URL, data=body, method="POST",
                                     headers={**headers, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            answer = resp.read().decode()
            location = resp.headers.get("location") or ""
            call_id = next((p for p in location.split("/") if re.match(r"^rtc_[\w-]+$", p)), None)
            call_id = call_id or resp.headers.get("openai-session-id")
        if not call_id or not answer.strip():
            raise RuntimeError(t("err.live_no_call"))
        return answer, call_id

    async def _main(self):
        self._stop = asyncio.Event()
        if self._cancel:
            return
        self.on_state("connecting", "")
        headers = make_headers(*credentials())

        # без STUN: сбор адресов мгновенный (со STUN ждёт 5 с), сервер OpenAI доступен напрямую
        pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
        self.track = MicTrack(self.loop)
        pc.addTrack(self.track)
        pc.createDataChannel("oai-events")

        # голос модели нам не нужен — просто выбрасываем
        blackhole = MediaBlackhole()

        @pc.on("track")
        def on_track(track):
            blackhole.addTrack(track)

        try:
            await pc.setLocalDescription(await pc.createOffer())
            answer, call_id = await asyncio.to_thread(self._post_call, pc.localDescription.sdp, headers)
            if self._cancel:
                return
            await pc.setRemoteDescription(RTCSessionDescription(sdp=answer, type="answer"))
            await blackhole.start()
            self.log.info(t("log.live_call"), call_id)

            async with websockets.connect(SIDEBAND_URL + call_id, additional_headers=headers) as ws:
                self.on_state("live", "")
                reader = asyncio.create_task(self._read(ws))
                stopper = asyncio.create_task(self._stop.wait())
                if self._cancel:
                    self._stop.set()
                await asyncio.wait({reader, stopper}, return_when=asyncio.FIRST_COMPLETED)
                try:
                    await ws.send(json.dumps({"type": "session.close"}))
                except Exception:
                    pass
                reader.cancel()
        finally:
            await blackhole.stop()
            await pc.close()

    async def _flusher(self, buf):
        """Закрывает фразу по паузе в кусочках текста."""
        while True:
            await asyncio.sleep(0.2)
            if buf.due():
                text = buf.flush()
                if text:
                    self.on_text(text)

    async def _read(self, ws):
        buf = TranscriptBuffer()
        flusher = asyncio.create_task(self._flusher(buf))
        try:
            await self._read_loop(ws, buf)
        finally:
            flusher.cancel()

    async def _read_loop(self, ws, buf):
        async for raw in ws:
            result = parse_event(raw)
            if not result:
                continue
            kind, value = result

            if kind == "fragment":
                buf.add(value)
            elif kind == "delegation":
                text = buf.on_delegation()
                if text:
                    self.on_text(text)
                # говорим модели, что текст ушёл агенту (как jauvex)
                await ws.send(json.dumps({
                    "type": "delegation.context.append",
                    "delegation_item_id": value,
                    "channel": "commentary",
                    "content": [{"type": "input_text", "text": "The transcript is sent directly to the coding agent."}],
                }))
            elif kind == "transcript":
                text = buf.on_final(value)
                if text:
                    self.on_text(text)
            elif kind == "error":
                self.log.warning("live: %s", value)
                self.on_state("error", value)
