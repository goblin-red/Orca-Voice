#!/bin/bash
# Установщик GOBL(in) Voice для Mac с Apple Silicon (macOS 14+). Ничего не требует заранее:
# сам скачивает программу, свой Python, whisper-server и модель Whisper.
#
#   установить или обновить:
#     curl -fsSL https://raw.githubusercontent.com/goblin-red/Orca-Voice/main/install.sh | bash
#   удалить:
#     ~/.goblin-voice/install.sh --uninstall
#
# Всё ставится в ~/.goblin-voice, в «Программы» кладётся только значок запуска.
# Права администратора, Homebrew и Xcode не нужны.

set -euo pipefail

REPO="goblin-red/Orca-Voice"
BRANCH="main"
WHISPER_RELEASE="v1.0"          # выпуск на GitHub, в котором лежит whisper-server
WHISPER_VERSION="1.9.4"
WHISPER_SHA256="ababe6aaae08737db20bbcf3a9d6360d1fe3d08ae95b39572855b4f1277acb35"
PYTHON_VERSION="3.13"
MODEL="ggml-small-q5_1.bin"
MODELS_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main"
APP_NAME="GOBL(in) Voice"
BUNDLE_ID="local.orca-voice"

DEST="${GOBLIN_VOICE_DIR:-$HOME/.goblin-voice}"

# ---------- сообщения

bold=$(printf '\033[1m'); red=$(printf '\033[31m'); reset=$(printf '\033[0m')
step() { printf '\n%s==> %s%s\n' "$bold" "$1" "$reset"; }
info() { printf '    %s\n' "$1"; }
warn() { printf '%s    Warning: %s%s\n' "$red" "$1" "$reset"; }
die()  { trap - ERR; printf '\n%sError: %s%s\n' "$red" "$1" "$reset" >&2; exit 1; }

trap 'printf "\n%sInstallation failed (line %s). Run the installer again to retry.%s\n" "$red" "$LINENO" "$reset" >&2' ERR

# ---------- проверки

[ "$(uname -s)" = "Darwin" ] || die "GOBL(in) Voice works on macOS only."
case "$DEST" in ""|"/"|"$HOME"|"$HOME/") die "Bad install folder: '$DEST'";; esac

# папка «Программы»: общая, а если туда нельзя писать — личная
if [ -n "${GOBLIN_VOICE_APPS:-}" ]; then
  APPS="$GOBLIN_VOICE_APPS"
elif [ -w /Applications ]; then
  APPS="/Applications"
else
  APPS="$HOME/Applications"
fi
APP="$APPS/$APP_NAME.app"

# наш ли это значок запуска (чужое приложение с таким же именем не трогаем)
is_our_app() {
  [ -f "$1/Contents/Info.plist" ] && grep -q "$BUNDLE_ID" "$1/Contents/Info.plist"
}

# ---------- удаление

if [ "${1:-}" = "--uninstall" ]; then
  [ -f "$DEST/app.py" ] || die "GOBL(in) Voice is not installed in $DEST."
  step "Removing $APP_NAME"
  sh "$DEST/stop.sh" >/dev/null 2>&1 || true
  for app in "/Applications/$APP_NAME.app" "$HOME/Applications/$APP_NAME.app" "$APP" "$APPS/Goblin Voice.app"; do
    if is_our_app "$app"; then rm -rf "$app"; info "removed $app"; fi
  done
  rm -rf "$DEST"
  info "removed $DEST (program, settings, models)"
  printf '\n%s was uninstalled.\n' "$APP_NAME"
  exit 0
fi

if [ -n "${1:-}" ]; then
  echo "Usage: install.sh [--uninstall]"
  case "$1" in --help|-h) exit 0;; *) exit 1;; esac
fi

# процессор: настоящий, даже если Терминал запущен через Rosetta
if [ "$(sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" != "1" ]; then
  die "This installer supports Macs with Apple Silicon (M1 and newer). Intel Macs are not supported yet."
fi

MACOS_MAJOR=$(sw_vers -productVersion | cut -d. -f1)
[ "$MACOS_MAJOR" -ge 14 ] || die "macOS 14 (Sonoma) or newer is required; this Mac runs $(sw_vers -productVersion)."

if [ -e "$APP" ] && ! is_our_app "$APP"; then
  die "Another application named '$APP_NAME' already exists in $APPS."
fi

printf '%s%s installer%s\n' "$bold" "$APP_NAME" "$reset"
info "Mac: Apple Silicon, macOS $(sw_vers -productVersion)"
info "Program folder: $DEST"
info "Launcher: $APP"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ---------- 1. программа

step "1/7  Getting $APP_NAME"

# если установщик запущен из папки с программой (например, из распакованного архива) — берём её
SELF="${BASH_SOURCE[0]:-}"
SRC=""
if [ -n "$SELF" ] && [ -f "$SELF" ]; then
  SELF_DIR="$(cd "$(dirname "$SELF")" && pwd)"
  if [ -f "$SELF_DIR/app.py" ] && [ "$SELF_DIR" != "$DEST" ]; then SRC="$SELF_DIR"; fi
fi

if [ -n "$SRC" ]; then
  info "from $SRC"
else
  info "downloading from github.com/$REPO"
  mkdir -p "$TMP/src"
  curl -fsSL "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" | tar -xz --strip-components 1 -C "$TMP/src"
  SRC="$TMP/src"
fi
[ -f "$SRC/app.py" ] || die "The program files are incomplete."

# прошлую копию останавливаем: файлы под ней сейчас поменяются
if [ -f "$DEST/stop.sh" ]; then sh "$DEST/stop.sh" >/dev/null 2>&1 || true; fi

# настройки, журналы, модели и окружение при обновлении остаются на месте
mkdir -p "$DEST"
rsync -a --delete \
  --exclude ".git" --exclude ".DS_Store" --exclude "__pycache__" \
  --exclude "config.json" --exclude "logs" --exclude "models" \
  --exclude ".venv" --exclude "bin" --exclude "python" --exclude ".uv-cache" \
  "$SRC/" "$DEST/"
chmod +x "$DEST/start.sh" "$DEST/stop.sh" "$DEST/install.sh"
info "version $(cat "$DEST/VERSION" 2>/dev/null || echo "?")"

# ---------- 2. Python и пакеты

step "2/7  Setting up Python $PYTHON_VERSION (private copy)"

mkdir -p "$DEST/bin"
UV="$DEST/bin/uv"
if [ ! -x "$UV" ]; then
  info "downloading uv (Python installer)"
  curl -fsSL "https://github.com/astral-sh/uv/releases/latest/download/uv-aarch64-apple-darwin.tar.gz" \
    | tar -xz --strip-components 1 -C "$DEST/bin"
fi

# свой Python и свой кэш — внутри папки программы, система не затрагивается
export UV_PYTHON_INSTALL_DIR="$DEST/python"
export UV_CACHE_DIR="$DEST/.uv-cache"
export UV_PYTHON_PREFERENCE="only-managed"
export UV_NO_CONFIG=1
export UV_NO_PROGRESS=1

if [ ! -x "$DEST/.venv/bin/python" ]; then
  "$UV" venv --quiet --python "$PYTHON_VERSION" "$DEST/.venv"
fi

# проверенные версии пакетов и только готовые сборки: ничего не компилируется на месте
# (proxy-tools — крошечный пакет на чистом Python, готовой сборки у него нет)
info "installing packages"
"$UV" pip install --quiet --compile-bytecode --python "$DEST/.venv/bin/python" \
  --only-binary :all: --no-binary proxy-tools \
  -r "$DEST/requirements.lock.txt"
rm -rf "$DEST/.uv-cache"
info "$("$DEST/.venv/bin/python" --version)"

# ---------- 3. whisper-server

step "3/7  Getting whisper-server $WHISPER_VERSION"

if [ "$(cat "$DEST/bin/.whisper-version" 2>/dev/null)" != "$WHISPER_VERSION" ] || [ ! -x "$DEST/bin/whisper-server" ]; then
  WHISPER_TAR="whisper-server-$WHISPER_VERSION-macos-arm64.tar.gz"
  if [ -n "${GOBLIN_VOICE_WHISPER_DIR:-}" ]; then
    cp "$GOBLIN_VOICE_WHISPER_DIR/$WHISPER_TAR" "$TMP/$WHISPER_TAR"       # для проверки до выпуска
  else
    curl -fsSL -o "$TMP/$WHISPER_TAR" "https://github.com/$REPO/releases/download/$WHISPER_RELEASE/$WHISPER_TAR"
  fi
  # сверяем контрольную сумму: файл должен быть ровно тем, что собран для выпуска
  [ "$(shasum -a 256 "$TMP/$WHISPER_TAR" | cut -d" " -f1)" = "$WHISPER_SHA256" ] || die "whisper-server download is corrupted."
  tar -xzf "$TMP/$WHISPER_TAR" -C "$DEST/bin"
  chmod +x "$DEST/bin/whisper-server"
  echo "$WHISPER_VERSION" > "$DEST/bin/.whisper-version"
fi
"$DEST/bin/whisper-server" --help >/dev/null 2>&1 || die "whisper-server does not start on this Mac."
info "ready"

# ---------- 4. модель Whisper

step "4/7  Getting the speech model ($MODEL, about 190 MB)"

mkdir -p "$DEST/models"
if [ -f "$DEST/models/$MODEL" ]; then
  info "already downloaded"
else
  curl -fL --progress-bar -o "$DEST/models/$MODEL.part" "$MODELS_URL/$MODEL"
  mv "$DEST/models/$MODEL.part" "$DEST/models/$MODEL"
fi

# ---------- 5. прогрев

step "5/7  Preparing the first start"

# При первом запуске macOS проверяет новые файлы, а Whisper готовит ускорение на видеочипе —
# это десятки секунд. Делаем это сейчас, чтобы программа открылась сразу.
"$DEST/.venv/bin/python" -c "import webview, sounddevice, numpy, aiortc, av, websockets" >/dev/null 2>&1 || true

WARM_PORT=$("$DEST/.venv/bin/python" -c "import socket; s = socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1])")
"$DEST/bin/whisper-server" -m "$DEST/models/$MODEL" --host 127.0.0.1 --port "$WARM_PORT" >/dev/null 2>&1 &
WARM_PID=$!
for _ in $(seq 1 180); do
  curl -s -m 1 -o /dev/null "http://127.0.0.1:$WARM_PORT/" && break
  kill -0 "$WARM_PID" 2>/dev/null || break
  sleep 0.5
done
kill "$WARM_PID" 2>/dev/null || true
wait "$WARM_PID" 2>/dev/null || true
info "done"

# ---------- 6. значок запуска

step "6/7  Adding $APP_NAME to $APPS"

mkdir -p "$APPS"
# значок с прежним названием убираем, чтобы в «Программах» не осталось двух
if is_our_app "$APPS/Goblin Voice.app"; then rm -rf "$APPS/Goblin Voice.app"; fi
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp "$DEST/$APP_NAME.app/Contents/Info.plist" "$APP/Contents/Info.plist"
cat > "$APP/Contents/MacOS/orca-voice" <<LAUNCHER
#!/bin/sh
# Запуск из Finder: PATH там пустой, поэтому задаём его сами (в том числе путь к команде orca)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/Applications/Orca.app/Contents/Resources/bin:\$PATH"
DIR="$DEST"
mkdir -p "\$DIR/logs"
cd "\$DIR"
exec "\$DIR/.venv/bin/python" "\$DIR/app.py" >> "\$DIR/logs/stdout.log" 2>&1
LAUNCHER
chmod +x "$APP/Contents/MacOS/orca-voice"
touch "$APP"
info "done"

# ---------- 7. Orca

step "7/7  Checking Orca"

if command -v orca >/dev/null 2>&1 || [ -x /Applications/Orca.app/Contents/Resources/bin/orca ]; then
  info "found"
else
  warn "Orca was not found. $APP_NAME controls agent tabs in Orca — install it from https://github.com/stablyai/orca"
fi

# ---------- готово

printf '\n%s%s is installed.%s\n' "$bold" "$APP_NAME" "$reset"
info "Open it from $APPS (or Spotlight: $APP_NAME). macOS will ask for microphone access on the first start."
info "Update: run this installer again.   Uninstall: $DEST/install.sh --uninstall"

if [ -z "${GOBLIN_VOICE_NO_LAUNCH:-}" ]; then
  open "$APP" || true
fi
