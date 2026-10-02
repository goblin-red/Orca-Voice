"""Ищет в распознанной фразе команды:

«дамбл-бамбл»   -> space  (пробел)
«рекс»          -> enter
«тузик-арбузик» -> toggle (переключить режим: штатный <-> OpenAI)
«переключи терминал» -> switch (следующая вкладка с агентом)
«заткнись»      -> stop   (прервать голос)

Сравниваем по звучанию, а не по написанию (идея из jauvex): Whisper путает гласные,
поэтому сверяем «скелет» из согласных и допускаем небольшую разницу в буквах.
"""

import re

# латиница -> кириллица, если Whisper написал слово латиницей ("rex", "dumble bumble")
LATIN = {
    "a": "а", "b": "б", "c": "к", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "х",
    "i": "и", "j": "дж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о", "p": "п",
    "q": "к", "r": "р", "s": "с", "t": "т", "u": "а", "v": "в", "w": "в", "x": "кс",
    "y": "й", "z": "з",
}
VOWELS = re.compile(r"[аеёиоуыэюяйьъ]+")


def squash(text):
    """Нижний регистр, латиница в кириллицу, только буквы."""
    text = text.lower().replace("ё", "е")
    text = "".join(LATIN.get(ch, ch) for ch in text)
    return re.sub(r"[^а-я]+", "", text)


def skeleton(text):
    """Только согласные: «дамблбамбл» -> «дмблбмбл»."""
    return VOWELS.sub("", squash(text))


def distance(a, b):
    """Расстояние Левенштейна."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def split_words(text):
    return [w for w in re.split(r"[\s,.!?;:…]+", text) if w]


class Variant:
    """Один вариант слова-команды.

    Длинный («дамбл-бамбл», «заткнись») — нечёткое сравнение по буквам и согласным.
    Короткий («рекс») — точное совпадение или тот же скелет согласных.
    """

    LONG = 7

    def __init__(self, text):
        self.sq = squash(text)
        self.skel = skeleton(text)
        self.long = len(self.sq) >= self.LONG

    def match(self, chunk):
        sq, sk = squash(chunk), skeleton(chunk)
        if not sq or not self.sq:
            return False
        if not self.long:
            return sq == self.sq or (len(sq) <= len(self.sq) + 1 and sk == self.skel)

        if self.sq in sq or (len(self.skel) >= 3 and self.skel in sk):
            return True
        if len(sq) > len(self.sq) * 1.6:
            return False
        return (distance(sq, self.sq) <= len(self.sq) // 3
                or distance(sk, self.skel) <= max(1, len(self.skel) // 4))


class Matcher:
    # «тузик-арбузик» (toggle) временно выключен: режим переключается тумблером в окне
    # ORDER = ("space", "toggle", "switch", "stop", "enter")
    ORDER = ("space", "switch", "stop", "enter")   # порядок проверки

    def __init__(self, cfg):
        self.variants = {}
        for name in self.ORDER:
            command = cfg["commands"].get(name) or {}
            if command.get("enabled", True):
                self.variants[name] = [Variant(w) for w in command.get("words", []) if w.strip()]
        self.max_words = cfg.get("max_words", 6)

    def match(self, name, chunk):
        return any(v.match(chunk) for v in self.variants.get(name, []))

    def is_enter(self, word):
        return self.match("enter", word)

    def _single(self, chunk):
        """Какая команда в этом куске (слово или пара слов) или None."""
        return next((name for name in self.variants if self.match(name, chunk)), None)

    def segments(self, text):
        """Фраза из режима OpenAI: текст и команды по порядку.

        «сделай аудит, рекс» -> [("text", "сделай аудит"), ("enter", None)]
        """
        tokens = re.findall(r"\S+", text)
        clean = [re.sub(r"[^\w-]+", "", t) for t in tokens]
        out, buf = [], []

        def flush():
            if buf:
                piece = " ".join(buf).rstrip(" ,;:—-")
                if piece:
                    out.append(("text", piece))
                buf.clear()

        i = 0
        while i < len(tokens):
            word = clean[i]
            nxt = clean[i + 1] if i + 1 < len(tokens) else ""
            single = self._single(word) if word else None
            pair = None
            if not single and word and nxt and not self._single(nxt):
                pair = self._single(word + nxt)

            if single or pair:
                flush()
                out.append((single or pair, None))
                i += 1 if single else 2
            else:
                buf.append(tokens[i])
                i += 1
        flush()
        return out

    def _has_stop(self, words):
        # слова и пары соседних слов: «shut up» — команда из двух слов
        chunks = words + [a + b for a, b in zip(words, words[1:])]
        return ["stop"] if any(self.match("stop", c) for c in chunks) else []

    def commands(self, text, long=False):
        """Список команд по порядку: ["space", "enter", ...].

        long=True — кусок длинной речи: в нём ищем только «заткнись»
        (чтобы не нажать Enter посреди диктовки).
        """
        words = split_words(text)
        if long or not words or len(words) > self.max_words:
            return self._has_stop(words)

        result = []
        i = 0
        while i < len(words):
            word = words[i]
            nxt = words[i + 1] if i + 1 < len(words) else ""

            single = self._single(word)
            if single:
                result.append(single)
                i += 1
                continue

            # «дамбл бамбл» / «тузик пузик» распознаны двумя словами
            pair = self._single(word + nxt) if nxt and not self._single(nxt) else None
            if pair:
                result.append(pair)
                i += 2
            else:
                i += 1
        return result
