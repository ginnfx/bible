#!/bin/bash
set -e

echo "Setting up bible...."

if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed."
    exit 1
fi

python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Python $python_version found"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -e .

if [ ! -f "$HOME/.config/bible-tui/bible.db" ]; then
    echo "Importing Bible data (this may take a minute)..."
    python scripts/import_data.py
else
    echo "Bible data already exists at $HOME/.config/bible-tui/bible.db"
fi

echo ""
echo "Setup complete."
echo ""
echo "To run the app:"
echo "  1. Activate the virtual environment: source .venv/bin/activate"
echo "  2. Launch: bible"
echo ""
echo "Other commands:"
echo "  bible read \"John 3:16\"        # read a verse, range, or chapter"
echo "  bible search \"love one another\""
echo "  bible today                   # verse of the day"
echo "  bible --help"
echo ""
