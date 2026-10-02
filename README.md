# GOBL(in) Voice

**English** · [Русский](README.ru.md)

A voice remote for coding agents running in [Orca](https://github.com/stablyai/orca) on macOS.
Say a word — and Space or Enter goes to the Orca tab in focus. Dictate a prompt, jump to the next
agent tab, and have the agent's answer read back to you. Hands stay off the keyboard.
One of the extra apps of [GOBL(in)](https://goblin.red).

- **Voice commands** — Space, Enter, next agent tab, stop the voice. The trigger words are yours to choose.
- **Voice typing** — everything you say is typed into the focused tab; finish the phrase with the Enter word to send it.
- **Answers read aloud** — when an agent (Claude, Codex, OpenCode) finishes, the macOS voice reads its reply.
- **Runs locally** — speech recognition is [whisper.cpp](https://github.com/ggml-org/whisper.cpp) on your Mac.
- **Two interface languages** — English and Russian, English by default, switched with the EN / RU buttons in the window header.

## Requirements

- A Mac with Apple Silicon (M1 or newer) and macOS 14 or newer
- [Orca](https://github.com/stablyai/orca)

Intel Macs are not supported yet.

## Install

Paste this line into Terminal:

```sh
curl -fsSL https://raw.githubusercontent.com/goblin-red/Orca-Voice/main/install.sh | bash
```

It takes about two minutes and needs no administrator rights, Homebrew or Xcode. The installer:

- puts the program into `~/.goblin-voice` with its own private Python — nothing else on your Mac is touched;
- downloads `whisper-server` (whisper.cpp built for Apple Silicon) and the speech model (about 190 MB);
- adds **GOBL(in) Voice** to your Applications folder and starts it.

On the first start macOS asks for microphone access.

| | |
| --- | --- |
| Start | Open **GOBL(in) Voice** from Applications or Spotlight |
| Quit | Close the window |
| Update | Run the install line again — your settings and models are kept |
| Uninstall | `~/.goblin-voice/install.sh --uninstall` |

<details>
<summary>Manual install (for developers)</summary>

Needs Python 3.13 or 3.14 and whisper.cpp (`brew install whisper-cpp`, provides `whisper-server`).

```sh
git clone https://github.com/goblin-red/Orca-Voice.git
cd Orca-Voice

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

mkdir -p models
curl -L -o models/ggml-small-q5_1.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small-q5_1.bin

./start.sh     # or double-click "GOBL(in) Voice.app" in this folder
./stop.sh      # closing the window also quits everything
```

Your settings are saved to `config.json`, which is created from `config.default.json` on the first run.

</details>

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

- **Interface** — English by default; the EN / RU buttons in the window header. They switch the window, statuses, the log
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
| `ui.html`, `ui_texts.js`, `logo.svg` | The window, its texts in two languages and the logo |
| `i18n.py` | Statuses, log and voice phrases in two languages |
| `config.default.json` | Default settings |
| `install.sh` | The installer |
| `requirements.lock.txt` | Tested package versions used by the installer |
| `tools/build-whisper-server.sh` | Builds the `whisper-server` file published in the release |

Code comments are in Russian. Changes are listed in [CHANGELOG.md](CHANGELOG.md), plans for the future in [PLANS.md](PLANS.md) (both in Russian).

## License

[MIT](LICENSE)
