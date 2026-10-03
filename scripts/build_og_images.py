#!/usr/bin/env python3
"""Share images (og:image) for the landing pages: one 1200x630 JPEG per topic,
Punjabi topic, quiz and exam page, in the site's dark-navy and gold style.

    python3 scripts/build_og_images.py          # draw what is new or changed
    python3 scripts/build_og_images.py --force  # redraw everything

Why: a link shared on WhatsApp / Telegram / X shows its og:image. One shared
cover for every page makes every link look the same; a card that names the
topic, the question count and the language gets opened.

How it fits the build:
  * reads data/landing-manifest.json, data/index.json, data/quiz-manifest.json
    and data/exams.json - run it AFTER build_landing_pages.py;
  * writes assets/img/og/<page>.jpg plus assets/img/og/index.json (one hash
    per image, so an unchanged page is never redrawn);
  * build_landing_pages.py points a page's og:image / twitter:image at its
    card when the file exists, and at assets/img/og-cover.png otherwise - so a
    machine without Pillow (or a page added since the last run) still ships a
    valid share image. Run build_landing_pages.py again after this script.

Fonts live in scripts/fonts/ (Inter, SIL Open Font License). Drop
NotoSansGurmukhi-Bold.ttf (also OFL, from Google Fonts) into the same folder
and the Punjabi pages print their Gurmukhi titles; without it they carry the
English title marked "In Punjabi".
"""
import hashlib
import json
import pathlib
import sys

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:
    print("build_og_images: Pillow not installed - pages keep og-cover.png")
    sys.exit(0)

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "assets" / "img" / "og"
FONTS = ROOT / "scripts" / "fonts"
VERSION = "og-1"                      # bump to redraw every card
W, H = 1200, 630

NAVY = (11, 15, 25)
GOLD = (245, 192, 64)
GOLD_SOFT = (232, 196, 110)
WHITE = (255, 255, 255)
MUTED = (168, 178, 204)
LINE = (52, 64, 96)

TITLE_FONT = FONTS / "InterDisplay-ExtraBold.otf"
LABEL_FONT = FONTS / "Inter-SemiBold.otf"
GURMUKHI_FONT = FONTS / "NotoSansGurmukhi-Bold.ttf"
HAS_GURMUKHI = GURMUKHI_FONT.exists()


def font(path, size):
    return ImageFont.truetype(str(path), size)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def is_gurmukhi(text):
    return any("਀" <= ch <= "੿" for ch in text)


# ------------------------------------------------------------------ data --
landing = read(DATA / "landing-manifest.json").get("pages", [])
index = read(DATA / "index.json")
SUBJECTS = {s["id"]: s for s in index.get("subjects", [])}
TOPICS = {}
for s in index.get("subjects", []):
    cats = {c.get("id"): c for c in s.get("categories", [])}
    for t in s.get("topics", []):
        TOPICS[(s["id"], t["id"])] = (s, cats.get(t.get("category")), t)
PA_TITLES = {(x.get("subject"), x.get("id")): (x.get("titles") or {}).get("pa", "")
             for x in read(DATA / "quiz-manifest.json").get("topics", [])}
EXAMS = {e["id"]: e for e in read(DATA / "exams.json").get("exams", [])}


def card_for(page):
    """(eyebrow, title, chips, title_is_gurmukhi) for one landing page."""
    kind, entity = page.get("type"), page.get("entity", "")
    if kind in ("topic", "quiz", "topic-pa"):
        sid, tid = entity.split("/", 1)
        if (sid, tid) not in TOPICS:
            return None
        s, c, t = TOPICS[(sid, tid)]
        count = int(t.get("count") or 0)
        eyebrow = s["name"] + (f"  ·  {c['name']}" if c else "")
        if kind == "topic-pa":
            pa = PA_TITLES.get((sid, tid)) or ""
            if HAS_GURMUKHI and is_gurmukhi(pa):
                return (eyebrow, pa, [f"{count} MCQ", "ਪੰਜਾਬੀ",
                                      "ਉੱਤਰ + ਵਿਆਖਿਆ"], True)
            return (eyebrow, t["name"], [f"{count} MCQs", "In Punjabi", "Answers explained"], False)
        if kind == "quiz":
            return (eyebrow, t["name"], [f"{count} MCQs", "Timed quiz", "Instant score"], False)
        langs = t.get("availableLanguages") or list((t.get("variants") or {}).keys())
        lang_chip = "English + Punjabi" if "pa" in langs else "Answers explained"
        return (eyebrow, t["name"], [f"{count} MCQs", lang_chip, "Free"], False)
    if kind == "exam":
        e = EXAMS.get(entity)
        if not e:
            return None
        chips = ["Syllabus", "PYQ papers" if e.get("pyq") else "Topic quizzes", "Free notes"]
        return ("Exam preparation", e["name"], chips, False)
    return None


# --------------------------------------------------------------- drawing --
def background():
    img = Image.new("RGB", (W, H), NAVY)
    glow = Image.new("RGB", (W, H), NAVY)
    g = ImageDraw.Draw(glow)
    g.ellipse((560, -140, 1380, 760), fill=(22, 44, 104))
    g.ellipse((-260, 380, 520, 900), fill=(26, 30, 58))
    return Image.blend(img, glow.filter(ImageFilter.GaussianBlur(120)), 0.9)


def wrap(draw, text, fnt, width, max_lines):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=fnt) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines if len(lines) <= max_lines else None


def fit_title(draw, text, path, width):
    for size in (76, 70, 64, 58, 52, 46, 42):
        fnt = font(path, size)
        lines = wrap(draw, text, fnt, width, 3)
        if lines:
            return fnt, lines, size
    fnt = font(path, 42)
    lines = wrap(draw, text, fnt, width, 99) or [text]
    lines = lines[:3]
    lines[-1] = lines[-1].rstrip(". ") + "…"
    return fnt, lines, 42


LOGO = None


def logo():
    global LOGO
    if LOGO is None:
        src = Image.open(ROOT / "assets" / "img" / "logo-mark.png").convert("RGBA")
        src = src.resize((300, 300), Image.LANCZOS)
        # an app-icon tile: rounded corners and a thin gold edge, so the
        # mark's own black square reads as a deliberate frame on the glow
        mask = Image.new("L", (300, 300), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, 299, 299), radius=36, fill=255)
        src.putalpha(mask)
        ImageDraw.Draw(src).rounded_rectangle((1, 1, 298, 298), radius=36,
                                              outline=(245, 192, 64, 150), width=2)
        LOGO = src
    return LOGO


def draw_card(eyebrow, title, chips, gurmukhi_title):
    img = background()
    d = ImageDraw.Draw(img)
    left, text_w = 72, 720

    # brand line
    d.line((left, 78, left + 44, 78), fill=GOLD, width=3)
    d.text((left + 60, 66), "HOUSE OF ASPIRANTS", font=font(LABEL_FONT, 22), fill=GOLD)

    # eyebrow (subject / category)
    ey_font = font(LABEL_FONT, 24)
    ey = eyebrow.upper()
    while d.textlength(ey, font=ey_font) > text_w and len(ey) > 8:
        ey = ey[:-2]
    d.text((left, 128), ey, font=ey_font, fill=MUTED)

    # title
    tpath = GURMUKHI_FONT if gurmukhi_title else TITLE_FONT
    tfont, lines, size = fit_title(d, title, tpath, text_w)
    y = 176
    lh = int(size * (1.32 if gurmukhi_title else 1.12))
    for i, line in enumerate(lines):
        d.text((left, y), line, font=tfont, fill=WHITE if i < len(lines) - 1 or len(lines) == 1 else GOLD_SOFT)
        y += lh

    # chips
    cfont = font(GURMUKHI_FONT if (gurmukhi_title and HAS_GURMUKHI) else LABEL_FONT, 24)
    x, cy = left, 470
    for chip in chips:
        tw = d.textlength(chip, font=cfont)
        box = (x, cy, x + tw + 36, cy + 50)
        d.rounded_rectangle(box, radius=25, outline=GOLD, width=2, fill=(20, 26, 44))
        d.text((x + 18, cy + (8 if not is_gurmukhi(chip) else 4)), chip, font=cfont, fill=WHITE)
        x = box[2] + 14

    # footer
    d.line((left, 556, left + text_w, 556), fill=LINE, width=1)
    d.text((left, 572), "houseofaspirants.in", font=font(LABEL_FONT, 24), fill=GOLD)
    d.text((left + 268, 572), "Free  ·  Punjab exam prep", font=font(LABEL_FONT, 24), fill=MUTED)

    # logo, right side
    lg = logo()
    img.paste(lg, (W - 300 - 70, (H - 300) // 2 - 10), lg)
    return img


# ------------------------------------------------------------------ main --
def out_name(page_file):
    return page_file.replace("/", "-")[:-5] + ".jpg"


def main():
    force = "--force" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    idx_path = OUT / "index.json"
    old = read(idx_path) if idx_path.exists() and not force else {}
    new, drawn = {}, 0
    for page in landing:
        card = card_for(page)
        if not card:
            continue
        name = out_name(page["file"])
        key = hashlib.sha1(json.dumps([VERSION, HAS_GURMUKHI, card],
                                      ensure_ascii=False).encode()).hexdigest()[:16]
        new[name] = key
        if old.get(name) == key and (OUT / name).exists():
            continue
        draw_card(*card).save(OUT / name, "JPEG", quality=84, optimize=True, progressive=True)
        drawn += 1
    for f in OUT.glob("*.jpg"):                 # cards for pages that are gone
        if f.name not in new:
            f.unlink()
    idx_path.write_text(json.dumps(dict(sorted(new.items())), indent=1) + "\n", encoding="utf-8")
    print(f"build_og_images: {len(new)} share cards, {drawn} drawn"
          + ("" if HAS_GURMUKHI else " (no Gurmukhi font - Punjabi pages use English titles)"))


if __name__ == "__main__":
    main()
