"""Render a vocab.json selection as one Telegram HTML message, deterministically."""

from html import escape

from .spec import TG_MESSAGE
from .telegram import visible_len
from .vocab_rank import CATEGORIES, find_in_order

TITLE = "🎧 <b>B1 Hören | Words Worth Knowing</b>"
CLOSER = "Recognize the signal. Find the answer."


def _html(text):
    return escape(str(text), quote=False)


def _quote(trap):
    """Quote with the surface fragments in bold, escaping everything else."""
    text = trap["quote"]
    out, pos = [], 0
    for start, end in find_in_order(text, trap["surface"]) or []:
        out += [_html(text[pos:start]), f"<b>{_html(text[start:end])}</b>"]
        pos = end
    return "„" + "".join(out) + _html(text[pos:]) + "“"


def _body(items, trap):
    n = len(items)
    lines = [TITLE, f"{n} high-value expression{'s' if n != 1 else ''} "
                    "from today's listening practice"]
    groups = {c: [i for i in items if i["category"] == c] for c in CATEGORIES}
    groups = {c: g for c, g in groups.items() if g}
    number = 0
    for category, group in groups.items():
        lines.append("")
        if len(groups) > 1:
            lines.append(f"<b>{_html(CATEGORIES[category])}</b>")
        for item in group:
            number += 1
            lines.append(f"{number}. <b>{_html(item['expression'])}</b> — {_html(item['english'])}")
    if trap:
        lines += ["", "💡 <b>Listening trap</b>", _quote(trap), _html(trap["note"])]
    lines += ["", CLOSER]
    return "\n".join(lines)


def render(vocab):
    """HTML text for the post; drops the trap, then the weakest items, to fit TG_MESSAGE."""
    items = sorted(vocab["items"], key=lambda i: -i["score"])
    trap = vocab.get("trap")
    if not items:
        raise ValueError("vocab has no items")
    while True:
        text = _body(items, trap)
        if visible_len(text) <= TG_MESSAGE:
            return text
        if trap:
            trap = None
        elif len(items) > 1:
            items = items[:-1]
        else:
            raise ValueError("vocab post does not fit one Telegram message")
