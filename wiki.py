"""Spireopedia: the in-game, Wikipedia-style lore encyclopedia (data in lore_articles.json).

Articles are served as JSON to the phone console's Wiki tab; there is no standalone site."""

import json
import os
import re
import unicodedata
from html import escape
from typing import Any, Dict, List, Tuple

from markupsafe import Markup

import i18n

ARTICLES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lore_articles.json")
_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")

_cache: Dict[str, Dict[str, Any]] = {}

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


def articles_path(language: str = i18n.SOURCE_LANGUAGE) -> str:
    """Each language has its own copy of the encyclopedia; without one, the English is shown."""
    translated = os.path.join(i18n.TRANSLATIONS_DIR, language, "lore_articles.json")
    return translated if language != i18n.SOURCE_LANGUAGE and os.path.exists(translated) else ARTICLES_PATH


def load_wiki(language: str = i18n.SOURCE_LANGUAGE) -> Dict[str, Any]:
    path = articles_path(language)
    mtime = os.path.getmtime(path)
    cached = _cache.get(path)
    if not cached or cached["mtime"] != mtime:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["by_slug"] = {a["slug"]: a for a in data["articles"]}
        cached = _cache[path] = {"mtime": mtime, "data": data}
    return cached["data"]


def render_markup(text: str, language: str = i18n.SOURCE_LANGUAGE) -> Markup:
    """Escape, then apply **bold**, [[slug|label]] links and blank-line paragraphs."""
    by_slug = load_wiki(language)["by_slug"]

    def link(m):
        slug, label = m.group(1).strip(), (m.group(2) or "").strip()
        article = by_slug.get(slug)
        label = label or (article["title"] if article else slug)
        if article:
            return f'<a href="#" class="wk-link" data-wiki="{slug}">{label}</a>'
        missing = i18n.tr("This article does not exist yet", language)
        return f'<span class="wk-new" title="{missing}">{label}</span>'

    def inline(chunk: str) -> str:
        chunk = escape(chunk, quote=False)
        chunk = _LINK_RE.sub(link, chunk)
        return _BOLD_RE.sub(r"<b>\1</b>", chunk)

    paras = [p for p in text.split("\n\n") if p.strip()]
    return Markup("".join(f"<p>{inline(p)}</p>" for p in paras))


def render_inline(text: str, language: str = i18n.SOURCE_LANGUAGE) -> Markup:
    html = str(render_markup(text, language))
    return Markup(html[3:-4] if html.startswith("<p>") and html.count("<p>") == 1 else html)


def backlinks(slug: str, language: str = i18n.SOURCE_LANGUAGE) -> List[Dict[str, Any]]:
    out = []
    for a in load_wiki(language)["articles"]:
        if a["slug"] == slug:
            continue
        blob = json.dumps(a, ensure_ascii=False)
        if re.search(r"\[\[" + re.escape(slug) + r"(\||\])", blob):
            out.append(a)
    return out


def _plain(text: str) -> str:
    """Lower case without accents: on a phone nobody types "obilí" when "obili" finds it too."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(c))


def search(query: str, language: str = i18n.SOURCE_LANGUAGE) -> List[Dict[str, Any]]:
    q = _plain(query.strip())
    if not q:
        return []
    hits: List[Tuple[int, Dict[str, Any]]] = []
    for a in load_wiki(language)["articles"]:
        score = 0
        if q in _plain(a["title"]):
            score += 10
        blob = _plain(json.dumps(a, ensure_ascii=False))
        score += min(blob.count(q), 9)
        if score:
            hits.append((score, a))
    return [a for _, a in sorted(hits, key=lambda x: -x[0])]


def validate(language: str = i18n.SOURCE_LANGUAGE) -> List[str]:
    """Return a list of problems (empty = OK): duplicate slugs, dead links, bad see_also."""
    data = load_wiki(language)
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


def index_payload(language: str = i18n.SOURCE_LANGUAGE) -> Dict[str, Any]:
    data = load_wiki(language)
    return {"meta": data["_meta"], "articles": [_summary(a) for a in data["articles"]]}


def article_payload(slug: str, language: str = i18n.SOURCE_LANGUAGE) -> Dict[str, Any]:
    """Article with all markup pre-rendered (escaped) to HTML for the Wiki tab."""
    by_slug = load_wiki(language)["by_slug"]
    a = by_slug.get(slug)
    if not a:
        return {}
    return {
        **_summary(a),
        "infobox": [[k, str(render_inline(v, language))] for k, v in a.get("infobox", {}).items()],
        "lead": str(render_markup(a.get("lead", ""), language)),
        "sections": [{"heading": s["heading"], "html": str(render_markup(s["body"], language))} for s in a.get("sections", [])],
        "see_also": [_summary(by_slug[s]) for s in a.get("see_also", []) if s in by_slug],
        "references": a.get("references", []),
        "linked_from": [_summary(b) for b in backlinks(slug, language)],
    }
