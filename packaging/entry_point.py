"""The packaged app's entry point - a real .py file on disk, since neither
PyInstaller nor Nuitka can target a console-script string the way pip
install can."""

from bible_tui.cli import main

if __name__ == "__main__":
    main()
