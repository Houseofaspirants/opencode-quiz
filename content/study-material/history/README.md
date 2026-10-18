# History — Study Material

Add chapters inside their period folder. No chapter registration or special PDF name is needed:

    history/ancient-history/english/<chapter>/<file.pdf>
    history/ancient-history/punjabi/<chapter>/<file.pdf>
    history/medieval-history/english/<chapter>/<file.pdf>
    history/medieval-history/punjabi/<chapter>/<file.pdf>
    history/modern-history/english/<chapter>/<file.pdf>
    history/modern-history/punjabi/<chapter>/<file.pdf>

Put multiple parts in the same chapter folder. Use the same chapter folder name
in English and Punjabi to count them as translations of one chapter. PDF file
names may differ; the chapter label comes from its folder. A new chapter in one
period cannot collide with an identically named chapter in another period.

Run `npm run publish` after adding files, then push through your usual flow.
The website groups new chapters under the period automatically on the next build.

Older `history/<language>/<chapter>/<file>` paths still work, but new uploads
should use a period folder so they are assigned automatically.
