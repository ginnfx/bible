#!/usr/bin/env bash
# Downloads the latest standalone `bible` binary from this repo's GitHub
# Releases and adds its install directory to the user's shell PATH. No Python,
# no cloning, no build step.
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

# Persist the install directory in the user's startup file. Since this script
# is usually piped into bash, it cannot update the calling terminal's PATH;
# the change takes effect in newly opened shells.
quoted_install_dir="'${INSTALL_DIR//\'/\'\\\'\'}'"
shell_name="${SHELL##*/}"
case "$shell_name" in
    bash)
        profile="$HOME/.bashrc"
        path_line="export PATH=$quoted_install_dir:\"\$PATH\""
        ;;
    zsh)
        profile="$HOME/.zshrc"
        path_line="export PATH=$quoted_install_dir:\"\$PATH\""
        ;;
    fish)
        profile="$HOME/.config/fish/config.fish"
        fish_install_dir="${INSTALL_DIR//\\/\\\\}"
        fish_install_dir="${fish_install_dir//\'/\\\'}"
        path_line="fish_add_path -- '$fish_install_dir'"
        ;;
    *)
        profile="$HOME/.profile"
        path_line="export PATH=$quoted_install_dir:\"\$PATH\""
        ;;
esac

mkdir -p "$(dirname "$profile")"
touch "$profile"
if ! grep -Fqx -- "$path_line" "$profile"; then
    printf '\n%s\n' "$path_line" >> "$profile"
    echo "Added $INSTALL_DIR to PATH in $profile"
else
    echo "$INSTALL_DIR is already configured in $profile"
fi

case ":$PATH:" in
    *":$INSTALL_DIR:"*) ;;
    *)
        echo "Open a new terminal, or run this now to use bible in this one:"
        echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
        ;;
esac

echo
echo "Run: bible"
