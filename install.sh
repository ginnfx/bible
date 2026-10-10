#!/usr/bin/env bash
# Downloads the latest standalone `bible` binary from this repo's GitHub
# Releases and puts it on the PATH. No Python, no cloning, no build step.
# (Windows: install.ps1, or the installer on the Releases page.)
set -euo pipefail

REPO="ginnfx/bible"
INSTALL_DIR="${BIBLE_INSTALL_DIR:-$HOME/.local/bin}"

os="$(uname -s)"
arch="$(uname -m)"

case "$os-$arch" in
    Darwin-arm64) asset="bible-macos-arm64" ;;
    Linux-x86_64) asset="bible-linux-x86_64" ;;
    *)
        echo "No prebuilt binary for $os $arch yet." >&2
        echo "Install from source instead: bash setup.sh" >&2
        exit 1
        ;;
esac

echo "Downloading bible ($asset)..."
mkdir -p "$INSTALL_DIR"
# /releases/latest/download/ always points at the newest release's asset,
# so there's no API call (or its rate limit) to look the tag up first.
if ! curl -fsSL "https://github.com/$REPO/releases/latest/download/$asset" -o "$INSTALL_DIR/bible"; then
    echo "Couldn't download the binary. Check https://github.com/$REPO/releases" >&2
    exit 1
fi
chmod +x "$INSTALL_DIR/bible"

echo "Installed to $INSTALL_DIR/bible"

case ":$PATH:" in
    *":$INSTALL_DIR:"*) ;;
    *)
        echo
        echo "$INSTALL_DIR isn't on your PATH yet. Add this to your shell profile:"
        echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
        ;;
esac

echo
echo "Run: bible"
