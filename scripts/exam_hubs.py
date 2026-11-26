"""exam_hubs.py - every exam guide becomes an exam hub plus one page per part.

    content/strategy/<guide>.md          one long guide per exam (source of truth)
                |
                v
    exams/<slug>.html                    the exam hub: overview + a card for
                                         every part of the exam
    exams/<slug>/<part>.html             one page per part, cut from the guide
                                         at its `##` headings
    pa/exams/<slug>.html, pa/exams/<slug>/<part>.html   the Punjabi edition

Students search "<exam> syllabus", "<exam> salary", "<exam> eligibility",
"<exam> physical standards" - one query, one page that answers it. The guide
stays the single thing an editor writes: this module never invents a fact, it
only decides which of the guide's own sections belong on which page.

Rules that keep the pages honest:

  * a part gets a page only when the guide has a heading for it. No salary
    heading, no salary page - never an empty "coming soon" page;
  * a heading can feed several parts ("Age, fee and pay" is eligibility,
    notification and salary at once); a heading nothing claims is treated as
    notification news ("Will there be posts in 2027?");
  * the Punjabi edition is classified from its own Gurmukhi headings, and the
    language switch on a part page only appears when the other language has
    that part too.

The URL of every guide is decided by config/exam-hubs.json (slug, names,
board). A guide missing from that file fails the build, so an exam can never
publish under an accidental URL.
"""

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "exam-hubs.json"
DOMAIN = "https://houseofaspirants.in"
HUB_DIR = "exams"

# Order of the cards on a hub and of the pills on every part page.
PARTS = ("notification", "eligibility", "exam-pattern", "syllabus",
         "prelims-syllabus", "mains-syllabus", "salary",
         "physical-standards", "preparation")

LABEL = {
    "overview": ("Overview", "ਸੰਖੇਪ", "🏠"),
    "notification": ("Notification", "ਨੋਟੀਫਿਕੇਸ਼ਨ", "🔔"),
    "eligibility": ("Eligibility", "ਯੋਗਤਾ", "✅"),
    "exam-pattern": ("Exam Pattern", "ਪੇਪਰ ਪੈਟਰਨ", "🧾"),
    "syllabus": ("Syllabus", "ਸਿਲੇਬਸ", "📚"),
    "prelims-syllabus": ("Prelims Syllabus", "ਪ੍ਰੀਲਿਮਸ ਸਿਲੇਬਸ", "📗"),
    "mains-syllabus": ("Mains Syllabus", "ਮੇਨਜ਼ ਸਿਲੇਬਸ", "📘"),
    "salary": ("Salary & Pay", "ਤਨਖ਼ਾਹ", "💰"),
    "physical-standards": ("Physical Standards", "ਫਿਜ਼ੀਕਲ ਟੈਸਟ", "🏃"),
    "preparation": ("Preparation Strategy", "ਤਿਆਰੀ ਰਣਨੀਤੀ", "🎯"),
    "previous-papers": ("Previous Papers", "ਪਿਛਲੇ ਪੇਪਰ", "📄"),
    "mock-tests": ("Free Mock Tests", "ਮੁਫ਼ਤ ਮੌਕ ਟੈਸਟ", "📝"),
}
SUB = {
    "notification": ("Vacancies, dates, fee & how to apply",
                     "ਅਸਾਮੀਆਂ, ਤਾਰੀਖਾਂ, ਫੀਸ ਅਤੇ ਅਪਲਾਈ ਕਰਨ ਦਾ ਤਰੀਕਾ"),
    "eligibility": ("Age limit, qualification & relaxation",
                    "ਉਮਰ ਹੱਦ, ਵਿੱਦਿਅਕ ਯੋਗਤਾ ਅਤੇ ਛੋਟ"),
    "exam-pattern": ("Marks, time, negative marking & stages",
                     "ਅੰਕ, ਸਮਾਂ, ਨੈਗੇਟਿਵ ਮਾਰਕਿੰਗ ਅਤੇ ਚੋਣ ਦੇ ਪੜਾਅ"),
    "syllabus": ("Official topics, section by section",
                 "ਹਰ ਹਿੱਸੇ ਦੇ official ਟਾਪਿਕ"),
    "prelims-syllabus": ("Official topics of the preliminary exam",
                         "ਪ੍ਰੀਲਿਮਸ (ਮੁੱਢਲੀ ਪ੍ਰੀਖਿਆ) ਦੇ official ਟਾਪਿਕ"),
    "mains-syllabus": ("Official topics of every mains paper",
                       "ਮੇਨਜ਼ (ਮੁੱਖ ਪ੍ਰੀਖਿਆ) ਦੇ ਹਰ ਪੇਪਰ ਦੇ official ਟਾਪਿਕ"),
    "salary": ("Pay scale and starting pay", "ਪੇਅ ਸਕੇਲ ਅਤੇ ਸ਼ੁਰੂਆਤੀ ਤਨਖ਼ਾਹ"),
    "physical-standards": ("Height, race & physical test events",
                           "ਕੱਦ, ਦੌੜ ਅਤੇ ਫਿਜ਼ੀਕਲ ਟੈਸਟ"),
    "preparation": ("Study plan & what to do first",
                    "ਪੜ੍ਹਾਈ ਪਲਾਨ ਅਤੇ ਪਹਿਲਾ ਕਦਮ"),
    "previous-papers": ("Official question papers & answer keys",
                        "official ਪ੍ਰਸ਼ਨ ਪੱਤਰ ਅਤੇ ਉੱਤਰ ਕੁੰਜੀਆਂ"),
    "mock-tests": ("Timed full-length mock test on the exam pattern",
                   "ਪੇਪਰ ਪੈਟਰਨ ਉੱਤੇ ਸਮਾਂ-ਬੱਧ ਪੂਰਾ ਮੌਕ ਟੈਸਟ"),
}

# Heading -> part. Every specific rule that matches applies; the notification
# rule only applies when nothing specific did (so "Eligibility (2026
# notification)" stays an eligibility heading), except that a fee is always
# notification news as well.
_RULES = {
    "physical-standards": (r"physical|\bpmt\b|\bpet\b|\bpst\b",
                           r"ਫਿਜ਼ੀਕਲ|ਸਰੀਰਕ|\bpmt\b|\bpet\b"),
    "syllabus": (r"syllabus|\bunits\b|what the main paper covers",
                 r"ਸਿਲੇਬਸ|\bunits\b|ਮੁੱਖ ਪੇਪਰ ਵਿੱਚ ਕੀ"),
    "exam-pattern": (r"pattern|selection|stage \d|papers? work|paper (actually )?asked"
                     r"|paper looked|papers show",
                     r"ਪੈਟਰਨ|ਚੋਣ|ਪੜਾਅ|ਪੇਪਰ ਕਿਹੋ ਜਿਹਾ"),
    "eligibility": (r"eligib|who can appear|\bage\b|attempts",
                    r"ਯੋਗਤਾ|ਉਮਰ|ਕੌਣ ਪੇਪਰ|attempts"),
    "salary": (r"\bpay\b|salary", r"ਤਨਖ਼ਾਹ|ਤਨਖਾਹ"),
    "preparation": (r"how to prepare|how i prepared|preparation plan|week plan",
                    r"ਤਿਆਰੀ ਕਿਵੇਂ|ਤਿਆਰੀ ਕੀਤੀ|ਤਿਆਰੀ ਪਲਾਨ|ਹਫ਼ਤੇ ਦੀ ਯੋਜਨਾ"),
}
_FEE = (r"\bfee\b", r"ਫੀਸ|ਫ਼ੀਸ")
_PRACTICE = (r"free practice", r"ਮੁਫ਼ਤ")
# A syllabus heading that names one stage of a two-stage exam gets its own
# page, so "Prelims syllabus" and "Mains syllabus" never share a page.
# ("What the main paper covers" is a one-stage exam's main paper - no match.)
_PRELIMS = (r"prelim|screening", r"ਪ੍ਰੀਲਿਮ|ਮੁੱਢਲੀ ਪ੍ਰੀਖਿਆ|ਸਕਰੀਨਿੰਗ|prelim")
_MAINS = (r"\bmains\b|main exam", r"ਮੇਨਜ਼|ਮੇਨਸ|ਮੁੱਖ ਪ੍ਰੀਖਿਆ|mains")


def _nfd(s):
    return unicodedata.normalize("NFD", str(s)).lower()


_RX = {k: tuple(re.compile(_nfd(p)) for p in pair) for k, pair in _RULES.items()}
_RX_FEE = tuple(re.compile(_nfd(p)) for p in _FEE)
_RX_PRACTICE = tuple(re.compile(_nfd(p)) for p in _PRACTICE)
_RX_PRELIMS = tuple(re.compile(_nfd(p)) for p in _PRELIMS)
_RX_MAINS = tuple(re.compile(_nfd(p)) for p in _MAINS)


def classify(heading, lang):
    """-> ("practice",) | tuple of PARTS the heading belongs to."""
    i = 1 if lang == "pa" else 0
    h = _nfd(re.sub(r"<[^>]+>", "", heading))
    if _RX_PRACTICE[i].search(h):
        return ("practice",)
    keys = [k for k in PARTS if k in _RX and _RX[k][i].search(h)]
    if "syllabus" in keys:
        if _RX_PRELIMS[i].search(h):
            keys[keys.index("syllabus")] = "prelims-syllabus"
        elif _RX_MAINS[i].search(h):
            keys[keys.index("syllabus")] = "mains-syllabus"
    if not keys or _RX_FEE[i].search(h):
        keys.append("notification")
    return tuple(k for k in PARTS if k in keys)


_H2 = re.compile(r'<h2 id="([^"]*)">(.*?)</h2>', re.S)


def split(body_html):
    """-> (preamble html, [(anchor, heading html, section html incl. <h2>)])"""
    marks = list(_H2.finditer(body_html))
    if not marks:
        return body_html, []
    pre = body_html[:marks[0].start()]
    out = []
    for n, m in enumerate(marks):
        end = marks[n + 1].start() if n + 1 < len(marks) else len(body_html)
        out.append((m.group(1), m.group(2), body_html[m.start():end]))
    return pre, out


def _plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html)).strip()


# --------------------------------------------------------------- titles -----
_TITLES = {
    "en": {
        "hub": ["{n} Exam{y}: Syllabus, Eligibility, Salary",
                "{n} Exam{y}: Syllabus & Eligibility", "{n} Exam{y}: Full Guide",
                "{n} Exam{y}"],
        "notification": ["{n} Notification{y}: Vacancies & Dates",
                         "{n} Notification{y}", "{n} Recruitment{y}"],
        "eligibility": ["{n} Eligibility{y}: Age Limit & Qualification",
                        "{n} Eligibility{y}: Age & Qualification", "{n} Eligibility{y}"],
        "exam-pattern": ["{n} Exam Pattern{y} & Selection Process",
                         "{n} Exam Pattern{y} & Selection", "{n} Exam Pattern{y}"],
        "syllabus": ["{n} Syllabus{y}: Subject-wise Topics", "{n} Syllabus{y}"],
        "prelims-syllabus": ["{n} Prelims Syllabus{y}: Paper-wise Topics",
                             "{n} Prelims Syllabus{y}", "{n} Prelims Syllabus"],
        "mains-syllabus": ["{n} Mains Syllabus{y}: Paper-wise Topics",
                           "{n} Mains Syllabus{y}", "{n} Mains Syllabus"],
        "salary": ["{n} Salary{y} & Pay Scale", "{n} Salary{y}"],
        "physical-standards": ["{n} Physical Standards{y}: Height & Tests",
                               "{n} Physical Test{y}: Height & Race",
                               "{n} Physical Standards{y}", "{n} Physical Test{y}"],
        "preparation": ["{n} Preparation Strategy{y}", "{n} Preparation Plan{y}",
                        "{n} Strategy{y}"],
    },
    "pa": {
        "hub": ["{n} ਪ੍ਰੀਖਿਆ{y}: ਸਿਲੇਬਸ, ਯੋਗਤਾ ਅਤੇ ਤਨਖ਼ਾਹ",
                "{n} ਪ੍ਰੀਖਿਆ{y}: ਸਿਲੇਬਸ ਅਤੇ ਯੋਗਤਾ", "{n} ਪ੍ਰੀਖਿਆ{y}"],
        "notification": ["{n} ਨੋਟੀਫਿਕੇਸ਼ਨ{y}: ਅਸਾਮੀਆਂ ਅਤੇ ਤਾਰੀਖਾਂ",
                         "{n} ਨੋਟੀਫਿਕੇਸ਼ਨ{y}", "{n} ਭਰਤੀ{y}"],
        "eligibility": ["{n} ਯੋਗਤਾ{y}: ਉਮਰ ਹੱਦ ਅਤੇ ਵਿੱਦਿਅਕ ਯੋਗਤਾ",
                        "{n} ਯੋਗਤਾ{y}: ਉਮਰ ਹੱਦ", "{n} ਯੋਗਤਾ{y}"],
        "exam-pattern": ["{n} ਪੇਪਰ ਪੈਟਰਨ{y} ਅਤੇ ਚੋਣ ਪ੍ਰਕਿਰਿਆ", "{n} ਪੇਪਰ ਪੈਟਰਨ{y}"],
        "syllabus": ["{n} ਸਿਲੇਬਸ{y}: ਹਿੱਸੇ ਅਨੁਸਾਰ ਟਾਪਿਕ", "{n} ਸਿਲੇਬਸ{y}"],
        "prelims-syllabus": ["{n} ਪ੍ਰੀਲਿਮਸ ਸਿਲੇਬਸ{y}", "{n} ਪ੍ਰੀਲਿਮਸ ਸਿਲੇਬਸ"],
        "mains-syllabus": ["{n} ਮੇਨਜ਼ ਸਿਲੇਬਸ{y}", "{n} ਮੇਨਜ਼ ਸਿਲੇਬਸ"],
        "salary": ["{n} ਤਨਖ਼ਾਹ{y} ਅਤੇ ਪੇਅ ਸਕੇਲ", "{n} ਤਨਖ਼ਾਹ{y}"],
        "physical-standards": ["{n} ਫਿਜ਼ੀਕਲ ਟੈਸਟ{y}: ਕੱਦ ਅਤੇ ਦੌੜ",
                               "{n} ਫਿਜ਼ੀਕਲ ਟੈਸਟ{y}"],
        "preparation": ["{n} ਤਿਆਰੀ ਰਣਨੀਤੀ{y}", "{n} ਤਿਆਰੀ{y}"],
    },
}
_DESCS = {
    "en": {
        "notification": "{n} notification{y}: vacancies, important dates, application fee, how to apply and the official notice, checked against the recruiting body's own documents.",
        "eligibility": "{n} eligibility{y}: age limit with category relaxation, educational qualification, the Punjabi requirement and every other condition in the official notification.",
        "exam-pattern": "{n} exam pattern{y}: number of questions, marks, time, negative marking, qualifying marks and every stage of selection, straight from the official notice.",
        "syllabus": "{n} syllabus{y}: the official topic-by-topic syllabus for every section of the paper, the marks each section carries and free practice for each topic.",
        "prelims-syllabus": "{n} prelims syllabus{y}: the official topic list for every preliminary paper, kept separate from the mains, with the marks and free practice.",
        "mains-syllabus": "{n} mains syllabus{y}: the official topic list for every paper of the main exam, kept separate from the prelims, with marks for each paper.",
        "salary": "{n} salary{y}: the pay scale and starting pay as the official notification gives them, with the related details. A free guide in English and Punjabi.",
        "physical-standards": "{n} physical standards{y}: minimum height and the physical test events with qualifying marks for men and women, from the official notification.",
        "preparation": "{n} preparation strategy{y}: a step-by-step study plan, what to study first, how to revise and practise with mocks, and free practice sets in both languages.",
    },
    "pa": {
        "notification": "{n} ਨੋਟੀਫਿਕੇਸ਼ਨ{y}: ਅਸਾਮੀਆਂ, ਜ਼ਰੂਰੀ ਤਾਰੀਖਾਂ, ਅਰਜ਼ੀ ਫੀਸ, ਅਪਲਾਈ ਕਰਨ ਦਾ ਤਰੀਕਾ ਅਤੇ official notice - ਭਰਤੀ ਕਰਨ ਵਾਲੀ ਸੰਸਥਾ ਦੇ ਆਪਣੇ ਦਸਤਾਵੇਜ਼ਾਂ ਤੋਂ।",
        "eligibility": "{n} ਯੋਗਤਾ{y}: ਉਮਰ ਹੱਦ ਅਤੇ ਵਰਗ ਅਨੁਸਾਰ ਛੋਟ, ਵਿੱਦਿਅਕ ਯੋਗਤਾ, ਪੰਜਾਬੀ ਦੀ ਸ਼ਰਤ ਅਤੇ ਬਾਕੀ ਸਾਰੀਆਂ ਸ਼ਰਤਾਂ - ਸਿੱਧਾ official notification ਤੋਂ।",
        "exam-pattern": "{n} ਪੇਪਰ ਪੈਟਰਨ{y}: ਸਵਾਲਾਂ ਦੀ ਗਿਣਤੀ, ਅੰਕ, ਸਮਾਂ, ਨੈਗੇਟਿਵ ਮਾਰਕਿੰਗ, ਪਾਸ ਅੰਕ ਅਤੇ ਚੋਣ ਦਾ ਹਰ ਪੜਾਅ - official notice ਅਨੁਸਾਰ, ਪੰਜਾਬੀ ਵਿੱਚ।",
        "syllabus": "{n} ਸਿਲੇਬਸ{y}: ਪੇਪਰ ਦੇ ਹਰ ਹਿੱਸੇ ਦਾ official ਸਿਲੇਬਸ, ਹਰ ਹਿੱਸੇ ਦੇ ਅੰਕ ਅਤੇ ਹਰ ਟਾਪਿਕ ਲਈ ਮੁਫ਼ਤ ਪ੍ਰੈਕਟਿਸ - ਪੰਜਾਬੀ ਅਤੇ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ।",
        "prelims-syllabus": "{n} ਪ੍ਰੀਲਿਮਸ ਸਿਲੇਬਸ{y}: ਮੁੱਢਲੀ ਪ੍ਰੀਖਿਆ ਦੇ ਹਰ ਪੇਪਰ ਦੇ official ਟਾਪਿਕ, ਮੇਨਜ਼ ਤੋਂ ਵੱਖਰੇ, ਅੰਕਾਂ ਅਤੇ ਮੁਫ਼ਤ ਪ੍ਰੈਕਟਿਸ ਸਮੇਤ - ਪੰਜਾਬੀ ਅਤੇ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ।",
        "mains-syllabus": "{n} ਮੇਨਜ਼ ਸਿਲੇਬਸ{y}: ਮੁੱਖ ਪ੍ਰੀਖਿਆ ਦੇ ਹਰ ਪੇਪਰ ਦੇ official ਟਾਪਿਕ, ਪ੍ਰੀਲਿਮਸ ਤੋਂ ਵੱਖਰੇ, ਹਰ ਪੇਪਰ ਦੇ ਅੰਕਾਂ ਸਮੇਤ - ਪੰਜਾਬੀ ਅਤੇ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ।",
        "salary": "{n} ਤਨਖ਼ਾਹ{y}: official notification ਅਨੁਸਾਰ ਪੇਅ ਸਕੇਲ ਅਤੇ ਸ਼ੁਰੂਆਤੀ ਤਨਖ਼ਾਹ, ਨਾਲ ਜੁੜੀ ਹੋਰ ਜਾਣਕਾਰੀ ਸਮੇਤ। ਪੰਜਾਬੀ ਅਤੇ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਮੁਫ਼ਤ ਗਾਈਡ।",
        "physical-standards": "{n} ਫਿਜ਼ੀਕਲ ਟੈਸਟ{y}: ਘੱਟੋ-ਘੱਟ ਕੱਦ ਅਤੇ ਫਿਜ਼ੀਕਲ ਟੈਸਟ ਦੇ ਈਵੈਂਟ, ਮਰਦਾਂ ਅਤੇ ਔਰਤਾਂ ਲਈ ਪਾਸ ਮਾਪਦੰਡਾਂ ਸਮੇਤ - official notification ਤੋਂ।",
        "preparation": "{n} ਤਿਆਰੀ ਰਣਨੀਤੀ{y}: ਕਦਮ-ਦਰ-ਕਦਮ ਪੜ੍ਹਾਈ ਪਲਾਨ, ਪਹਿਲਾਂ ਕੀ ਪੜ੍ਹਨਾ ਹੈ, ਰਿਵੀਜ਼ਨ ਅਤੇ ਮੌਕ ਟੈਸਟ ਦਾ ਤਰੀਕਾ, ਅਤੇ ਮੁਫ਼ਤ ਪ੍ਰੈਕਟਿਸ ਸੈੱਟ।",
    },
}
_FILL = {"en": [" Free in English and Punjabi.", " Updated regularly."],
         "pa": [" ਪੰਜਾਬੀ ਅਤੇ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਮੁਫ਼ਤ।", " ਸਮੇਂ-ਸਮੇਂ ਅੱਪਡੇਟ।"]}
TITLE_MAX = 60
DESC_MIN, DESC_MAX = 140, 160


def fit_title(variants, name, year):
    for y in ((f" {year}", "") if year else ("",)):
        for v in variants:
            t = v.format(n=name, y=y)
            if len(t) <= TITLE_MAX:
                return t
    return variants[-1].format(n=name, y="")[:TITLE_MAX].rstrip(" :-&")


def fit_desc(template, name, year, lang):
    for y in ((f" {year}", "") if year else ("",)):
        d = template.format(n=name, y=y)
        for f in _FILL[lang]:
            if len(d) >= DESC_MIN:
                break
            d += f
        if DESC_MIN <= len(d) <= DESC_MAX:
            return d
    # last resort: cut at a word boundary so the length contract still holds
    d = template.format(n=name, y="")
    while len(d) > DESC_MAX - 1:
        d = d.rsplit(" ", 1)[0]
    d = d.rstrip(" ,:-") + "."
    for f in _FILL[lang]:
        if len(d) >= DESC_MIN:
            break
        if len(d + f) <= DESC_MAX:
            d += f
    return d


def year_of(*texts):
    years = [int(y) for t in texts for y in re.findall(r"\b(20[2-3]\d)\b", str(t or ""))]
    return str(max(years)) if years else ""


# --------------------------------------------------------------- config -----
def load_config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"boards": {}, "guides": {}}


def guide_key(path):
    name = Path(str(path)).name
    for suf in (".pa.md", ".md"):
        if name.endswith(suf):
            return name[:-len(suf)]
    return name


def hub_file(path, lang, err):
    """content/strategy/<guide>.md -> exams/<slug>.html (pa/... for Punjabi)."""
    cfg = load_config()
    key = guide_key(path)
    g = (cfg.get("guides") or {}).get(key)
    if not g or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(g.get("slug") or "")):
        err(f"{path}: exam guide not registered in config/exam-hubs.json "
            f"(add \"{key}\" with slug, name, namePa and board)")
        return ""
    f = f"{HUB_DIR}/{g['slug']}.html"
    return f"pa/{f}" if lang == "pa" else f


def part_file(slug, part, lang):
    f = f"{HUB_DIR}/{slug}/{part}.html"
    return f"pa/{f}" if lang == "pa" else f


def url_of(file):
    return f"{DOMAIN}/{file[:-5]}"


# --------------------------------------------------------------- render -----
def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _label(key, lang):
    en, pa, icon = LABEL[key]
    return (pa if lang == "pa" else en), icon


def nav_html(exam, lang, current):
    """The pill row every page of one exam carries: Overview + each part."""
    items = [("overview", exam["file"][lang])]
    items += [(k, exam["parts"][k]["file"][lang]) for k in PARTS
              if lang in exam["parts"].get(k, {}).get("file", {})]
    pills = []
    for key, href in items:
        text, icon = _label(key, lang)
        cur = ' aria-current="page"' if key == current else ""
        pills.append(f'<a class="xh-pill" href="{_esc(href)}"{cur}>'
                     f'<span aria-hidden="true">{icon}</span> {_esc(text)}</a>')
    aria = "ਇਸ ਪ੍ਰੀਖਿਆ ਬਾਰੇ" if lang == "pa" else "About this exam"
    return f'<nav class="xh-nav" aria-label="{aria}">{"".join(pills)}</nav>\n'


def cards_html(exam, lang, exclude=""):
    cards = []
    links = [(k, exam["parts"][k]["file"][lang]) for k in PARTS
             if k != exclude and lang in exam["parts"].get(k, {}).get("file", {})]
    if exam.get("pyqFile"):
        links.append(("previous-papers", exam["pyqFile"]))
    if exam.get("mockFile"):
        links.append(("mock-tests", exam["mockFile"]))
    for key, href in links:
        text, icon = _label(key, lang)
        sub = SUB[key][1 if lang == "pa" else 0]
        hot = " xh-card-hot" if key == "mock-tests" else ""
        cards.append(
            f'<a class="xh-card{hot}" href="{_esc(href)}">'
            f'<span class="xh-ico" aria-hidden="true">{icon}</span>'
            f'<span class="xh-txt"><b>{_esc(text)}</b><small>{_esc(sub)}</small></span>'
            f'<span class="xh-arrow" aria-hidden="true">→</span></a>')
    return f'<div class="xh-grid">{"".join(cards)}</div>\n'


def _toc(sections):
    return [(a, _plain(h)) for a, h, _ in sections]


def _mock_ids():
    """guide key -> mock exam id, from data/mock-patterns.json (`guide`)."""
    try:
        cfg = json.loads((ROOT / "data" / "mock-patterns.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(e.get("guide")): str(e.get("id")) for e in cfg.get("exams") or []
            if e.get("guide") and e.get("id") and e.get("papers")}


# --------------------------------------------------------------- build ------
def prepare(records, err, warn, info, landing_files=frozenset()):
    """Split every strategy record (both languages) into an exam hub plus part
    pages. Rewrites each record's hub body in place and returns
    (exams, part records). Part records are plain dicts the caller renders
    with its own page renderer."""
    cfg = load_config()
    guides = cfg.get("guides") or {}
    boards = cfg.get("boards") or {}
    exams = {}
    for rec in records:
        key = guide_key(rec["path"])
        g = guides.get(key)
        if not g:
            continue                     # hub_file() already failed the build
        if str(g.get("board") or "") not in boards:
            err(f"config/exam-hubs.json: {key}: unknown board {g.get('board')!r}")
            continue
        ex = exams.setdefault(key, {
            "key": key, "slug": g["slug"], "board": g["board"],
            "name": {"en": str(g.get("name") or ""), "pa": str(g.get("namePa") or g.get("name") or "")},
            "file": {}, "title": {}, "records": {}, "parts": {}, "practice": {},
        })
        ex["records"][rec["lang"]] = rec
        ex["file"][rec["lang"]] = rec["file"]
        pid = str(g.get("pyq") or "")
        if pid and (ROOT / "pyq" / pid / "index.html").exists():
            ex["pyqFile"] = f"pyq/{pid}/index.html"
        # "Free Mock Tests" opens the site's own timed mock test, on this
        # exam's real pattern when data/mock-patterns.json has one.
        mid = _mock_ids().get(key, "")
        ex["mockFile"] = f"mock.html?exam={mid}" if mid else "mock.html"
        pr = str(g.get("practice") or "")
        if pr and f"exam-{pr}.html" in landing_files:
            ex["practiceFile"] = f"exam-{pr}.html"

    slugs = {}
    for ex in exams.values():
        if ex["slug"] in slugs:
            err(f"config/exam-hubs.json: slug {ex['slug']!r} used by both "
                f"{slugs[ex['slug']]} and {ex['key']}")
        slugs[ex["slug"]] = ex["key"]
        en = ex["records"].get("en")
        ex["year"] = year_of(en["title"] if en else "", (en or {}).get("seoTitle", ""))

    out = []
    for ex in sorted(exams.values(), key=lambda e: e["slug"]):
        # pass 1: which parts exist in which language
        cut = {}
        for lang, rec in ex["records"].items():
            pre, secs = split(rec["bodyHtml"])
            buckets = {k: [] for k in PARTS}
            practice, first = [], None
            for n, (a, h, body) in enumerate(secs):
                labels = classify(h, lang)
                if labels == ("practice",):
                    practice.append((a, h, body))
                    continue
                if n == 0 and "notification" in labels:
                    first = (a, h, body)
                for k in labels:
                    buckets[k].append((a, h, body))
            cut[lang] = (pre, buckets, practice, first)
            for k in PARTS:
                if buckets[k]:
                    ex["parts"].setdefault(k, {"file": {}})["file"][lang] = \
                        part_file(ex["slug"], k, lang)

        # pass 2: hub body + part records
        for lang, rec in ex["records"].items():
            pre, buckets, practice, first = cut[lang]
            name = ex["name"][lang]
            hub_title = fit_title(_TITLES[lang]["hub"], name, ex["year"])
            ex["title"][lang] = hub_title
            head_txt = ("ਇਸ ਪ੍ਰੀਖਿਆ ਬਾਰੇ ਤੁਸੀਂ ਕੀ ਜਾਣਨਾ ਚਾਹੁੰਦੇ ਹੋ?" if lang == "pa"
                        else "What do you want to know about this exam?")
            keep = ([first] if first else []) + practice
            hub_body = (pre
                        + f'<h2 id="explore">{_esc(head_txt)}</h2>\n'
                        + cards_html(ex, lang)
                        + "".join(b for _, _, b in keep))
            rec["guideTitle"] = rec["title"]
            rec["title"] = hub_title
            rec["seoTitle"] = hub_title
            rec["bodyHtml"] = nav_html(ex, lang, "overview") + hub_body
            rec["toc"] = [("explore", head_txt)] + _toc(keep)
            _reading(rec)
            rec["examHub"] = {"slug": ex["slug"], "name": name,
                              "board": ex["board"]}

            for i, k in enumerate(PARTS):
                secs = buckets[k]
                if not secs:
                    continue
                f = part_file(ex["slug"], k, lang)
                other = "en" if lang == "pa" else "pa"
                alt = ex["parts"][k]["file"].get(other)
                title = fit_title(_TITLES[lang][k], name, ex["year"])
                desc = fit_desc(_DESCS[lang][k], name, ex["year"], lang)
                more_h = ("ਇਸ ਪ੍ਰੀਖਿਆ ਬਾਰੇ ਹੋਰ" if lang == "pa"
                          else f"More about the {name} exam")
                body = (nav_html(ex, lang, k)
                        + "".join(b for _, _, b in secs)
                        + ("".join(b for _, _, b in practice) if k == "preparation" else "")
                        + f'<h2 id="more">{_esc(more_h)}</h2>\n'
                        + cards_html(ex, lang, exclude=k))
                toc = _toc(secs) + ([] if k != "preparation" else _toc(practice)) \
                    + [("more", more_h)]
                kw_base = ex["name"]["en"].lower()
                words = {"notification": "notification", "eligibility": "eligibility",
                         "exam-pattern": "exam pattern", "syllabus": "syllabus",
                         "salary": "salary", "physical-standards": "physical test",
                         "preparation": "preparation strategy"}[k]
                kws = [f"{kw_base} {words}"]
                if ex["year"]:
                    kws.append(f"{kw_base} {words} {ex['year']}")
                kws += [f"{kw_base} exam", f"{kw_base} {words} pdf"]
                part = dict(rec)
                for drop in ("seoDescription", "summary", "subtitle", "pdf",
                             "relatedContent", "thumbnail"):
                    part.pop(drop, None)
                part.update({
                    "file": f, "url": url_of(f), "title": title, "seoTitle": title,
                    "description": desc, "bodyHtml": body, "toc": toc,
                    "keywords": kws, "faq": _faq_for(rec.get("faq"), k),
                    "examPart": {"key": k, "hubFile": rec["file"],
                                 "hubTitle": hub_title, "name": name,
                                 "altFile": alt},
                    "langAltFiles": ({"en": f, "pa": alt} if lang == "en" else
                                     {"en": alt, "pa": f}) if alt else None,
                })
                _reading(part)
                out.append(part)
    info(f"exam hubs: {len(exams)} exam(s), {len(out)} part page(s)")
    return exams, out


def _reading(rec):
    words = len(_plain(rec["bodyHtml"]).split())
    rec["wordCount"] = words
    rec["readingMinutes"] = max(1, -(-words // 200))


_FAQ_RX = {
    "notification": r"vacanc|post|notification|date|fee|apply|ਅਸਾਮੀ|ਫੀਸ|ਫ਼ੀਸ|ਤਾਰੀਖ",
    "eligibility": r"age|eligib|qualif|degree|punjabi|attempt|ਉਮਰ|ਯੋਗਤਾ",
    "exam-pattern": r"question|marks|negative|pattern|qualif|merit|paper|ਸਵਾਲ|ਅੰਕ|ਪੈਟਰਨ|ਮਾਰਕਿੰਗ|ਪੇਪਰ",
    "syllabus": r"syllabus|subject|topic|section|ਸਿਲੇਬਸ|ਵਿਸ਼ੇ",
    "salary": r"salary|pay|ਤਨਖ਼ਾਹ|ਤਨਖਾਹ",
    "physical-standards": r"height|physical|race|chest|ਕੱਦ|ਫਿਜ਼ੀਕਲ|ਦੌੜ",
    "preparation": r"prepar|study|start|ਤਿਆਰੀ",
}


def _faq_for(faq, part):
    """Only the questions this part actually answers - FAQ schema on a page
    must be visible on that page, and a syllabus page has no business
    answering the height question."""
    if not isinstance(faq, list):
        return []
    rx = re.compile(_nfd(_FAQ_RX[part]))
    return [x for x in faq if isinstance(x, dict) and rx.search(_nfd(x.get("q", "")))]


def manifest_entries(parts):
    return [{"file": p["file"], "url": p["url"], "title": p["title"],
             "description": p["description"]} for p in parts]


def write_index(exams):
    """data/exam-hubs.json: what core.js and the landing builder read to link
    an exam's hub without knowing the URL scheme."""
    rows = []
    for ex in sorted(exams.values(), key=lambda e: e["slug"]):
        rows.append({
            "slug": ex["slug"], "guide": ex["key"], "board": ex["board"],
            "name": ex["name"]["en"], "namePa": ex["name"]["pa"],
            "file": ex["file"].get("en", ""), "filePa": ex["file"].get("pa", ""),
            "parts": {k: v["file"] for k, v in sorted(ex["parts"].items())},
            **({"pyq": ex["pyqFile"]} if ex.get("pyqFile") else {}),
            **({"practice": ex["practiceFile"]} if ex.get("practiceFile") else {}),
        })
    path = ROOT / "data" / "exam-hubs.json"
    text = json.dumps({"version": 1, "exams": rows}, ensure_ascii=False, indent=2) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
    return rows
