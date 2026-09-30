# Polity — Study Material

Folders, not lists, are the registration. Four levels, in order:

    <this subject>/README.md
    <this subject>/metadata.json                 optional, keyed by file name
    <this subject>/<language>/<chapter>/<file>    a folder is a language, a
                                                  folder is a chapter, a file
                                                  is a part

```bash
mkdir -p content/study-material/polity/english/my-chapter
cp "part-1.pdf" content/study-material/polity/english/my-chapter/
npm run publish
```

and a reader reaches it at **Study → Polity → English → my-chapter → Part 1**.
Nothing is registered by hand: no subject list, no language list, no chapter
list.

The subject page shows **only** its language cards (🇵🇺 Punjabi / 🇬🇧 English)
until one is chosen — then that language's chapters, then that chapter's parts
in reading order. Languages are discovered from folder names, so a folder this
site has never seen (`urdu/`, `hindi/`) becomes a language of its own on the
next build.

- What can be uploaded and what gets derived: `content/study-material/README.md`
- Optional overrides: `metadata.json` here (all of this subject), beside a
  chapter, or beside the file itself — the nearest one wins
- Supported: `.pdf`, `.md`, `.json` — `README.md` is ignored

The Constitution, Parliament, judiciary, panchayati raj and fundamental rights.
