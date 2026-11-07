/**
 * The Summit of Realms - translates what page scripts write, as they write it.
 *
 * Loaded (in the <head>, before anything is drawn) only when a screen is not in English. Pages and server messages
 * are translated by the server (i18n.py); this catches the texts in the scripts. Scripts keep writing English, so
 * the game logic knows nothing about languages. A text is looked up as a whole, as a pattern with {placeholders},
 * and piece by piece, in the same way as on the server.
 */
(function () {
  'use strict';

  const PLACEHOLDER = /\{(\w+)\}/g;
  const PLURAL = /\{(\w+):([^|{}]*)\|([^|{}]*)\|([^|{}]*)\}/g;
  const SPLITTERS = [/(?<=[.!?])\s+/, /(;\s+)/, /(\s+\|\s+)/, /(\s+·\s+)/, /(:\s+)/, /(,\s+)/, /(\s+→\s+)/, /(\s+[—–]\s+)/];
  const DEEPEST = 7;
  const LETTER = /\p{L}/u;
  const ALNUM = /[\p{L}\p{N}]/u;

  const UPPER = 'A-Z0-9ÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ';
  const NUMBER = '[+\\-−–=±]?\\d[\\d.,:]*%?';
  // Free text never runs on into the next sentence (see i18n.py).
  const FREE = '(?:(?![.!?]\\s+[A-Z0-9ÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ„“"])[\\s\\S])+?';
  const SENTENCE = /(?<=[.!?])\s+/;
  const KINDS = [[/^n\d*$/, NUMBER], [/^amount\d*$/, `${NUMBER}(?: [A-Z][a-z]+)?`],
                 [/^(name\d*|\w+_name)$/, `[${UPPER}][\\wáčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ'’\\-]*(?: [\\wáčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ'’\\-]+)*`]];
  const exact = new Map();
  let patterns = [];
  let structural = [];
  const memo = new Map();

  function compile(key, value) {
    const names = [];
    let source = '', last = 0;
    for (const m of key.matchAll(PLACEHOLDER)) {
      source += escapeRegex(key.slice(last, m.index));
      const kind = KINDS.find(([test]) => test.test(m[1]));
      const body = kind ? kind[1] : FREE;
      source += names.includes(m[1]) ? `(?:${body})` : `(${body})`;
      names.push(m[1]);
      last = m.index + m[0].length;
    }
    source += escapeRegex(key.slice(last));
    const fixedText = key.replace(PLACEHOLDER, '');
    return { regex: new RegExp(`^${source}$`, 's'), names, value, fixed: fixedText.length, letters: (fixedText.match(/\p{L}/gu) || []).length };
  }

  function escapeRegex(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function addCatalogue(entries) {
    for (const [rawKey, value] of Object.entries(entries || {})) {
      const key = rawKey.replace(/\s+/g, ' ').trim();
      exact.set(key, value);
      if (key.includes('{')) patterns.push(compile(key, value));
    }
    // A text of several sentences also teaches its sentences (see i18n.py).
    for (const [key, value] of Array.from(exact.entries())) {
      if (key.includes('{')) continue;
      const keys = key.split(SENTENCE), values = value.split(SENTENCE);
      if (keys.length > 1 && keys.length === values.length) keys.forEach((k, i) => { if (!exact.has(k)) exact.set(k, values[i]); });
    }
    const all = patterns.concat(structural).sort((a, b) => b.fixed - a.fixed);
    patterns = all.filter(p => p.letters >= 3);
    structural = all.filter(p => p.letters < 3);
    memo.clear();
  }

  function pluralForm(number, one, few, many) {
    number = Math.abs(number);
    if (number === 1) return one;
    return number >= 2 && number <= 4 ? few : many;
  }

  function fill(value, names, groups, depth) {
    const captured = {};
    let index = 0;
    for (const name of names) {
      if (!(name in captured)) { captured[name] = groups[index]; index += 1; }
    }
    const text = value.replace(PLURAL, (_m, name, one, few, many) => {
      const digits = String(captured[name] || '').match(/\d+/);
      return pluralForm(digits ? Number(digits[0]) : 0, one, few, many);
    });
    return text.replace(PLACEHOLDER, (m, name) => (name in captured ? one(captured[name], depth + 1) : m));
  }

  function whole(core, depth) {
    if (exact.has(core)) return exact.get(core);
    if (depth >= DEEPEST) return null;
    return match(patterns, core, depth);
  }

  function match(list, core, depth) {
    for (const { regex, names, value } of list) {
      const m = core.match(regex);
      if (m) return fill(value, names, m.slice(1), depth);
    }
    return null;
  }

  function lookup(core, depth) {
    const found = whole(core, depth);
    if (found !== null) return found;
    let start = 0, end = core.length;
    while (start < end && !ALNUM.test(core[start])) start += 1;
    while (end > start && !ALNUM.test(core[end - 1])) end -= 1;
    for (const [a, b] of [[start, core.length], [0, end], [start, end]]) {
      if ((a || b < core.length) && a < b) {
        const inner = whole(core.slice(a, b), depth);
        if (inner !== null) return core.slice(0, a) + inner + core.slice(b);
      }
    }
    if (depth < DEEPEST) {
      for (let s = 0; s < SPLITTERS.length; s += 1) {
        const pieces = core.split(SPLITTERS[s]);
        if (pieces.length > 1) {
          const done = pieces.map(p => one(p, depth + 1));
          if (done.some((d, i) => d !== pieces[i])) return done.join(s === 0 ? ' ' : '');
          break;
        }
      }
      return match(structural, core, depth);
    }
    return null;
  }

  function one(text, depth) {
    const stripped = text.trim();
    if (!stripped || !LETTER.test(stripped)) return text;
    const lead = text.slice(0, text.length - text.trimStart().length);
    const trail = text.slice(text.trimEnd().length);
    const found = lookup(stripped.replace(/\s+/g, ' '), depth);
    return found === null ? text : lead + found + trail;
  }

  function tr(text) {
    if (typeof text !== 'string' || !text) return text;
    if (memo.has(text)) return memo.get(text);
    const result = one(text, 0);
    if (memo.size > 5000) memo.clear();
    memo.set(text, result);
    if (result === text && LETTER.test(text) && misses.size < 2000) misses.add(text.trim());
    return result;
  }

  // What could not be translated, for the tests and for anyone checking a language by hand.
  const misses = new Set();

  // ------------------------------------------------------------------------ the page itself
  const SKIP = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'CODE']);
  const ATTRIBUTES = ['title', 'placeholder', 'aria-label'];

  function skipped(node) {
    for (let el = node.nodeType === 1 ? node : node.parentElement; el; el = el.parentElement) {
      if (SKIP.has(el.tagName) || el.hasAttribute('data-no-translate')) return true;
    }
    return false;
  }

  function translateNode(node) {
    if (node.nodeType === 3) {
      if (skipped(node)) return;
      const translated = tr(node.data);
      if (translated !== node.data) node.data = translated;
    } else if (node.nodeType === 1) {
      if (skipped(node)) return;
      for (const name of ATTRIBUTES) translateAttribute(node, name);
      for (const child of node.childNodes) translateNode(child);
    }
  }

  function translateAttribute(el, name) {
    const value = el.getAttribute(name);
    if (!value) return;
    const translated = tr(value);
    if (translated !== value) el.setAttribute(name, translated);
  }

  const observer = new MutationObserver(records => {
    for (const r of records) {
      if (r.type === 'childList') r.addedNodes.forEach(translateNode);
      else if (r.type === 'characterData') translateNode(r.target);
      else if (r.type === 'attributes' && !skipped(r.target)) translateAttribute(r.target, r.attributeName);
    }
    observer.takeRecords();       // our own changes need no second look
  });
  observer.observe(document.documentElement, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRIBUTES });

  window.tr = tr;
  window.i18n = { add: addCatalogue, misses };
}());
