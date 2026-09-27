"""content_engine.py | Phase 3 - the AI Content Engine.

Three jobs, standard library only:

1. **TEMPLATES** - the eleven reusable content templates. Each template maps an
   editorial format onto the collection that publishes it and carries its
   front-matter contract, a body outline (used by ``scripts/new_content.py``
   to scaffold a draft) and the *recommendation plan* the builder renders on
   the finished page.

2. **score() / rank()** - the recommendation engine. A deterministic facet
   model over subject, exam, category, difficulty, tags and language ranks
   candidates for a seed document and returns the reason each one was picked.
   Same tree in -> same ranking out, so CI can diff the output.

3. **build_graph()** - the internal content graph: nodes (every published
   page), edges (one per contextual internal link the builder really emitted,
   with the reason and a weight) and the silos that connect pillar pages to
   subject hubs, exam hubs, topic clusters and the leaves underneath them.

Nothing here invents content. A recommendation slot with no data behind it
resolves to a *reserved* chip - never to a page that does not exist.
"""

import json
import re

# =============================================================================
# 1. CONTENT TEMPLATES
# =============================================================================
# Every template is reusable across languages and collections: the front
# matter contract is validated by scripts/build_content.py, the outline is
# what scripts/new_content.py writes into a fresh draft, and `plan` is the
# ordered list of recommendation slots rendered on the published page.
#
# Slot sources:
#   quiz                related practice quizzes for this page's subjects
#   subject             the subject hub(s) for this page's subjects
#   coll:<collection>   engine-ranked documents from another collection
#   hub:<collection>    that collection's hub page (always exists)
#   page:<anchor>       an anchor on this page (rendered only if present)
#   coll:<c>?tag=<t>    documents of <c> whose tags contain <t>
TEMPLATES = {
    "study-note": {
        "label": "Study Note",
        "collection": "notes",
        "schema": "Article",
        "chaptered": True,
        "summary": "One subject, one idea, one read. Carries reading time, "
                   "difficulty, exam tags, a table of contents and the quiz "
                   "that tests it.",
        "required": ["title", "description", "published", "subject"],
        "optional": ["difficulty", "exams", "tags", "quiz", "pdf", "updated"],
        "outline": [
            "## What this covers",
            "## The concept, explained simply",
            "## How it is asked in the exam",
            "## Points to remember",
        ],
        "plan": [
            {"src": "quiz", "eyebrow": "Practice quiz",
             "title": "Test yourself on this", "limit": 3},
            {"src": "subject", "eyebrow": "Related subject",
             "title": "Keep going in this subject", "limit": 3},
            {"src": "coll:current-affairs", "eyebrow": "Related current affairs",
             "title": "What is moving in this area", "limit": 3},
            {"src": "coll:expected-mcqs", "eyebrow": "Practice set",
             "title": "Expected MCQs", "limit": 3,
             "reserved": "Expected MCQs are published only after they are "
                         "reviewed - this slot stays empty until then."},
            {"src": "coll:previous-year-questions", "eyebrow": "Past papers",
             "title": "Previous Year Questions", "limit": 3,
             "reserved": "Previous year papers are listed only once the "
                         "official paper exists to link."},
        ],
    },
    "current-affairs": {
        "label": "Current Affairs",
        "collection": "current-affairs",
        "schema": "Article",
        "summary": "One development at a time, explained in Punjabi and "
                   "English, linked to the quiz set and the monthly issue.",
        "required": ["title", "description", "published"],
        "optional": ["category", "difficulty", "exam", "updated"],
        "outline": [
            "## What happened",
            "## Why it matters for the exam",
            "## Facts to remember",
            "## Source",
        ],
        "plan": [
            {"src": "quiz", "eyebrow": "Quiz",
             "title": "Attempt the set that tests this", "limit": 3},
            {"src": "coll:magazine?latest=1", "eyebrow": "Monthly magazine",
             "title": "Read the issue that covers this period", "limit": 1,
             "fallback": "magazine.html", "fallback_title": "Magazine archive"},
            {"src": "coll:news", "eyebrow": "Related news",
             "title": "Other notices from the same bodies", "limit": 3,
             "reserved": "News items are published only when an official "
                         "notification exists to link."},
            {"src": "coll:current-affairs?tag=scheme", "eyebrow": "Government schemes",
             "title": "Schemes worth remembering", "limit": 3,
             "reserved": "Scheme explainers appear here as they are published."},
            {"src": "subject:gk", "eyebrow": "Punjab GK",
             "title": "The static side of this event", "limit": 1,
             "fallback": "subject.html?subject=gk",
             "fallback_title": "Punjab GK practice"},
        ],
    },
    "monthly-magazine": {
        "label": "Monthly Magazine",
        "collection": "magazine",
        "schema": "Article",
        "summary": "One issue per month: cover, PDF, highlights and the quiz "
                   "built from the events that matter to Punjab exams.",
        "required": ["title", "description", "published", "month"],
        "optional": ["pdf", "quiz", "highlights", "cover", "expected_mcqs"],
        "outline": [
            "## Highlights of the issue",
            "## In this issue",
            "## What to revise",
        ],
        "plan": [
            {"src": "quiz", "eyebrow": "Quiz",
             "title": "Related current affairs sets", "limit": 3},
            {"src": "coll:current-affairs", "eyebrow": "Related current affairs",
             "title": "The articles this issue is built from", "limit": 3},
            {"src": "coll:previous-year-questions", "eyebrow": "Past papers",
             "title": "Previous Year Questions", "limit": 3,
             "reserved": "Previous year papers are listed only once the "
                         "official paper exists to link."},
        ],
    },
    "preparation-strategy": {
        "label": "Preparation Strategy",
        "collection": "strategy",
        "schema": "Article",
        "summary": "Method over motivation: study plans, timetables, revision "
                   "cycles and mock-test analysis you can use this week.",
        "required": ["title", "description", "published", "category"],
        "optional": ["difficulty", "exams", "tags", "updated"],
        "outline": [
            "## The plan",
            "## How to run a week",
            "## What to measure",
            "## Common mistakes",
        ],
        "plan": [
            {"src": "quiz", "eyebrow": "Practice quiz",
             "title": "Put the method to work", "limit": 3},
            {"src": "coll:notes", "eyebrow": "Related notes",
             "title": "Study notes to run the plan on", "limit": 3},
            {"src": "hub:pdfs", "eyebrow": "Books & PDFs",
             "title": "Material to study from", "limit": 1},
            {"src": "coll:magazine?latest=1", "eyebrow": "Monthly magazine",
             "title": "Current affairs, already revised", "limit": 1,
             "fallback": "magazine.html", "fallback_title": "Magazine archive"},
        ],
    },
    "motivation": {
        "label": "Motivation Article",
        "collection": "strategy",
        "schema": "Article",
        "summary": "Honest, specific pieces about staying in the prep - written "
                   "to be useful in week four, not just in week one.",
        "required": ["title", "description", "published", "category"],
        "optional": ["difficulty", "exams", "tags", "updated"],
        "outline": [
            "## The real problem",
            "## What actually helped",
            "## What to do tomorrow",
        ],
        "plan": [
            {"src": "coll:strategy", "eyebrow": "Preparation strategy",
             "title": "Turn the feeling into a plan", "limit": 3},
            {"src": "quiz", "eyebrow": "Practice quiz",
             "title": "The fastest way to feel progress", "limit": 3},
            {"src": "hub:sessions", "eyebrow": "Live session",
             "title": "Ask the doubts live", "limit": 1},
        ],
    },
    "book-review": {
        "label": "Book Review",
        "collection": "strategy",
        "schema": "Article",
        "summary": "What a book is actually worth for a Punjab exam - which "
                   "chapters to read, which to skip, and what to use instead.",
        "required": ["title", "description", "published", "category"],
        "optional": ["difficulty", "exams", "tags", "pdf", "updated"],
        "outline": [
            "## Who should buy it",
            "## What is good in it",
            "## What to skip",
            "## What to use instead",
        ],
        "plan": [
            {"src": "hub:pdfs", "eyebrow": "Free PDFs",
             "title": "What you can download here instead", "limit": 1},
            {"src": "coll:notes", "eyebrow": "Related notes",
             "title": "The same ground, in note form", "limit": 3},
            {"src": "quiz", "eyebrow": "Practice quiz",
             "title": "Check what stuck", "limit": 3},
        ],
    },
    "live-session-summary": {
        "label": "Live Session Summary",
        "collection": "sessions",
        "schema": "Event",
        "summary": "What the weekly session covered: the topic, the questions "
                   "discussed and the doubts students raised.",
        "required": ["title", "description", "published", "date"],
        "optional": ["time", "start_time", "platform", "join", "status",
                     "questions", "doubts", "summary"],
        "outline": [
            "## What the session covered",
            "## Questions discussed",
            "## Student doubts",
            "## What to do next",
        ],
        "plan": [
            {"src": "coll:notes", "eyebrow": "Related notes",
             "title": "Read what the session taught", "limit": 3},
            {"src": "quiz", "eyebrow": "Practice quiz",
             "title": "Practise the same topic", "limit": 3},
            {"src": "coll:strategy", "eyebrow": "Preparation strategy",
             "title": "Make it part of the week", "limit": 3},
        ],
    },
    "recruitment-notification": {
        "label": "Recruitment Notification",
        "collection": "recruitment",
        "schema": "Article",
        "summary": "A restatement of the recruiting body's own notification: "
                   "eligibility, syllabus, selection and dates - official "
                   "link first, nothing guessed.",
        "required": ["title", "description", "published", "post", "official_url"],
        "optional": ["exam", "official_source", "eligibility", "syllabus",
                     "selection", "dates", "expected_questions",
                     "previous_papers", "tags", "subjects"],
        "outline": [
            "## At a glance",
            "## Eligibility",
            "## Syllabus",
            "## Selection process",
            "## Important dates",
        ],
        "plan": [
            {"src": "page:eligibility", "eyebrow": "On this page",
             "title": "Eligibility", "limit": 1},
            {"src": "page:syllabus", "eyebrow": "On this page",
             "title": "Syllabus", "limit": 1},
            {"src": "coll:strategy", "eyebrow": "Preparation strategy",
             "title": "How to prepare for this post", "limit": 3},
            {"src": "hub:pdfs", "eyebrow": "Books",
             "title": "Free PDFs for this exam", "limit": 1},
            {"src": "coll:previous-year-questions", "eyebrow": "Previous papers",
             "title": "Previous Papers", "limit": 3,
             "reserved": "Papers are listed only when the official PDF exists "
                         "to link."},
            {"src": "coll:expected-mcqs", "eyebrow": "Expected questions",
             "title": "Expected Questions", "limit": 3,
             "reserved": "Expected questions are published only after they "
                         "are reviewed."},
            {"src": "hub:sessions", "eyebrow": "Live session",
             "title": "Ask the doubts live", "limit": 1},
        ],
    },
    "exam-analysis": {
        "label": "Exam Analysis",
        "collection": "blogs",
        "schema": "Article",
        "summary": "What a paper or a shift actually looked like - difficulty, "
                   "pattern, cut-off signals and what it changes for you.",
        "required": ["title", "description", "published"],
        "optional": ["category", "difficulty", "exams", "tags", "updated"],
        "outline": [
            "## How the paper was",
            "## Section by section",
            "## What it changes for the next attempt",
        ],
        "plan": [
            {"src": "quiz", "eyebrow": "Practice quiz",
             "title": "Try the same difficulty", "limit": 3},
            {"src": "coll:notes", "eyebrow": "Related notes",
             "title": "Close the gaps the paper exposed", "limit": 3},
            {"src": "coll:news", "eyebrow": "Related news",
             "title": "Official notices behind this", "limit": 3,
             "reserved": "News items are published only when an official "
                         "notification exists to link."},
        ],
    },
    "expected-mcq": {
        "label": "Expected MCQs",
        "collection": "expected-mcqs",
        "schema": "Article",
        "summary": "Forecast questions built from the syllabus and the pattern "
                   "of the exam - published only once reviewed. Schema-ready; "
                   "the slot stays empty until verified data exists.",
        "required": ["title", "description", "published", "subject"],
        "optional": ["difficulty", "exams", "tags", "quiz", "updated"],
        "outline": [
            "## What is being predicted",
            "## The questions",
            "## Why these are likely",
        ],
        "plan": [
            {"src": "quiz", "eyebrow": "Practice quiz",
             "title": "Drill the same area now", "limit": 3},
            {"src": "coll:notes", "eyebrow": "Related notes",
             "title": "Study the concept first", "limit": 3},
            {"src": "coll:previous-year-questions", "eyebrow": "Past papers",
             "title": "Check it against the real paper", "limit": 3,
             "reserved": "Previous year papers are listed only once the "
                         "official paper exists to link."},
        ],
    },
    "previous-year-question": {
        "label": "Previous Year Questions",
        "collection": "previous-year-questions",
        "schema": "Article",
        "summary": "Questions from the official paper itself, with the source "
                   "named - published only when that paper exists to cite.",
        "required": ["title", "description", "published", "exams"],
        "optional": ["difficulty", "tags", "quiz", "pdf", "updated"],
        "outline": [
            "## Paper and year",
            "## The questions",
            "## What it tells you about the exam",
        ],
        "plan": [
            {"src": "quiz", "eyebrow": "Practice quiz",
             "title": "Attempt the same topic", "limit": 3},
            {"src": "coll:notes", "eyebrow": "Related notes",
             "title": "Revise before you attempt", "limit": 3},
            {"src": "coll:expected-mcqs", "eyebrow": "Forecast",
             "title": "Expected MCQs for the next attempt", "limit": 3,
             "reserved": "Expected MCQs are published only after they are "
                         "reviewed - this slot stays empty until then."},
        ],
    },
}

# Collection -> default template when a document does not name one. The
# strategy and blog collections are split by category so one folder can carry
# several editorial formats without inventing new directories.
_DEFAULT_TEMPLATE = {
    "notes": "study-note",
    "current-affairs": "current-affairs",
    "magazine": "monthly-magazine",
    "strategy": "preparation-strategy",
    "sessions": "live-session-summary",
    "recruitment": "recruitment-notification",
    "blogs": "exam-analysis",
    "news": "exam-analysis",
    "expected-mcqs": "expected-mcq",
    "previous-year-questions": "previous-year-question",
}

# Collections with no dedicated template fall back to this generic plan, so
# every published page still earns contextual links.
GENERIC_PLAN = [
    {"src": "quiz", "eyebrow": "Practice quiz", "title": "Practise this topic",
     "limit": 3},
    {"src": "coll:notes", "eyebrow": "Related notes", "title": "Study notes",
     "limit": 3},
    {"src": "coll:current-affairs", "eyebrow": "Related current affairs",
     "title": "Current affairs", "limit": 3},
]


def template_for(collection, category=""):
    """Resolve the template that governs a document in `collection`."""
    cat = str(category or "").lower()
    if collection == "strategy":
        if "motiv" in cat:
            return "motivation"
        if "book" in cat:
            return "book-review"
    if collection == "blogs":
        if "book" in cat:
            return "book-review"
        if "motiv" in cat:
            return "motivation"
        if "analysis" in cat or not cat:
            return "exam-analysis"
    return _DEFAULT_TEMPLATE.get(collection, "")


def plan_for(template_key):
    """The recommendation plan for a template key ('' -> generic)."""
    tpl = TEMPLATES.get(template_key)
    return tpl["plan"] if tpl else GENERIC_PLAN


def scaffold_for(template_key):
    """Front-matter block + body outline used by scripts/new_content.py."""
    tpl = TEMPLATES[template_key]
    lines = [f"type: {template_key}", "draft: true", "language: en"]
    for field in tpl["required"]:
        if field in ("title", "description", "published"):
            continue
        lines.append(f"# {field}:")
    for field in tpl["optional"][:6]:
        if field in ("title", "description", "published", "updated"):
            continue
        lines.append(f"# {field}:")
    lines += ["title:", "description:",
              "# published: YYYY-MM-DD   # set when this is ready to publish"]
    return lines, tpl


# =============================================================================
# 2. RECOMMENDATION ENGINE
# =============================================================================
# Weighted facets. `subject` and `exam` say "this belongs to the same part of
# the syllabus"; `category`, `difficulty` and `tags` say "it is the same kind
# of page"; `language` keeps a Punjabi reader in Punjabi when it can.
WEIGHTS = {
    "subject": 6,
    "exam": 4,
    "tag": 3,
    "category": 3,
    "difficulty": 2,
    "language": 2,
    "featured": 2,
    "collection": 1,
}


def _set(record, key):
    value = record.get(key) or []
    if isinstance(value, str):
        value = [value]
    return {str(v).strip().lower() for v in value if str(v).strip()}


def score(seed, candidate, same_collection=False):
    """Score one candidate against a seed. Returns (score, reasons).

    Deterministic: only facet overlap decides, so the same content tree always
    produces the same ranking and CI can diff it.
    """
    s, reasons = 0, []
    for facet, key, label in (("subjects", "subject", "same subject"),
                              ("exams", "exam", "same exams"),
                              ("tags", "tag", "shared tags")):
        shared = _set(seed, facet) & _set(candidate, facet)
        if shared:
            s += WEIGHTS[key] * len(shared)
            reasons.append(label)
    for facet, weight in (("category", "category"), ("difficulty", "difficulty")):
        a = str(seed.get(facet) or "").strip().lower()
        b = str(candidate.get(facet) or "").strip().lower()
        if a and b and a == b:
            s += weight
            reasons.append(f"same {facet}")
    if candidate.get("featured"):
        s += WEIGHTS["featured"]
        reasons.append("featured")
    if same_collection:
        s += WEIGHTS["collection"]
        reasons.append("same section")
    # `language` is deliberately NOT in the score: sharing a language is a
    # preference, not a reason to call two documents related. rank() applies
    # it as a tie-break between candidates that already overlap on facets.
    return s, reasons


def rank(seed, pool, limit=3, exclude=(), prefer_lang=None, require_score=True):
    """Best `limit` candidates for `seed`, best first.

    `require_score=False` keeps zero-overlap documents (used when a section
    would otherwise have nothing real to link at all); `prefer_lang` breaks
    ties towards a language without ever excluding the other one.
    """
    seed_key = seed.get("file") or seed.get("url") or ""
    out = []
    for cand in pool:
        key = cand.get("file") or cand.get("url") or ""
        if not key or key == seed_key or key in exclude:
            continue
        s, why = score(seed, cand, same_collection=(
            cand.get("collection") == seed.get("collection")))
        if require_score and s <= 0:
            continue
        if prefer_lang and cand.get("lang") == prefer_lang:
            s += WEIGHTS["language"]
            why.append("your language")
        out.append((s, _neg_date(cand.get("published", "")), key, cand, why))
    out.sort(key=lambda t: (-t[0], t[1], t[2]))
    return [(c, s, why) for _, _, _, c, why in out[:limit]]


def _neg_date(iso):
    """Newest published date first, as a sortable tuple."""
    parts = str(iso or "").split("-")
    try:
        return tuple(-int(p) for p in parts[:3]) + (0,) * (3 - len(parts))
    except ValueError:
        return (0, 0, 0)


# =============================================================================
# 3. CONTENT GRAPH - nodes, contextual edges, silos
# =============================================================================
GRAPH_NOTE = (
    "Built by scripts/build_content.py from the published tree only. Nodes are "
    "pages, edges are contextual internal links the builder actually rendered "
    "(from -> to, with the slot that produced it), silos connect a pillar page "
    "to its subject hub, exam hub, topic clusters and leaves. Deterministic: "
    "no run timestamps, so a rebuild either matches byte for byte or fails CI."
)


def node_id(file):
    return str(file or "").lstrip("/")


def make_node(record, hub_file=""):
    return {
        "id": node_id(record.get("file")),
        "url": "/" + str(record.get("file") or "").lstrip("/"),
        "type": record.get("collection", ""),
        "template": record.get("template", ""),
        "title": record.get("title", ""),
        "lang": record.get("lang", "en"),
        "subjects": list(record.get("subjects") or []),
        "exams": list(record.get("exams") or []),
        "tags": list(record.get("tags") or []),
        "hub": hub_file,
    }


def make_edge(source, target, rel, weight=1):
    return {
        "from": node_id(source),
        "to": node_id(target),
        "rel": rel,
        "weight": int(weight),
    }


def _slug_in(haystack, needle):
    return str(needle).lower() in str(haystack or "").lower()


def build_silos(index, articles, exams, landing, records):
    """Pillar -> hub -> cluster -> leaf, for subjects and for exams.

    Every URL is one the site really serves; a silo with no pillar still
    publishes with `pillar: null` rather than an invented one.
    """
    by_type = {}
    for p in landing or []:
        if p.get("type") and p.get("entity"):
            by_type.setdefault(p["type"], {})[str(p["entity"])] = p.get("file")
    subject_pages = by_type.get("subject", {})
    exam_pages = by_type.get("exam", {})
    category_pages = by_type.get("category", {})
    topic_pages = by_type.get("topic", {})
    cluster_pages = by_type.get("cluster", {})
    # entity "<subject>/<category>" -> "<subject>/<category-id>"
    category_by_id = {}
    for entity, file in category_pages.items():
        if "/" in str(entity):
            category_by_id[str(entity).split("/", 1)[1]] = file

    def _page(landing_path):
        if not landing_path:
            return None
        text = str(landing_path).strip()
        return text[1:] if text.startswith("/") else text

    silos = []
    for subj in index.get("subjects", []):
        sid = subj.get("id", "")
        if not sid:
            continue
        pillars = [a for a in (articles or []) if sid in (a.get("subjects") or [])]
        # A pillar must be about this subject: prefer the guide named after it,
        # then the narrowest guide, then the newest.
        subject_tokens = [t for t in re.split(r"[-\s]+", sid) if t]

        def subject_pillar_key(a):
            hay = f'{a.get("id", "")} {a.get("title", "")}'.lower()
            matched = sum(1 for t in subject_tokens if t and t in hay)
            return (-matched, len(a.get("subjects") or []),
                    str(a.get("published", "")))

        pillars.sort(key=subject_pillar_key)
        pillar = pillars[0] if pillars else None
        clusters = []
        for cat in subj.get("categories", []) or []:
            cid = cat.get("id") if isinstance(cat, dict) else str(cat)
            file = (category_pages.get(f"{sid}/{cid}")
                    or category_by_id.get(str(cid))
                    or _page(cat.get("landing") if isinstance(cat, dict) else None))
            if file:
                clusters.append(file)
        for topic in subj.get("topics", []) or []:
            tid = topic.get("id")
            file = (topic_pages.get(f"{sid}/{tid}")
                    or cluster_pages.get(str(tid))
                    or _page(topic.get("landing"))
                    or (f"quiz.html?subject={sid}&topic={tid}"
                        if topic.get("available") else None))
            if file:
                clusters.append(file)
        leaves = [node_id(r["file"]) for r in records
                  if sid in (r.get("subjects") or [])]
        silos.append({
            "id": f"subject:{sid}",
            "kind": "subject",
            "name": subj.get("name", sid),
            "pillar": str(pillar["url"]).lstrip("/") if pillar else None,
            "hub": (subject_pages.get(sid)
                    or _page(subj.get("landing"))
                    or f"subject.html?subject={sid}"),
            "clusters": sorted(set(clusters)),
            "leaves": sorted(set(leaves)),
        })

    for ex in exams or []:
        eid = str(ex.get("id") or "")
        if not eid:
            continue
        ex_subjects = set(str(s) for s in (ex.get("subjects") or []))
        pillars = [a for a in (articles or [])
                   if ex_subjects & set(a.get("subjects") or [])]
        # Prefer the guide that is actually about this exam (title/id match),
        # then the narrowest guide - a pillar must be about this silo, not just
        # share one subject with it.
        tokens = [t for t in re.split(r"[-\s]+", eid) if t]

        def exam_pillar_key(a):
            hay = f'{a.get("id", "")} {a.get("title", "")}'.lower()
            matched = sum(1 for t in tokens if t and t in hay)
            return (-matched, len(a.get("subjects") or []),
                    str(a.get("published", "")))

        pillars.sort(key=exam_pillar_key)
        pillar = pillars[0] if pillars else None
        name = str(ex.get("name") or eid)
        leaves = [node_id(r["file"]) for r in records
                  if name in [str(e) for e in (r.get("exams") or [])]]
        clusters = []
        for cat in ex.get("categories", []) or []:
            file = category_pages.get(str(cat)) or category_by_id.get(str(cat))
            if file:
                clusters.append(file)
        silos.append({
            "id": f"exam:{eid}",
            "kind": "exam",
            "name": name,
            "pillar": str(pillar["url"]).lstrip("/") if pillar else None,
            "hub": exam_pages.get(eid) or f"exam-{eid}.html",
            "clusters": sorted(set(clusters)),
            "leaves": sorted(set(leaves)),
        })
    return sorted(silos, key=lambda s: (s["kind"], s["id"]))


def build_graph(nodes, edges, silos):
    nodes = sorted(nodes, key=lambda n: n["id"])
    edges = sorted(edges, key=lambda e: (e["from"], e["rel"], e["to"]))
    silos = sorted(silos, key=lambda s: (s["kind"], s["id"]))
    return {
        "$note": GRAPH_NOTE,
        "version": 1,
        "facets": ["subject", "exam", "category", "difficulty", "tags",
                   "language"],
        "weights": dict(WEIGHTS),
        "counts": {"nodes": len(nodes), "edges": len(edges),
                   "silos": len(silos),
                   "clusters": sum(len(s["clusters"]) for s in silos),
                   "pillars": sum(1 for s in silos if s.get("pillar"))},
        "nodes": nodes,
        "edges": edges,
        "silos": silos,
    }


_INTERNAL_HOST = "houseofaspirants.in"


def link_floor(html_main):
    """Unique contextual internal links inside a page's <main>.

    Two rules that matter: share links (t.me, twitter, wa.me) merely *embed*
    the page URL, so host matching - not substring matching - decides what is
    really ours; and an absolute link to our own domain is normalised to its
    site-relative path so the graph and the >=5 floor never count the same
    link twice.
    """
    out = set()
    for href in re.findall(r'href="([^"]+)"', html_main or ""):
        h = href.strip()
        if h.startswith(("#", "mailto:", "tel:", "//")):
            continue
        if h.startswith(("http://", "https://")):
            m = re.match(r"^https?://([^/:?#]+)", h)
            host = m.group(1).lower() if m else ""
            if host.startswith("www."):
                host = host[4:]
            if host != _INTERNAL_HOST:
                continue                       # external (incl. share links)
            h = h[m.end():]
        h = h.split("#", 1)[0].split("?", 1)[0].lstrip("/")
        if h:
            out.add(h)
    return out
