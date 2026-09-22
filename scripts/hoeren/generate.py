"""LLM generation of exam parts, normalisation into exam.json shape, and repair loop."""

import json
import sys
from pathlib import Path
from string import Template

from . import llm, schemas
from .blueprint import used_skins
from .spec import DIALOGUE, MC, ONTOLOGY, PARTS, SOLO, SPEAKER, TF
from .validate import check_part

PROMPTS = Path(__file__).parent / "prompts"


def prompt_for(part, blueprint):
    body = Template((PROMPTS / f"teil{part}.md").read_text()).substitute(
        blueprint=json.dumps(blueprint[str(part)], ensure_ascii=False, indent=2),
        avoid=", ".join(sorted(used_skins())) or "none",
    )
    return body + "\n\n" + (PROMPTS / "common.md").read_text()


def question_type(part, number):
    if part == 1:
        return TF if number % 2 else MC
    return {2: MC, 3: TF, 4: SPEAKER}[part]


def cast(part, speakers):
    """Assign an approved voice to each speaker for local audio rendering."""
    if part in (1, 2):
        for s in speakers:
            s["voice"] = SOLO[s["gender"]]
    elif part == 3:
        for s in speakers:
            s["voice"] = DIALOGUE[s["gender"]]
    else:
        # Two women and one man: Markus is the man; Petra and Anna the women,
        # with Petra taking the moderator if she is a woman.
        women = sorted((s for s in speakers if s["gender"] == "f"),
                       key=lambda s: s["id"] != "moderator")
        for s in speakers:
            s["voice"] = "markus" if s["gender"] == "m" else None
        for s, voice in zip(women, ["petra", "anna"]):
            s["voice"] = voice
    return speakers


def normalise(part, raw):
    units = raw["units"] if part == 1 else [raw]
    out = []
    for i, u in enumerate(units):
        unit = {
            "id": f"teil{part}-text{i + 1}" if part == 1 else f"teil{part}",
            "title": f"Text {i + 1}" if part == 1 else None,
            "topic": u.get("topic"),
            "speakers": cast(part, u["speakers"]),
            "facts": u["facts"],
            "turns": u["turns"],
            "questions": [],
        }
        if part == 1:
            unit["text_type"] = u["text_type"]
        for q in u["questions"]:
            q = {"type": question_type(part, q["number"]), **q}
            if q["type"] != MC:
                q["options"] = []
            unit["questions"].append(q)
        out.append(unit)
    return {
        "part": part,
        "instruction": PARTS[part]["instruction"],
        "plays": PARTS[part]["plays"],
        "situation": None if part == 1 else raw["situation"],
        "topic": None if part == 1 else raw["topic"],
        "units": out,
    }


def generate_part(part, blueprint, model=None, effort=None, retries=2, log=print):
    system = ONTOLOGY.read_text()
    prompt = prompt_for(part, blueprint)
    schema = schemas.for_part(part)
    cost = 0.0
    raw, c = llm.complete_json(system, prompt, schema, model, effort)
    cost += c
    for attempt in range(retries + 1):
        result = normalise(part, raw)
        errors, warnings = check_part(result, blueprint)
        log(f"Teil {part}: attempt {attempt + 1}: {len(errors)} errors, {len(warnings)} warnings")
        if not errors or attempt == retries:
            break
        repair = (
            prompt
            + "\n\n## Repair\n\nYour previous JSON is below. It failed these checks:\n\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\n\nReturn the complete corrected JSON. Change only what is needed.\n\n```json\n"
            + json.dumps(raw, ensure_ascii=False)
            + "\n```"
        )
        raw, c = llm.complete_json(system, repair, schema, model, effort)
        cost += c
    result["validation"] = {"errors": errors, "warnings": warnings}
    result["cost_usd"] = round(cost, 4)
    return result


def stderr_log(msg):
    print(msg, file=sys.stderr)
