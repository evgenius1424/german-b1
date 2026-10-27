"""Post-exam vocabulary: LLM extraction → vocab_rank selection → exams/<id>/vocab.json.

The tracked vocab.json is the source for the Telegram post, so publishing never calls
the LLM. exams/vocab-history.json records every exam's selection (normalised keys) so
later exams prefer new expressions.
"""

import datetime
import json
from pathlib import Path
from string import Template

from . import llm, vocab_rank
from .schemas import INT, STR, arr, obj
from .spec import MC, SPEAKER, VOCAB_COUNT, VOCAB_HISTORY, VOCAB_MAX

PROMPT = Path(__file__).parent / "prompts" / "vocab.md"
SYSTEM = ("You are an experienced Goethe-Zertifikat B1 examiner and German teacher. "
          "Answer only with the requested JSON.")
RECENT = 80  # history entries shown to the model
FILE = "vocab.json"

ITEM = obj(
    expression=STR,
    surface=arr(STR),
    english=STR,
    category={"type": "string", "enum": list(vocab_rank.CATEGORIES)},
    example=STR,
    trap_note=STR,
    **{k: INT for k in vocab_rank.WEIGHTS},
)
SCHEMA = obj(items=arr(ITEM))


class VocabError(RuntimeError):
    pass


def _answer(q, speakers):
    if q["type"] == MC:
        return next((f"{o['id']}) {o['text']}" for o in q["options"] if o["id"] == q["answer"]), q["answer"])
    if q["type"] == SPEAKER:
        return speakers.get(q["answer"], {}).get("name", q["answer"])
    return q["answer"]


def _question(q, speakers):
    lines = [f"Q{q['number']}: {q['prompt']}"]
    if q["type"] == MC:
        lines += [f"  {o['id']}) {o['text']}" + (f" (wrong: {o['why_wrong']})" if o.get("why_wrong") else "")
                  for o in q["options"]]
    lines.append(f"  answer: {_answer(q, speakers)}; evidence: „{q.get('evidence_quote', '')}“")
    return "\n".join(lines)


def transcripts(exam):
    """Plain-text transcripts with questions and keys, as model input."""
    blocks = []
    for key, part in sorted(exam["parts"].items()):
        for unit in part["units"]:
            speakers = {s["id"]: s for s in unit["speakers"]}
            title = f"### Teil {key}" + (f" · {unit['title']}" if unit.get("title") else "")
            turns = "\n".join(f"{speakers[t['speaker']]['name']}: {t['text']}" for t in unit["turns"])
            questions = "\n".join(_question(q, speakers) for q in unit["questions"])
            blocks.append(f"{title}\n\n{turns}\n\nQuestions:\n{questions}")
    return "\n\n".join(blocks)


def load_history(path=VOCAB_HISTORY):
    return json.loads(path.read_text()) if path.exists() else {"exams": {}}


def history_entries(history, exclude=None):
    """[(exam_id, expression, key)] in exam order, without `exclude`."""
    return [(eid, e["expression"], e["key"]) for eid, entries in sorted(history["exams"].items())
            if eid != exclude for e in entries]


def record(history, exam_id, items, path=VOCAB_HISTORY):
    history["exams"][exam_id] = [{"expression": i["expression"], "key": vocab_rank.key(i["expression"])}
                                 for i in items]
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n")


def extract(exam, past, count, model=None, effort=None):
    """Ask the model for ranked candidates. Returns (candidates, cost)."""
    recent = ", ".join(dict.fromkeys(expr for _, expr, _ in past[-RECENT:])) or "none"
    prompt = Template(PROMPT.read_text()).substitute(
        categories=", ".join(vocab_rank.CATEGORIES),
        history=recent,
        candidates=min(count + 10, 30),
        transcripts=transcripts(exam),
    )
    try:
        out, cost = llm.complete_json(SYSTEM, prompt, SCHEMA, model, effort)
    except llm.LLMError as e:
        raise VocabError(f"vocab extraction failed: {e}") from e
    return out.get("items") or [], cost


def generate(exam, exam_dir, count=VOCAB_COUNT, model=None, effort=None,
             history_path=VOCAB_HISTORY, log=print):
    """Extract, select and write vocab.json; record the selection in the history."""
    if not 1 <= count <= VOCAB_MAX:
        raise VocabError(f"count must be 1–{VOCAB_MAX}")
    history = load_history(history_path)
    past = history_entries(history, exclude=exam["id"])
    candidates, cost = extract(exam, past, count, model, effort)
    if not candidates:
        raise VocabError("the model returned no vocabulary candidates")
    items, trap, rejected = vocab_rank.select(candidates, exam, {k for _, _, k in past}, count)
    if not items:
        reasons = "; ".join(f"{r['expression']}: {r['reason']}" for r in rejected[:10])
        raise VocabError(f"no usable vocabulary items ({reasons})")
    if len(items) < 10:
        log(f"vocab: only {len(items)} usable items; publishing fewer rather than padding")
    vocab = {
        "exam_id": exam["id"],
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "model": model or "default",
        "count": count,
        "cost_usd": round(cost, 4),
        "items": items,
        "trap": trap,
        "rejected": rejected,
    }
    (exam_dir / FILE).write_text(json.dumps(vocab, ensure_ascii=False, indent=2) + "\n")
    record(history, exam["id"], items, history_path)
    log(f"{exam_dir / FILE}: {len(items)} items, {len(rejected)} rejected"
        + (", repeats: " + ", ".join(i["expression"] for i in items if i["repeat"])
           if any(i["repeat"] for i in items) else ""))
    return vocab


def load(exam_dir):
    path = exam_dir / FILE
    return json.loads(path.read_text()) if path.exists() else None
