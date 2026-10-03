#!/usr/bin/env python3
"""Re-encode PDF first-page previews (assets/img/pdf/<hash>.jpg|png) as WebP.

The Mac draws a new preview with sips, which cannot write WebP. When that
machine has no cwebp and no Pillow, the preview stays a JPEG; run this once
anywhere Pillow is installed, then rebuild:

    python3 scripts/previews_to_webp.py
    node scripts/build_content_manifest.ts   # picks the .webp, sweeps the .jpg

Same picture, same size, about 60% fewer bytes.
"""
import pathlib
import sys

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is needed: pip install pillow")

DIR = pathlib.Path(__file__).resolve().parent.parent / "assets" / "img" / "pdf"
done = 0
for src in sorted(DIR.glob("*")):
    if src.suffix not in (".jpg", ".png") or len(src.stem) != 12:
        continue
    out = src.with_suffix(".webp")
    with Image.open(src) as im:
        im.convert("RGB").save(out, "WEBP", quality=72, method=6)
    src.unlink()
    done += 1
print(f"previews converted to WebP: {done}")
