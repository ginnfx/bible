#!/usr/bin/env bash
# Builds the standalone Linux x86_64 `bible` executable inside a container,
# so the host doesn't need a Linux machine - only Docker (or colima on
# macOS: `brew install colima docker && colima start --arch x86_64`).
#
# Uses Nuitka (compiles to real machine code) rather than a bytecode-
# freezing tool - it runs faster and starts up quicker than a frozen-
# bytecode archive.
set -euo pipefail
cd "$(dirname "$0")/.."

# An older base (Debian 11/bullseye, glibc 2.31) so the built binary runs
# on older host systems too - glibc is forward- but not backward-compatible,
# so building on the newest base would silently narrow who can run it.
IMAGE="python:3.11-slim-bullseye"
CONTAINER_NAME="bible-tui-linux-build"

docker run --rm --platform linux/amd64 --name "$CONTAINER_NAME" \
    -v "$PWD":/src -w /src "$IMAGE" \
    bash -c '
        set -e
        # bullseye (Debian 11) is past its normal support window, so its
        # packages moved to the archive mirror - the default one 404s.
        sed -i "s|deb.debian.org|archive.debian.org|g; s|security.debian.org|archive.debian.org|g" /etc/apt/sources.list
        sed -i "/bullseye-security/d" /etc/apt/sources.list
        apt-get update -qq && apt-get install -y -qq binutils gcc patchelf >/dev/null
        pip install --quiet --upgrade pip
        pip install --quiet -e ".[packaging]"
        python -m nuitka \
            --onefile \
            --output-dir=dist/linux-x86_64 \
            --output-filename=bible \
            --include-data-file=bible_tui/data/schema.sql=bible_tui/data/schema.sql \
            --include-data-file=bible_tui/ui/themes.tcss=bible_tui/ui/themes.tcss \
            --include-data-file=packaging/seed/bible.db=seed/bible.db \
            --assume-yes-for-downloads \
            --remove-output \
            --jobs=2 \
            packaging/entry_point.py
    '

echo "Linux x86_64 build: dist/linux-x86_64/bible"
