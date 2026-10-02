# Orca Voice

**English** · [Русский](README.ru.md)

A voice remote for coding agents running in [Orca](https://github.com/stablyai/orca) on macOS.
Say a word — and Space or Enter goes to the Orca tab in focus. Dictate a prompt, jump to the next
agent tab, and have the agent's answer read back to you. Hands stay off the keyboard.

- **Voice commands** — Space, Enter, next agent tab, stop the voice. The trigger words are yours to choose.
- **Voice typing** — everything you say is typed into the focused tab; finish the phrase with the Enter word to send it.
- **Answers read aloud** — when an agent (Claude, Codex, OpenCode) finishes, the macOS voice reads its reply.
- **Runs locally** — speech recognition is [whisper.cpp](https://github.com/ggml-org/whisper.cpp) on your Mac.
- **Two interface languages** — English and Russian, switched with the RU / EN buttons in the window header.

## Requirements

- macOS 13 or newer
- [Orca](https://github.com/stablyai/orca) with its `orca` command-line tool available in `PATH`
- Python 3 (developed and tested on 3.14)
- whisper.cpp: `brew install whisper-cpp` (provides `whisper-server`)

## Install

```sh
git clone https://github.com/goblin-red/orca-voice.git
cd orca-voice

# Python environment
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Whisper model (about 190 MB)
mkdir -p models
curl -L -o models/ggml-small-q5_1.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small-q5_1.bin
```

## Run

```sh
./start.sh     # or double-click "Orca Voice.app" in this folder
./stop.sh      # closing the window also quits everything
```

On the first start macOS asks for microphone access. Your settings are saved to `config.json`,
which is created from `config.default.json` on the first run.

## Voice commands

| Default word | What it does |
| --- | --- |
| `dumble bumble` | Space to the focused tab (in Claude with `/voice` on: start or stop recording) |
| `rex` | Enter — send the message to the agent |
| `switch terminal` | Go to the next agent tab in the active project, in a loop |
| `shut up` | Interrupt the voice while it is reading an answer |

Russian words work out of the box too: «дамбл-бамбл», «рекс», «переключи терминал», «заткнись».

Every command accepts a list of variants — the ways Whisper may hear the word. Matching is fuzzy
(by the consonant skeleton), so small differences are fine. If a word does not trigger, look at the
“Heard” line on the Dashboard and add that spelling in **Settings → Voice commands**.

Without voice typing, say a command as a separate short phrase. With voice typing on, you can put it
at the end of a sentence: “audit the project, rex”.

## Languages

- **Interface** — the RU / EN buttons in the window header. They switch the window, statuses, the log
  and the service phrases the voice says.
- **Recognition** — a separate setting: **Settings → Recognition (Whisper) → Language**.
- **Voice** — pick a macOS voice that matches the language of your agents' answers.

## OpenAI mode (experimental)

Besides local Whisper there is a cloud mode that streams the microphone to OpenAI's realtime
speech service. It needs no API key: it uses **your own** ChatGPT subscription through the Codex
sign-in on your computer (`codex login`, which creates `~/.codex/auth.json`). Nothing is bundled with
this repository — each user signs in with their own account.

Please note:

- This is an unofficial, undocumented endpoint. It may change or stop working at any time, and using it
  is at your own risk.
- In this mode your microphone audio is sent to OpenAI. In standard mode all audio stays on your Mac.

## Files

| File | Purpose |
| --- | --- |
| `app.py` | The core: window, modes, commands, settings |
| `listener.py` | Microphone and the speech detector |
| `whisper_srv.py` | Starts `whisper-server` and sends phrases to it |
| `matcher.py` | Finds command words in recognized text |
| `orca_cli.py` | Talks to Orca through its CLI |
| `speaker.py` | Watches the agents and reads their answers aloud |
| `live.py` | OpenAI mode |
| `settings_server.py` | Local server (127.0.0.1) for the window |
| `ui.html`, `ui_texts.js` | The window and its texts in two languages |
| `i18n.py` | Statuses, log and voice phrases in two languages |
| `config.default.json` | Default settings |

Code comments are in Russian. Plans for the future are in [PLANS.md](PLANS.md) (in Russian).

## License

[MIT](LICENSE)
