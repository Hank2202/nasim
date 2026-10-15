"""Spireopedia: the in-game, Wikipedia-style lore encyclopedia (data in lore_articles.json).

Articles are served as JSON to the phone console's Wiki tab; there is no standalone site."""

import json
import os
import re
from html import escape
from typing import Any, Dict, List, Tuple

from markupsafe import Markup

ARTICLES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lore_articles.json")
_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")

_cache: Dict[str, Any] = {"mtime": None, "data": None}

# Realm id (scenario_config.json) -> Spireopedia article slug
REALM_ARTICLES = {
    "sylvan": "sylvan-concordat",
    "val_khor": "iron-val-khor",
    "solaria": "solaris-ascendancy",
    "umbra": "umbral-enclave",
    "aquila": "aquila-maritime-league",
    "aethelgard": "aethelgard-dominion",
}


def realm_article(realm_id: str) -> str:
    return REALM_ARTICLES.get(realm_id, "")


def load_wiki() -> Dict[str, Any]:
    mtime = os.path.getmtime(ARTICLES_PATH)
    if _cache["mtime"] != mtime:
        with open(ARTICLES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["by_slug"] = {a["slug"]: a for a in data["articles"]}
        _cache.update(mtime=mtime, data=data)
    return _cache["data"]


def render_markup(text: str) -> Markup:
    """Escape, then apply **bold**, [[slug|label]] links and blank-line paragraphs."""
    by_slug = load_wiki()["by_slug"]

    def link(m):
        slug, label = m.group(1).strip(), (m.group(2) or "").strip()
        article = by_slug.get(slug)
        label = label or (article["title"] if article else slug)
        if article:
            return f'<a href="#" class="wk-link" data-wiki="{slug}">{label}</a>'
        return f'<span class="wk-new" title="This article does not exist yet">{label}</span>'

    def inline(chunk: str) -> str:
        chunk = escape(chunk, quote=False)
        chunk = _LINK_RE.sub(link, chunk)
        return _BOLD_RE.sub(r"<b>\1</b>", chunk)

    paras = [p for p in text.split("\n\n") if p.strip()]
    return Markup("".join(f"<p>{inline(p)}</p>" for p in paras))


def render_inline(text: str) -> Markup:
    html = str(render_markup(text))
    return Markup(html[3:-4] if html.startswith("<p>") and html.count("<p>") == 1 else html)


def backlinks(slug: str) -> List[Dict[str, Any]]:
    out = []
    for a in load_wiki()["articles"]:
        if a["slug"] == slug:
            continue
        blob = json.dumps(a, ensure_ascii=False)
        if re.search(r"\[\[" + re.escape(slug) + r"(\||\])", blob):
            out.append(a)
    return out


def search(query: str) -> List[Dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return []
    hits: List[Tuple[int, Dict[str, Any]]] = []
    for a in load_wiki()["articles"]:
        score = 0
        if q in a["title"].lower():
            score += 10
        blob = json.dumps(a, ensure_ascii=False).lower()
        score += min(blob.count(q), 9)
        if score:
            hits.append((score, a))
    return [a for _, a in sorted(hits, key=lambda x: -x[0])]


def validate() -> List[str]:
    """Return a list of problems (empty = OK): duplicate slugs, dead links, bad see_also."""
    data = load_wiki()
    problems, seen = [], set()
    for a in data["articles"]:
        if a["slug"] in seen:
            problems.append(f"duplicate slug {a['slug']}")
        seen.add(a["slug"])
    for a in data["articles"]:
        for target in _LINK_RE.findall(json.dumps(a, ensure_ascii=False)):
            if target[0].strip() not in seen:
                problems.append(f"{a['slug']}: dead link [[{target[0]}]]")
        for s in a.get("see_also", []):
            if s not in seen:
                problems.append(f"{a['slug']}: bad see_also {s}")
        if a["category"] not in data["_meta"]["categories"]:
            problems.append(f"{a['slug']}: unknown category {a['category']}")
    return problems


def _summary(a: Dict[str, Any]) -> Dict[str, Any]:
    return {k: a[k] for k in ("slug", "title", "subtitle", "category")}


def index_payload() -> Dict[str, Any]:
    data = load_wiki()
    return {"meta": data["_meta"], "articles": [_summary(a) for a in data["articles"]]}


def article_payload(slug: str) -> Dict[str, Any]:
    """Article with all markup pre-rendered (escaped) to HTML for the Wiki tab."""
    a = load_wiki()["by_slug"].get(slug)
    if not a:
        return {}
    by_slug = load_wiki()["by_slug"]
    return {
        **_summary(a),
        "infobox": [[k, str(render_inline(v))] for k, v in a.get("infobox", {}).items()],
        "lead": str(render_markup(a.get("lead", ""))),
        "sections": [{"heading": s["heading"], "html": str(render_markup(s["body"]))} for s in a.get("sections", [])],
        "see_also": [_summary(by_slug[s]) for s in a.get("see_also", []) if s in by_slug],
        "references": a.get("references", []),
        "linked_from": [_summary(b) for b in backlinks(slug)],
    }
