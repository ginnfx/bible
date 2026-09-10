# bible

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

An open-source Bible reader for the terminal, built with
[Textual](https://textual.textualize.io/),  and three public-domain translations (KJV, ASV, WEB).

The reading experience follows
[christ-cli](https://github.com/whoisyurii/christ-cli) - the Books │
Chapters │ Scripture layout, vim-style movement, live preview, themes,
`y`/`Y` copy on top of this project's own SQLite-backed study features.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/ginnfx/bible/main/install.sh | bash
```

Downloads the latest standalone binary (macOS Apple Silicon or Linux
x86_64) and puts `bible` on your PATH. No Python required.

Other platforms, or to run from source instead:

```bash
bash setup.sh
```

Or manually:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
python scripts/import_data.py   # one-time Bible data import (~80MB db)
```

Config and database live under `~/.config/bible-tui/`. Pass `--profile
NAME` (or set `BIBLE_TUI_PROFILE`) to keep separate config/database pairs.

Building your own standalone binary is covered in [`packaging/`](packaging/).

## Usage

```sh
bible                              # launch the interactive browser
bible read "John 3:16"             # a verse, range, or chapter
bible "1cor 13:4-7"                # bare form means `read`
bible search "love one another"
bible random
bible today                        # same verse all day, new one tomorrow
bible stats
bible read "John 3:16" -t ASV      # override the last-used translation
```

References are forgiving (`jn 3:16`, `1cor 13`, `Ps 23`). Lookup commands
are pipe-aware - plain text when piped, a rendered card in a terminal.

### Data

```sh
bible check [--thorough]                  # verify database integrity
bible backup [path] [--personal]          # dated copy, or just your own data
bible restore <path> [--replace]          # merge in, or mirror exactly
bible print "John 3:16"                   # via CUPS (macOS/Linux)
```

## The browser

| Key | Action |
|---|---|
| `←` `→` / `h` `l` | switch panels |
| `↑` `↓` / `j` `k` | move within the focused panel |
| `enter` | open book / load chapter / open study view |
| `g` | go to a reference |
| `alt+←` `alt+→` | history back / forward |
| `tab` `shift+tab` | narrow Books panel by testament/category |
| `/` | live search |
| `p` | toggle verse-per-line ⇄ paragraph view |
| `y` / `Y` | copy verse / start a verse range |
| `t` | cycle themes |
| `v` | choose translation |
| `s` | study view: interlinear, cross references, commentary |
| `ctrl+t` | browse topics |
| `[` `]` | previous / next chapter |
| `f` | focus mode |
| `\` | compare verse across translations |
| `r` | random verse |
| `R` | reading modes (memorise, dictate, quiz, speed-read, listen, sermon, contemplative, meditative, prayer, journal) |
| `e` | export chapter (text, Markdown, JSON, CSV) |
| `ctrl+p` | print chapter |
| `b` / `B` | toggle / name bookmark |
| `ctrl+b` | browse bookmarks and reading lists |
| `*` | toggle favourite |
| `m` | cycle highlight colour |
| `n` | add or edit a note |
| `D` | display settings |
| `P` | reading plans |
| `S` | your reading record |
| `?` | full keybinding reference |
| `q` `q` | quit |

Position, translation, theme, and per-book chapter are all saved on exit.
Copying uses the native clipboard and OSC 52, so it works over SSH.


## Tests

```bash
pytest
```

Service-layer tests need no setup; `test_app_smoke.py`'s integration tests
need a fully-imported `bible.db` and skip automatically otherwise.

## Data sources

All Bible text is public domain; the Strong's lexicon and cross-reference
compilations are CC-BY-SA derivatives of public-domain material.

- **KJV, ASV**: [scrollmapper/bible_databases](https://github.com/scrollmapper/bible_databases)
- **WEB**: [seven1m/open-bibles](https://github.com/seven1m/open-bibles)
- **Strong's dictionaries**: [openscriptures/strongs](https://github.com/openscriptures/strongs)
- **Cross references**: scrollmapper/bible_databases `sources/extras` (openbible.info)
- **Commentary**: [lyteword/mhenry-concise](https://github.com/lyteword/mhenry-concise) - Matthew Henry's Concise Commentary

`scripts/import_data.py` rebuilds `bible.db` from these sources from scratch;
it isn't part of the shipped app.

## License

Licensed under the [GNU General Public License v3.0 or later](LICENSE).
You're free to run, study, modify, and redistribute this software, provided
any distributed modified version is licensed under the GPL too and comes
with its source. The bundled CC-BY-SA data above keeps its own attribution
and share-alike terms independent of the code's license.
