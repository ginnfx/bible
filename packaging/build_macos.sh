#!/usr/bin/env bash
# Builds the standalone macOS `bible` executable, natively, on a Mac.
#
# Uses Nuitka (compiles to real machine code) rather than a bytecode-
# freezing tool - it runs faster and starts up quicker than a frozen-
# bytecode archive.
set -euo pipefail
cd "$(dirname "$0")/.."

VENV=".venv"
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install --quiet -e ".[packaging]"

echo "Building seed database (content only - your reading data is stripped)..."
"$VENV/bin/python" scripts/build_seed_db.py

# `xcrun`'s own clang works from a clean shell; if something on this
# machine's PATH shadows `clang` (a Swift toolchain manager, an old
# CommandLineTools symlink, ...), Nuitka would pick that one up instead.
# Pointing CC/CXX at the real one directly sidesteps that entirely, and
# SDKROOT is what makes a bare `clang` invocation find libSystem at all.
export SDKROOT="$(xcrun --show-sdk-path)"
export CC="$(xcrun -f clang)"
export CXX="$(xcrun -f clang++)"

"$VENV/bin/python" -m nuitka \
    --onefile \
    --output-dir=dist/macos \
    --output-filename=bible \
    --include-data-file=bible_tui/data/schema.sql=bible_tui/data/schema.sql \
    --include-data-file=bible_tui/ui/themes.tcss=bible_tui/ui/themes.tcss \
    --include-data-file=packaging/seed/bible.db=seed/bible.db \
    --assume-yes-for-downloads \
    --remove-output \
    packaging/entry_point.py

echo "macOS build: dist/macos/bible"
