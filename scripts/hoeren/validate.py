"""Checks a normalised exam part against the format, the blueprint and the TTS rules.

Errors are fed back to the LLM for repair; warnings are only reported.
"""

import re

from .spec import MC, MC_OPTIONS, PARTS, SPEAKER, TF, TG_MESSAGE, WORDS

INTERJECTION = re.compile(r"\b(ach|oh|haha|hihi|hm+|na ja|naja|mensch|wow|tja|äh+m?|uff|juhu)\b", re.I)
STAGE = re.compile(r"[\[\]()*_<>~#]|[\U0001F300-\U0001FAFF]")
ABBREV = re.compile(r"\b(z\. ?B\.|bzw\.|ca\.|usw\.|ggf\.|evtl\.|d\. ?h\.|u\. ?a\.)", re.I)


def norm(text):
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def words(text):
    return len(text.split())


def check_part(part, blueprint):
    """Returns (errors, warnings) as lists of strings."""
    n = part["part"]
    errors, warnings = [], []
    err, warn = errors.append, warnings.append
    plan = blueprint[str(n)]
    planned = {q["number"]: q for q in (
        [q for u in plan["units"] for q in u["questions"]] if n == 1 else plan["questions"])}

    questions = [q for u in part["units"] for q in u["questions"]]
    numbers = [q["number"] for q in questions]
    if numbers != list(PARTS[n]["numbers"]):
        err(f"item numbers must be exactly {list(PARTS[n]['numbers'])}, got {numbers}")

    if n == 1 and len(part["units"]) != 5:
        err(f"Teil 1 needs 5 units, got {len(part['units'])}")

    for i, unit in enumerate(part["units"]):
        where = unit["id"]
        speakers = {s["id"]: s for s in unit["speakers"]}
        check_speakers(n, i, unit, plan, err)

        total = 0
        for t in unit["turns"]:
            if t["speaker"] not in speakers:
                err(f"{where}: turn by unknown speaker id '{t['speaker']}'")
            total += words(t["text"])
            if words(t["text"]) > WORDS["turn_max"]:
                warn(f"{where}: a turn has {words(t['text'])} words (TTS is tested up to ~100)")
            if "!" in t["text"]:
                err(f"{where}: no exclamation marks in turns (TTS acts): {t['text'][:60]}")
            if m := INTERJECTION.search(t["text"]):
                err(f"{where}: interjection '{m.group(0)}' in turn (TTS acts): {t['text'][:60]}")
            if m := STAGE.search(t["text"]):
                err(f"{where}: stage direction or symbol '{m.group(0)}' in turn: {t['text'][:60]}")
            if m := ABBREV.search(t["text"]):
                warn(f"{where}: abbreviation '{m.group(0)}' — write it out for TTS")
        lo, hi = WORDS["unit1"] if n == 1 else WORDS[n]
        if not lo <= total <= hi:
            warn(f"{where}: audio has {total} words, target {lo}–{hi}")

        per_turn = [norm(t["text"]) for t in unit["turns"]]
        full = " ".join(per_turn)
        fact_ids = {f["id"] for f in unit["facts"]}
        last_pos = -1
        for q in unit["questions"]:
            num = q["number"]
            tag = f"item {num}"
            want = planned.get(num)
            if want:
                if q["answer"] != want["answer"]:
                    err(f"{tag}: answer must be '{want['answer']}' (blueprint), got '{q['answer']}'")
                if q["trap"] != want["trap"]:
                    warn(f"{tag}: trap {q['trap']} differs from blueprint {want['trap']}")
            check_question(q, tag, speakers, err, warn)
            if q["target_fact"] not in fact_ids:
                warn(f"{tag}: target_fact '{q['target_fact']}' is not a fact id")

            quote = norm(q["evidence_quote"])
            pos = full.find(quote) if quote else -1
            if pos < 0:
                err(f"{tag}: evidence_quote is not verbatim in the audio: '{q['evidence_quote'][:80]}'")
                continue
            if n in (2, 3, 4) and pos < last_pos:
                (warn if n == 4 else err)(
                    f"{tag}: evidence comes earlier in the audio than the previous item's; "
                    "items must follow audio order")
            last_pos = max(last_pos, pos)
            if q["type"] == SPEAKER:
                owners = {unit["turns"][k]["speaker"] for k, t in enumerate(per_turn) if quote in t}
                if not owners:
                    err(f"{tag}: evidence_quote spans several turns; quote one turn of the owner")
                elif q["answer"] not in owners:
                    err(f"{tag}: evidence is spoken by {sorted(owners)}, but the answer is '{q['answer']}'")

    if n == 3:
        for sid in ("f", "m"):
            turns = sum(t["speaker"] == sid for t in part["units"][0]["turns"])
            if turns < 5:
                err(f"Teil 3: speaker '{sid}' has only {turns} turns; it must be a real conversation")
    if n == 4:
        for sid in ("moderator", "guest1", "guest2"):
            turns = sum(t["speaker"] == sid for t in part["units"][0]["turns"])
            if turns < 3:
                err(f"Teil 4: speaker '{sid}' has only {turns} turns")
    return errors, warnings


def check_speakers(n, i, unit, plan, err):
    where = unit["id"]
    speakers = unit["speakers"]
    genders = {s["id"]: s["gender"] for s in speakers}
    if n == 1:
        want = plan["units"][i]["speaker_gender"]
        if len(speakers) != 1 or speakers[0]["gender"] != want:
            err(f"{where}: needs exactly one speaker of gender '{want}'")
    elif n == 2:
        want = plan["speaker_gender"]
        if len(speakers) != 1 or speakers[0]["gender"] != want:
            err(f"{where}: needs exactly one speaker of gender '{want}'")
    elif n == 3:
        if genders != {"f": "f", "m": "m"}:
            err(f"{where}: speakers must be id 'f' (gender f) and id 'm' (gender m), got {genders}")
    elif n == 4:
        if genders != plan["genders"]:
            err(f"{where}: speakers must be {plan['genders']}, got {genders}")


def check_question(q, tag, speakers, err, warn):
    shown = f"{q['number']}. {q['prompt']}"
    if len(shown) > TG_MESSAGE:
        err(f"{tag}: question is too long for a Telegram message ({len(shown)} > {TG_MESSAGE})")
    if len(q["explanation"]) > TG_MESSAGE:
        err(f"{tag}: explanation is too long for a Telegram comment ({len(q['explanation'])} > {TG_MESSAGE})")
    if not 1 <= q["difficulty"] <= 5:
        err(f"{tag}: difficulty must be 1–5")

    if q["type"] == MC:
        ids = [o["id"] for o in q["options"]]
        if ids != MC_OPTIONS:
            err(f"{tag}: options must be a, b, c in order, got {ids}")
        texts = [norm(o["text"]) for o in q["options"]]
        if len(set(texts)) != len(texts):
            err(f"{tag}: options are not distinct")
        for o in q["options"]:
            if len(f"{o['id']}) {o['text']}") > TG_MESSAGE:
                err(f"{tag}: option {o['id']} is too long for a Telegram message")
            if o["id"] != q["answer"] and not o["why_wrong"].strip():
                warn(f"{tag}: distractor {o['id']} has no why_wrong")
    else:
        if q["options"]:
            warn(f"{tag}: {q['type']} item should have no options; they are ignored")
        lo, hi = WORDS["tf"] if q["type"] == TF else WORDS["speaker_statement"]
        if not lo <= words(q["prompt"]) <= hi:
            warn(f"{tag}: statement has {words(q['prompt'])} words, target {lo}–{hi}")
    if q["type"] == SPEAKER and q["answer"] not in speakers:
        err(f"{tag}: answer '{q['answer']}' is not a speaker id")
