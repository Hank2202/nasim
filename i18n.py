"""
Languages. The game is written in English; other languages are catalogues of "English text -> translation"
in translations/<language>/*.json. The code, the database and save files stay in English, and everything is
translated on its way out, so a game keeps working when the language changes and every screen can speak its own.

  * Pages and JSON leaving the server pass through here (app.py). The catalogues on the server may hold secrets:
    secret missions, quiz questions and answers, scripted crises.
  * What page scripts write themselves is translated in the browser by static/js/i18n.js, from public.json and,
    on the facilitator's pages, deck.json. Those two files are sent to browsers, so they must hold no secrets.

A catalogue entry is a text, or a text with {placeholders}:

    "Your vote is in: you abstained.": "Váš hlas je zapsán: zdrželi jste se."
    "Turn {n} of {max}": "Kolo {n} z {max}"
    "{n} votes": "{n} {n:hlas|hlasy|hlasů}"

Placeholders match by their name: n, n2... a number; amount, amount2... a number with an optional resource word
("+5 Grain"); name, name2... or anything ending in _name, a name in capitals ("Iron Val-Khor"); any other name, any text.
What a placeholder matches is translated as well, and {n:one|few|many} picks the Czech plural form for the number.
Patterns with hardly any fixed words ("{x} ({y})") are only tried once a text could not be split into parts.
Symbols around a text (arrows, ticks, a final colon) do not have to be in the catalogue.
"""

import html
import json
import os
import re
from typing import Any, Dict, List, Optional

LANGUAGES = {"en": "English", "cs": "Čeština"}
SOURCE_LANGUAGE = "en"
COOKIE = "summit_lang"       # one device's own choice; without it a screen follows the language of the game
TRANSLATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translations")
# The files with the catalogue for the server; public and deck are also sent to browsers.
CATALOGUE_FILES = ("pages", "messages", "config", "quiz", "public", "deck")
BROWSER_FILES = ("public", "deck")

_PLACEHOLDER = re.compile(r"\{(\w+)\}")
_PLURAL = re.compile(r"\{(\w+):([^|{}]*)\|([^|{}]*)\|([^|{}]*)\}")
_NUMBER = r"[+\-−–=±]?\d[\d.,:]*%?"
_UPPER = "A-Z0-9ÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ"
# Free text never runs on into the next sentence: "Verdict: {a}." must not swallow the two sentences after it.
_FREE = '(?:(?![.!?]\\s+[A-Z0-9ÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ„“"])[\\s\\S])+?'
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_KINDS = ((re.compile(r"^n\d*$"), _NUMBER),
          (re.compile(r"^amount\d*$"), _NUMBER + r"(?: [A-Z][a-z]+)?"),
          (re.compile(r"^(name\d*|\w+_name)$"), f"[{_UPPER}][\\w'’\\-]*(?: [\\w'’\\-]+)*"))
_WHITESPACE = re.compile(r"\s+")
# Parts of a longer text that can be translated one by one when the whole is not in the catalogue.
_SPLITTERS = tuple(re.compile(p) for p in (r"(?<=[.!?])\s+", r"(;\s+)", r"(\s+\|\s+)", r"(\s+·\s+)", r"(:\s+)", r"(,\s+)", r"(\s+→\s+)", r"(\s+[—–]\s+)"))
_DEEPEST = 7


def plural_form(number: int, one: str, few: str, many: str) -> str:
    """Czech: 1 hlas, 2-4 hlasy, 5 hlasů (and 0 hlasů)."""
    number = abs(number)
    if number == 1:
        return one
    return few if 2 <= number <= 4 else many


class Catalogue:
    """Finds the translation of a text: the text itself, a pattern with placeholders, or its parts."""

    def __init__(self, entries: Dict[str, str]):
        self.exact: Dict[str, str] = {}
        self.patterns: List[Any] = []
        for key, value in entries.items():
            key = _WHITESPACE.sub(" ", key).strip()
            self.exact[key] = value
            if "{" in key:
                self.patterns.append(self._compile(key, value))
        # A text of several sentences also teaches its sentences, for when one of them turns up inside another text.
        for key, value in list(self.exact.items()):
            if "{" not in key:
                keys, values = _SENTENCE.split(key), _SENTENCE.split(value)
                if 1 < len(keys) == len(values):
                    for k, v in zip(keys, values):
                        self.exact.setdefault(k, v)
        # The most specific patterns (the most fixed text) come first; those with hardly any words come last of all.
        self.patterns.sort(key=lambda p: -p[3])
        self.structural = [p for p in self.patterns if p[4] < 3]
        self.patterns = [p for p in self.patterns if p[4] >= 3]
        self._memo: Dict[str, str] = {}

    @staticmethod
    def _compile(key: str, value: str):
        names: List[str] = []
        parts: List[str] = []
        last = 0
        for m in _PLACEHOLDER.finditer(key):
            parts.append(re.escape(key[last:m.start()]))
            body = next((kind for test, kind in _KINDS if test.match(m.group(1))), _FREE)
            parts.append(f"({body})" if m.group(1) not in names else f"(?:{body})")
            names.append(m.group(1))
            last = m.end()
        parts.append(re.escape(key[last:]))
        fixed_text = _PLACEHOLDER.sub("", key)
        letters = sum(c.isalpha() for c in fixed_text)
        return re.compile("^" + "".join(parts) + "$", re.S), names, value, len(fixed_text), letters

    def translate(self, text: str) -> str:
        if not text:
            return text
        hit = self._memo.get(text)
        if hit is not None:
            return hit
        result = self._translate(text, 0)
        if len(self._memo) > 50000:      # clocks and news keep producing new strings; a day's worth is plenty
            self._memo.clear()
        self._memo[text] = result
        return result

    def _translate(self, text: str, depth: int) -> str:
        # Whitespace around a text stays where it is; inside a text it does not matter.
        stripped = text.strip()
        if not stripped or not any(c.isalpha() for c in stripped):
            return text
        lead = text[:len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()):]
        core = _WHITESPACE.sub(" ", stripped)
        found = self._lookup(core, depth)
        if found is None:
            return text
        return lead + found + trail

    def _lookup(self, core: str, depth: int) -> Optional[str]:
        found = self._whole(core, depth)
        if found is not None:
            return found
        # Symbols and punctuation around the words: "▶ Resume", "Grain:", "(all of them)".
        start, end = 0, len(core)
        while start < end and not core[start].isalnum():
            start += 1
        while end > start and not core[end - 1].isalnum():
            end -= 1
        # Symbols in front only, then behind only, then both: "— Silk: 85 (Target: ≥50)." keeps its final bracket.
        for a, b in ((start, len(core)), (0, end), (start, end)):
            if (a or b < len(core)) and a < b:
                found = self._whole(core[a:b], depth)
                if found is not None:
                    return core[:a] + found + core[b:]
        if depth < _DEEPEST:
            for splitter in _SPLITTERS:
                pieces = splitter.split(core)
                if len(pieces) > 1:
                    done = [self._translate(p, depth + 1) for p in pieces]
                    if done != pieces:
                        joiner = " " if splitter is _SPLITTERS[0] else ""
                        return joiner.join(done)
                    break
            return self._match(self.structural, core, depth)
        return None

    def _whole(self, core: str, depth: int) -> Optional[str]:
        exact = self.exact.get(core)
        if exact is not None:
            return exact
        if depth >= _DEEPEST:
            return None
        return self._match(self.patterns, core, depth)

    def _match(self, patterns, core: str, depth: int) -> Optional[str]:
        for regex, names, value, _fixed, _letters in patterns:
            m = regex.match(core)
            if m:
                return self._fill(value, names, m.groups(), depth)
        return None

    def _fill(self, value: str, names: List[str], groups: tuple, depth: int) -> str:
        captured = {}
        index = 0
        for name in names:
            if name not in captured:
                captured[name] = groups[index]
                index += 1

        def plural(m):
            digits = re.search(r"\d+", captured.get(m.group(1), ""))
            return plural_form(int(digits.group()) if digits else 0, m.group(2), m.group(3), m.group(4))

        text = _PLURAL.sub(plural, value)
        return _PLACEHOLDER.sub(lambda m: self._translate(captured[m.group(1)], depth + 1) if m.group(1) in captured else m.group(0), text)


_catalogues: Dict[str, Catalogue] = {}
_stamps: Dict[str, float] = {}


def _files(language: str, names) -> List[str]:
    return [os.path.join(TRANSLATIONS_DIR, language, f"{name}.json") for name in names]


def load_entries(language: str, names=CATALOGUE_FILES) -> Dict[str, str]:
    entries: Dict[str, str] = {}
    for path in _files(language, names):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                entries.update(json.load(f))
    return entries


def catalogue(language: str) -> Optional[Catalogue]:
    if language == SOURCE_LANGUAGE or language not in LANGUAGES:
        return None
    stamp = max((os.path.getmtime(p) for p in _files(language, CATALOGUE_FILES) if os.path.exists(p)), default=0)
    if language not in _catalogues or _stamps.get(language) != stamp:
        _catalogues[language] = Catalogue(load_entries(language))
        _stamps[language] = stamp
    return _catalogues[language]


def tr(text: str, language: str) -> str:
    book = catalogue(language)
    return book.translate(text) if book else text


# Values that are codes for the software, never words for people.
_CODE_KEYS = {"id", "type", "status", "phase", "kind", "mode", "outcome", "effect_type", "builder", "resource", "pin", "slug", "article",
              "emoji", "icon", "theme_color", "seat", "tone", "choice", "context", "grade", "tier", "complexity", "scenario", "language"}
_CODE_ENDINGS = ("_id", "_ids", "_tier", "_grade", "_resource", "_key", "_color", "_status", "_type")


def translate_tree(value: Any, language: str) -> Any:
    """A copy of a JSON value with its texts translated. Codes (ids, statuses...) are left alone."""
    book = catalogue(language)
    return _walk(value, book) if book else value


def _walk(value: Any, book: Catalogue) -> Any:
    if isinstance(value, str):
        return book.translate(value)
    if isinstance(value, list):
        return [_walk(v, book) for v in value]
    if isinstance(value, dict):
        return {k: (v if _is_code(k, v) else _walk(v, book)) for k, v in value.items()}
    return value


def _is_code(key: str, value: Any) -> bool:
    """A code is a word or a list of words under a code's name ("phase": "working"); a whole block such as
    "mission_status" is still read for its texts."""
    if not (key in _CODE_KEYS or key.endswith(_CODE_ENDINGS)):
        return False
    return isinstance(value, str) or (isinstance(value, list) and all(isinstance(v, str) for v in value))


_SCRIPTS = re.compile(r"(<script\b.*?</script>|<style\b.*?</style>|<svg\b.*?</svg>)", re.S | re.I)
_TEXT_NODE = re.compile(r">([^<>]+)<")
_TAG = re.compile(r"<[a-zA-Z][^<>]*>")
_ATTRIBUTE = re.compile(r'\b(title|placeholder|aria-label|alt|data-cost|data-gain|data-name)="([^"]*)"')


def html_fragments(page: str) -> List[str]:
    """The texts a page shows, as translate_page sees them (the catalogue tools and the tests use this)."""
    found: List[str] = []
    for i, chunk in enumerate(_SCRIPTS.split(page)):
        if i % 2:
            continue
        found.extend(html.unescape(t) for t in _TEXT_NODE.findall(chunk) if t.strip())
        for tag in _TAG.findall(chunk):
            found.extend(html.unescape(v) for _name, v in _ATTRIBUTE.findall(tag) if v.strip())
    return found


def translate_page(page: str, language: str) -> str:
    """Translate the text between the tags of an HTML page, and the attributes people can read."""
    book = catalogue(language)
    if not book:
        return page

    def text_node(m):
        original = html.unescape(m.group(1))
        translated = book.translate(original)
        return m.group(0) if translated == original else ">" + html.escape(translated, quote=False) + "<"

    def attribute(m):
        original = html.unescape(m.group(2))
        translated = book.translate(original)
        return m.group(0) if translated == original else f'{m.group(1)}="{html.escape(translated, quote=True)}"'

    pieces = _SCRIPTS.split(page)
    for i in range(0, len(pieces), 2):
        chunk = _TAG.sub(lambda m: _ATTRIBUTE.sub(attribute, m.group(0)), pieces[i])
        # A second pass over the same chunk: attributes are inside tags, text nodes between them.
        pieces[i] = _TEXT_NODE.sub(text_node, chunk)
    return "".join(pieces)


def browser_catalogue(language: str, name: str) -> Dict[str, str]:
    """What a page script needs in the browser. Never the whole catalogue: that holds secrets."""
    if name not in BROWSER_FILES or language == SOURCE_LANGUAGE or language not in LANGUAGES:
        return {}
    return load_entries(language, (name,))
