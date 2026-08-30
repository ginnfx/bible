# Standalone builds

Turns `bible` into a single executable a recipient can run with no Python
install, no `pip`, and no `import-data` step - everything (interpreter,
Textual/PyYAML, and a content-only copy of the Bible database) is bundled
in. Nothing here is published anywhere; a build is a file you hand
someone directly.

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

### Windows x86_64

Not built yet - PyInstaller doesn't cross-compile, and there's no Windows
host or reliable Wine-based path available here. Building this needs
either a real Windows machine/VM running `packaging/build_macos.sh`'s
approach (a `.spec`-driven PyInstaller build, same spec file, just run on
Windows), or wiring a `windows-latest` matrix leg into the existing
`build.yml` workflow. Tracked as a follow-up, the same way the
tabs/split-views reader work is.

## Distributing

Hand over the single file (`dist/macos/bible` or
`dist/linux-x86_64/bible`) - no installer needed. On Linux/macOS the
recipient may need `chmod +x bible` once if the executable bit didn't
survive the transfer.
