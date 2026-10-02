"""Микрофон + простой детектор речи по громкости: режет поток на короткие фразы."""

import io
import queue
import threading
import wave
from collections import deque

import numpy as np
import sounddevice as sd

from i18n import t

RATE = 16000
FRAME = 480            # 30 мс
FRAME_MS = 30
PREROLL_FRAMES = 10    # 300 мс звука до начала речи, чтобы не срезать первый слог


def to_wav(samples):
    """float32 [-1..1] -> байты WAV 16 бит моно."""
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


class Listener(threading.Thread):
    """Слушает микрофон и вызывает on_phrase(wav_bytes, long, spoken) на каждую фразу.

    long=True   — кусок длинной речи (например, пока читает голос): в нём ищем только «заткнись».
    spoken=True — во время фразы звучал наш голос: её нельзя печатать, только искать «заткнись».
    dictation   — включён голосовой ввод: фразы до dictation_max_s, длинная речь режется без повторов.
    tap — если задан, звук уходит туда (режим OpenAI), а свой детектор речи молчит.
    hold — если возвращает True (говорит наш голос), в tap идёт тишина, а звук слушаем сами:
           так ответ ИИ не попадёт в OpenAI, а «заткнись» всё равно услышим.
    """

    def __init__(self, vad_cfg, on_phrase, log):
        super().__init__(daemon=True)
        self.cfg = vad_cfg
        self.on_phrase = on_phrase
        self.log = log
        self.paused = False
        self.level = 0.0          # текущая громкость (для меню)
        self.tap = None           # куда отдавать звук в режиме OpenAI
        self.hold = None          # функция: True — пока говорит наш голос
        self.dictation = False    # голосовой ввод текста в штатном режиме
        self.mute_on_speech = True  # пока говорит голос — микрофон полностью выключен
        self._muted = False
        self._held = False
        self._reset = False       # сбросить незаконченную фразу
        self._frames = queue.Queue()
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def reset(self):
        """Забыть недослушанную фразу (после live-режима)."""
        self._reset = True

    def _callback(self, indata, frames, time_info, status):
        samples = indata[:, 0].copy()
        tap = self.tap
        if self.paused:
            # микрофон выключен — никуда ничего не идёт (в OpenAI — тишина)
            if tap:
                tap(np.zeros_like(samples))
            self.level = 0.0
            return
        speaking = bool(self.hold and self.hold())

        # говорит голос и включено «выключать микрофон» — не слушаем вообще
        if speaking and self.mute_on_speech:
            if tap:
                tap(np.zeros_like(samples))
            self.level = 0.0
            self._muted = True
            return
        if self._muted:
            self._muted = False
            self._reset = True     # забываем обрывки, пойманные вокруг голоса

        held = bool(tap and speaking)

        if tap and not held:
            if self._held:
                self._reset = True     # голос замолчал — забываем, что слушали сами
            tap(samples)
        else:
            if tap:
                tap(np.zeros_like(samples))   # OpenAI получает тишину
            self._frames.put((samples, speaking))
        self._held = held

    def run(self):
        noise = self.cfg["min_level"] / 2  # плавающий уровень фонового шума
        preroll = deque(maxlen=PREROLL_FRAMES)
        speech = []                        # кадры текущей фразы
        loud_run = 0                       # сколько громких кадров подряд
        quiet_run = 0                      # сколько тихих кадров подряд в речи
        was_long = False                   # фраза уже резалась на куски
        spoken = False                     # во время фразы звучал наш голос
        overlap = 1000 // FRAME_MS         # 1 с перекрытия между кусками

        with sd.InputStream(samplerate=RATE, channels=1, dtype="float32",
                            blocksize=FRAME, callback=self._callback):
            self.log.info(t("log.mic_open"))
            while not self._stop.is_set():
                try:
                    frame, speaking = self._frames.get(timeout=0.5)
                except queue.Empty:
                    continue

                if self.paused or self._reset:
                    self._reset = False
                    speech, was_long, spoken, quiet_run, loud_run = [], False, False, 0, 0
                    preroll.clear()
                    continue

                # настройки читаем каждый кадр — их можно менять на ходу
                min_level = self.cfg["min_level"]
                start_ratio = self.cfg["start_ratio"]
                silence_frames = self.cfg["silence_ms"] // FRAME_MS
                min_frames = self.cfg["min_speech_ms"] // FRAME_MS
                max_s = self.cfg.get("dictation_max_s", 30) if self.dictation else self.cfg["max_speech_s"]
                max_frames = int(max_s * 1000 / FRAME_MS)

                rms = float(np.sqrt(np.mean(frame ** 2)))
                self.level = rms
                threshold = max(min_level, noise * start_ratio)

                # ---- тишина: ждём начала речи
                if not speech:
                    preroll.append(frame)
                    if rms > threshold:
                        loud_run += 1
                        if loud_run >= 2:
                            speech = list(preroll)
                            quiet_run = 0
                            spoken = speaking
                    else:
                        loud_run = 0
                        noise = noise * 0.98 + rms * 0.02   # подстраиваемся под фон
                    continue

                # ---- идёт речь
                speech.append(frame)
                spoken = spoken or speaking
                quiet_run = quiet_run + 1 if rms < threshold * 0.7 else 0

                if len(speech) > max_frames:
                    if self.dictation and not spoken:
                        # диктовка: отдаём кусок целиком и продолжаем без повторов
                        self.on_phrase(to_wav(np.concatenate(speech)), False, False)
                        speech = []
                    else:
                        # длинная речь: кусок только для «заткнись», продолжаем с перекрытием
                        self.on_phrase(to_wav(np.concatenate(speech)), True, spoken)
                        speech = speech[-overlap:]
                        was_long = True
                    spoken = speaking

                if quiet_run >= silence_frames:
                    # конец фразы
                    if len(speech) - quiet_run >= min_frames:
                        self.on_phrase(to_wav(np.concatenate(speech)), was_long, spoken)
                    speech = []
                    preroll.clear()
                    loud_run = 0
                    quiet_run = 0
                    was_long = False
                    spoken = False
