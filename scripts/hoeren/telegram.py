"""Build the ordered Telegram channel/comment manifest for one exam.

One channel post per Teil: the audio with the questions as its caption
(Teil 1: an album of five audio files, each captioned with its own two items).
The first comment under each post holds the answer key and the transcript.
"""

import re
from html import escape, unescape

from .spec import MC, SPEAKER, TF, TG_MESSAGE

TG_CAPTION = 1024
SPEAKER_ORDER = ["moderator", "guest1", "guest2"]
# Without a performer, Telegram Desktop shows the file name instead of the title.
PERFORMER = "Hören B1"


def unit_path(exam_dir, unit):
    """Return the conventional, regenerable path for a unit's audio file."""
    return exam_dir / "audio" / f"{unit['id']}.mp3"


def _html(text):
    return escape(str(text), quote=False)


def visible_len(html):
    """Length Telegram counts against its limits: text after entity parsing."""
    return len(unescape(re.sub(r"<[^>]+>", "", html)))


def _speaker_label(speaker):
    return (f"{speaker['name']} ({speaker['role']})"
            if speaker["id"] == "moderator" else speaker["name"])


def _answer_label(question, speakers):
    answer = question["answer"]
    if question["type"] == TF:
        return "Richtig" if answer == "richtig" else "Falsch"
    if question["type"] == MC:
        option = next(o for o in question["options"] if o["id"] == answer)
        return f"{answer}) {option['text']}"
    if question["type"] == SPEAKER:
        return f"{'abc'[SPEAKER_ORDER.index(answer)]}) {speakers[answer]['name']}"
    raise ValueError(question["type"])


def _question(question):
    line = f"<b>{question['number']}.</b> {_html(question['prompt'])}"
    if question["type"] == TF:
        line += " <i>(R/F)</i>"
    elif question["type"] == MC:
        line += "".join(f"\n      {o['id']}) {_html(o['text'])}" for o in question["options"])
    return line


def _plays(part):
    return "zweimal" if part["plays"] == 2 else "einmal"


def _header(part, with_instruction):
    numbers = [q["number"] for unit in part["units"] for q in unit["questions"]]
    lines = [f"<b>Teil {part['part']}</b> · Aufgaben {numbers[0]}–{numbers[-1]}"]
    if with_instruction:
        lines.append(f"<i>{_html(part['instruction'])}</i>")
    else:
        lines[0] += (f" · Sie hören {'jeden' if len(part['units']) > 1 else 'den'}"
                     f" Text {_plays(part)}.")
    if part["situation"]:
        lines.append(_html(part["situation"]))
    if part["part"] == 4:
        speakers = {s["id"]: s for s in part["units"][0]["speakers"]}
        lines.append("  ".join(f"<b>{'abc'[i]})</b> {_html(_speaker_label(speakers[sid]))}"
                               for i, sid in enumerate(SPEAKER_ORDER)))
    return "\n".join(lines)


def _caption(blocks):
    text = "\n\n".join(b for b in blocks if b)
    if visible_len(text) > TG_CAPTION:
        raise ValueError(f"Telegram caption is too long ({visible_len(text)} > {TG_CAPTION})")
    return text


def _unit_caption(part, unit, header):
    title = f"<b>{_html(unit['title'])}</b>\n" if unit["title"] and len(part["units"]) > 1 else ""
    return _caption([header, title + "\n".join(_question(q) for q in unit["questions"])])


def _captions(part):
    """One caption per unit; the part header goes on the first. Drop the
    boilerplate instruction if the header would push a caption over the limit."""
    for with_instruction in (True, False):
        header = _header(part, with_instruction)
        try:
            return [_unit_caption(part, unit, header if i == 0 else "")
                    for i, unit in enumerate(part["units"])]
        except ValueError:
            if not with_instruction:
                raise


def _transcript(unit):
    speakers = {s["id"]: s for s in unit["speakers"]}
    named = len(speakers) > 1
    return "\n".join(
        (f"<b>{_html(speakers[t['speaker']]['name'])}:</b> " if named else "") + _html(t["text"])
        for t in unit["turns"])


def _split(text):
    if visible_len(text) <= TG_MESSAGE:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        candidate = line if not current else current + "\n" + line
        if current and visible_len(candidate) > TG_MESSAGE:
            chunks.append(current)
            current = line
        else:
            current = candidate
    return chunks + [current]


def _comments(part):
    answers = ["<b>Lösungen</b>"]
    for unit in part["units"]:
        speakers = {s["id"]: s for s in unit["speakers"]}
        for q in unit["questions"]:
            answers.append(f"<b>{q['number']}. {_html(_answer_label(q, speakers))}</b>"
                           f" — {_html(q['explanation'])}")
    transcripts = []
    for unit in part["units"]:
        title = f"<b>{_html(unit['title'])}</b>\n" if unit["title"] and len(part["units"]) > 1 else ""
        transcripts.append(title + _transcript(unit))
    text = "\n".join(answers) + "\n\n<b>Transkript</b>\n\n" + "\n\n".join(transcripts)
    return [{"text": chunk, "parse_mode": "HTML"} for chunk in _split(text)]


def _audio_post(part, exam_dir):
    n = part["part"]
    media = []
    for unit, caption in zip(part["units"], _captions(part)):
        title = f"Teil {n}" + (f" · {unit['title']}" if unit["title"] and len(part["units"]) > 1 else "")
        media.append({
            "type": "audio",
            "file": str(unit_path(exam_dir, unit).relative_to(exam_dir)),
            "title": title,
            "performer": PERFORMER,
            "caption": caption,
            "parse_mode": "HTML",
        })
    post = {"id": f"teil{n}", "comments": _comments(part)}
    if len(media) == 1:
        item = media[0]
        return post | {
            "method": "sendAudio",
            "params": {k: v for k, v in item.items() if k not in ("type", "file")},
            "files": {"audio": item["file"]},
        }
    return post | {"method": "sendMediaGroup", "media": media}


def build(exam, exam_dir):
    parts = sorted(exam["parts"].values(), key=lambda p: p["part"])
    return {"exam_id": exam["id"], "channel": "@german_b1_horen",
            "posts": [_audio_post(part, exam_dir) for part in parts]}
