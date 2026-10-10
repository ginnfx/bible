# Standalone builds

Turns `bible` into a single executable a recipient can run with no Python
install, no `pip`, and no `import-data` step - everything (interpreter,
Textual/PyYAML, and a content-only copy of the Bible database) is bundled
in. Tagged builds are published to this repo's GitHub Releases (see
[Distributing](#distributing)).

## What's bundled

- The Python runtime and all dependencies (PyInstaller `--onefile`).
- `bible_tui/data/schema.sql` and `bible_tui/ui/themes.tcss`.
- A **content-only** seed database (`packaging/seed/bible.db`) -
  translations, verses, Strong's, cross-references, commentary. Built by
  `scripts/build_seed_db.py`, which strips every user-data table
  (bookmarks, notes, highlights, reading history, settings - anything a
  reader has personally added) out of a real database before it's bundled.
  **Never bundle a raw copy of your own `~/.config/bible-tui/bible.db`
  directly** - it has your personal reading data in it.

On first run, if the resolved config directory has no `bible.db` yet, the
app copies the bundled seed into place automatically (`bible_tui/data/
database.py`'s `ensure_seeded`) - so `bible read "John 3:16"` works the
moment the executable is run, before any configuration exists.

## Building

### macOS (native)

```bash
./packaging/build_macos.sh
```

Builds `dist/macos/bible`. Runs on the architecture it's built on
(Apple Silicon vs Intel) - this project's own builds so far are arm64.

### Linux x86_64 (via Docker/colima - no Linux machine needed)

```bash
# One-time, if Docker isn't already set up on macOS:
brew install colima docker
colima start --arch x86_64 --cpu 4 --memory 6 --disk 30

./packaging/build_linux.sh
```

Builds `dist/linux-x86_64/bible` inside a `python:3.11-slim-bullseye`
container - an older glibc (2.31) so the binary also runs on newer
distros (Ubuntu 20.04+, Debian 11+, most others from the last ~5 years).
glibc compatibility only goes forward, never back, so building on the
*newest* base would silently narrow who can run the result.

### Windows x86_64 (native, on a Windows machine)

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```

Builds `dist\windows\bible.exe`. If [Inno Setup 6](https://jrsoftware.org/isinfo.php)
is installed (`winget install JRSoftware.InnoSetup`), it also builds
`dist\windows\bible-windows-x86_64-setup.exe` from
[`windows/bible.iss`](windows/bible.iss). That's a per-user installer
(no admin prompt) that adds a Start menu entry, puts `bible` on the user
PATH, and registers an uninstaller under Settings › Apps.

Nuitka doesn't cross-compile, so this needs Windows. The `windows-latest`
leg of `.github/workflows/build.yml` runs the same steps on every `v*` tag.

## Distributing

Pushing a `v*` tag runs `.github/workflows/build.yml`, which builds all
three platforms and attaches them to a GitHub Release on this repo:

- `bible-windows-x86_64-setup.exe`: the installer most Windows users want
- `bible-windows-x86_64.exe`: the bare executable, no install
- `bible-macos-arm64`, `bible-linux-x86_64`

`install.sh` and `install.ps1` always fetch the newest release. A manual run
of the workflow builds without publishing; download the binaries from that
run's artifacts.

A local build is also just one file you can hand over directly. On
Linux/macOS the recipient may need `chmod +x bible` once if the executable
bit didn't survive the transfer.
