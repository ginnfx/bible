#!/usr/bin/env bash
# Downloads the latest standalone `bible` binary from the releases repo and
# puts it on the PATH. No Python, no cloning, no build step.
set -euo pipefail

REPO="ginnfx/bible-tui-releases"
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

tag="$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
    | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')"
if [ -z "$tag" ]; then
    echo "Couldn't find a release. Check https://github.com/$REPO/releases" >&2
    exit 1
fi

echo "Downloading bible $tag ($asset)..."
mkdir -p "$INSTALL_DIR"
curl -fsSL "https://github.com/$REPO/releases/download/$tag/$asset" -o "$INSTALL_DIR/bible"
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
