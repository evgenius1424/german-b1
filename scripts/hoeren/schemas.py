"""JSON schemas the LLM must fill, one per exam part. Counts are checked in validate.py."""

from .spec import MC_OPTIONS, SLOTS, TRAPS


def obj(**props):
    return {"type": "object", "properties": props, "required": list(props),
            "additionalProperties": False}


def arr(items):
    return {"type": "array", "items": items}


STR = {"type": "string"}
INT = {"type": "integer"}

SPEAKER = obj(id=STR, name=STR, gender={"type": "string", "enum": ["f", "m"]}, role=STR)
FACT = obj(id=STR, statement=STR, frame=STR)
TURN = obj(speaker=STR, text=STR)
OPTION = obj(id={"type": "string", "enum": MC_OPTIONS}, text=STR, fact_id=STR, why_wrong=STR)


def question(answers):
    return obj(
        number=INT,
        prompt=STR,
        options=arr(OPTION),
        answer={"type": "string", "enum": answers},
        target_fact=STR,
        evidence_quote=STR,
        trap={"type": "string", "enum": TRAPS},
        slot={"type": "string", "enum": SLOTS},
        difficulty=INT,
        explanation=STR,
    )


def unit(answers, **extra):
    return obj(**extra, speakers=arr(SPEAKER), facts=arr(FACT), turns=arr(TURN),
               questions=arr(question(answers)))


ANSWERS = {
    1: ["richtig", "falsch", *MC_OPTIONS],
    2: MC_OPTIONS,
    3: ["richtig", "falsch"],
    4: ["moderator", "guest1", "guest2"],
}


def for_part(part):
    if part == 1:
        return obj(units=arr(unit(ANSWERS[1], number=INT, text_type=STR, topic=STR)))
    return unit(ANSWERS[part], situation=STR, topic=STR)
