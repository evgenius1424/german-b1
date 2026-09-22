"""Random but balanced exam plan: skins, answer key, traps and speaker genders.

Code decides these so that answer keys are balanced and exams differ from each
other; the LLM only writes content that satisfies the plan.
"""

import json
import random

from .spec import (
    EXAMS, MC_OPTIONS, PART_TRAPS, PARTS, TEIL1_TEXT_TYPES, TEIL2_SETTINGS,
    TEIL3_SCENARIOS, TEIL4_TOPICS,
)

DIFFICULTY = [2, 3, 3, 3, 4, 4, 4, 5]


def used_skins():
    """Settings, scenarios and topics of earlier exams, to avoid repeats."""
    used = set()
    for path in EXAMS.glob("*/exam.json"):
        bp = json.loads(path.read_text()).get("blueprint", {})
        used.update(
            filter(None, (bp.get("2", {}).get("setting"), bp.get("3", {}).get("scenario"),
                          bp.get("4", {}).get("topic")))
        )
    return used


def pick(rng, pool, used):
    fresh = [x for x in pool if x not in used] or pool
    return rng.choice(fresh)


def balanced(rng, values, n):
    """n values spread as evenly as possible over `values`, shuffled."""
    out = [values[i % len(values)] for i in range(n)]
    rng.shuffle(out)
    return out


def no_long_runs(rng, seq, limit=2):
    for _ in range(200):
        rng.shuffle(seq)
        if all(len(set(seq[i : i + limit + 1])) > 1 for i in range(len(seq) - limit)):
            return seq
    return seq


def make(seed):
    rng = random.Random(seed)
    used = used_skins()
    mc = balanced(rng, MC_OPTIONS, 10)
    tf1 = balanced(rng, ["richtig", "falsch"], 5)
    n_true = rng.choice([3, 4])
    tf3 = no_long_runs(rng, ["richtig"] * n_true + ["falsch"] * (7 - n_true))

    def q(number, answer, traps):
        return {"number": number, "answer": answer, "trap": rng.choice(traps),
                "difficulty": rng.choice(DIFFICULTY)}

    units = []
    for i, text_type in enumerate(rng.sample(TEIL1_TEXT_TYPES, 5)):
        units.append({
            "text": i + 1,
            "text_type": text_type,
            "speaker_gender": rng.choice("fm"),
            "questions": [
                q(2 * i + 1, tf1[i], PART_TRAPS["1_global"]),
                q(2 * i + 2, mc[i], PART_TRAPS["1_detail"]),
            ],
        })

    moderator = rng.choice("fm")
    # Three voices must be Petra, Anna (female) and Markus (male): two women, one man.
    guests = ["f", "m"] if moderator == "f" else ["f", "f"]
    rng.shuffle(guests)
    n_mod = rng.choice([1, 2])
    rest = 8 - n_mod
    owners = no_long_runs(rng, ["moderator"] * n_mod + ["guest1"] * (rest // 2)
                          + ["guest2"] * (rest - rest // 2))

    return {
        "seed": seed,
        "1": {"units": units},
        "2": {
            "setting": pick(rng, TEIL2_SETTINGS, used),
            "speaker_gender": rng.choice("fm"),
            "questions": [q(n, mc[5 + i], PART_TRAPS[2]) for i, n in enumerate(PARTS[2]["numbers"])],
        },
        "3": {
            "scenario": pick(rng, TEIL3_SCENARIOS, used),
            "questions": [q(n, tf3[i], PART_TRAPS[3]) for i, n in enumerate(PARTS[3]["numbers"])],
        },
        "4": {
            "topic": pick(rng, TEIL4_TOPICS, used),
            "genders": {"moderator": moderator, "guest1": guests[0], "guest2": guests[1]},
            "questions": [q(n, owners[i], PART_TRAPS[4]) for i, n in enumerate(PARTS[4]["numbers"])],
        },
    }
