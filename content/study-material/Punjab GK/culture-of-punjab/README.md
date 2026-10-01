# culture-of-punjab — Study Material

Study → General Knowledge → Punjab GK → **culture-of-punjab**.

This folder *is* the registration: there is no category list to append to, no
language list, no chapter list and no page to write. Everything this category
shows — its name, its description, its chapter count and its page count — comes
from the files that sit here.

    <this folder>/<language>/<chapter>/<file>    a folder is a language, a
                                                 folder is a chapter, a file
                                                 is a part

```bash
mkdir -p "content/study-material/culture-of-punjab/punjabi/my-chapter"
cp "part-1.pdf" "content/study-material/culture-of-punjab/punjabi/my-chapter/"
npm run publish
```

and a reader reaches it at
**Study → General Knowledge → Punjab GK → culture-of-punjab → Punjabi → my-chapter → Part 1**.

- The hierarchy this folder hangs from: the `hierarchies` block in
  `content/study-material/metadata.json`
- What gets derived, and the optional overrides:
  `content/study-material/README.md`
- Supported: `.pdf`, `.md`, `.json` — `README.md` is ignored
