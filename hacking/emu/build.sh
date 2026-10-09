#!/bin/sh
# Build the headless mGBA harness.  Needs cmake, a C compiler and git.
#   sh build.sh            -> ./gbarun
set -e
cd "$(dirname "$0")"
if [ ! -d mgba ]; then
    git clone --depth 1 --branch 0.10.5 https://github.com/mgba-emu/mgba.git mgba
fi
cmake -S mgba -B mgba/build -DCMAKE_BUILD_TYPE=Release -DBUILD_STATIC=ON -DBUILD_SHARED=OFF \
      -DBUILD_QT=OFF -DBUILD_SDL=OFF -DUSE_DEBUGGERS=ON -DUSE_GDB_STUB=ON -DM_CORE_GB=OFF \
      -DUSE_FFMPEG=OFF -DUSE_PNG=OFF -DUSE_ZLIB=OFF -DUSE_LIBZIP=OFF -DUSE_SQLITE3=OFF \
      -DUSE_MINIZIP=OFF -DUSE_EPOXY=OFF -DUSE_ELF=OFF -DUSE_LUA=OFF -DENABLE_SCRIPTING=OFF \
      -DBUILD_LTO=ON >/dev/null
cmake --build mgba/build --target mgba -j"$(nproc 2>/dev/null || echo 2)"
cc -O2 -I mgba/include -I mgba/build/include gbarun.c mgba/build/libmgba.a -lm -lpthread -o gbarun
echo "built ./gbarun"
