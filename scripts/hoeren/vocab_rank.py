"""Check, rank and select vocabulary candidates. Pure functions; no LLM, no I/O.

Validation drops bad items with a reason instead of failing: the surface form must
occur in the transcript, the expression must be a plausible normalisation of it
(inflection, ablaut, separable verbs, participles), and names, numbers, basic words
and duplicates are rejected.
"""

import math
import re
from difflib import SequenceMatcher
from os.path import commonprefix

CATEGORIES = {
    "contrast": "🔀 Corrections & contrasts",
    "time": "⏱ Time & sequence",
    "cause": "🔗 Reasons & consequences",
    "condition": "⚖️ Conditions & limits",
    "change": "🔄 Changes & cancellations",
    "instruction": "📋 Rules & instructions",
    "concept": "🎯 Answer-bearing words",
}

# Heuristic weights from the feature spec; scores are 0–10.
WEIGHTS = {
    "answer_relevance": 0.35,
    "cross_scenario": 0.30,
    "b1_likelihood": 0.20,
    "learner_confusion": 0.10,
    "context_clarity": 0.05,
}
ANSWER_BONUS = 0.5    # surface found in a question's evidence quote
REPEAT_PENALTY = 0.75  # already published; mild, so top signal words can recur
LEADER_FLOOR = 6.0    # a category's best item is guaranteed a slot only above this
MAX_EXPRESSION = 40
MAX_ENGLISH = 60
MAX_EXAMPLE = 160

GAP = {"…", "...", "..", "-", "–"}
AUXILIARIES = {"sein", "haben", "werden"}  # optional in multiword lemmas: enthalten sein
PLACEHOLDERS = {"sich", "etw.", "etwas", "jdn.", "jdm.", "jemanden", "jemandem", "jmdn.", "jmdm."}
WEEKDAYS_MONTHS = {
    "montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag",
    "januar", "februar", "märz", "april", "mai", "juni", "juli", "august",
    "september", "oktober", "november", "dezember",
}
# Single-word A1 basics that never earn a slot on their own.
BASIC = {
    "und", "oder", "aber", "ich", "du", "sie", "wir", "sein", "haben", "werden", "machen",
    "gehen", "kommen", "sagen", "gut", "schön", "groß", "klein", "heute", "morgen", "tag",
    "jahr", "zeit", "uhr", "ja", "nein", "bitte", "danke", "hallo", "sehr", "viel", "auch",
    "hier", "da", "jetzt", "dann", "gern", "gerne", "essen", "trinken", "haus", "auto",
    "stadt", "arbeit", "arbeiten", "kaufen", "wohnen", "heißen", "name", "freund",
    "familie", "kind", "geld", "neu", "alt", "wieder", "kein", "nicht", "mit", "in",
}


def fold(word):
    """Lower-case, umlauts and ß spelled out plain, letters only."""
    word = word.lower().translate(str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss"}))
    return re.sub(r"[^a-z]", "", word)


def skeleton(word):
    """Consonants only, so ablaut (gilt/gelten, läuft/laufen) does not matter."""
    return re.sub(r"[aeiouy]", "", fold(word))


def _related(lemma, form):
    """Is `form` (from the transcript) plausibly an inflection of `lemma`?"""
    a, b = fold(lemma), fold(form)
    if not a or not b:
        return False
    if a == b:
        return True
    if max(len(a), len(b)) <= 4:
        return False  # doch ≠ dich, nur ≠ nun
    variants = {b}
    if len(b) > 5 and b.startswith("ge"):
        variants.add(b[2:])  # gelohnt → lohnt
    if len(b) > 5 and "ge" in b[1:]:
        variants.add(b[0] + b[1:].replace("ge", "", 1))  # abgeschlossen → abschlossen
    for v in variants:
        if not v or a[0] != v[0]:
            continue
        sa, sb = skeleton(a), skeleton(v)
        if len(commonprefix([sa, sb])) >= min(3, len(sa), len(sb)):
            return True
        if SequenceMatcher(None, a, v).ratio() >= 0.6:  # nimmt/nehmen
            return True
    return False


def tokens(expression):
    """Content tokens of an expression: no gap markers or placeholders."""
    words = [w.strip("()[],;:!?\"'„“") for w in expression.split()]
    words = [w for w in words if w and w not in GAP and w.lower() not in PLACEHOLDERS]
    return [w for w in words if w.lower() not in AUXILIARIES] if len(words) > 1 else words


def key(expression):
    """History/dedup key: inflection-tolerant, order-preserving."""
    return " ".join(skeleton(w) or fold(w) for w in tokens(expression))


def same_expression(a, b):
    """Same lemma up to inflection or ablaut (gelten/gilt, Schicht/Schichten)."""
    ta, tb = tokens(a), tokens(b)
    return len(ta) == len(tb) and all(_related(x, y) or _related(y, x) for x, y in zip(ta, tb))


def _pattern(fragment):
    words = [re.escape(w) for w in fragment.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", re.IGNORECASE)


def find_in_order(text, fragments):
    """Spans of the fragments, in order, in text; None if any is missing."""
    spans, pos = [], 0
    for fragment in fragments:
        m = _pattern(fragment).search(text, pos)
        if not m:
            return None
        spans.append(m.span())
        pos = m.end()
    return spans


def _squash(text):
    text = re.sub(r"[„“”\"»«]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def transcript_turns(exam):
    return [t["text"] for p in exam["parts"].values() for u in p["units"] for t in u["turns"]]


def evidence(exam):
    return [q.get("evidence_quote", "") for p in exam["parts"].values()
            for u in p["units"] for q in u["questions"]]


def names(exam):
    out = {fold(w) for w in WEEKDAYS_MONTHS}
    for p in exam["parts"].values():
        for u in p["units"]:
            for s in u["speakers"]:
                out.update(fold(w) for w in s["name"].split())
    return out


def check(item, turns, banned):
    """Return a rejection reason, or None if the item is usable."""
    expr, surface = item.get("expression", "").strip(), item.get("surface") or []
    if not expr or not item.get("english", "").strip():
        return "empty expression or translation"
    if item.get("category") not in CATEGORIES:
        return f"unknown category {item.get('category')!r}"
    if len(expr) > MAX_EXPRESSION or len(item["english"]) > MAX_ENGLISH:
        return "too long for one phone line"
    if re.search(r"\d", expr):
        return "number or date"
    words = tokens(expr)
    if not words:
        return "no content words"
    if any(fold(w) in banned for w in words):
        return "proper name or date"
    if len(words) == 1 and words[0].lower() in BASIC:
        return "basic A1 word"
    if not surface or not all(isinstance(f, str) and f.strip() for f in surface):
        return "no transcript form"
    if not any(find_in_order(t, surface) for t in turns):
        return "not found in transcript"
    forms = [w for f in surface for w in f.split()]
    candidates = forms + [a + b for a in forms for b in forms if a is not b]
    if not all(any(_related(w, c) for c in candidates) for w in words):
        return "expression does not match its transcript form"
    return None


def example_ok(item, turns):
    """The example is a verbatim transcript sentence containing the surface form."""
    ex = _squash(item.get("example", ""))
    if not ex or len(ex) > MAX_EXAMPLE or not item.get("trap_note", "").strip():
        return False
    return (any(ex in _squash(t) for t in turns)
            and find_in_order(ex, item["surface"]) is not None)


def score(item, quotes, history):
    s = sum(w * min(10, max(0, int(item.get(k, 0)))) for k, w in WEIGHTS.items())
    if any(find_in_order(q, item["surface"]) for q in quotes):
        s += ANSWER_BONUS
    if key(item["expression"]) in history:
        s -= REPEAT_PENALTY
    return round(s, 2)


def select(candidates, exam, history=(), count=15):
    """Validate, score, dedup and pick up to `count` items with category diversity.

    Returns (items, trap, rejected). Items are sorted best first and carry `score`
    and `repeat`; trap is the best item with a usable example, or None.
    """
    turns, quotes, banned, history = transcript_turns(exam), evidence(exam), names(exam), set(history)
    rejected, valid = [], []
    for item in candidates:
        reason = check(item, turns, banned)
        if reason:
            rejected.append({"expression": item.get("expression", ""),
                             "surface": item.get("surface"), "reason": reason})
            continue
        valid.append(item | {"score": score(item, quotes, history),
                             "repeat": key(item["expression"]) in history})
    valid.sort(key=lambda i: -i["score"])
    unique, seen_keys, seen_glosses = [], set(), set()
    for item in valid:
        k, gloss = key(item["expression"]), fold(item["english"])
        if (k in seen_keys or gloss in seen_glosses
                or any(same_expression(item["expression"], u["expression"]) for u in unique)):
            rejected.append({"expression": item["expression"], "reason": "duplicate or synonym"})
            continue
        seen_keys.add(k)
        seen_glosses.add(gloss)
        unique.append(item)
    # Diversity: the best item of each category first, then by score under a cap.
    cap = max(2, math.ceil(count / 4))
    leaders = {}
    for item in unique:
        if item["score"] >= LEADER_FLOOR:
            leaders.setdefault(item["category"], item)
    picked = sorted(leaders.values(), key=lambda i: -i["score"])[:count]
    per_cat = dict.fromkeys(CATEGORIES, 0) | {i["category"]: 1 for i in picked}
    for item in unique:
        if len(picked) >= count:
            break
        if item not in picked and per_cat[item["category"]] < cap:
            per_cat[item["category"]] += 1
            picked.append(item)
    items = sorted(picked, key=lambda i: -i["score"])
    rejected += [{"expression": i["expression"], "reason": "ranked out"}
                 for i in unique if i not in picked]
    trap = next((i for i in items if example_ok(i, turns)), None)
    trap = trap and {"expression": trap["expression"], "surface": trap["surface"],
                     "quote": _squash(trap["example"]), "note": trap["trap_note"].strip()}
    return items, trap, rejected
