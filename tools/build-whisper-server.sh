#!/bin/bash
# Сборка whisper-server (whisper.cpp) для выпуска на GitHub: один файл без внешних библиотек,
# Apple Silicon, macOS 13+, ускорение Metal. Нужны cmake и инструменты командной строки Xcode.
#
#   tools/build-whisper-server.sh [папка для результата]
#
# Результат — whisper-server-<версия>-macos-arm64.tar.gz; его скачивает install.sh.
set -euo pipefail

VERSION="1.9.4"
OUT="$(mkdir -p "${1:-dist}" && cd "${1:-dist}" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

git clone --quiet --depth 1 --branch "v$VERSION" https://github.com/ggml-org/whisper.cpp.git "$WORK/whisper.cpp"
cd "$WORK/whisper.cpp"

cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=13.0 \
  -DBUILD_SHARED_LIBS=OFF \
  -DGGML_NATIVE=OFF \
  -DGGML_OPENMP=OFF \
  -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON \
  -DWHISPER_BUILD_TESTS=OFF \
  -DWHISPER_BUILD_EXAMPLES=ON \
  -DWHISPER_BUILD_SERVER=ON \
  -DWHISPER_SDL2=OFF \
  -DWHISPER_CURL=OFF > /dev/null
cmake --build build --target whisper-server -j 8 > /dev/null

# GGML_NATIVE=OFF — без подстройки под процессор сборочной машины;
# шейдеры Metal вшиты в файл, поэтому рядом с ним ничего класть не нужно
mkdir pack
cp build/bin/whisper-server pack/
cp LICENSE pack/whisper.cpp-LICENSE.txt
strip -x pack/whisper-server
codesign --force --sign - pack/whisper-server      # подпись «для себя»: без неё файл на ARM не запустится

TAR="$OUT/whisper-server-$VERSION-macos-arm64.tar.gz"
COPYFILE_DISABLE=1 tar -czf "$TAR" -C pack whisper-server whisper.cpp-LICENSE.txt

echo "$TAR"
echo "  $(file -b pack/whisper-server)"
echo "  библиотеки: $(otool -L pack/whisper-server | tail -n +2 | awk '{print $1}' | sed 's|.*/||' | tr '\n' ' ')"
echo "  минимальная macOS: $(otool -l pack/whisper-server | grep -A4 LC_BUILD_VERSION | grep minos | awk '{print $2}')"
